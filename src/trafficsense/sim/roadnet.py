"""Parse a CityFlow roadnet into per-intersection lanes, movements, phases and neighbours.

Everything here is derived from the roadnet file; nothing is hardcoded per scenario.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

TURN_TYPES = ("go_straight", "turn_left", "turn_right")


def lane_id(road_id: str, index: int) -> str:
    return f"{road_id}_{index}"


@dataclass(frozen=True)
class Movement:
    index: int                # index into the intersection's roadLinks
    approach: str             # N / E / S / W: the side the traffic comes from
    turn: str                 # go_straight / turn_left / turn_right
    in_road: str
    out_road: str
    lane_links: tuple[tuple[str, str], ...]   # (in_lane, out_lane)

    @property
    def in_lanes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(a for a, _ in self.lane_links))

    @property
    def out_lanes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(b for _, b in self.lane_links))

    @property
    def name(self) -> str:
        return f"{self.approach}-{self.turn}"


@dataclass(frozen=True)
class Phase:
    index: int
    duration: float
    movements: tuple[int, ...]    # Movement indexes served
    is_transition: bool


@dataclass
class Intersection:
    id: str
    point: tuple[float, float]
    incoming_roads: list[str]
    outgoing_roads: list[str]
    incoming_lanes: list[str]
    outgoing_lanes: list[str]
    movements: list[Movement]
    phases: list[Phase]
    neighbours: dict[str, str] = field(default_factory=dict)   # neighbour id -> direction N/E/S/W

    @property
    def green_phases(self) -> list[Phase]:
        return [p for p in self.phases if not p.is_transition]

    @property
    def transition_phase(self) -> Phase:
        """The single transition (yellow) phase. Raises if there is not exactly one."""
        t = [p for p in self.phases if p.is_transition]
        if len(t) != 1:
            raise ValueError(
                f"{self.id}: expected exactly one transition phase, found {[p.index for p in t]}"
            )
        return t[0]


@dataclass
class Roadnet:
    path: Path
    intersections: dict[str, Intersection]   # non-virtual only

    @property
    def ids(self) -> list[str]:
        return list(self.intersections)


def _direction(dx: float, dy: float) -> str:
    """Compass bucket of the vector (dx, dy); CityFlow's y axis points north."""
    ang = math.degrees(math.atan2(dy, dx)) % 360
    if ang < 45 or ang >= 315:
        return "E"
    if ang < 135:
        return "N"
    if ang < 225:
        return "W"
    return "S"


def _is_transition(links: list[int], duration: float, turn_of: dict[int, str],
                   median_duration: float) -> bool:
    """A phase is a transition phase if it serves no links, only right turns,
    or is much shorter than the intersection's typical phase (< half the median)."""
    if not links:
        return True
    if all(turn_of[k] == "turn_right" for k in links):
        return True
    return duration < 0.5 * median_duration


def load_roadnet(path: str | Path) -> Roadnet:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Roadnet not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    roads = {r["id"]: r for r in raw["roads"]}
    virtual = {i["id"] for i in raw["intersections"] if i["virtual"]}
    result: dict[str, Intersection] = {}

    for it in raw["intersections"]:
        if it["virtual"]:
            continue
        iid = it["id"]
        px, py = it["point"]["x"], it["point"]["y"]

        incoming = [r for r in it["roads"] if roads[r]["endIntersection"] == iid]
        outgoing = [r for r in it["roads"] if roads[r]["startIntersection"] == iid]
        if not incoming or not outgoing:
            raise ValueError(f"{iid}: no incoming or outgoing roads")

        def approach_of(road_id: str) -> str:
            # The road's point just before the intersection tells us which side traffic comes from.
            pts = roads[road_id]["points"]
            prev = pts[-2]
            return _direction(prev["x"] - px, prev["y"] - py)

        movements = []
        for k, rl in enumerate(it["roadLinks"]):
            if rl["type"] not in TURN_TYPES:
                raise ValueError(f"{iid}: unknown roadLink type {rl['type']!r}")
            links = tuple(
                (lane_id(rl["startRoad"], ll["startLaneIndex"]),
                 lane_id(rl["endRoad"], ll["endLaneIndex"]))
                for ll in rl["laneLinks"]
            )
            movements.append(Movement(k, approach_of(rl["startRoad"]), rl["type"],
                                      rl["startRoad"], rl["endRoad"], links))

        turn_of = {m.index: m.turn for m in movements}
        lightphases = it["trafficLight"]["lightphases"]
        durations = sorted(float(p["time"]) for p in lightphases)
        median = durations[len(durations) // 2]
        phases = []
        for k, ph in enumerate(lightphases):
            links = list(ph["availableRoadLinks"])
            bad = [x for x in links if x not in turn_of]
            if bad:
                raise ValueError(f"{iid} phase {k}: roadLink indexes {bad} out of range")
            phases.append(Phase(k, float(ph["time"]), tuple(links),
                                _is_transition(links, float(ph["time"]), turn_of, median)))

        result[iid] = Intersection(
            id=iid,
            point=(px, py),
            incoming_roads=incoming,
            outgoing_roads=outgoing,
            incoming_lanes=[lane_id(r, j) for r in incoming for j in range(len(roads[r]["lanes"]))],
            outgoing_lanes=[lane_id(r, j) for r in outgoing for j in range(len(roads[r]["lanes"]))],
            movements=movements,
            phases=phases,
        )

    # Neighbours: non-virtual intersections at the other end of a road.
    for iid, inter in result.items():
        for r in inter.incoming_roads + inter.outgoing_roads:
            other = roads[r]["startIntersection"] if roads[r]["endIntersection"] == iid \
                else roads[r]["endIntersection"]
            if other in virtual or other == iid:
                continue
            ox, oy = result[other].point
            inter.neighbours[other] = _direction(ox - inter.point[0], oy - inter.point[1])

    return Roadnet(path=path, intersections=result)
