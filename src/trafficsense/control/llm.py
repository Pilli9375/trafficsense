"""LLM signal control: one LLM call per intersection decision (adapted from CoLLMLight).

Modes: `cooperative` (the prompt includes a summary of each neighbouring intersection) and
`isolated` (own intersection only); see trafficsense.llm.prompt for exactly what is sent.

Timing, from llm.* in the config, follows MaxPressure so the two differ only in the decision
rule: decisions fall on a grid of `decision_interval` seconds; an intersection is asked only
when it may switch (not in transition, green shown for at least `min_green`, which must be
>= signal.min_green). The env inserts the transition phase and enforces min/max green. When
keeping the current phase would reach max_green before the next decision, the current phase
is not offered.

Failures: a timeout, server error or an invalid answer (see prompt.parse_response) keeps the
current phase and is counted by type and logged. If the server is unreachable
(LLMUnavailable), or `max_consecutive_failures` calls in a row fail, the run stops with an
error. Nothing is filled in silently.

Outputs: provenance() for summary.json (model and digest, call/failure counts, latency
mean/p95) and decisions.jsonl (one line per call) via write_artifacts().
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from trafficsense.control.base import Controller
from trafficsense.llm import prompt
from trafficsense.llm.client import LLMError, LLMUnavailable, OllamaClient
from trafficsense.sim.env import TrafficEnv

log = logging.getLogger(__name__)

REQUIRED = ("decision_interval", "min_green", "max_consecutive_failures")


class LLMController(Controller):
    def __init__(self, cfg: dict[str, Any], name: str = "llm_cooperative", client: Any = None):
        self.name = name
        if name not in cfg["controllers"]:
            raise KeyError(f"Config is missing controllers.{name}")
        self.mode = cfg["controllers"][name].get("mode")
        if self.mode not in prompt.MODES:
            raise ValueError(f"controllers.{name}.mode must be one of {prompt.MODES}, got {self.mode!r}")
        llm = cfg["llm"]
        missing = [k for k in REQUIRED if llm.get(k) is None]
        if missing:
            raise KeyError(f"Config is missing llm.{missing} (decided after scripts/benchmark_llm.py)")
        self.interval = int(llm["decision_interval"])
        self.min_green = int(llm["min_green"])
        self.max_green = int(cfg["signal"]["max_green"])
        self.max_consecutive = int(llm["max_consecutive_failures"])
        env_min = int(cfg["signal"]["min_green"])
        if self.interval <= 0:
            raise ValueError(f"llm.decision_interval must be positive, got {self.interval}")
        if not env_min <= self.min_green < self.max_green:
            raise ValueError(f"llm.min_green must be in [signal.min_green {env_min}, max_green {self.max_green}), "
                             f"got {self.min_green}")
        self.client = client if client is not None else OllamaClient.from_config(llm)
        self.model_info = self.client.model_info()          # raises if the server or model is missing
        self.server_version = self.client.server_version()
        self.decisions: list[dict[str, Any]] = []
        self._consecutive = 0

    def act(self, env: TrafficEnv) -> None:
        if int(round(env.time)) % self.interval != 0:
            return
        for iid in env.intersection_ids:
            if not env.can_switch(iid) or env.time_in_phase(iid) < self.min_green:
                continue
            self._decide(env, iid)

    def _decide(self, env: TrafficEnv, iid: str) -> None:
        cur = env.signals[iid].green_phase
        allowed = [p.index for p in env.intersection(iid).green_phases]
        if env.time_in_phase(iid) + self.interval >= self.max_green:
            allowed.remove(cur)
        obs = prompt.observe(env, iid, allowed, self.mode, self.min_green)
        msgs = prompt.messages(obs)
        rec: dict[str, Any] = {"step": int(env.time), "intersection": iid, "current_phase": cur,
                               "time_in_phase": env.time_in_phase(iid), "allowed": allowed}
        try:
            res = self.client.chat(msgs, prompt.response_schema(allowed))
            rec.update(latency_s=res.latency_s, prompt_tokens=res.prompt_tokens,
                       response_tokens=res.response_tokens, server_model=res.model, raw=res.content)
            phase, reason = prompt.parse_response(res.content, allowed)
        except LLMUnavailable:
            raise
        except (LLMError, prompt.InvalidResponse) as e:
            self._consecutive += 1
            rec.update(ok=False, failure_type=e.failure_type, error=str(e), phase=cur, reason=None,
                       action="kept current phase (failure)")
            self.decisions.append(rec)
            n = sum(1 for d in self.decisions if not d["ok"])
            log.warning("LLM failure #%d (%s) at t=%s %s: %s", n, e.failure_type, rec["step"], iid, e)
            if self._consecutive >= self.max_consecutive:
                raise RuntimeError(f"{self._consecutive} LLM calls in a row failed (last: {e.failure_type}: {e}); "
                                   "stopping the run") from e
            return
        self._consecutive = 0
        switched = env.request_phase(iid, phase)
        rec.update(ok=True, failure_type=None, phase=phase, reason=reason,
                   action="switch" if switched else "keep")
        self.decisions.append(rec)

    # ---- reporting ----------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        d = self.decisions
        fails: dict[str, int] = {}
        for x in d:
            if not x["ok"]:
                fails[x["failure_type"]] = fails.get(x["failure_type"], 0) + 1
        lat = [x["latency_s"] for x in d if "latency_s" in x]   # every call that got an answer
        pt = [x["prompt_tokens"] for x in d if x.get("prompt_tokens") is not None]
        rt = [x["response_tokens"] for x in d if x.get("response_tokens") is not None]
        served = sorted({x["server_model"] for x in d if "server_model" in x})
        return {
            "calls": len(d),
            "ok": sum(1 for x in d if x["ok"]),
            "failures": sum(fails.values()),
            "failures_by_type": dict(sorted(fails.items())),
            "failure_rate": sum(fails.values()) / len(d) if d else None,
            "switches_requested": sum(1 for x in d if x.get("action") == "switch"),
            "latency_n": len(lat),
            "latency_mean_s": float(np.mean(lat)) if lat else None,
            "latency_p95_s": float(np.percentile(lat, 95)) if lat else None,   # numpy linear interpolation
            "latency_max_s": float(np.max(lat)) if lat else None,
            "prompt_tokens_mean": float(np.mean(pt)) if pt else None,
            "response_tokens_mean": float(np.mean(rt)) if rt else None,
            "server_reported_models": served,
            "latency_note": "wall clock per call, over calls that returned a response (timeouts excluded, counted as failures)",
        }

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "mode": self.mode, "decision_interval": self.interval,
                "min_green": self.min_green, "phases": "all",
                "client": {"host": self.client.host, "endpoint": self.client.endpoint,
                           "timeout_s": self.client.timeout_s, "options": self.client.options,
                           "keep_alive": self.client.keep_alive},
                "max_consecutive_failures": self.max_consecutive}

    def provenance(self) -> dict[str, Any]:
        st = self.stats()
        served = st["server_reported_models"]
        return {"model": served[0] if len(served) == 1 else (served or self.model_info["name"]),
                "provider": self.client.provider,
                "llm": {**st, "model_digest": self.model_info["digest"], "model_details": self.model_info["details"],
                        "server_version": self.server_version, "decisions_log": "decisions.jsonl"}}

    def write_artifacts(self, out_dir: Path) -> None:
        with (out_dir / "decisions.jsonl").open("w", encoding="utf-8") as f:
            for rec in self.decisions:
                f.write(json.dumps(rec) + "\n")
