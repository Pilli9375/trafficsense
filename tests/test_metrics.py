import pytest

from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker


@pytest.fixture(scope="module")
def run600(cfg, synthetic_4x4):
    env = TrafficEnv(cfg, "synthetic_4x4")
    m = MetricsTracker(env)
    for _ in range(600):
        env.step()
        m.update()
    return env, m


def test_throughput_positive_after_600_steps(run600):
    _, m = run600
    s = m.summary()["network"]
    assert s["throughput"] > 0
    assert s["vehicles_entered"] == s["throughput"] + s["vehicles_running_at_end"]
    assert all(p["throughput"] > 0 for p in m.summary()["per_intersection"].values())


def test_basic_metric_sanity(run600):
    env, m = run600
    s = m.summary()["network"]
    assert s["att"] > 0
    assert s["steps"] == 600
    assert s["queue_mean_total"] == pytest.approx(s["queue_mean_per_intersection"] * 16)
    assert 0 < s["waiting_time_mean"] < 600


def test_queue_matches_stopped_vehicles(run600):
    # CityFlow's waiting count and our speed threshold must agree on the last step
    env, m = run600
    speed = env.eng.get_vehicle_speed()
    lane_veh = env.eng.get_lane_vehicles()
    for i in env.intersection_ids:
        stopped = sum(speed[v] < 0.1 for l in env.intersection(i).incoming_lanes for v in lane_veh[l])
        row = [r for r in m.rows if r["intersection"] == i][-1]
        assert row["queue"] == stopped


def test_rows_per_step_per_intersection(run600):
    _, m = run600
    assert len(m.rows) == 600 * 16
    assert m.rows[0].keys() >= {"time", "intersection", "phase", "queue", "throughput_cum"}


def test_summary_without_steps_raises(cfg, synthetic_4x4):
    with pytest.raises(RuntimeError):
        MetricsTracker(TrafficEnv(cfg, "synthetic_4x4")).summary()


def test_cityflow_att_includes_vehicles_waiting_to_enter(cfg, synthetic_4x4):
    """Pins down what get_average_travel_time() measures: every generated vehicle, timed from
    its flow startTime; finished ones up to the step before we see them gone, the rest
    (running or still queued to enter) up to now."""
    import json
    flows = json.loads(synthetic_4x4["flow"].read_text())
    start = {f"flow_{i}_0": f["startTime"] for i, f in enumerate(flows)}
    env = TrafficEnv(cfg, "synthetic_4x4")
    finish, prev = {}, set()
    for _ in range(900):
        env.step()
        run = set(env.eng.get_vehicles(include_waiting=False))
        for v in prev - run:
            finish[v] = env.time - 1
        prev = run
    now = env.time
    pending = set(env.eng.get_vehicles(include_waiting=True))
    assert len(pending) > len(prev)            # some vehicles are still queued to enter
    total = sum(finish[v] - start[v] for v in finish) + sum(now - start[v] for v in pending)
    assert env.eng.get_average_travel_time() == pytest.approx(total / (len(finish) + len(pending)), abs=1e-6)


def test_lane_change_shadows_are_not_vehicles(cfg):
    # Jinan with lane changing produces "<id>_shadow" placeholders from ~t=139
    on = {**cfg, "sim": {**cfg["sim"], "lane_change": True}}
    env = TrafficEnv(on, "jinan_3x4")
    m = MetricsTracker(env)
    seen_shadow = False
    for _ in range(300):
        env.step()
        m.update()
        seen_shadow |= any(v.endswith("_shadow") for vs in env.eng.get_lane_vehicles().values() for v in vs)
    assert seen_shadow
    assert not any(v.endswith("_shadow") for s in m.int_seen.values() for v in s)
