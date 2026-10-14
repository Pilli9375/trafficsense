"""Metrics measured from the simulator, as defined in CLAUDE.md.

Call `update()` once after every `env.step()`.

* ATT: engine.get_average_travel_time() at the end of the run. CityFlow averages over every
  vehicle generated so far, timed from its scheduled start: finished vehicles up to their
  finish, vehicles still driving AND vehicles still queued to enter the network up to now.
  So entry-queue delay is included (verified in tests/test_metrics.py).
* Queue length: waiting vehicles (speed < 0.1 m/s, CityFlow's waiting count) on an
  intersection's incoming lanes, averaged over steps.
* Waiting time: seconds each vehicle spends with speed < 0.1 m/s, averaged over all vehicles
  that entered the network. Per intersection: seconds stopped on that intersection's incoming
  lanes, averaged over the vehicles that were on those lanes.
* Throughput: vehicles that finished their trip (were running and then left the network).
  Per intersection: vehicles that were on an incoming lane and later on an outgoing lane.
Apart from ATT, vehicles still waiting to enter the network are not counted.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from trafficsense.sim.env import TrafficEnv

STOP_SPEED = 0.1   # m/s


class MetricsTracker:
    def __init__(self, env: TrafficEnv):
        self.env = env
        self.ids = env.intersection_ids
        self._in_lanes = {i: env.intersection(i).incoming_lanes for i in self.ids}
        self._out_lanes = {i: env.intersection(i).outgoing_lanes for i in self.ids}

        self.steps = 0
        self._running: set[str] = set()
        self.seen: set[str] = set()
        self.finished = 0
        self.vehicle_wait: dict[str, float] = defaultdict(float)

        self.queue_sum = {i: 0.0 for i in self.ids}
        self.int_wait = {i: 0.0 for i in self.ids}
        self.int_seen: dict[str, set[str]] = {i: set() for i in self.ids}
        self.int_crossed: dict[str, set[str]] = {i: set() for i in self.ids}
        self.rows: list[dict[str, Any]] = []

    def update(self) -> None:
        eng = self.env.eng
        dt = self.env.interval
        waiting = eng.get_lane_waiting_vehicle_count()
        lane_veh = eng.get_lane_vehicles()
        speed = eng.get_vehicle_speed()
        running = set(eng.get_vehicles(include_waiting=False))

        self.finished += len(self._running - running)
        self._running = running
        self.seen |= running
        for v in running:
            if speed[v] < STOP_SPEED:
                self.vehicle_wait[v] += dt

        t = self.env.time
        for i in self.ids:
            q = sum(waiting[l] for l in self._in_lanes[i])
            self.queue_sum[i] += q
            on_in = 0
            for l in self._in_lanes[i]:
                for v in lane_veh[l]:
                    on_in += 1
                    self.int_seen[i].add(v)
                    if speed[v] < STOP_SPEED:
                        self.int_wait[i] += dt
            for l in self._out_lanes[i]:
                for v in lane_veh[l]:
                    if v in self.int_seen[i]:
                        self.int_crossed[i].add(v)
            self.rows.append({
                "time": t,
                "intersection": i,
                "phase": self.env.current_phase(i),
                "in_transition": int(self.env.in_transition(i)),
                "queue": q,
                "vehicles_incoming": on_in,
                "throughput_cum": len(self.int_crossed[i]),
            })
        self.steps += 1

    def summary(self) -> dict[str, Any]:
        if self.steps == 0:
            raise RuntimeError("No steps recorded")
        per_int = {}
        for i in self.ids:
            n = len(self.int_seen[i])
            per_int[i] = {
                "queue_mean": self.queue_sum[i] / self.steps,
                "waiting_time_mean": self.int_wait[i] / n if n else 0.0,
                "throughput": len(self.int_crossed[i]),
                "vehicles_seen": n,
            }
        n_seen = len(self.seen)
        return {
            "network": {
                "att": self.env.eng.get_average_travel_time(),
                "queue_mean_per_intersection": sum(p["queue_mean"] for p in per_int.values()) / len(per_int),
                "queue_mean_total": sum(self.queue_sum.values()) / self.steps,
                "waiting_time_mean": sum(self.vehicle_wait.values()) / n_seen if n_seen else 0.0,
                "throughput": self.finished,
                "vehicles_entered": n_seen,
                "vehicles_running_at_end": len(self._running),
                "steps": self.steps,
            },
            "per_intersection": per_int,
        }
