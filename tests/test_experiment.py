import csv
import json

from trafficsense.experiment import run_experiment


def test_run_writes_summary_and_metrics(cfg, synthetic_4x4, tmp_path):
    out = run_experiment(cfg, "synthetic_4x4", "maxpressure", steps=60, seed=3, out_root=tmp_path)
    assert out.name.endswith("_synthetic_4x4_maxpressure_s3")
    s = json.loads((out / "summary.json").read_text())
    prov = s["provenance"]
    for key in ("controller", "model", "provider", "seed", "scenario", "sim_steps",
                "git_commit", "timestamp"):
        assert key in prov
    assert prov["seed"] == 3 and prov["sim_steps"] == 60 and len(prov["git_commit"]) == 40
    assert s["metrics"]["steps"] == 60
    with (out / "metrics.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 60 * 16
