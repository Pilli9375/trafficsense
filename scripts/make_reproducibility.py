"""Generate the tables in docs/reproducibility.md from the fresh-clone check's record.

    python scripts/make_reproducibility.py          # update the doc
    python scripts/make_reproducibility.py --check  # exit 1 if the doc is out of date

Input: outputs/reproducibility/fresh_clone.json, written once when the repository was checked
from a fresh clone (docs/reproducibility.md says how each part was measured). It holds the raw
comparisons, not conclusions: every committed run that was re-run with its committed and
re-run values, the repeated lane-changing runs, the LLM and detector re-runs, timings, sizes
and the dashboard page checks. The README's setup numbers are tagged against the same file
(facts r.*, src/trafficsense/report/facts.py).
"""
import argparse
import json
import sys

from trafficsense.config import repo_root
from trafficsense.report.numbers import render_blocks

ROOT = repo_root()
DOC = ROOT / "docs" / "reproducibility.md"
RECORD = ROOT / "outputs" / "reproducibility" / "fresh_clone.json"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def duration(s):
    if s is None:
        return "–"
    return f"{s:.0f} s" if s < 120 else f"{s / 60:.0f} min"


def rel(a, b):
    return 0.0 if a == b else abs(a - b) / abs(a)


def outcome(identical, note=""):
    return ("**identical**" if identical else "differs") + (f" ({note})" if note else "")


def env_table(r):
    return table(["", ""], r["environment"])


def steps_table(r):
    return table(["Step", "Command", "Result", "Time"],
                 [(s["step"], f"`{s['command']}`", s["result"], duration(s.get("seconds"))) for s in r["steps"]])


def summary_table(r):
    det = r["deterministic_runs"]
    n_det = sum(x["identical"] for x in det)
    v = r["validation"]
    off = [x for x in v if x["side"] == "ours" and not x["lane_change"]]
    on = [x for x in v if x["side"] == "ours" and x["lane_change"]]
    theirs = [x for x in v if x["side"] == "collmlight"]

    def count(rows, kind):
        return sum(x["outcome"] == kind for x in rows)

    def lane_change_row(rows):
        same = all(x["throughput_identical"] and x["queue_identical"] for x in rows)
        return (f"throughput and queue identical in {'all' if same else 'not all'}; CityFlow ATT identical in "
                f"{sum(x['rel_diff'] == 0 for x in rows)}, otherwise at most {max(x['rel_diff'] for x in rows):.1e} "
                f"relative apart")

    lc = r["lane_change_repeats"]["by_profile"].values()
    n_lc = sum(len(p["att"]) for p in lc)
    tp_same = all(len(set(p["throughput"])) == 1 for p in lc)
    att_varied = sum(len(set(p["att"])) > 1 for p in lc)
    llm, d = r["llm"], r["detector"]
    rows = [
        ("FixedTime, Webster, MaxPressure, preemption (Indian 2x2 all seeds, emergency seeds, Jinan)",
         f"{len(det)} runs", f"{n_det} of {len(det)} identical in every metric"),
        ("Validation, ours, lane changing off (default profiles)", f"{len(off)} files",
         f"{count(off, 'identical')} identical; {count(off, 'settings changed since')} made with an earlier default "
         f"setting, identical when re-run with it"),
        ("Validation, ours, lane changing on (matched profiles)", f"{len(on)} files", lane_change_row(on)),
        ("Validation, CoLLMLight's own code (lane changing on)", f"{len(theirs)} files", lane_change_row(theirs)),
        ("Lane-changing profiles, each run 5 times in a row", f"{n_lc} runs",
         f"throughput {'identical in every repeat' if tp_same else 'varied'}; ATT varied in {att_varied} of {len(lc)} "
         f"profiles"),
        ("LLM, pre-registered arm, 600 s", "1 run",
         f"{llm['identical_answers']} of {llm['calls']} answers identical, {llm['failures']} failures; "
         f"metrics {'identical' if llm['metrics_identical'] else 'different'}"),
        ("Detector, IDD test split", f"{d['images']} images",
         f"mAP50 {d['rerun']['mAP50']:.3f} (committed {d['committed']['mAP50']:.3f}), "
         f"mAP50-95 {d['rerun']['mAP50_95']:.3f} (committed {d['committed']['mAP50_95']:.3f}); every other value "
         f"{'identical' if not d['detector_test_differences'] and not d['error_model_differences'] else 'NOT identical'}"),
    ]
    return table(["What was re-run", "How many", "Result"], rows)


def runs_table(r):
    rows = [(x["scenario"], x["controller"], x["seed"], f"{x['att_committed']:.4f}", f"{x['att_rerun']:.4f}",
             x["throughput_committed"], x["throughput_rerun"], outcome(x["identical"]))
            for x in sorted(r["deterministic_runs"], key=lambda x: (x["scenario"], x["controller"], x["seed"]))]
    return table(["Scenario", "Controller", "Seed", "ATT committed (s)", "ATT re-run (s)", "Trips committed",
                  "Trips re-run", "Every metric"], rows)


