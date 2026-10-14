"""Prompt and response schema for LLM signal control (one call per intersection decision).

observe() collects what the LLM is told, all measured from the simulator at decision time:
  * current green phase and seconds shown, min/max green, transition length;
  * for each candidate green phase, its movements, each with
      queue        stopped vehicles (speed < 0.1 m/s) on the movement's incoming lanes,
      moving       vehicles on those lanes that are not stopped (approaching the stop line),
      downstream   stopped vehicles on the movement's exit lanes;
  * vehicle-type counts on each approach (all vehicles on its incoming lanes);
  * cooperative mode only, per neighbouring intersection: its current phase, the stopped
    vehicles there whose movement leads onto the road into us (and how many of them have
    green now), and the stopped vehicles on the road from us into it.
Free turns (CityFlow `turn_right`) run in every phase, including the transition, so the LLM
cannot affect them and they are left out. Movement names are neutral about the side of
the road: "straight", "cross-turn" (CityFlow turn_left, crossing the opposing flow).

Two prompt versions render the same observation:
  * v1 (Phase 3a, kept for the record): every movement's queue/moving/downstream, vehicle
    types per approach, neighbours; the rules say switching "wastes green time"; reason <= 25
    words. About 650 tokens.
  * v2: one line per phase with a precomputed pressure and queue, so the model does no
    arithmetic; neighbours as in v1; no vehicle types (to stay under ~300 tokens; pressure
    counts vehicles regardless of type, as MaxPressure does); the transition is stated as a
    fact without advice; reason <= 15 words.
  * guided (llm_guided_mp): MaxPressure ranks the phases; only the offered options (its top
    phases, and keeping the current one when allowed) are listed, in rank order, with their
    pressure and queue; neighbours as in v2; reason <= 15 words.
Phase pressure here is MaxPressure's (queue minus downstream queue, summed over the phase's
movements) without the free turns. Every green phase serves all free turns, so leaving them
out lowers every phase by the same amount and keeps MaxPressure's ranking.

The answer must be JSON {"phase": <allowed id>, "reason": "<= N words"} (N per version).
parse_response() raises InvalidResponse with a failure type for anything else; the
controller counts it.
"""
from __future__ import annotations

import json
from typing import Any

from trafficsense.sim.env import TrafficEnv

VERSIONS = ("v1", "v2", "guided")
MAX_REASON_WORDS = {"v1": 25, "v2": 15, "guided": 15}
TURN_LABEL = {"go_straight": "straight", "turn_left": "cross-turn"}
FREE_TURN = "turn_right"
MODES = ("cooperative", "isolated")

# v1: unchanged since the Phase 3a benchmark (tests pin its hash).
SYSTEM_PROMPT = """You control the traffic signal of one intersection in a city road network with mixed \
Indian traffic (two-wheelers, auto-rickshaws, cars, buses, trucks).
At each decision you choose which green phase to show next. Goal: keep vehicles moving and queues short \
across the whole network, so total travel time is low.
Rules of the signal:
- Choosing the current phase keeps it green. Choosing another phase first shows a {transition} s \
transition in which only free turns move, so switching too often wastes green time.
- A green phase cannot be ended before {min_green} s and is ended automatically at {max_green} s.
Data you get for each movement: queue = stopped vehicles waiting at the stop line; moving = vehicles \
driving towards the stop line; downstream = stopped vehicles on the exit road (a full exit road blocks \
the movement).
Answer with JSON only: {{"phase": <one of the allowed phase ids>, "reason": "<at most 25 words>"}}."""

SYSTEM_PROMPT_V2 = """You pick the next green phase for one traffic signal in an Indian city. Goal: short \
queues and low travel time network-wide.
Changing phase starts a {transition} s transition in which only free turns move. A green lasts {min_green} to \
{max_green} s.
queue = stopped vehicles a phase serves; pressure = queue minus stopped vehicles on their exit roads.
Reply JSON: {{"phase": <allowed id>, "reason": "<at most {words} words>"}}"""


SYSTEM_PROMPT_GUIDED = """You help a MaxPressure controller run one traffic signal in an Indian city. Goal: \
short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = stopped vehicles a phase serves minus stopped vehicles on their exit \
roads; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a {transition} s transition in which only free turns move. A green lasts {min_green} to \
{max_green} s.
Reply JSON: {{"phase": <offered id>, "reason": "<at most {words} words>"}}"""


def movement_label(m) -> str:
    return f"{m.approach} {TURN_LABEL[m.turn]}"


def phase_label(inter, phase) -> str:
    """Short name of a green phase from its non-free movements, e.g. "W+E straight",
    "W+E cross-turn", or "N only" for every movement of one approach."""
    ms = [inter.movements[k] for k in phase.movements if inter.movements[k].turn != FREE_TURN]
    turns = [TURN_LABEL[t] for t in TURN_LABEL if any(m.turn == t for m in ms)]
    sides = list(dict.fromkeys(m.approach for m in ms))
    if len(turns) == 1:
        return f"{'+'.join(sides)} {turns[0]}"
    if len(sides) == 1:
        return f"{sides[0]} only" if len(turns) == len(TURN_LABEL) else f"{sides[0]} {'+'.join(turns)}"
    return ", ".join(movement_label(m) for m in ms)


