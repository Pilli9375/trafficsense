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