def validation_table(r):
    rows = []
    for x in r["validation"]:
        if x["outcome"] == "identical":
            res = "**identical**" + (" (apart from fields added later)" if x.get("added_fields") else "")
        elif x["outcome"] == "settings changed since":
            res = f"made with {x['made_with']}; re-run with it: **identical**"
        else:
            res = f"ATT {x['rel_diff']:.1e} relative; throughput and queue identical"
        rows.append((x["side"], x["file"], "on" if x["lane_change"] else "off", f"{x['att_committed']:.4f}",
                     f"{x['att_rerun']:.4f}", res))
    return table(["Code", "File", "Lane changing", "CityFlow ATT committed (s)", "Re-run (s)", "Result"], rows)


def lane_change_table(r):
    lc = r["lane_change_repeats"]
    rows = []
    for name, p in lc["by_profile"].items():
        att = p["att"]
        rows.append((name, len(att), len(set(att)), f"{min(att):.4f}", f"{max(att):.4f}",
                     f"{rel(min(att), max(att)):.1e}", len(set(p["throughput"])), len(set(p["waiting_time_mean"]))))
    return table(["Profile (engine seed 47)", "Runs", "Distinct ATT", "Lowest ATT (s)", "Highest ATT (s)",
                  "Spread (relative)", "Distinct throughput", "Distinct waiting time"], rows)


def cityflow_table(r):
    rows = [("on" if c["lane_change"] else "off", ", ".join(f"{a:.5f}" for a in c["att"]), len(set(c["att"])))
            for c in r["pure_cityflow"]["runs"]]
    return table(["Lane changing", "ATT of each run (s)", "Distinct"], rows)


def llm_table(r):
    llm, cg = r["llm"], r["llm_cpu_gpu"]
    rows = [("Committed run", llm["committed"]["calls"], llm["committed"]["failures"],
             f"{llm['committed']['latency_mean_s']:.2f}", f"{llm['committed']['latency_p95_s']:.2f}",
             f"{llm['committed']['att']:.2f}"),
            ("Fresh clone, GPU", llm["rerun"]["calls"], llm["rerun"]["failures"],
             f"{llm['rerun']['latency_mean_s']:.2f}", f"{llm['rerun']['latency_p95_s']:.2f}", f"{llm['rerun']['att']:.2f}")]
    rows2 = [(m.upper(), cg[m]["calls"], cg[m]["failures"], f"{cg[m]['latency_mean_s']:.2f}",
              f"{cg[m]['latency_p95_s']:.2f}") for m in ("gpu", "cpu")]
    return (table(["600 s run", "Calls", "Failures", "Latency mean (s)", "p95 (s)", "ATT at 600 s (s)"], rows)
            + "\n\nCPU fallback, 120 s of the same setup:\n\n"
            + table(["Ollama on", "Calls", "Failures", "Latency mean (s)", "p95 (s)"], rows2))


def detector_table(r):
    d = r["detector"]
    rows = [(k, f"{d['committed'][k]:.6f}", f"{d['rerun'][k]:.6f}", outcome(d["committed"][k] == d["rerun"][k]))
            for k in ("mAP50", "mAP50_95")]
    rows.append(("Every other value in detector_test.json and error_model.json (per class, error rates, error model)",
                 "", "", outcome(not d["detector_test_differences"] and not d["error_model_differences"],
                                 "apart from the weights path, now repo-relative")))
    t = table(["Metric", "Committed", "Re-run", ""], rows)
    s = d["speed"]
    t2 = table(["Device", "Images", "Time per image (ms)"],
               [(dev.upper(), s[dev]["images"], f"{1000 * s[dev]['s_per_image']:.0f}") for dev in ("gpu", "cpu")])
    return t + "\n\nInference speed, one image at a time at 640 px:\n\n" + t2


def dashboard_table(r):
    return table(["Setup", "Page", "Loads without error", "What it shows"],
                 [(x["setup"], x["page"], "yes" if x["ok"] else "**no**", x["shows"]) for x in r["dashboard"]])


def sizes_table(r):
    return table(["Item", "Size"], [(k, f"{v:.1f} GB" if v >= 0.95 else f"{1000 * v:.0f} MB")
                                     for k, v in r["sizes_gb"].items()])


def second_laptop_tables(r):
    s = r["second_laptop"]
    t = s["llm_trial"]
    trial = table(["LLM trial", "Length", "Calls", "Failures", "p95 latency (s)"],
                  [("600 s trial, second laptop", f"{t['seconds']} s", t["calls"], t["failures"],
                    f"{t['latency_p95_s']:.2f}")])
    return "\n\n".join([table(["", ""], s["hardware"]), table(["What was run", "Result"], s["worked"]), trial,
                         table(["Gap found (a stranger would hit it)", "Fix"], s["gaps"])])


def build() -> dict:
    r = json.loads(RECORD.read_text())
    return {"repro_env": env_table(r), "repro_summary": summary_table(r), "repro_steps": steps_table(r),
            "repro_runs": runs_table(r), "repro_validation": validation_table(r),
            "repro_lanechange": lane_change_table(r), "repro_cityflow": cityflow_table(r),
            "repro_llm": llm_table(r), "repro_detector": detector_table(r),
            "repro_dashboard": dashboard_table(r), "repro_sizes": sizes_table(r),
            "repro_second": second_laptop_tables(r)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = DOC.read_text()
    new = render_blocks(doc, build(), str(DOC.relative_to(ROOT)))
    if args.check:
        ok = new == doc
        print("docs/reproducibility.md matches the fresh-clone record" if ok else
              "docs/reproducibility.md is out of date; run scripts/make_reproducibility.py")
        sys.exit(0 if ok else 1)
    DOC.write_text(new)
    print(f"Updated {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