def response_schema(allowed: list[int], version: str) -> dict[str, Any]:
    """JSON schema passed as Ollama's `format`. maxLength bounds the generated text (latency);
    the word limit itself is checked in parse_response."""
    return {"type": "object",
            "properties": {"phase": {"type": "integer", "enum": sorted(allowed)},
                           "reason": {"type": "string", "maxLength": 8 * MAX_REASON_WORDS[version]}},
            "required": ["phase", "reason"]}


class InvalidResponse(ValueError):
    def __init__(self, failure_type: str, msg: str):
        super().__init__(msg)
        self.failure_type = failure_type


def parse_response(text: str, allowed: list[int], max_words: int) -> tuple[int, str]:
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        raise InvalidResponse("invalid_json", f"not JSON: {text[:200]!r}") from e
    if not isinstance(obj, dict) or set(obj) != {"phase", "reason"}:
        raise InvalidResponse("invalid_schema", f"expected exactly keys phase, reason: {text[:200]!r}")
    phase, reason = obj["phase"], obj["reason"]
    if isinstance(phase, bool) or not isinstance(phase, int):
        raise InvalidResponse("invalid_schema", f"phase is not an integer: {phase!r}")
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidResponse("invalid_schema", f"reason is not a non-empty string: {reason!r}")
    if phase not in allowed:
        raise InvalidResponse("phase_not_allowed", f"phase {phase} not in allowed {sorted(allowed)}")
    if len(reason.split()) > max_words:
        raise InvalidResponse("reason_too_long", f"reason has {len(reason.split())} words (max {max_words})")
    return phase, reason.strip()


def _road_between(env: TrafficEnv, a: str, b: str) -> str | None:
    """The road from intersection a to intersection b, if any."""
    roads = set(env.intersection(a).outgoing_roads) & set(env.intersection(b).incoming_roads)
    if len(roads) > 1:
        raise ValueError(f"More than one road from {a} to {b}: {sorted(roads)}")
    return next(iter(roads), None)


def observe(env: TrafficEnv, iid: str, allowed: list[int], mode: str, min_green: int) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    inter = env.intersection(iid)
    waiting = env.eng.get_lane_waiting_vehicle_count()
    count = env.eng.get_lane_vehicle_count()
    lane_veh = env.eng.get_lane_vehicles()
    by_idx = {m.index: m for m in inter.movements}

    def mv(m) -> dict[str, Any]:
        q = sum(waiting[l] for l in m.in_lanes)
        return {"movement": movement_label(m), "queue": q, "moving": sum(count[l] for l in m.in_lanes) - q,
                "downstream": sum(waiting[l] for l in m.out_lanes)}

    phases = []
    for p in inter.green_phases:
        ms = [mv(by_idx[k]) for k in p.movements if by_idx[k].turn != FREE_TURN]
        phases.append({"id": p.index, "label": phase_label(inter, p), "movements": ms,
                       "queue": sum(m["queue"] for m in ms),
                       "pressure": sum(m["queue"] - m["downstream"] for m in ms)})
    on_approach: dict[str, list[str]] = {}
    for m in inter.movements:
        for l in m.in_lanes:
            on_approach.setdefault(m.approach, []).extend(lane_veh[l])
    types = {a: env.vehicle_types.count(v) for a, v in sorted(on_approach.items())}

    obs: dict[str, Any] = {
        "intersection": iid, "time": int(env.time), "current_phase": env.signals[iid].green_phase,
        "time_in_phase": env.time_in_phase(iid), "min_green": min_green, "max_green": env.max_green,
        "transition_s": env.transition_time[iid], "phases": phases, "vehicle_types": types,
        "allowed": sorted(allowed),
    }
    if mode == "cooperative":
        obs["neighbours"] = [_neighbour(env, iid, nb, d, waiting) for nb, d in sorted(inter.neighbours.items())]
    return obs


def _neighbour(env: TrafficEnv, iid: str, nb: str, direction: str, waiting: dict[str, int]) -> dict[str, Any]:
    n = env.intersection(nb)
    sig = env.signals[nb]
    green = None if sig.in_transition else sig.green_phase
    served = set(n.phases[green].movements) if green is not None else set()
    to_us, from_us = _road_between(env, nb, iid), _road_between(env, iid, nb)
    toward = [m for m in n.movements if m.out_road == to_us]
    return {
        "id": nb, "direction": direction,
        "phase": green, "phase_movements": [movement_label(n.movements[k]) for k in sorted(served)
                                            if n.movements[k].turn != FREE_TURN],
        "phase_label": None if green is None else phase_label(n, n.phases[green]),
        "queue_heading_to_us": sum(waiting[l] for m in toward for l in m.in_lanes),
        "of_which_green_now": sum(waiting[l] for m in toward if m.index in served or m.turn == FREE_TURN
                                  for l in m.in_lanes),
        "queue_on_road_from_us": sum(waiting[l] for m in n.movements if m.in_road == from_us for l in m.in_lanes),
    }


