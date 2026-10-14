"""Generate the tables in docs/validation.md from outputs/validation/*.json.

    python scripts/validation/make_tables.py          # rewrite the tables in place
    python scripts/validation/make_tables.py --check  # exit 1 if the doc is out of date

Each table sits between <!-- BEGIN:name --> and <!-- END:name --> markers in the doc.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "outputs" / "validation"
DOC = ROOT / "docs" / "validation.md"

DATASETS = [("synthetic_4x4", "synthetic_4x4"), ("jinan", "jinan_3x4"), ("hangzhou", "hangzhou_4x4")]


def load(path):
    return json.loads(path.read_text())


def theirs(ds, model, seed=0):
    return load(VAL / "collmlight" / f"{ds}_{model}_s{seed}.json")


def ours(sc, profile, seed):
    return load(VAL / "ours" / f"{sc}_{profile}_s{seed}.json")


def engine_seed(ds, model, seed=0):
    return theirs(ds, model, seed)["engine_configs"][-1]["seed"]


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def f1(x):
    return f"{x:.1f}"


def cm_row(label, m, seed):
    return [label, f1(m["test_avg_travel_time_over"]), int(m["test_throughput_over"]),
            f1(m["test_avg_queue_len_over"]), f1(m["test_avg_waiting_time_over"]),
            f1(m["cityflow_att"]), seed]


CM_HEADER = ["Run", "ATT (their def.)", "Throughput (their def.)", "Queue (their def., network total)",
             "Waiting (their def.)", "CityFlow ATT", "Engine seed"]


def crosscheck(ds, sc):
    s_ft, s_mp = engine_seed(ds, "Fixedtime"), engine_seed(ds, "MaxPressure")
    rows = [
        cm_row("CoLLMLight code: FixedTime", theirs(ds, "Fixedtime")["results"], s_ft),
        cm_row("Ours, replaying their FixedTime (phases 1,3 on a 30 s grid)",
               ours(sc, "replica_fixedtime", s_ft)["collmlight_metrics"], s_ft),
        cm_row("CoLLMLight code: MaxPressure", theirs(ds, "MaxPressure")["results"], s_mp),
        cm_row("Ours, MaxPressure matched to theirs",
               ours(sc, "matched_maxpressure", s_mp)["collmlight_metrics"], s_mp),
    ]
    return table(CM_HEADER, rows)


def ours_table(ds, sc):
    s = engine_seed(ds, "MaxPressure")
    runs = [
        ("CoLLMLight code: FixedTime", None, theirs(ds, "Fixedtime")["results"]),
        ("CoLLMLight code: MaxPressure", None, theirs(ds, "MaxPressure")["results"]),
        ("Ours: FixedTime, 4 phases, 30 s grid (matched, correct cycle)", ours(sc, "matched_fixedtime", s), None),
        ("Ours: MaxPressure matched", ours(sc, "matched_maxpressure", s), None),
        ("Ours default: FixedTime (4 paired phases, 30 s)", ours(sc, "default_fixedtime", 0), None),
        ("Ours default: FixedTime all 8 phases", ours(sc, "default_fixedtime_all_phases", 0), None),
        ("Ours default: MaxPressure (8 phases, 5 s, min 10 / max 60)", ours(sc, "default_maxpressure", 0), None),
    ]
    rows = []
    for label, o, t in runs:
        if o is not None:
            tm, cm = o["trafficsense_metrics"], o["collmlight_metrics"]
            rows.append([label, f1(tm["att"]), f1(tm["queue_mean_per_intersection"]),
                         f1(tm["waiting_time_mean"]), tm["throughput"], f1(cm["test_avg_travel_time_over"]),
                         int(cm["test_throughput_over"])])
        else:
            rows.append([label, f1(t["cityflow_att"]), "–", "–", "–", f1(t["test_avg_travel_time_over"]),
                         int(t["test_throughput_over"])])
    return table(["Run", "ATT (CityFlow)", "Queue / intersection", "Waiting time / vehicle",
                  "Throughput (finished trips)", "ATT (CoLLMLight def.)", "Throughput (CoLLMLight def.)"], rows)


def exactness_table():
    keys = [("ATT", "test_avg_travel_time_over"), ("Throughput", "test_throughput_over"),
            ("Queue", "test_avg_queue_len_over"), ("Waiting", "test_avg_waiting_time_over"),
            ("CityFlow ATT", "cityflow_att")]
    rows = []
    for ds, sc in DATASETS:
        for model, profile in (("Fixedtime", "replica_fixedtime"), ("MaxPressure", "matched_maxpressure")):
            t = theirs(ds, model)
            o = ours(sc, profile, engine_seed(ds, model))["collmlight_metrics"]
            cells = []
            for _, k in keys:
                a, b = t["results"][k], o[k]
                cells.append("identical" if a == b else f"{abs(a - b) / abs(a):.1e} rel.")
            rows.append([sc, model] + cells)
    return table(["Dataset", "Controller"] + [n for n, _ in keys], rows)


def seeds_table():
    rows = []
    for model in ("Fixedtime", "MaxPressure"):
        for seed in (0, 1, 2):
            p = VAL / "collmlight" / f"synthetic_4x4_{model}_s{seed}.json"
            if p.exists():
                d = load(p)
                r = d["results"]
                rows.append([model, seed, d["engine_configs"][-1]["seed"], f"{r['test_avg_travel_time_over']:.4f}",
                             int(r["test_throughput_over"]), f"{r['test_avg_queue_len_over']:.4f}",
                             f"{r['cityflow_att']:.4f}"])
    return table(["CoLLMLight model", "numpy seed", "Engine seed drawn", "ATT (their def.)",
                  "Throughput (their def.)", "Queue (their def.)", "CityFlow ATT"], rows)


def demand_table():
    d = load(VAL / "demand_synthetic_4x4.json")
    rows = [[r["road"], r["vehicles"], f"{100 * r['share']:.1f}%",
             ", ".join(f"{k} {v}" for k, v in sorted(r["first_turn"].items(), key=lambda kv: -kv[1]))]
            for r in d["by_entry_road"]]
    return table(["Entry road", "Vehicles / h", "Share", "Turn at first intersection"], rows)


def capacity_table():
    d = load(VAL / "demand_synthetic_4x4.json")
    b, c = d["busiest_road"], d["lane_capacity"]
    rows = [
        ["Demand on road_2_5_3 (all lanes)", b["vehicles_per_hour"]],
        ["Demand needing its straight lane", b["busiest_lane_vehicles_per_hour"]],
        ["Straight-lane capacity, measured (permanent green, 1 veh/s fed)",
         f"{c['measured_permanent_green']['measured_veh_per_hour']:.0f}"],
        ["Straight-lane capacity, ESTIMATE from car-following parameters",
         f"{c['estimate_veh_per_hour_ESTIMATE']:.0f}"],
        ["Demand / measured capacity", f"{b['demand_over_measured_capacity']:.2f}"],
    ]
    return table(["Quantity", "veh / h"], rows)


def time_table():
    d = load(VAL / "demand_synthetic_4x4.json")
    return table(["Start time", "Vehicles"], [[k, v] for k, v in d["by_start_time_10min"].items()])


def build():
    t = {
        "crosscheck_synthetic": crosscheck("synthetic_4x4", "synthetic_4x4"),
        "crosscheck_jinan": crosscheck("jinan", "jinan_3x4"),
        "crosscheck_hangzhou": crosscheck("hangzhou", "hangzhou_4x4"),
        "all_synthetic": ours_table("synthetic_4x4", "synthetic_4x4"),
        "all_jinan": ours_table("jinan", "jinan_3x4"),
        "all_hangzhou": ours_table("hangzhou", "hangzhou_4x4"),
        "seeds": seeds_table(),
        "exactness": exactness_table(),
        "demand": demand_table(),
        "capacity": capacity_table(),
        "demand_time": time_table(),
    }
    return t


def render(doc, tables):
    for name, body in tables.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(doc):
            raise KeyError(f"Marker for table {name!r} missing in {DOC}")
        doc = pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = DOC.read_text()
    new = render(doc, build())
    if args.check:
        if new != doc:
            print("docs/validation.md tables are out of date; run scripts/validation/make_tables.py")
            sys.exit(1)
        print("docs/validation.md tables match outputs/validation")
        return
    DOC.write_text(new)
    print(f"Updated {DOC}")


if __name__ == "__main__":
    main()
