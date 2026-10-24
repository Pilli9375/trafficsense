"""Make the replays of the dashboard's Network Replay page (pre-registered in docs/dashboard.md).

    python scripts/make_replays.py           # replay every run in dashboard.replays.runs (skips finished ones)
    python scripts/make_replays.py --force   # make them all again
    python scripts/make_replays.py --check   # exit 1 unless every replay exists and matches its source run

Before replaying, the pre-registered selection is checked against the data: the configured
seed must be the one whose flow file has the most emergency vehicles among dashboard.replays.seeds,
and the run list must be exactly the full-length, exact-count runs of that scenario and seed
in outputs/emergency/runs and outputs/model_size/runs. Each replay must reproduce its run's
metrics exactly (trafficsense.sim.replay.record raises otherwise). Output: paths.replays/<run>/.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from trafficsense.config import load_config, repo_root, resolve_path
from trafficsense.experiment import git_info
from trafficsense.sim.replay import record, sha256
from trafficsense.sim.vehicles import VehicleTypes

RUN_ROOTS = ("outputs/emergency/runs", "outputs/model_size/runs")


def ambulance_counts(cfg: dict, scenario: str, seeds: list[int]) -> dict[int, int]:
    root = repo_root()
    sc = cfg["scenarios"][scenario]
    with (root / sc["vehicle_types"]).open(encoding="utf-8") as f:
        ytypes = yaml.safe_load(f)
    named = {**ytypes["vehicle_types"], **ytypes.get("emergency_vehicle_types", {})}
    out = {}
    for s in seeds:
        flow = root / sc["flow"].format(seed=s)
        vt = VehicleTypes(flow, named)
        n = len(json.loads(flow.read_text()))
        out[s] = sum(vt.of(f"flow_{i}_0") == sc["emergency_vehicle_type"] for i in range(n))
    return out


def eligible_runs(scenario: str, seed: int) -> list[str]:
    root = repo_root()
    found = []
    for rr in RUN_ROOTS:
        for p in sorted((root / rr).glob("*/summary.json")):
            s = json.loads(p.read_text())
            pv = s["provenance"]
            obs = s.get("observation")
            if (pv["scenario"] == scenario and pv["seed"] == seed and pv["sim_steps"] == 3600
                    and not pv.get("git_dirty") and (obs is None or obs.get("key") == "perfect")):
                found.append(str(p.parent.relative_to(root)))
    return found


def check_selection(cfg: dict) -> dict:
    rc = cfg["dashboard"]["replays"]
    counts = ambulance_counts(cfg, rc["scenario"], rc["seeds"])
    best = max(counts, key=lambda s: (counts[s], -s))
    if best != rc["seed"]:
        raise SystemExit(f"Selection rule picks seed {best} (ambulances per seed {counts}), config says {rc['seed']}")
    listed, found = sorted(rc["runs"]), sorted(eligible_runs(rc["scenario"], rc["seed"]))
    if listed != found:
        raise SystemExit(f"dashboard.replays.runs is not every eligible run.\n listed only: "
                         f"{sorted(set(listed) - set(found))}\n eligible, not listed: {sorted(set(found) - set(listed))}")
    print(f"selection rule: ambulances per seed {counts} -> seed {best}; {len(listed)} runs")
    return counts


def is_current(out: Path, run: Path) -> bool:
    meta = out / "meta.json"
    if not meta.is_file() or not (out / "replay.npz").is_file():
        return False
    m = json.loads(meta.read_text())
    return m["source_summary_sha256"] == sha256(run / "summary.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cfg = load_config("configs/default.yaml")
    root = repo_root()
    check_selection(cfg)
    out_root = resolve_path(cfg, "replays")
    runs = cfg["dashboard"]["replays"]["runs"]
    if args.check:
        stale = [r for r in runs if not is_current(out_root / Path(r).name, root / r)]
        print("replays match their runs" if not stale else f"missing or stale replays: {stale}")
        sys.exit(1 if stale else 0)
    if not out_root.is_dir():
        raise SystemExit(f"{out_root} does not exist; create the symlink to D (configs/default.yaml, paths.replays)")
    git = git_info()
    if git["dirty"]:
        raise SystemExit("Uncommitted code changes: commit before making replays (their meta.json records the commit)")
    for r in runs:
        out = out_root / Path(r).name
        if not args.force and is_current(out, root / r):
            print(f"done already: {Path(r).name}")
            continue
        meta = record(cfg, root / r, out, git)
        v = meta["verified"]
        size = (out / "replay.npz").stat().st_size / 2**20
        print(f"{Path(r).name}: {meta['controller']} {meta['model'] or ''} | ATT {v['network_metrics_identical']['att']:.2f} "
              f"identical, {v['emergency_vehicles_identical']} ambulances identical | {size:.1f} MiB")


if __name__ == "__main__":
    main()
