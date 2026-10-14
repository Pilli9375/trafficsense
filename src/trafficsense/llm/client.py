"""Ollama client: native /api/chat with a JSON-schema `format` (structured output).

Every call uses temperature and seed from the config (0 and a fixed seed by default), a
timeout, and `think: false`. The result carries what the server reported: the model name,
token counts and durations, plus the wall-clock latency measured here.

Errors are raised, never hidden:
  * LLMUnavailable  the server cannot be reached, or the model is not installed. A run
                    cannot continue; callers must let this propagate.
  * LLMTimeout      no answer within timeout_s.
  * LLMServerError  the server answered with an HTTP error or an "error" field, or a body
                    that is not the expected chat response.
Each error has `failure_type`, which the controller counts.

The HTTP session is injectable (`session=`) so tests can use an in-process fake; nothing in
the package starts a fake server.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


class LLMError(Exception):
    failure_type = "llm_error"


class LLMUnavailable(LLMError):
    failure_type = "unavailable"


class LLMTimeout(LLMError):
    failure_type = "timeout"


class LLMServerError(LLMError):
    failure_type = "server_error"


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str                  # as reported by the server in the response
    latency_s: float            # wall clock, request sent -> response parsed
    prompt_tokens: int | None   # prompt_eval_count (None if the server did not report it)
    response_tokens: int | None  # eval_count
    total_duration_s: float | None
    load_duration_s: float | None
    done_reason: str | None


REQUIRED = ("host", "endpoint", "model", "timeout_s", "temperature", "seed", "num_ctx", "num_predict",
            "keep_alive")


class OllamaClient:
    provider = "ollama"

    def __init__(self, host: str, model: str, endpoint: str = "/api/chat", timeout_s: float = 60.0,
                 temperature: float = 0.0, seed: int = 0, num_ctx: int = 4096, num_predict: int = 128,
                 keep_alive: str = "30m", session: Any = None):
        if not model:
            raise ValueError("No LLM model given (llm.model in the config is null)")
        if timeout_s <= 0:
            raise ValueError(f"timeout_s must be positive, got {timeout_s}")
        self.host = host.rstrip("/")
        self.endpoint = endpoint
        self.model = model
        self.timeout_s = float(timeout_s)
        self.options = {"temperature": float(temperature), "seed": int(seed), "num_ctx": int(num_ctx),
                        "num_predict": int(num_predict)}
        self.keep_alive = keep_alive
        self.session = session if session is not None else requests.Session()

    @classmethod
    def from_config(cls, llm_cfg: dict[str, Any], session: Any = None, model: str | None = None) -> "OllamaClient":
        if llm_cfg.get("provider") != "ollama":
            raise ValueError(f"llm.provider must be 'ollama', got {llm_cfg.get('provider')!r}")
        missing = [k for k in REQUIRED if k != "model" and llm_cfg.get(k) is None]   # model: checked in __init__
        if missing:
            raise KeyError(f"Config is missing llm.{missing}")
        return cls(host=llm_cfg["host"], model=model or llm_cfg["model"], endpoint=llm_cfg["endpoint"],
                   timeout_s=llm_cfg["timeout_s"], temperature=llm_cfg["temperature"], seed=llm_cfg["seed"],
                   num_ctx=llm_cfg["num_ctx"], num_predict=llm_cfg["num_predict"],
                   keep_alive=llm_cfg["keep_alive"], session=session)

    # ---- HTTP ---------------------------------------------------------------------------
    def _request(self, method: str, path: str, json_body: dict | None = None,
                 timeout: float | None = None) -> dict[str, Any]:
        url = self.host + path
        try:
            r = self.session.request(method, url, json=json_body, timeout=timeout or self.timeout_s)
        except requests.exceptions.Timeout as e:
            raise LLMTimeout(f"{method} {url}: no answer within {timeout or self.timeout_s:.0f} s") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMUnavailable(f"Cannot reach the Ollama server at {self.host}: {e}") from e
        try:
            body = r.json()
        except ValueError:
            body = None
        if r.status_code != 200:
            msg = body.get("error") if isinstance(body, dict) else r.text[:200]
            if r.status_code == 404 and path != "/api/tags":
                raise LLMUnavailable(f"{method} {url}: HTTP 404 ({msg}); is model {self.model!r} pulled?")
            raise LLMServerError(f"{method} {url}: HTTP {r.status_code}: {msg}")
        if not isinstance(body, dict):
            raise LLMServerError(f"{method} {url}: response is not a JSON object: {r.text[:200]!r}")
        if "error" in body:
            raise LLMServerError(f"{method} {url}: {body['error']}")
        return body

    # ---- model info ---------------------------------------------------------------------
    def server_version(self) -> str:
        return str(self._request("GET", "/api/version", timeout=10)["version"])

    def model_info(self) -> dict[str, Any]:
        """Name, digest and details of the configured model, as listed by the server."""
        tags = self._request("GET", "/api/tags", timeout=10).get("models", [])
        for m in tags:
            if self.model in (m.get("name"), m.get("model")):
                return {"name": m.get("name"), "digest": m.get("digest"), "size_bytes": m.get("size"),
                        "details": m.get("details", {})}
        raise LLMUnavailable(f"Model {self.model!r} is not installed on {self.host} "
                             f"(installed: {[m.get('name') for m in tags]}); run `ollama pull {self.model}`")

    def loaded_models(self) -> list[dict[str, Any]]:
        """/api/ps: models in memory, with `size` and `size_vram` (bytes) as the server reports them."""
        return self._request("GET", "/api/ps", timeout=10).get("models", [])

    def unload(self, model: str | None = None) -> None:
        """Ask the server to drop a model from memory now (keep_alive 0)."""
        self._request("POST", "/api/generate", {"model": model or self.model, "keep_alive": 0}, timeout=60)

    # ---- chat ---------------------------------------------------------------------------
    def chat(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> ChatResult:
        body = {"model": self.model, "messages": messages, "format": schema, "stream": False, "think": False,
                "options": self.options, "keep_alive": self.keep_alive}
        t0 = time.perf_counter()
        resp = self._request("POST", self.endpoint, body)
        latency = time.perf_counter() - t0
        msg = resp.get("message")
        if not isinstance(msg, dict) or not isinstance(msg.get("content"), str):
            raise LLMServerError(f"Chat response has no message content: {str(resp)[:200]}")

        def secs(k: str) -> float | None:
            return resp[k] / 1e9 if isinstance(resp.get(k), (int, float)) else None

        return ChatResult(content=msg["content"], model=str(resp.get("model", "")), latency_s=latency,
                          prompt_tokens=resp.get("prompt_eval_count"), response_tokens=resp.get("eval_count"),
                          total_duration_s=secs("total_duration"), load_duration_s=secs("load_duration"),
                          done_reason=resp.get("done_reason"))
