"""Vehicle type of each simulated vehicle, from the flow file.

CityFlow does not report a vehicle's type, but it names vehicles `flow_<i>_<k>` after the
flow-file entry i they come from, and each entry holds the vehicle's parameters. A type is a
distinct parameter set (VEHICLE_KEYS). With `named` types (e.g. vehicle_types from
configs/scenarios/indian_2x2.yaml) each parameter set must match exactly one named type;
otherwise types are called `vehicle` (one type) or `type_0`, `type_1`, ... by frequency.
This is ground truth from the simulator; the perception layer will later estimate the same
counts from video.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any

from trafficsense.sim.demand import VEHICLE_KEYS

_ID = re.compile(r"^flow_(\d+)_\d+$")


def _key(v: dict[str, Any]) -> tuple:
    return tuple(float(v[k]) for k in VEHICLE_KEYS)


class VehicleTypes:
    def __init__(self, flow_path: str | Path, named: dict[str, dict[str, Any]] | None = None):
        flows = json.loads(Path(flow_path).read_text())
        keys = [_key(f["vehicle"]) for f in flows]
        if named:
            by_key: dict[tuple, str] = {}
            for name, t in named.items():
                missing = [k for k in VEHICLE_KEYS if k not in t]
                if missing:
                    raise KeyError(f"vehicle type {name!r} is missing {missing}")
                if _key(t) in by_key:
                    raise ValueError(f"vehicle types {by_key[_key(t)]!r} and {name!r} have the same parameters")
                by_key[_key(t)] = name
            unknown = {k for k in keys if k not in by_key}
            if unknown:
                raise ValueError(f"{flow_path}: {len(unknown)} vehicle parameter set(s) match no named type")
            self.names = list(named)
        else:
            common = [k for k, _ in collections.Counter(keys).most_common()]
            by_key = {common[0]: "vehicle"} if len(common) == 1 else {k: f"type_{i}" for i, k in enumerate(common)}
            self.names = list(by_key.values())
        self._of_flow = [by_key[k] for k in keys]

    def of(self, vehicle_id: str) -> str:
        m = _ID.match(vehicle_id)
        if not m:
            raise ValueError(f"Vehicle id {vehicle_id!r} is not of the form flow_<i>_<k>")
        return self._of_flow[int(m.group(1))]

    def count(self, vehicle_ids: list[str]) -> dict[str, int]:
        """Counts per type, in the type order of self.names, zeros left out."""
        c = collections.Counter(self.of(v) for v in vehicle_ids if not v.endswith("_shadow"))
        return {n: c[n] for n in self.names if c[n]}
