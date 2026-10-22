# TrafficSense — Claude Code Guide

Multi-agent traffic signal control for Indian urban roads: CityFlow simulation, LLM-based cooperative signal control (adapted from CoLLMLight, ICLR 2026) running on a local model via Ollama, a YOLOv8 perception layer, and a Streamlit dashboard. B.Tech capstone; it will be examined in a viva, so every number must be reproducible and honest.

## Ground rules (non-negotiable)

1. **No mock, fake, or random data anywhere in the results path.** Test fakes live only in `tests/` and are injected in code; they never run as a server on a real port, and nothing they produce is written to `outputs/`.
2. **Fail loudly.** If the LLM server is down, a response can't be parsed, a file is missing, or a config value is invalid, raise a clear error. Never silently fall back to a default phase or a placeholder value. Log every LLM failure with its count in the run summary.
3. **Every result file records where it came from:** controller name, model name (as reported by the server), provider, seed, scenario, sim length, git commit hash, timestamp, and for LLM runs: number of calls, failures, mean/p95 latency.
4. **No hardcoded paths.** All paths come from `configs/*.yaml` and are resolved relative to the repo root. No `C:\`, `/mnt/c`, `/home/<user>` anywhere.
5. **No made-up metrics.** Every metric is measured from the simulator. If something is an estimate or heuristic, it is named as one in code, output, and docs.
6. **Docs must match the data.** README and report numbers are generated from (or checked against) the files in `outputs/`.
7. Ask before deleting user data, rewriting git history, or changing the experiment design.

## Environment

- Everything runs inside **WSL2 Ubuntu 22.04, Python 3.10/3.11** (CityFlow does not build on Python 3.13: its bundled pybind11 is too old).
- Hardware: **GTX 1650 (4 GB VRAM)**, 16 GB RAM, Ryzen 5 4600H.
  - The LLM and YOLO cannot share the GPU at the same time. Don't run both at once.
  - `gemma3:4b` barely fits in 4 GB; benchmark before choosing the model.
  - YOLO training: yolov8n, batch ~8 at 640. GTX 16-series can produce NaN losses with AMP; if so set `amp=False`.
- CityFlow: build from source (`git clone https://github.com/cityflow-project/CityFlow && pip install .`).
- LLM: Ollama at `http://localhost:11434`. Use the native `/api/chat` endpoint with `format` (JSON schema) for structured output.

## Simulator facts (verified)

- CityFlow lane IDs are `{road_id}_{lane_index}`.
- Each intersection's `roadLinks[i]` has `startRoad`, `endRoad`, `type` (`go_straight` / `turn_left` / `turn_right`) and `laneLinks` (`startLaneIndex`, `endLaneIndex`).
- `trafficLight.lightphases[k].availableRoadLinks` lists indexes into `roadLinks`.
- In CoLLMLight's `Synthetic/4_4` roadnet, **phase 0 is a 5 s transition phase with right turns only**; the real green phases are 1–8. Never use phase 0 as a green phase. Detect transition phases from the roadnet rather than hardcoding.
- `set_tl_phase` switches instantly, so the controller wrapper must insert the transition (yellow) phase and enforce min/max green itself. Config must have `"rlTrafficLight": true`.
- `get_vehicles(include_waiting=False)` — the old code passed a non-existent keyword and throughput was always 0.
- Synthetic 4x4 uses a fixed flow file, so deterministic controllers (FixedTime, MaxPressure) give identical results across seeds. Seed variation matters for LLM sampling and for generated flows.

## Target repo layout

```
configs/                 # default.yaml + per-experiment overrides
data/external/           # downloaded datasets & CoLLMLight roadnets (gitignored)
data/scenarios/          # our generated scenarios (indian_2x2 roadnet + flows)
src/trafficsense/
  sim/                   # roadnet parsing, env wrapper, signal timing, metrics
  control/               # fixedtime, maxpressure, llm (cooperative / isolated)
  llm/                   # Ollama client, prompts, response schema
  perception/            # dataset prep, training, inference, perception-error model
  dashboard/             # Streamlit app (reads outputs/ only)
scripts/                 # CLI entry points (run_experiment.py, benchmark_llm.py, ...)
tests/                   # pytest
outputs/                 # results; one folder per run with summary.json + metrics.csv
```

Install as a package (`pyproject.toml`, `pip install -e .`) — no `sys.path.insert` hacks.

## Metrics (definitions)

- **ATT** – average travel time: `engine.get_average_travel_time()` at the end of the run.
- **Queue length** – mean over steps of waiting vehicles (speed < 0.1 m/s) on incoming lanes, per intersection and network-wide.
- **Waiting time** – per vehicle, seconds spent with speed < 0.1 m/s; averaged over vehicles.
- **Throughput** – vehicles that finished their trip.
- Default run length 3600 steps. Report mean ± std over seeds where seeds vary.

## Commands

```bash
pip install -e ".[dev]"
pytest -q
python scripts/run_experiment.py --config configs/default.yaml --controller maxpressure --scenario synthetic_4x4
python scripts/benchmark_llm.py --arm v2 --models qwen2.5:3b   # or --arm v2: every model of the arm
python scripts/run_full_experiments.py            # full experiments (resumable; --dry-run lists runs)
python scripts/run_model_size.py --bench          # exploratory model-size study (--full, --dry-run)
python scripts/probe_hosted.py --capabilities     # hosted (NVIDIA NIM) endpoint checks; key in gitignored .env
streamlit run src/trafficsense/dashboard/app.py
```

## Working style

- Small, focused commits per logical change.
- Write or update tests with each change; run `pytest` before saying a step is done.
- When a result looks surprising (e.g. MaxPressure loses to FixedTime), investigate and explain it before moving on. Don't tune until numbers look good.
- Explain decisions in plain language; the user wants the "why" first.
