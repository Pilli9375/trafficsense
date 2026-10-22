"""Hosted chat client: an OpenAI-compatible /chat/completions API (NVIDIA NIM).

Used only by the exploratory model-size study (scripts/run_model_size.py). Unlike Ollama this is
NOT local: every prompt leaves the machine and goes to the provider's servers, and the model
behind a hosted id can change without notice. The id the API returns with each response is
recorded per call (decisions.jsonl) and per run (summary.json), with the date of the run.

The interface matches OllamaClient (chat, model_info, server_version, provider, host, endpoint,
timeout_s, options, keep_alive), so the LLM controllers use either one unchanged; make_client()
picks the class from llm.provider.

API key: read from the environment variable named by `api_key_env`, else from the gitignored
`env_file` (a KEY=value file, path relative to the repo root). The key only ever goes into the
Authorization header; it is not stored in options, not logged and not written to any output.

Rate limits and errors:
  * a client-side limiter allows at most `rate_limit_rpm` requests in any 60 s window
    (every attempt counts, retries included); the time it waits is recorded per call;
  * HTTP 429 and 5xx (500, 502, 503, 504), and a dropped connection, are retried up to
    `max_retries` times with exponential backoff (backoff_s x 2^k, at most backoff_max_s,
    or the server's Retry-After if it is longer). Retries are recorded per call
    (ChatResult.retries / LLMError.retries) and counted separately from failures. When the
    retries run out the call fails (failure type retries_exhausted); a connection that keeps
    dropping raises LLMUnavailable, which stops the run;
  * a timeout fails the call (failure type timeout) and is not retried, as with Ollama;
  * 401/403 (key rejected) and 404 (model not served for this key) raise LLMUnavailable;
  * any other HTTP error, or a body without message content, raises LLMServerError.
The answer itself is validated by prompt.parse_response, whatever the server's structured-
output support (`structured_output`: json_schema sends the schema as an OpenAI
response_format; none sends no format and relies on that validation alone).
"""
from __future__ import annotations

import collections
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from trafficsense.config import repo_root
from trafficsense.llm.client import ChatResult, LLMServerError, LLMTimeout, LLMUnavailable, OllamaClient

RETRY_STATUS = (429, 500, 502, 503, 504)
STRUCTURED = ("json_schema", "none")
REQUIRED = ("base_url", "endpoint", "model", "timeout_s", "temperature", "seed", "max_tokens", "api_key_env",
            "env_file", "rate_limit_rpm", "max_retries", "backoff_s", "backoff_max_s", "structured_output")


class LLMRetriesExhausted(LLMServerError):
    failure_type = "retries_exhausted"


def load_api_key(name: str, env_file: Path) -> str:
    """The key from the environment, else from env_file. Never echoes the value."""
    if os.environ.get(name):
        return os.environ[name]
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and k.strip() == name and v.strip().strip("'\""):
                return v.strip().strip("'\"")
    raise LLMUnavailable(f"API key {name} is not set: put a line {name}=<your key> in {env_file.name} "
                         "(gitignored) or export it")


