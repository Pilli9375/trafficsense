"""What the LLM controllers chose: replay each benchmark run from its decisions.jsonl and score
every decision against the phase pressures at that moment.

    python scripts/analyze_llm_decisions.py            # write outputs/llm_benchmark/decisions_analysis.json + doc table
    python scripts/analyze_llm_decisions.py --check    # exit 1 if docs/llm_benchmark.md is out of date

Replay: the scenario is rebuilt (same seed) and, at each logged decision, the logged phase is
requested; the simulator is deterministic, so the replay must end with the run's ATT exactly
(checked; the script stops otherwise). At every decision the MaxPressure pressures of the
allowed phases are computed from the simulator state, the same numbers prompt v2 shows (up to
a constant per intersection, see llm/prompt.py).

Per run, over successful calls:
  keep                 the LLM chose the current phase
  highest pressure     the chosen phase has the highest pressure among the allowed phases
  keep, other higher   kept the current phase although an allowed phase had higher pressure,
                       as a share of the calls where one had
These describe the decisions; they are not simulator metrics.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.control.maxpressure import phase_pressures
from trafficsense.sim.env import TrafficEnv

RUNS = Path("outputs/llm_benchmark/runs")
OUT = Path("outputs/llm_benchmark/decisions_analysis.json")
DOC = Path("docs/llm_benchmark.md")
ARM_ORDER = {"v1": 0, "v2": 1, "guided": 2}


def replay(cfg: dict, run_dir: Path) -> dict:
    s = json.loads((run_dir / "summary.json").read_text())
    pv = s["provenance"]
    decisions = [json.loads(line) for line in (run_dir / "decisions.jsonl").open(encoding="utf-8")]
    at = collections.defaultdict(list)
    for d in decisions:
        at[d["step"]].append(d)
    env = TrafficEnv(cfg, pv["scenario"], seed=pv["seed"])
    n = collections.Counter()
    for _ in range(pv["sim_steps"]):
        for d in at.pop(int(env.time), []):
            iid, cur = d["intersection"], d["current_phase"]
            if env.signals[iid].green_phase != cur or env.time_in_phase(iid) != d["time_in_phase"]:
                raise SystemExit(f"{run_dir.name}: replay diverged at t={d['step']} {iid}")
            pr = phase_pressures(env.intersection(iid), env.get_state(iid))
            allowed = {p: pr[p] for p in d["allowed"]}
            best = max(allowed.values())
            n["calls"] += 1
            if d["ok"]:
                n["ok"] += 1
                n["keep"] += d["phase"] == cur
                n["highest"] += allowed[d["phase"]] == best
                if cur in allowed and allowed[cur] < best:
                    n["other_higher"] += 1
                    n["keep_other_higher"] += d["phase"] == cur
            env.request_phase(iid, d["phase"])
        env.step()
    if at:
        raise SystemExit(f"{run_dir.name}: decisions after the end of the run")
    if env.eng.get_average_travel_time() != s["metrics"]["att"]:
        raise SystemExit(f"{run_dir.name}: replay ATT {env.eng.get_average_travel_time()} != run ATT "
                         f"{s['metrics']['att']}")
    return {"run": run_dir.name, "model": pv["model"], "controller": pv["controller"],
            "prompt": pv["controller_params"].get("prompt", "v1"), "calls": n["calls"], "ok": n["ok"],
            "keep_rate": n["keep"] / n["ok"], "highest_pressure_rate": n["highest"] / n["ok"],
            "keep_when_other_higher_rate": n["keep_other_higher"] / n["other_higher"] if n["other_higher"] else None,
            "replay_att_matches": True}


def analyse(root: Path) -> dict:
    cfg = load_config("configs/default.yaml")
    rows = []
    for p in sorted((root / RUNS).glob("*/decisions.jsonl")):
        rows.append(replay(cfg, p.parent))
    rows.sort(key=lambda r: (ARM_ORDER[r["prompt"]], r["model"]))
    return {"script": "scripts/analyze_llm_decisions.py", "runs": rows}


def table(a: dict) -> str:
    def pct(x):
        return "–" if x is None else f"{100 * x:.0f}%"
    out = ["| Prompt | Model | Successful calls | Kept current phase | Chose highest-pressure phase | "
           "Kept current although another had higher pressure |", "|---|---|---|---|---|---|"]
    for r in a["runs"]:
        out.append(f"| {r['prompt']} | `{r['model']}` | {r['ok']} | {pct(r['keep_rate'])} | "
                   f"{pct(r['highest_pressure_rate'])} | {pct(r['keep_when_other_higher_rate'])} |")
    return "\n".join(out)


def render(doc: str, body: str) -> str:
    begin, end = "<!-- BEGIN:llm_decisions -->", "<!-- END:llm_decisions -->"
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pat.search(doc):
        raise KeyError(f"Marker for llm_decisions missing in {DOC}")
    return pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = repo_root()
    if args.check:
        stored = json.loads((root / OUT).read_text())
        doc = (root / DOC).read_text()
        ok = render(doc, table(stored)) == doc and analyse(root)["runs"] == stored["runs"]
        print("decision analysis matches the runs and the doc" if ok else
              "decision analysis out of date; run scripts/analyze_llm_decisions.py")
        sys.exit(0 if ok else 1)
    a = analyse(root)
    (root / OUT).write_text(json.dumps(a, indent=1))
    (root / DOC).write_text(render((root / DOC).read_text(), table(a)))
    print(table(a))


if __name__ == "__main__":
    main()
