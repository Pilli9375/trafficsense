"""Observation layer: exact view, camera-error view (sim/observation.py) on the Indian 2x2 scenario."""
import copy
import json

import numpy as np
import pytest

from trafficsense.control import make_controller
from trafficsense.experiment import run_experiment
from trafficsense.sim import observation as ob
from trafficsense.sim.env import TrafficEnv


def with_obs(cfg, **ocfg):
    c = copy.deepcopy(cfg)
    c["observation"] = ocfg
    return c


def advance(env, ctl, steps):
    for _ in range(steps):
        ctl.act(env)
        env.step()


def test_uniform_p1_reproduces_exact_counts(cfg):
    exact = TrafficEnv(cfg, "indian_2x2_peak", seed=0)
    noisy = TrafficEnv(with_obs(cfg, level="uniform", p_detect=1.0), "indian_2x2_peak", seed=0)
    ca, cb = make_controller("maxpressure", cfg), make_controller("maxpressure", cfg)
    for _ in range(4):
        advance(exact, ca, 150)
        advance(noisy, cb, 150)
        a, b = exact.lane_view(), noisy.lane_view()
        assert a.waiting == b.waiting and a.count == b.count and sum(a.count.values()) > 0
        lanes = sorted(a.count)
        assert a.type_counts(lanes, exact.vehicle_types.names) == b.type_counts(lanes, noisy.vehicle_types.names)
        iid = exact.intersection_ids[0]
        assert exact.get_state(iid) == noisy.get_state(iid)


def test_uniform_p1_run_equals_perfect_run(cfg, tmp_path):
    a = json.loads((run_experiment(cfg, "indian_2x2_peak", "maxpressure", steps=600, seed=1,
                                   out_root=tmp_path / "a") / "summary.json").read_text())
    b = json.loads((run_experiment(with_obs(cfg, level="uniform", p_detect=1.0), "indian_2x2_peak", "maxpressure",
                                   steps=600, seed=1, out_root=tmp_path / "b") / "summary.json").read_text())
    assert a["metrics"] == b["metrics"] and a["signal"] == b["signal"]
    assert a["observation"] == {"key": "perfect", "noised": False}
    assert b["observation"]["key"] == "uniform_p1.00" and b["observation"]["snapshots"] > 0


def test_detection_rate_and_redraw(cfg):
    env = TrafficEnv(with_obs(cfg, level="uniform", p_detect=0.5), "indian_2x2_peak", seed=0)
    ctl = make_controller("fixedtime", cfg)
    advance(env, ctl, 300)
    first = env.lane_view()
    assert env.lane_view() is first                        # same step: same snapshot
    seen = []
    for _ in range(200):
        advance(env, ctl, 1)
        seen.append(env.lane_view().count)
    s = env.observer.summary()
    for c, r in s["realized"]["detection_rate"].items():
        n = s["realized"]["true_vehicle_observations"][c]
        assert abs(r - 0.5) < 4 * np.sqrt(0.25 / n), (c, r, n)
    assert s["realized"]["false_per_road_snapshot"] == {j: 0.0 for j in ob.COUNTED}
    assert len({json.dumps(x, sort_keys=True) for x in seen}) > 150   # redrawn every observation


def test_seeded_draws(cfg):
    def log(seed):
        env = TrafficEnv(with_obs(cfg, level="uniform", p_detect=0.7), "indian_2x2_peak", seed=seed)
        ctl = make_controller("maxpressure", cfg)
        advance(env, ctl, 400)
        return env.observer.log
    assert log(0) == log(0) and log(0) != log(1)


def test_false_detections_poisson_and_labels(cfg):
    env = TrafficEnv(cfg, "indian_2x2_peak", seed=0)
    params = ob.NoiseParams("test", {c: 1.0 for c in ob.DETECTOR_CLASSES},
                            {c: {"person": 1.0} for c in ob.DETECTOR_CLASSES},   # every vehicle labelled person
                            {j: (0.5 if j == "car" else 0.0) for j in ob.COUNTED})
    env.observer = ob.NoisyObserver(env, params, 0)
    ctl = make_controller("fixedtime", cfg)
    for _ in range(300):
        advance(env, ctl, 1)
        v = env.lane_view()
    s = env.observer.summary()
    assert s["realized"]["false_per_road_snapshot"]["car"] == pytest.approx(0.5, abs=0.05)
    # Only phantoms are counted: every real vehicle was labelled person, which is not a vehicle.
    assert sum(s["realized"]["lost_to_non_vehicle_label"].values()) == sum(s["realized"]["true_vehicle_observations"].values())
    assert sum(v.waiting.values()) == sum(v.count.values())                       # phantoms are stopped
    assert set(v.type_counts(sorted(v.count), env.vehicle_types.names)) <= {"car"}


