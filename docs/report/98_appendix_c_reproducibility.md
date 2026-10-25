# Reproducibility {#sec:app-repro}

## How the results are kept honest

* **Provenance in every run.** Each run writes a folder `<time>_<scenario>_<controller>_s<seed>/`
  with `summary.json` (metrics plus controller, parameters, model as reported by the server,
  provider, seed, scenario, run length, git commit and whether the tree was clean, time, and for
  LLM runs the calls, failures by type and latency), `metrics.csv` (per-second metrics) and, for LLM
  runs, `decisions.jsonl` (every decision with the raw answer).
* **Generated documents.** Every table in the project's documents is generated from the result
  files by a script, and each script has a `--check` mode that fails if the document and the data
  disagree.
* **This report.** Every table in this report is generated from the result files or copied from a
  checked document by `scripts/make_report.py`. Every other number taken from the data carries an
  invisible tag naming its source (a value in a result file, or a cell of a checked table), and
  `make_report.py --check` fails if any shown number differs from its source at the precision
  shown, or if the text contains an untagged number that is not a year, a reference, a small count
  or a product name. The figures are drawn from the result files, and the values each one plots are
  stored beside it and checked. `scripts/build_report.py` refuses to build the Word and PDF files
  unless that check passes, and then checks that the figure, table and section numbers in the PDF
  equal those in the Word file.

## Steps

The project runs in WSL2 Ubuntu 22.04 with Python 3.10. The commands below are run from the
repository root in its virtual environment; the batch scripts are resumable and skip finished runs.

```bash
# environment
python3.10 -m venv .venv && source .venv/bin/activate
git clone https://github.com/cityflow-project/CityFlow.git ../CityFlow && pip install ../CityFlow
pip install -e ".[dev,dashboard,perception]"
scripts/fetch_collmlight_data.sh                      # CoLLMLight roadnets and flows
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b && ollama pull gemma4:e4b && ollama pull qwen2.5:3b

# Chapter 4: validation, scenario, baselines
python scripts/validation/run_collmlight_baseline.py --model Fixedtime --dataset synthetic_4x4 --seed 0
python scripts/validation/run_matched.py --scenario synthetic_4x4 --profile replica_fixedtime --engine-seed 47
python scripts/validation/make_tables.py
python scripts/generate_indian_roadnet.py
python scripts/calibrate_indian_demand.py --rates 1000 2000 3000 4000 4500 4750 5000 5250 5500 5750 6000 7000 8000 10000 12000 14000
python scripts/generate_indian_flow.py --level all --seed 0 1 2
python scripts/tune_maxpressure.py && python scripts/tune_maxpressure_min_green.py
python scripts/run_indian_experiments.py && python scripts/make_indian_tables.py

# Chapter 7: LLM benchmark, full experiments, ambulances
python scripts/benchmark_llm.py --arm v3 && python scripts/benchmark_llm.py --arm hybrid_v3
python scripts/benchmark_llm.py --arm guarded_v3
python scripts/generate_indian_flow.py --level all --seed 0 1 2 --emergency
python scripts/generate_indian_flow.py --level peak --seed 3 4 && python scripts/generate_indian_flow.py --level peak --seed 3 4 --emergency
python scripts/run_full_experiments.py && python scripts/make_results.py

# Chapter 5: detector (IDD downloaded separately, linked at data/external/idd_detection)
python scripts/prepare_idd.py && python scripts/resize_idd.py
python scripts/train_detector.py --full
python scripts/eval_detector.py --stage val && python scripts/eval_detector.py --stage test
python scripts/make_perception_results.py

# Chapter 7: camera errors and the exploratory model-size study
python scripts/run_camera_error.py && python scripts/run_camera_decomposition.py
python scripts/make_camera_error.py
python scripts/run_model_size.py --bench && python scripts/run_model_size.py --full
python scripts/make_model_size.py

# This report
python scripts/make_report.py && python scripts/build_report.py

# Checks
pytest -q
for s in validation/make_tables make_indian_tables make_baseline_tables make_results \
         make_camera_error make_model_size make_perception_results make_report; do
  python scripts/$s.py --check
done
python scripts/benchmark_llm.py --check
```

LLM runs are not bit-for-bit repeatable on a GPU (@sec:seeds): a re-run gives slightly different
numbers. The logged decisions reproduce each run exactly, and the dashboard's replays are kept only
when they do. The hosted model of the model-size study needs an API key in a git-ignored `.env`
file and is subject to the provider's rate limits.

## Data not in the repository

IDD is downloaded from its authors after registration and is not redistributed; the detector
weights, training runs, the dashboard's replays and its sample clip are kept outside the
repository and reached through git-ignored links set in `configs/default.yaml`. CoLLMLight's
roadnets and flows are downloaded by `scripts/fetch_collmlight_data.sh`.
