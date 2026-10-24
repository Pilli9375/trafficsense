"""Replays of saved runs (sim/replay.py): runs made here in tmp_path with MaxPressure and with an
injected fake LLM client (no server; nothing written to outputs/)."""
import copy
import csv
import json

import numpy as np
import pytest

from trafficsense.control.guided import LLMGuidedMPController
from trafficsense.experiment import run_experiment
from trafficsense.sim.replay import record
from test_llm_controller import FakeClient, lowest_allowed

SCENARIO, SEED, STEPS = "indian_2x2_peak_amb", 1, 320   # seed 1: an ambulance at t = 257 s
GIT = {"commit": "test", "dirty": True}


@pytest.fixture(scope="module")
def mp_run(cfg, tmp_path_factory):
    return run_experiment(cfg, SCENARIO, "maxpressure", steps=STEPS, seed=SEED,
                          out_root=tmp_path_factory.mktemp("runs"))


@pytest.fixture(scope="module")
def llm_run(cfg, tmp_path_factory):
    c = copy.deepcopy(cfg)
    c["llm"].update(model="fake:1b", decision_interval=5, min_green=15)
    ctl = LLMGuidedMPController(c, client=FakeClient(lowest_allowed), name="llm_guided_mp_v3")
    return run_experiment(c, SCENARIO, "llm_guided_mp_v3", steps=STEPS, seed=SEED,
                          out_root=tmp_path_factory.mktemp("runs"), ctl=ctl)


def test_rerun_controller_replay_matches_run(cfg, mp_run, tmp_path):
    meta = record(cfg, mp_run, tmp_path / "rp", GIT)
    assert meta["drive"] == "controller re-run"
    assert meta["verified"]["emergency_vehicles_identical"] == 1
    z = np.load(tmp_path / "rp" / "replay.npz")
    ids = meta["intersections"]
    assert z["phase"].shape == (STEPS, len(ids)) and z["queue"].shape == (STEPS, len(ids), 4)
    # per-approach queues add up to metrics.csv's per-intersection queue, step by step
    with (mp_run / "metrics.csv").open() as f:
        rows = list(csv.DictReader(f))
    q = {(int(float(r["time"])), r["intersection"]): int(r["queue"]) for r in rows}
    ph = {(int(float(r["time"])), r["intersection"]): int(r["phase"]) for r in rows}
    for t in range(STEPS):
        for i, iid in enumerate(ids):
            assert z["queue"][t, i].sum() == q[(t + 1, iid)]
            assert z["phase"][t, i] == ph[(t + 1, iid)]
    # vehicles: offsets consistent, the ambulance appears
    off = z["veh_offsets"]
    assert off[0] == 0 and off[-1] == len(z["veh_x"]) and len(off) == STEPS + 1
    assert meta["vehicle_types"].index("ambulance") in set(z["veh_type"].tolist())
    log = [json.loads(l) for l in (tmp_path / "rp" / "decisions_replay.jsonl").open()]
    assert log and all(set(d["mp_pressures"]) for d in log)


def test_decision_log_replay_matches_run(cfg, llm_run, tmp_path):
    c = copy.deepcopy(cfg)
    c["llm"].update(model="fake:1b", decision_interval=5, min_green=15)
    meta = record(c, llm_run, tmp_path / "rp", GIT)
    assert meta["drive"].startswith("decisions.jsonl")
    assert meta["model"] == "fake:1b"
    assert not (tmp_path / "rp" / "decisions_replay.jsonl").exists()


def test_metric_mismatch_raises(cfg, mp_run, tmp_path):
    bad = tmp_path / "run"
    bad.mkdir()
    for f in ("summary.json", "metrics.csv"):
        (bad / f).write_bytes((mp_run / f).read_bytes())
    s = json.loads((bad / "summary.json").read_text())
    s["metrics"]["att"] += 1e-9
    (bad / "summary.json").write_text(json.dumps(s))
    with pytest.raises(RuntimeError, match="does not reproduce"):
        record(cfg, bad, tmp_path / "rp", GIT)


def test_tampered_decision_log_raises(cfg, llm_run, tmp_path):
    bad = tmp_path / "run"
    bad.mkdir()
    (bad / "summary.json").write_bytes((llm_run / "summary.json").read_bytes())
    lines = (llm_run / "decisions.jsonl").read_text().splitlines()
    switch = next(k for k, l in enumerate(lines) if json.loads(l)["action"] == "switch")
    d = json.loads(lines[switch])
    d["phase"] = d["current_phase"]               # pretend the controller kept its phase
    lines[switch] = json.dumps(d)
    (bad / "decisions.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(RuntimeError):
        record(cfg, bad, tmp_path / "rp", GIT)


def test_noisy_run_rejected(cfg, mp_run, tmp_path):
    bad = tmp_path / "run"
    bad.mkdir()
    s = json.loads((mp_run / "summary.json").read_text())
    s["observation"] = {"key": "junction", "noised": True}
    (bad / "summary.json").write_text(json.dumps(s))
    with pytest.raises(ValueError, match="exact counts"):
        record(cfg, bad, tmp_path / "rp", GIT)
