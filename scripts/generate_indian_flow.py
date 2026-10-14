"""Generate Indian 2x2 flow files: one per demand level and seed.

    python scripts/generate_indian_flow.py --level peak --seed 0
    python scripts/generate_indian_flow.py --level all --seed 0 1 2
    python scripts/generate_indian_flow.py --level all --seed 0 1 2 --emergency

Writes <output_dir>/flow_<level>_s<seed>.json (CityFlow flow file) and a .meta.json next to it
(vehicle type per flow entry, counts, generator settings). See trafficsense.sim.demand.
With --emergency it writes flow_<level>_amb_s<seed>.json instead: the normal flow with
ambulances appended (configs/scenarios/indian_2x2.yaml, `emergency`). The normal flow is
regenerated and must equal the existing flow_<level>_s<seed>.json, which is left untouched.
"""
import argparse
import json

from trafficsense.config import load_config, repo_root
from trafficsense.sim.demand import add_emergency, generate
from trafficsense.sim.roadnet import load_roadnet


def flow_path(sc: dict, level: str, seed: int, emergency: bool = False):
    return repo_root() / sc["output_dir"] / f"flow_{level}{'_amb' if emergency else ''}_s{seed}.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario-config", default="configs/scenarios/indian_2x2.yaml")
    ap.add_argument("--level", required=True, help="a key of demand_levels, or 'all'")
    ap.add_argument("--seed", type=int, nargs="+", required=True)
    ap.add_argument("--emergency", action="store_true", help="write the _amb flow (normal flow + ambulances)")
    args = ap.parse_args()

    sc = load_config(args.scenario_config)
    net = load_roadnet(repo_root() / sc["roadnet"]["file"])
    levels = list(sc["demand_levels"]) if args.level == "all" else [args.level]
    for level in levels:
        for seed in args.seed:
            flows, meta = generate(net, sc, level, seed)
            meta["scenario_config"] = args.scenario_config
            p = flow_path(sc, level, seed)
            if args.emergency:
                if not p.is_file() or json.loads(p.read_text()) != flows:
                    raise SystemExit(f"{p.relative_to(repo_root())} is missing or differs from a fresh generation; "
                                     "the ambulance flow must extend the flow used by the other runs")
                flows, em = add_emergency(net, sc, flows, seed)
                meta.update(emergency=em, base_flow=str(p.relative_to(repo_root())),
                            vehicle_type_of_flow=meta["vehicle_type_of_flow"] + [em["vehicle_type"]] * len(em["emergency"]),
                            vehicles=len(flows))
                meta["vehicles_by_type"][em["vehicle_type"]] = len(em["emergency"])
                p = flow_path(sc, level, seed, emergency=True)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(flows), encoding="utf-8")
            p.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            print(f"Wrote {p.relative_to(repo_root())}: {meta['vehicles']} vehicles, {meta['vehicles_by_type']}")


if __name__ == "__main__":
    main()
