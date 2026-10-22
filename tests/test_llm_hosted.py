"""HostedClient (NVIDIA NIM, OpenAI-compatible) against an in-process fake session: no network,
no port. A fake clock/sleep makes the rate limiter and backoff instant and checkable."""
import pytest
import requests

from trafficsense.llm.client import LLMServerError, LLMTimeout, LLMUnavailable, OllamaClient
from trafficsense.llm.hosted import (HostedClient, LLMRetriesExhausted, RateLimiter, load_api_key,
                                     make_client)

SECRET = "nvapi-test-secret-value"


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.text = str(body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def request(self, method, url, json=None, headers=None, timeout=None):
        self.requests.append({"method": method, "url": url, "json": json, "headers": headers, "timeout": timeout})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return FakeResponse(*r)


class FakeTime:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


OK = {"model": "deepseek-ai/deepseek-v4.1-flash", "choices": [{"finish_reason": "stop", "message": {
      "role": "assistant", "content": '{"phase": 2, "reason": "x"}'}}],
      "usage": {"prompt_tokens": 300, "completion_tokens": 20}}


def client(*replies, **kw):
    s, t = FakeSession(*replies), FakeTime()
    c = HostedClient("https://api.example/v1", "deepseek-ai/deepseek-v4.1-flash", SECRET, timeout_s=9,
                     session=s, clock=t.clock, sleep=t.sleep, **kw)
    return c, s, t


def test_chat_sends_openai_body_and_reports_server_values():
    c, s, _ = client((200, OK), structured_output="json_schema", extra_body={"chat_template_kwargs": {"thinking": False}})
    r = c.chat([{"role": "user", "content": "hi"}], {"type": "object"})
    req = s.requests[0]
    assert req["url"] == "https://api.example/v1/chat/completions" and req["timeout"] == 9
    assert req["json"]["temperature"] == 0 and req["json"]["stream"] is False
    assert req["json"]["chat_template_kwargs"] == {"thinking": False}
    assert req["json"]["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert r.content == OK["choices"][0]["message"]["content"] and r.model == OK["model"]
    assert (r.prompt_tokens, r.response_tokens, r.retries, r.reasoning_chars) == (300, 20, (), 0)


def test_no_format_sent_when_structured_output_is_none():
    c, s, _ = client((200, OK))
    c.chat([{"role": "user", "content": "hi"}], {"type": "object"})
    assert "response_format" not in s.requests[0]["json"]


def test_key_only_in_the_header():
    c, s, _ = client((200, OK))
    c.chat([{"role": "user", "content": "hi"}], {})
    assert s.requests[0]["headers"]["Authorization"] == f"Bearer {SECRET}"
    assert SECRET not in repr(c) and SECRET not in str(c.options) and SECRET not in str(s.requests[0]["json"])


def test_429_and_5xx_are_retried_with_backoff_and_counted():
    c, s, t = client((429, {"error": "rate"}, {"Retry-After": "7"}), (503, {"error": "busy"}), (200, OK),
                     backoff_s=2)
    r = c.chat([{"role": "user", "content": "hi"}], {})
    assert r.retries == ("429", "503") and len(s.requests) == 3
    assert t.slept == [7.0, 4.0]          # Retry-After beats 2 s; then 2 * 2^1
    assert r.wait_s == pytest.approx(11.0)


def test_retries_exhausted_is_a_counted_failure_with_its_retries():
    c, _, _ = client(*[(500, {"error": "x"})] * 3, max_retries=2)
    with pytest.raises(LLMRetriesExhausted) as e:
        c.chat([{"role": "user", "content": "hi"}], {})
    assert e.value.failure_type == "retries_exhausted" and e.value.retries == ("500", "500")


def test_timeout_is_a_failure_not_retried():
    c, s, _ = client(requests.exceptions.ReadTimeout("slow"))
    with pytest.raises(LLMTimeout):
        c.chat([{"role": "user", "content": "hi"}], {})
    assert len(s.requests) == 1


def test_connection_drops_are_retried_then_stop_the_run():
    c, _, _ = client((requests.exceptions.ConnectionError("reset")), (200, OK))
    assert c.chat([{"role": "user", "content": "hi"}], {}).retries == ("connection",)
    c, _, _ = client(*[requests.exceptions.ConnectionError("down")] * 3, max_retries=2)
    with pytest.raises(LLMUnavailable):
        c.chat([{"role": "user", "content": "hi"}], {})


@pytest.mark.parametrize("reply,err", [
    ((401, {"detail": "bad key"}), LLMUnavailable),
    ((404, {"detail": "Function not found for account"}), LLMUnavailable),
    ((400, {"detail": "bad request"}), LLMServerError),
    ((200, {"choices": []}), LLMServerError),
    ((200, {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}), LLMServerError),
])
def test_typed_errors(reply, err):
    c, _, _ = client(reply)
    with pytest.raises(err):
        c.chat([{"role": "user", "content": "hi"}], {})


def test_reasoning_output_is_measured():
    body = {**OK, "choices": [{"finish_reason": "stop", "message": {"content": "{}", "reasoning_content": "abcd"}}]}
    c, _, _ = client((200, body))
    assert c.chat([{"role": "user", "content": "hi"}], {}).reasoning_chars == 4


def test_rate_limiter_allows_rpm_per_60_s_window():
    t = FakeTime()
    lim = RateLimiter(3, t.clock, t.sleep)
    waits = [lim.acquire() for _ in range(4)]
    assert waits == [0, 0, 0, 60.0]       # the 4th waits until the 1st leaves the window
    t.now += 30                           # t = 90; the window holds t = 60
    assert lim.acquire() == 0 and lim.acquire() == 0
    assert lim.acquire() == pytest.approx(30.0)   # full until t = 120


def test_limiter_counts_every_attempt():
    c, _, t = client((429, {}), (200, OK), rate_limit_rpm=1, backoff_s=1)
    c.chat([{"role": "user", "content": "hi"}], {})
    assert sum(t.slept) == pytest.approx(60.0)   # 1 s backoff, then 59 s until the window frees


def test_model_info_requires_listed_id():
    c, _, _ = client((200, {"data": [{"id": "deepseek-ai/deepseek-v4.1-flash", "owned_by": "deepseek-ai"}]}))
    info = c.model_info()
    assert info["name"] == "deepseek-ai/deepseek-v4.1-flash" and info["details"]["local"] is False
    c, _, _ = client((200, {"data": [{"id": "other"}]}))
    with pytest.raises(LLMUnavailable, match="not listed"):
        c.model_info()


def test_load_api_key_env_then_file_and_never_echoes(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text(f"# comment\nOTHER=1\nNVIDIA_API_KEY='{SECRET}'\n")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert load_api_key("NVIDIA_API_KEY", f) == SECRET
    monkeypatch.setenv("NVIDIA_API_KEY", "from-env")
    assert load_api_key("NVIDIA_API_KEY", f) == "from-env"
    monkeypatch.delenv("NVIDIA_API_KEY")
    f.write_text(f"NVIDIA_API_KEY=\n")
    with pytest.raises(LLMUnavailable) as e:
        load_api_key("NVIDIA_API_KEY", f)
    assert SECRET not in str(e.value)


def test_make_client_dispatches_on_provider(cfg, monkeypatch):
    assert isinstance(make_client(dict(cfg["llm"], model="m:1b"), session=FakeSession()), OllamaClient)
    monkeypatch.setenv("NVIDIA_API_KEY", SECRET)
    hosted = dict(cfg["llm"], **cfg["llm_hosted"]["nvidia_nim"])
    c = make_client(hosted, session=FakeSession())
    assert isinstance(c, HostedClient) and c.model == cfg["llm_hosted"]["nvidia_nim"]["model"]
    with pytest.raises(ValueError, match="provider"):
        make_client(dict(cfg["llm"], provider="openai"))


def test_env_file_is_gitignored():
    import subprocess
    from trafficsense.config import repo_root
    out = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=repo_root())
    assert out.returncode == 0, ".env must be gitignored (it holds the API key)"
