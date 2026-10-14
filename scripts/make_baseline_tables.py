"""Generate the tables in docs/baselines.md from the baseline result files.

    python scripts/make_baseline_tables.py          # update the doc
    python scripts/make_baseline_tables.py --check  # exit 1 if the doc is out of date

Inputs: outputs/baselines/maxpressure_sweep.json (scripts/tune_maxpressure.py).
Each table sits between <!-- BEGIN:name --> and <!-- END:name --> markers in the doc.
Mean ± std is over seeds 0, 1, 2; std is the sample standard deviation (ddof = 1).
"""
import argparse
import json
import re
import sys

from trafficsense.config import repo_root

ROOT = repo_root()
DOC = ROOT / "docs" / "baselines.md"
SWEEP = ROOT / "outputs" / "baselines" / "maxpressure_sweep.json"
TRANSITION_S = 5
MIN_GREEN = 10


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def ms(e, nd):
    return f"{e['mean']:.{nd}f} ± {e['std']:.{nd}f}"


def shortest_green(interval):
    """First decision-grid point at least MIN_GREEN after the transition ends (tested in
    tests/test_baselines.py)."""
    k = 1
    while k * interval - TRANSITION_S < MIN_GREEN:
        k += 1
    return k * interval - TRANSITION_S


def sweep_table(sw, sc):
    rows = []
    rank = sw["selection"]["rank"][sc]
    for k, e in sw["results"][sc].items():
        rows.append([f"{k} s", f"{shortest_green(int(k))} s", ms(e["att"], 1), ms(e["throughput"], 0),
                     ms(e["waiting_to_enter"], 1), ms(e["queue_mean_per_intersection"], 2),
                     ms(e["transition_share"], 3), f"{rank[k]:g}"])
    return table(["Decision interval", "Shortest possible green", "ATT (s)", "Throughput",
                  "Waiting to enter at 3600 s", "Queue / int. (veh)", "Time in transition", "ATT rank"], rows)


def selection_table(sw):
    sel = sw["selection"]
    scs = sw["provenance"]["scenarios"]
    rows = []
    for k in map(str, sw["provenance"]["intervals"]):
        rows.append([f"{k} s"] + [f"{sel['rank'][sc][k]:g}" for sc in scs]
                    + [f"{sel['mean_rank'][k]:.2f}", f"{sel['mean_att_over_best'][k]:.3f}",
                       "**chosen**" if int(k) == sel["chosen_decision_interval"] else ""])
    return table(["Interval"] + [f"Rank: {sc}" for sc in scs] + ["Mean rank", "Mean ATT / best", ""], rows)


def build():
    sw = json.loads(SWEEP.read_text())
    tables = {f"mp_sweep_{sc}": sweep_table(sw, sc) for sc in sw["provenance"]["scenarios"]}
    tables["mp_selection"] = selection_table(sw)
    return tables


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
        ok = new == doc
        print("docs/baselines.md matches the results" if ok else
              "docs/baselines.md is out of date; run scripts/make_baseline_tables.py")
        sys.exit(0 if ok else 1)
    DOC.write_text(new)
    print(f"Updated {DOC}")


if __name__ == "__main__":
    main()