class RateLimiter:
    """At most `rpm` acquisitions in any 60 s window. acquire() returns the seconds it waited."""

    def __init__(self, rpm: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if rpm <= 0:
            raise ValueError(f"rate_limit_rpm must be positive, got {rpm}")
        self.rpm, self.clock, self.sleep = int(rpm), clock, sleep
        self.sent: collections.deque[float] = collections.deque()

    def acquire(self) -> float:
        waited = 0.0
        while True:
            now = self.clock()
            while self.sent and now - self.sent[0] >= 60.0:
                self.sent.popleft()
            if len(self.sent) < self.rpm:
                self.sent.append(now)
                return waited
            pause = 60.0 - (now - self.sent[0])
            self.sleep(pause)
            waited += pause


class HostedClient:
    provider = "nvidia_nim"
    keep_alive = None

    def __init__(self, base_url: str, model: str, api_key: str, endpoint: str = "/chat/completions",
                 timeout_s: float = 60.0, temperature: float = 0.0, seed: int = 0, max_tokens: int = 128,
                 extra_body: dict[str, Any] | None = None, structured_output: str = "none",
                 rate_limit_rpm: float = 40, max_retries: int = 5, backoff_s: float = 2.0,
                 backoff_max_s: float = 60.0, session: Any = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        if not model:
            raise ValueError("No LLM model given")
        if timeout_s <= 0:
            raise ValueError(f"timeout_s must be positive, got {timeout_s}")
        if structured_output not in STRUCTURED:
            raise ValueError(f"structured_output must be one of {STRUCTURED}, got {structured_output!r}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {max_retries}")
        self.host = base_url.rstrip("/")
        self.endpoint = endpoint
        self.model = model
        self.timeout_s = float(timeout_s)
        self.extra_body = dict(extra_body or {})
        self.structured = structured_output
        self.max_retries, self.backoff_s, self.backoff_max_s = int(max_retries), float(backoff_s), float(backoff_max_s)
        self.limiter = RateLimiter(rate_limit_rpm, clock, sleep)
        self.sleep = sleep
        # What summary.json records about the requests (no key in here).
        self.options = {"temperature": float(temperature), "seed": int(seed), "max_tokens": int(max_tokens),
                        "extra_body": self.extra_body, "structured_output": structured_output,
                        "rate_limit_rpm": rate_limit_rpm, "max_retries": self.max_retries,
                        "backoff_s": self.backoff_s, "backoff_max_s": self.backoff_max_s}
        self._headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        self.session = session if session is not None else requests.Session()

    def __repr__(self) -> str:
        return f"HostedClient({self.host!r}, {self.model!r})"

    @classmethod
    def from_config(cls, llm_cfg: dict[str, Any], session: Any = None, model: str | None = None,
                    **kw: Any) -> "HostedClient":
        if llm_cfg.get("provider") != cls.provider:
            raise ValueError(f"llm.provider must be {cls.provider!r}, got {llm_cfg.get('provider')!r}")
        missing = [k for k in REQUIRED if k != "model" and llm_cfg.get(k) is None]
        if missing:
            raise KeyError(f"Config is missing llm.{missing}")
        env_file = Path(llm_cfg["env_file"])
        if env_file.is_absolute():
            raise ValueError(f"llm.env_file must be relative to the repo root, got {env_file}")
        key = load_api_key(llm_cfg["api_key_env"], repo_root() / env_file)
        return cls(base_url=llm_cfg["base_url"], model=model or llm_cfg["model"], api_key=key,
                   endpoint=llm_cfg["endpoint"], timeout_s=llm_cfg["timeout_s"],
                   temperature=llm_cfg["temperature"], seed=llm_cfg["seed"], max_tokens=llm_cfg["max_tokens"],
                   extra_body=llm_cfg.get("extra_body") or {}, structured_output=llm_cfg["structured_output"],
                   rate_limit_rpm=llm_cfg["rate_limit_rpm"], max_retries=llm_cfg["max_retries"],
                   backoff_s=llm_cfg["backoff_s"], backoff_max_s=llm_cfg["backoff_max_s"], session=session, **kw)

    # ---- HTTP ---------------------------------------------------------------------------
    def _send(self, method: str, path: str, body: dict | None, timeout: float) -> tuple[dict, float, tuple, float]:
        """One request with rate limiting and retries. Returns (json body, latency of the answered
        attempt, retries, seconds waited in the limiter and backoff)."""
        url = self.host + path
        retries: list[str] = []
        waited = 0.0
        while True:
            waited += self.limiter.acquire()
            t0 = time.perf_counter()
            try:
                r = self.session.request(method, url, json=body, headers=self._headers, timeout=timeout)
            except requests.exceptions.Timeout as e:
                err = LLMTimeout(f"{method} {url}: no answer within {timeout:.0f} s")
                err.retries = tuple(retries)
                raise err from e
            except requests.exceptions.ConnectionError as e:
                if len(retries) >= self.max_retries:
                    err = LLMUnavailable(f"Cannot reach {self.host} after {len(retries)} retries: {e}")
                    err.retries = tuple(retries)
                    raise err from e
                retries.append("connection")
                waited += self._backoff(len(retries), None)
                continue
            latency = time.perf_counter() - t0
            if r.status_code in RETRY_STATUS:
                if len(retries) >= self.max_retries:
                    err = LLMRetriesExhausted(f"{method} {url}: HTTP {r.status_code} after {len(retries)} retries: "
                                              f"{r.text[:200]}")
                    err.retries = tuple(retries)
                    raise err
                retries.append(str(r.status_code))
                waited += self._backoff(len(retries), r.headers.get("Retry-After"))
                continue
            try:
                data = r.json()
            except ValueError:
                data = None
            if r.status_code in (401, 403, 404):
                raise LLMUnavailable(f"{method} {url}: HTTP {r.status_code} ({r.text[:200]}); is the API key valid "
                                     f"and is {self.model!r} served for it?")
            if r.status_code != 200 or not isinstance(data, dict):
                err = LLMServerError(f"{method} {url}: HTTP {r.status_code}: {r.text[:200]}")
                err.retries = tuple(retries)
                raise err
            return data, latency, tuple(retries), waited

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        pause = min(self.backoff_s * 2 ** (attempt - 1), self.backoff_max_s)
        try:
            pause = max(pause, float(retry_after)) if retry_after is not None else pause
        except ValueError:
            pass
        self.sleep(pause)
        return pause

    # ---- model info ---------------------------------------------------------------------
    def server_version(self) -> str:
        return f"{self.host} (hosted, OpenAI-compatible; checked {datetime.now(timezone.utc):%Y-%m-%d})"

    def model_info(self) -> dict[str, Any]:
        """The model as GET /models lists it. Being listed does not prove it is served (some
        listed ids answer 404), so callers make one real call before a run."""
        data, _, _, _ = self._send("GET", "/models", None, 30)
        for m in data.get("data", []):
            if m.get("id") == self.model:
                return {"name": m["id"], "digest": None, "size_bytes": None,
                        "details": {"owned_by": m.get("owned_by"), "created": m.get("created"),
                                    "listed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "hosted": True, "local": False}}
        raise LLMUnavailable(f"Model {self.model!r} is not listed by {self.host}/models")

    def loaded_models(self) -> list[dict[str, Any]]:
        return []

    # ---- chat ---------------------------------------------------------------------------
    def chat(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> ChatResult:
        body = {"model": self.model, "messages": messages, "stream": False,
                "temperature": self.options["temperature"], "seed": self.options["seed"],
                "max_tokens": self.options["max_tokens"], **self.extra_body}
        if self.structured == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "decision", "schema": schema}}
        resp, latency, retries, waited = self._send("POST", self.endpoint, body, self.timeout_s)
        try:
            choice = resp["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError, TypeError):
            err = LLMServerError(f"Chat response has no choices[0].message: {str(resp)[:200]}")
            err.retries = retries
            raise err from None
        if not isinstance(msg.get("content"), str) or not msg["content"]:
            err = LLMServerError(f"Chat response has no message content (finish_reason "
                                 f"{choice.get('finish_reason')!r}): {str(msg)[:200]}")
            err.retries = retries
            raise err
        usage = resp.get("usage") or {}
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        return ChatResult(content=msg["content"], model=str(resp.get("model", "")), latency_s=latency,
                          prompt_tokens=usage.get("prompt_tokens"), response_tokens=usage.get("completion_tokens"),
                          total_duration_s=None, load_duration_s=None, done_reason=choice.get("finish_reason"),
                          reasoning_chars=len(reasoning), retries=retries, wait_s=waited)


def make_client(llm_cfg: dict[str, Any], session: Any = None):
    """The client for llm.provider: ollama (local) or nvidia_nim (hosted)."""
    provider = llm_cfg.get("provider")
    if provider == OllamaClient.provider:
        return OllamaClient.from_config(llm_cfg, session=session)
    if provider == HostedClient.provider:
        return HostedClient.from_config(llm_cfg, session=session)
    raise ValueError(f"llm.provider must be 'ollama' or 'nvidia_nim', got {provider!r}")
