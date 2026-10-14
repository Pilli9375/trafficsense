"""Generate the Indian 2x2 roadnet from configs/scenarios/indian_2x2.yaml.

Uses CityFlow's own grid generator (vendored in trafficsense.sim._vendor.cityflow_grid) with
tlPlan=False, which gives phase 0 = 5 s transition phase (right turns only) and 8 green phases,
the same phase layout as the CoLLMLight roadnets.

    python scripts/generate_indian_roadnet.py [--scenario-config configs/scenarios/indian_2x2.yaml]
"""
import argparse
import json

from trafficsense.config import load_config, repo_root
from trafficsense.sim._vendor.cityflow_grid import gridToRoadnet
from trafficsense.sim.roadnet import load_roadnet


def build(rn: dict) -> dict:
    rows, cols = int(rn["rows"]), int(rn["cols"])
    lanes = rn["lanes"]
    width = rn["intersection_width_m"]
    return gridToRoadnet(
        rowNumber=rows,
        columnNumber=cols,
        rowDistances=[rn["spacing_m"]] * (cols - 1),
        columnDistances=[rn["spacing_m"]] * (rows - 1),
        outRowDistance=rn["boundary_road_m"],
        outColumnDistance=rn["boundary_road_m"],
        intersectionWidths=[[width] * cols for _ in range(rows)],
        laneWidth=rn["lane_width_m"],
        laneMaxSpeed=rn["lane_max_speed_mps"],
        numLeftLanes=int(lanes["left"]),
        numStraightLanes=int(lanes["straight"]),
        numRightLanes=int(lanes["right"]),
        tlPlan=False,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario-config", default="configs/scenarios/indian_2x2.yaml")
    args = ap.parse_args()
    sc = load_config(args.scenario_config)
    rn = sc["roadnet"]
    out = repo_root() / rn["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(rn), indent=1), encoding="utf-8")

    net = load_roadnet(out)   # fails loudly if the parser can't make sense of it
    for iid, inter in net.intersections.items():
        print(f"{iid}: transition phase {inter.transition_phase.index} "
              f"({inter.transition_phase.duration:.0f} s), greens {[p.index for p in inter.green_phases]}, "
              f"paired {[p.index for p in inter.paired_phases]}, neighbours {inter.neighbours}")
    print(f"Wrote {out.relative_to(repo_root())}")


if __name__ == "__main__":
    main()