def test_ambulances_are_not_noised(cfg):
    env = TrafficEnv(with_obs(cfg, level="uniform", p_detect=0.01), "indian_2x2_peak_amb", seed=0)
    assert env.emergency_types == ["ambulance"]
    ctl = make_controller("maxpressure", cfg)
    flows = json.loads(env.flow_path.read_text())
    first = min(f["startTime"] for i, f in enumerate(flows)
                if env.vehicle_types.of(f"flow_{i}_0") == "ambulance")
    advance(env, ctl, int(first))
    found = 0
    for _ in range(120):
        advance(env, ctl, 1)
        lane_veh = env.eng.get_lane_vehicles()
        amb = {l: sum(env.vehicle_types.of(x) == "ambulance" for x in vs) for l, vs in lane_veh.items()}
        if any(amb.values()):
            v = env.lane_view()
            for l, n in amb.items():
                if n:
                    assert v.type_counts([l], env.vehicle_types.names).get("ambulance", 0) == n
                    found += 1
    assert found > 0


def test_webster_never_observes(cfg, tmp_path):
    a = json.loads((run_experiment(cfg, "indian_2x2_peak", "fixedtime_webster", steps=600, seed=0,
                                   out_root=tmp_path / "a") / "summary.json").read_text())
    b = json.loads((run_experiment(with_obs(cfg, level="crowded"), "indian_2x2_peak", "fixedtime_webster",
                                   steps=600, seed=0, out_root=tmp_path / "b") / "summary.json").read_text())
    assert a["metrics"] == b["metrics"] and b["observation"]["snapshots"] == 0


def test_noise_params_from_error_model(tmp_path):
    em = {"classes": list(ob.DETECTOR_CLASSES), "conf_threshold": 0.3,
          "p_detect": {c: 0.6 for c in ob.DETECTOR_CLASSES},
          "miss_rate_by_size": {c: {"small": {"gt": 10, "miss_rate": 0.9}, "medium": {"gt": 30, "miss_rate": 0.2},
                                    "large": {"gt": 10, "miss_rate": 0.0}} for c in ob.DETECTOR_CLASSES},
          "p_label_given_detected": {c: {d: (0.9 if d == c else 0.1 / 6) for d in ob.DETECTOR_CLASSES}
                                     for c in ob.DETECTOR_CLASSES},
          "false_det_per_image": {c: {"value": 0.1} for c in ob.DETECTOR_CLASSES}}
    f = tmp_path / "em.json"
    f.write_text(json.dumps(em))
    j = ob.noise_params({"level": "junction"}, f)
    assert j.p_detect["car"] == pytest.approx(1 - 6 / 40)          # pooled medium + large
    assert ob.noise_params({"level": "crowded"}, f).p_detect["car"] == 0.6
    assert set(j.false_det) == set(ob.COUNTED) and j.source["sha256"] and j.source["file"] == str(f)
    assert ob.repo_relative(ob.repo_root() / "outputs" / "x.json") == "outputs/x.json"
    u = ob.noise_params({"level": "uniform", "p_detect": 0.8}, f)
    assert u.key == "uniform_p0.80" and u.false_det["car"] == 0 and u.p_label["bus"] == {"bus": 1.0}
    with pytest.raises(ValueError):
        ob.observation_key({"level": "blurry"})
    with pytest.raises(FileNotFoundError):
        ob.make_observer(None, {"level": "junction"}, tmp_path / "missing.json", 0)


def test_sim_types_all_mapped(cfg):
    env = TrafficEnv(cfg, "indian_2x2_peak_amb", seed=0)
    assert set(env.vehicle_types.names) - set(env.emergency_types) == set(ob.SIM_TO_DETECTOR)
