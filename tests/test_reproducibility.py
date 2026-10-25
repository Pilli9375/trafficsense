"""docs/reproducibility.md is generated from outputs/reproducibility/fresh_clone.json (scripts/make_reproducibility.py)."""
import importlib.util
import json
import subprocess
import sys

from trafficsense.config import repo_root

ROOT = repo_root()


def load():
    spec = importlib.util.spec_from_file_location("make_reproducibility", ROOT / "scripts" / "make_reproducibility.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doc_matches_the_record():
    r = subprocess.run([sys.executable, "scripts/make_reproducibility.py", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_record_is_consistent():
    rec = json.loads((ROOT / "outputs/reproducibility/fresh_clone.json").read_text())
    off = [v for v in rec["validation"] if v["side"] == "ours" and not v["lane_change"]]
    # every default-profile file is either identical or was made with a setting that reproduces it exactly
    assert all(v["outcome"] == "identical" or v.get("rerun_with_that_setting_identical") for v in off)
    assert all(v["outcome"] in ("identical", "lane-change noise") for v in rec["validation"] if v["lane_change"])
    assert rec["facts"]["det_runs"] == len(rec["deterministic_runs"])
    assert rec["facts"]["det_runs_identical"] == sum(x["identical"] for x in rec["deterministic_runs"])
    assert not rec["llm"]["provenance_fields_missing"]


def test_summary_counts_add_up():
    mod = load()
    rec = json.loads((ROOT / "outputs/reproducibility/fresh_clone.json").read_text())
    row = [l for l in mod.summary_table(rec).splitlines() if "lane changing off" in l][0]
    n_files, text = row.split(" | ")[1], row.split(" | ")[2]
    n = int(n_files.split()[0])
    parts = [int(w) for w in text.replace(";", "").split() if w.isdigit()]
    assert sum(parts) == n, row