def render(obs: dict[str, Any]) -> str:
    """The user message: compact text, one line per phase/approach/neighbour."""
    lines = [f"Intersection {obs['intersection']}, time {obs['time']} s.",
             f"Current green: phase {obs['current_phase']}, shown for {obs['time_in_phase']} s."]
    lines.append("Phases (movement: queue/moving/downstream):")
    for p in obs["phases"]:
        cur = " (current)" if p["id"] == obs["current_phase"] else ""
        ms = "; ".join(f"{m['movement']}: {m['queue']}/{m['moving']}/{m['downstream']}" for m in p["movements"])
        lines.append(f"  phase {p['id']}{cur}: {ms}")
    lines.append("Vehicles on each approach:")
    for a, c in obs["vehicle_types"].items():
        lines.append(f"  {a}: " + (", ".join(f"{k} {v}" for k, v in c.items()) or "none"))
    if "neighbours" in obs:
        lines.append("Neighbouring intersections:")
        for nb in obs["neighbours"]:
            ph = "in transition" if nb["phase"] is None else \
                f"phase {nb['phase']} ({', '.join(nb['phase_movements'])})"
            lines.append(f"  {nb['direction']} {nb['id']}: {ph}; {nb['queue_heading_to_us']} stopped there "
                         f"heading to us ({nb['of_which_green_now']} on green now); "
                         f"{nb['queue_on_road_from_us']} stopped on our road into it.")
    lines.append(f"Allowed phases: {obs['allowed']}. Reply with JSON only.")
    return "\n".join(lines)


def _neighbour_line(nb: dict[str, Any]) -> str:
    ph = "in transition" if nb["phase"] is None else f"phase {nb['phase']} ({nb['phase_label']})"
    return (f"{nb['direction']}: {ph}; {nb['queue_heading_to_us']} stopped toward us, "
            f"{nb['of_which_green_now']} on green; {nb['queue_on_road_from_us']} stopped on our road to it")


def render_v2(obs: dict[str, Any]) -> str:
    """v2 user message: one line per phase (pressure, queue), then neighbours."""
    cur = next(p for p in obs["phases"] if p["id"] == obs["current_phase"])
    lines = [f"Phase {cur['id']} ({cur['label']}) green for {obs['time_in_phase']} s.",
             "phase: pressure, queue"]
    for p in obs["phases"]:
        lines.append(f"{p['id']} {p['label']}: {p['pressure']}, {p['queue']}")
    if "neighbours" in obs:
        lines.append("Neighbours:")
        lines.extend(_neighbour_line(nb) for nb in obs["neighbours"])
    every = [p["id"] for p in obs["phases"]]
    left_out = [i for i in every if i not in obs["allowed"]]
    lines.append("Allowed: all" if not left_out else
                 f"Allowed: all except {', '.join(map(str, left_out))}" if len(left_out) < len(every) / 2 else
                 f"Allowed: {', '.join(map(str, obs['allowed']))}")
    return "\n".join(lines)


def render_guided(obs: dict[str, Any]) -> str:
    """Guided user message: the offered options in MaxPressure's rank order (obs["ranking"])."""
    cur = next(p for p in obs["phases"] if p["id"] == obs["current_phase"])
    by_id = {p["id"]: p for p in obs["phases"]}
    lines = [f"Phase {cur['id']} ({cur['label']}) green for {obs['time_in_phase']} s.",
             "Options, best MaxPressure rank first (phase: pressure, queue):"]
    for i in [r for r in obs["ranking"] if r in obs["allowed"]]:
        p = by_id[i]
        keep = " (keep current)" if i == obs["current_phase"] else ""
        lines.append(f"{i} {p['label']}{keep}: {p['pressure']}, {p['queue']}")
    if "neighbours" in obs:
        lines.append("Neighbours:")
        lines.extend(_neighbour_line(nb) for nb in obs["neighbours"])
    return "\n".join(lines)


def messages(obs: dict[str, Any], version: str) -> list[dict[str, str]]:
    if version == "v1":
        sys = SYSTEM_PROMPT.format(transition=obs["transition_s"], min_green=obs["min_green"],
                                   max_green=obs["max_green"])
        user = render(obs)
    elif version == "v2":
        sys = SYSTEM_PROMPT_V2.format(transition=obs["transition_s"], min_green=obs["min_green"],
                                      max_green=obs["max_green"], words=MAX_REASON_WORDS["v2"])
        user = render_v2(obs)
    elif version == "guided":
        sys = SYSTEM_PROMPT_GUIDED.format(transition=obs["transition_s"], min_green=obs["min_green"],
                                          max_green=obs["max_green"], words=MAX_REASON_WORDS["guided"])
        user = render_guided(obs)
    else:
        raise ValueError(f"prompt version must be one of {VERSIONS}, got {version!r}")
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]
