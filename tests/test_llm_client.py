"""OllamaClient against an in-process fake HTTP session (no server, no port)."""
import pytest
import requests

from trafficsense.llm.client import (LLMServerError, LLMTimeout, LLMUnavailable, OllamaClient)


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    """Returns queued (status, body) pairs, or raises queued exceptions; records requests."""
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def request(self, method, url, json=None, timeout=None):
        self.requests.append({"method": method, "url": url, "json": json, "timeout": timeout})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return FakeResponse(*r)


CHAT_OK = {"model": "m:1b", "message": {"role": "assistant", "content": '{"phase": 2, "reason": "x"}'},
           "done": True, "done_reason": "stop", "prompt_eval_count": 300, "eval_count": 20,
           "total_duration": 1_500_000_000, "load_duration": 100_000_000}


def client(*replies, **kw):
    s = FakeSession(*replies)
    return OllamaClient("http://h:1", "m:1b", timeout_s=7, seed=3, session=s, **kw), s


def test_chat_sends_schema_options_and_reports_server_values():
    c, s = client((200, CHAT_OK))
    r = c.chat([{"role": "user", "content": "hi"}], {"type": "object"})
    req = s.requests[0]
    assert req["url"] == "http://h:1/api/chat" and req["timeout"] == 7
    assert req["json"]["format"] == {"type": "object"} and req["json"]["stream"] is False
    assert req["json"]["think"] is False
    assert req["json"]["options"]["temperature"] == 0 and req["json"]["options"]["seed"] == 3
    assert r.content == CHAT_OK["message"]["content"] and r.model == "m:1b"
    assert r.prompt_tokens == 300 and r.response_tokens == 20
    assert r.total_duration_s == pytest.approx(1.5) and r.latency_s >= 0


@pytest.mark.parametrize("reply,err", [
    (requests.exceptions.ConnectionError("refused"), LLMUnavailable),
    (requests.exceptions.ReadTimeout("slow"), LLMTimeout),
    ((500, {"error": "out of memory"}), LLMServerError),
    ((404, {"error": "model not found"}), LLMUnavailable),
    ((200, {"error": "bad format"}), LLMServerError),
    ((200, {"model": "m", "done": True}), LLMServerError),        # no message
    ((200, ValueError("not json")), LLMServerError),
])
def test_chat_raises_typed_errors(reply, err):
    c, _ = client(reply)
    with pytest.raises(err):
        c.chat([{"role": "user", "content": "hi"}], {})


def test_failure_types_are_distinct():
    assert {LLMUnavailable.failure_type, LLMTimeout.failure_type, LLMServerError.failure_type} == \
        {"unavailable", "timeout", "server_error"}


def test_model_info_reads_digest_and_fails_if_missing():
    tags = {"models": [{"name": "m:1b", "model": "m:1b", "digest": "abc", "size": 5, "details": {"family": "x"}}]}
    c, _ = client((200, tags))
    assert c.model_info() == {"name": "m:1b", "digest": "abc", "size_bytes": 5, "details": {"family": "x"}}
    c, _ = client((200, {"models": [{"name": "other"}]}))
    with pytest.raises(LLMUnavailable, match="ollama pull"):
        c.model_info()


def test_from_config_requires_every_setting(cfg):
    llm = dict(cfg["llm"], model="m:1b")
    assert OllamaClient.from_config(llm, session=FakeSession()).model == "m:1b"
    with pytest.raises(ValueError, match="model"):
        OllamaClient.from_config(dict(cfg["llm"]), session=FakeSession())   # model is null in default.yaml
    bad = dict(llm)
    del bad["timeout_s"]
    with pytest.raises(KeyError, match="timeout_s"):
        OllamaClient.from_config(bad, session=FakeSession())
    with pytest.raises(ValueError, match="provider"):
        OllamaClient.from_config(dict(llm, provider="openai"), session=FakeSession())


def test_prompt_that_may_be_truncated_raises():
    c, _ = client((200, dict(CHAT_OK, prompt_eval_count=2000)), num_ctx=2048, num_predict=128)
    with pytest.raises(ValueError, match="num_ctx"):
        c.chat([{"role": "user", "content": "hi"}], {})
