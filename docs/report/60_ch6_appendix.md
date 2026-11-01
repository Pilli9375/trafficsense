# Appendix {#sec:appendix}

The appendix gives what is needed to check or repeat the work: the configuration in force
(@sec:app-config), the prompts (@sec:app-prompts), the reproduction steps (@sec:app-repro), the
full result tables behind the summaries of Chapter 4 (@sec:app-tables), the abbreviations
(@sec:abbrev) and listings of the key source files (@sec:app-code).

## Configuration {#sec:app-config}

Every setting used in the experiments is read from YAML files in `configs/`; no setting is typed
into code. The listings below are copied from the files by the report's build script, so they are
the settings actually in force.

### Main Configuration

Excerpt of `configs/default.yaml`:

<!-- BEGIN:code_config -->
```yaml
sim:
  steps: 3600          # default run length (CLAUDE.md)
  interval: 1.0        # seconds per simulator step
  seed: 0
  threads: 1
  lane_change: false   # CityFlow laneChange; CoLLMLight runs with true
signal:
  min_green: 10        # s
  max_green: 60        # s
emergency:
  detection_range_m: 150   # ASSUMPTION: an ambulance on an incoming lane within this distance of
                           # the stop line is detected (lanes are 176-188 m long; at 12.5 m/s an
                           # ambulance covers 150 m in 12 s, enough for a 5 s decision step plus
                           # the 5 s transition)
controllers:  # excerpt
  fixedtime:
    green_time: 30     # s per green phase
    phases: paired     # the 4 opposing-approach phases that serve every non-right movement once
  fixedtime_webster:      # 4 paired phases; cycle and splits by Webster's method (control/webster.py)
    cycle_min: 60          # s
    cycle_max: 180         # s
    demand_window_s: 3600  # lane demand = vehicles in the flow file starting in [0, window)
    measurement_reps: 30   # random-order queues averaged for saturation flow / start-up loss
    measurement_seed: 0    # seed of those queue orders (not the run seed)
  maxpressure:
    decision_interval: 5   # s between re-evaluations
    min_green: 15          # s, controller's own minimum green (>= signal.min_green).
                           # Chosen by scripts/tune_maxpressure_min_green.py (docs/baselines.md)
    phases: all            # all | paired (CoLLMLight's MaxPressure uses the 4 paired phases)
    tie_break: keep_current  # keep_current | lowest_index (CoLLMLight: np.argmax -> lowest)
  preemption_mp:           # MaxPressure + rule-based ambulance preemption (control/preemption.py)
    decision_interval: 5   # same timing as the default MaxPressure and the LLM benchmark
    min_green: 15
    tie_break: keep_current
  llm_guided_mp_v3:
    mode: cooperative
    prompt: guided_v3
    options: 2
    tie_break: keep_current
  llm_guarded_mp:          # llm_guided_mp_v3 + guard: the LLM's phase is applied only if its pressure
    mode: cooperative      # >= 0.8 x the top phase's (control/guided.py), else MaxPressure's choice
    prompt: guided_v3
    options: 2
    tie_break: keep_current
    guard_ratio: 0.8
llm:
  provider: ollama
  host: http://localhost:11434
  endpoint: /api/chat  # native endpoint, structured output via `format` (JSON schema)
  model: null          # chosen after scripts/benchmark_llm.py; must be set for LLM runs
  timeout_s: 60        # per call; a timeout counts as a failed decision
  temperature: 0
  seed: 0              # LLM sampling seed, fixed (recorded in every summary.json)
  num_ctx: 2048        # context window (tokens). Prompts are ~650; at 4096 llama3.2:3b no longer fits
                       # fully in the GTX 1650's VRAM. A prompt that could be truncated raises.
  num_predict: 128     # cap on generated tokens; the JSON answer needs about 40
  keep_alive: 30m      # keep the model loaded between calls
  decision_interval: null  # s; decided after scripts/benchmark_llm.py
  min_green: null          # s; LLM controller's own min green (>= signal.min_green)
  max_consecutive_failures: 20  # this many failed calls in a row stops the run with an error
```
<!-- END:code_config -->

### Indian 2x2 Scenario

Excerpt of `configs/scenarios/indian_2x2.yaml`; the vehicle-type parameters are given in @tbl:mix.

<!-- BEGIN:code_scenario -->
```yaml
roadnet:
  file: data/scenarios/indian_2x2/roadnet.json
  rows: 2
  cols: 2
  spacing_m: 200            # between intersections (Phase 2 spec)
  boundary_road_m: 200      # entry/exit roads to the network edge (ASSUMPTION: same as spacing)
  lane_width_m: 3.0         # Phase 2 spec (~3.0 m)
  lanes:                    # per direction, one lane per turn (CityFlow generator layout)
    left: 1
    straight: 1
    right: 1
  lane_max_speed_mps: 12.5  # 45 km/h; Phase 2 spec range 11-13 m/s (ASSUMPTION within it)
  intersection_width_m: 12  # distance from the centre to the stop line (ASSUMPTION, see doc)
  # Phases come from the generator: phase 0 = 5 s transition (right turns only), phases 1-8 green.
turn_probabilities:       # ASSUMPTION
  go_straight: 0.60
  turn_right: 0.25        # Indian free left
  turn_left: 0.15         # Indian right turn
entry_weights:            # ASSUMPTION
  W: 1.0
  E: 1.0
  N: 0.6
  S: 0.6
demand_levels:
  offpeak:
    veh_per_hour: 2375
  peak:
    veh_per_hour: 4750
emergency:
  vehicle_type: ambulance
  veh_per_hour: 6           # ASSUMPTION (Phase 3b spec "~6/hour", whole 2x2 network, both levels)
  seed_offset: 1000         # ASSUMPTION: any fixed offset; ambulance RNG seed = flow seed + 1000
```
<!-- END:code_scenario -->

## Prompts {#sec:app-prompts}

The system prompts below are rendered by the controllers' own code (`src/trafficsense/llm/prompt.py`)
with the timing used in the experiments. The LLM must answer with JSON that matches a schema
listing the allowed phase numbers; the reason is checked for length after parsing.

### Prompt v1 (First Round)

<!-- BEGIN:code_prompt_v1 -->
```text
You control the traffic signal of one intersection in a city road network with mixed Indian traffic (two-wheelers, auto-rickshaws, cars, buses, trucks).
At each decision you choose which green phase to show next. Goal: keep vehicles moving and queues short across the whole network, so total travel time is low.
Rules of the signal:
- Choosing the current phase keeps it green. Choosing another phase first shows a 5 s transition in which only free turns move, so switching too often wastes green time.
- A green phase cannot be ended before 15 s and is ended automatically at 60 s.
Data you get for each movement: queue = stopped vehicles waiting at the stop line; moving = vehicles driving towards the stop line; downstream = stopped vehicles on the exit road (a full exit road blocks the movement).
Answer with JSON only: {"phase": <one of the allowed phase ids>, "reason": "<at most 25 words>"}.
```
<!-- END:code_prompt_v1 -->

The v1 user message listed, for every phase, each movement's queue, moving and downstream counts,
the vehicle types per approach, and the neighbours.

### Prompt v2

<!-- BEGIN:code_prompt_v2 -->
```text
You pick the next green phase for one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
queue = stopped vehicles a phase serves; pressure = queue minus stopped vehicles on their exit roads.
Reply JSON: {"phase": <allowed id>, "reason": "<at most 15 words>"}
```
<!-- END:code_prompt_v2 -->

### Prompt v3 (v2 with Two Lines Changed)

<!-- BEGIN:code_prompt_v3 -->
```text
You pick the next green phase for one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
queue = stopped vehicles a phase serves; pressure = vehicles waiting to go minus vehicles already stopped on their exit roads. HIGHER pressure = the phase needs green MORE.
Reply JSON: {"phase": <allowed id>, "reason": "<short reason>"}. The reason must be 15 words or fewer.
```
<!-- END:code_prompt_v3 -->

### Guided Prompt (Hybrid Arm)

<!-- BEGIN:code_prompt_guided -->
```text
You help a MaxPressure controller run one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = stopped vehicles a phase serves minus stopped vehicles on their exit roads; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
Reply JSON: {"phase": <offered id>, "reason": "<at most 15 words>"}
```
<!-- END:code_prompt_guided -->

### Guided Prompt v3 (hybrid_v3 and the Pre-Registered Guarded Arm)

<!-- BEGIN:code_prompt_guided_v3 -->
```text
You help a MaxPressure controller run one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = vehicles waiting to go minus vehicles already stopped on their exit roads; HIGHER pressure = the phase needs green MORE; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
Reply JSON: {"phase": <offered id>, "reason": "<short reason>"}. The reason must be 15 words or fewer.
```
<!-- END:code_prompt_guided_v3 -->

In the emergency scenarios one sentence is added:

<!-- BEGIN:code_prompt_guided_v3_amb -->
```text
You help a MaxPressure controller run one traffic signal in an Indian city. Goal: short queues and low travel time network-wide.
MaxPressure ranks phases by pressure = vehicles waiting to go minus vehicles already stopped on their exit roads; HIGHER pressure = the phase needs green MORE; queue = stopped vehicles a phase serves. Choose one of the offered phases; neighbour data may help.
Changing phase starts a 5 s transition in which only free turns move. A green lasts 15 to 60 s.
Ambulances, if listed, must get through quickly: give green to a phase that serves them.
Reply JSON: {"phase": <offered id>, "reason": "<short reason>"}. The reason must be 15 words or fewer.
```
<!-- END:code_prompt_guided_v3_amb -->

### An Example User Message

The user message of the guided prompts at a real simulator state:
<!-- BEGIN:code_example_time -->
Indian 2x2 peak with ambulances, seed 2, `intersection_2_2` at t = 265 s, under MaxPressure control up to that moment. MaxPressure ranks phase 2 (S+N straight) first, but an ambulance 70 m from the stop line is served by phases 6, 1, so a phase that serves it is among the options.
<!-- END:code_example_time -->

<!-- BEGIN:code_prompt_user -->
```text
Phase 1 (W+E straight) green for 15 s.
Options, best MaxPressure rank first (phase: pressure, queue):
2 S+N straight: 3, 4
3 W+E cross-turn: 3, 4
6 E only: -2, 3
1 W+E straight (keep current): -4, 0
Ambulances within 150 m:
E straight, 70 m from the stop line; served by phase 6, 1
Neighbours:
W: phase 1 (W+E straight); 9 stopped toward us, 7 on green; 4 stopped on our road to it
S: phase 5 (W only); 0 stopped toward us, 0 on green; 1 stopped on our road to it
```
<!-- END:code_prompt_user -->

### A Logged Decision

One decision of the pre-registered arm, as logged in `decisions.jsonl` (selected keys): the first
decision of its emergency run (seed 0) in which the LLM's choice differed from MaxPressure's and
served an ambulance. The model's reason still mentions "low pressure", but its choice gives the
ambulance green; because that phase serves a listed ambulance, the guard does not apply. The
guard's pressures are those shown in the prompt, which leave out the free turns.

<!-- BEGIN:code_decision -->
```json
{
 "step": 1980,
 "intersection": "intersection_1_2",
 "current_phase": 5,
 "time_in_phase": 15,
 "allowed": [1, 2, 5, 8],
 "mp_ranking": [1, 2, 8, 4, 6, 7, 5, 3],
 "mp_choice": 1,
 "ambulances": [{"vehicle": "flow_4668_0", "approach": "N", "distance_m": 44.2, "movement": "N cross-turn", "phases": [8, 4]}],
 "latency_s": 1.42,
 "prompt_tokens": 340,
 "server_model": "llama3.2:3b",
 "raw": "{\"phase\": 8, \"reason\": \"Low pressure, serving ambulances within 150m\"}",
 "llm_phase": 8,
 "guard_threshold": 2.4,
 "guard_llm_pressure": 3,
 "guard_override": false,
 "guard_ambulance_exempt": true,
 "phase": 8
}
```
<!-- END:code_decision -->

## Reproducibility {#sec:app-repro}

### How the Results Are Kept Honest

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
  unless that check passes; the PDF is LibreOffice's conversion of the Word file itself, and
  `scripts/check_report_format.py` then checks the Word file against the college format.

### Steps

The project runs in WSL2 Ubuntu 22.04 with Python 3.10. The commands below are run from the
repository root in its virtual environment; the batch scripts are resumable and skip finished runs.

```bash
# environment (exact versions: requirements-lock.txt)
python3.10 -m venv .venv && source .venv/bin/activate
git clone https://github.com/cityflow-project/CityFlow.git ../CityFlow
git -C ../CityFlow checkout 81ee0f4 && pip install ../CityFlow
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
pip install -e ".[dev,dashboard,perception]" -c requirements-lock.txt
scripts/fetch_collmlight_data.sh                      # CoLLMLight roadnets and flows
curl -fsSL https://ollama.com/install.sh | sh         # or Ollama for Windows (README)
ollama pull llama3.2:3b && ollama pull gemma4:e4b && ollama pull qwen2.5:3b

# Sections 2.2.1, 2.2.2 and 4.1: validation, scenario, baselines
python scripts/validation/run_collmlight_baseline.py --model Fixedtime --dataset synthetic_4x4 --seed 0
python scripts/validation/run_matched.py --scenario synthetic_4x4 --profile replica_fixedtime --engine-seed 47
python scripts/validation/make_tables.py
python scripts/generate_indian_roadnet.py
python scripts/calibrate_indian_demand.py --rates 1000 2000 3000 4000 4500 4750 5000 5250 5500 5750 6000 7000 8000 10000 12000 14000
python scripts/generate_indian_flow.py --level all --seed 0 1 2
python scripts/tune_maxpressure.py && python scripts/tune_maxpressure_min_green.py
python scripts/run_indian_experiments.py && python scripts/make_indian_tables.py

# Sections 4.2 to 4.4: LLM benchmark, full experiments, ambulances
python scripts/benchmark_llm.py --arm v3 && python scripts/benchmark_llm.py --arm hybrid_v3
python scripts/benchmark_llm.py --arm guarded_v3
python scripts/generate_indian_flow.py --level all --seed 0 1 2 --emergency
python scripts/generate_indian_flow.py --level peak --seed 3 4 && python scripts/generate_indian_flow.py --level peak --seed 3 4 --emergency
python scripts/run_full_experiments.py && python scripts/make_results.py

# Sections 2.2.3 and 4.7: detector (IDD downloaded separately, linked at data/external/idd_detection)
python scripts/prepare_idd.py && python scripts/resize_idd.py
python scripts/train_detector.py --full
python scripts/eval_detector.py --stage val && python scripts/eval_detector.py --stage test
python scripts/make_perception_results.py

# Sections 4.5 and 4.6: camera errors and the exploratory model-size study
python scripts/run_camera_error.py && python scripts/run_camera_decomposition.py
python scripts/make_camera_error.py
python scripts/run_model_size.py --bench && python scripts/run_model_size.py --full
python scripts/make_model_size.py

# Dashboard replays, from the committed runs
python scripts/build_replays.py

# This report
python scripts/make_report.py && python scripts/build_report.py

# Checks
pytest -q
for s in validation/make_tables make_indian_tables make_baseline_tables make_results \
         make_camera_error make_model_size make_perception_results make_reproducibility make_report; do
  python scripts/$s.py --check
done
python scripts/benchmark_llm.py --check
```

### A Check from a Fresh Clone

To test these steps, the repository was cloned from GitHub into an empty folder and set up from
the README alone, and every deterministic result was run again
(`docs/reproducibility.md`, generated from `outputs/reproducibility/fresh_clone.json`). All
42<!--=r.det_runs_identical--> of the 42<!--=r.det_runs--> runs of the fixed-time, Webster, MaxPressure and preemption
controllers came out identical in every metric, as did the detector's test-split evaluation
(mAP50 0.563<!--=r.map50-->, mAP50-95 0.375<!--=r.map5095-->, and the whole camera error model), the IDD label
conversion and the dashboard's replays. A 600<!--=b.steps--> s run of the pre-registered LLM arm repeated
the committed run exactly, in all 121<!--=r.llm_identical_answers--> answers. The check found gaps
in the setup instructions, not in the results: tests and checks that failed in a clean
install, an evaluation script that read an absolute path, a PyTorch build the GPU driver could
not use, and no pinned versions. Each was fixed, and the affected steps were run again in the
same clone.

The one part that did not repeat exactly was CityFlow with lane changing on, which only the
validation's matched runs use: the same run, repeated, gives a slightly different average
travel time, in CoLLMLight's code as in ours, while throughput and their queue length never
changed (@sec:validation).

LLM runs are not guaranteed to be bit-for-bit repeatable on a GPU (@sec:seeds): a re-run can
give slightly different numbers. The logged decisions reproduce each run exactly, and the dashboard's replays are kept only
when they do. The hosted model of the model-size study needs an API key in a git-ignored `.env`
file and is subject to the provider's rate limits.

### Data Not in the Repository

IDD is downloaded from its authors after registration and is not redistributed; the detector
weights, training runs, the dashboard's replays and its sample clip are kept outside the
repository and reached through git-ignored links set in `configs/default.yaml`. CoLLMLight's
roadnets and flows are downloaded by `scripts/fetch_collmlight_data.sh`.

## Full Tables {#sec:app-tables}

### Every Baseline Run on the Indian Network

::: {#tbl:app-per-seed short="Every baseline run on the Indian 2x2 network"}
<!-- BEGIN:tab_app_per_seed -->
| Level | Controller | Seed | ATT (s) | Queue / int. | Waiting (s) | Throughput | Waiting to enter |
|------------|----------------------|--------:|---------:|---------:|-----------:|-------------:|-----------:|
| offpeak | FixedTime, 4 paired phases, 30 s | 0 | 121.6 | 10.44 | 64.1 | 2285 | 0 |
| offpeak | FixedTime, 4 paired phases, 30 s | 1 | 121.2 | 10.53 | 63.1 | 2325 | 0 |
| offpeak | FixedTime, 4 paired phases, 30 s | 2 | 121.6 | 10.77 | 63.9 | 2338 | 0 |
| offpeak | FixedTime, all 8 phases, 30 s | 0 | 128.3 | 11.49 | 70.6 | 2267 | 0 |
| offpeak | FixedTime, all 8 phases, 30 s | 1 | 128.8 | 11.82 | 70.9 | 2304 | 0 |
| offpeak | FixedTime, all 8 phases, 30 s | 2 | 130.7 | 12.33 | 73.1 | 2322 | 0 |
| offpeak | FixedTime, 4 paired phases, Webster plan | 0 | 104.4 | 7.33 | 45.0 | 2280 | 0 |
| offpeak | FixedTime, 4 paired phases, Webster plan | 1 | 100.7 | 6.85 | 41.1 | 2329 | 0 |
| offpeak | FixedTime, 4 paired phases, Webster plan | 2 | 96.1 | 6.28 | 37.2 | 2350 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 0 | 87.2 | 4.72 | 29.0 | 2291 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 1 | 88.2 | 4.94 | 29.6 | 2347 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 2 | 89.1 | 5.17 | 30.7 | 2358 | 0 |
| offpeak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 0 | 81.0 | 3.73 | 22.9 | 2289 | 0 |
| offpeak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 1 | 81.6 | 3.82 | 22.9 | 2345 | 0 |
| offpeak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 2 | 81.3 | 3.86 | 22.9 | 2362 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 0 | 81.2 | 3.72 | 22.9 | 2290 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 1 | 82.2 | 3.92 | 23.5 | 2345 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 2 | 82.7 | 4.07 | 24.1 | 2361 | 0 |
| peak | FixedTime, 4 paired phases, 30 s | 0 | 291.2 | 43.64 | 144.8 | 4061 | 325 |
| peak | FixedTime, 4 paired phases, 30 s | 1 | 275.8 | 44.54 | 142.3 | 4238 | 285 |
| peak | FixedTime, 4 paired phases, 30 s | 2 | 272.7 | 45.14 | 145.1 | 4198 | 313 |
| peak | FixedTime, all 8 phases, 30 s | 0 | 300.3 | 46.98 | 156.2 | 4016 | 335 |
| peak | FixedTime, all 8 phases, 30 s | 1 | 288.7 | 47.83 | 153.6 | 4188 | 311 |
| peak | FixedTime, all 8 phases, 30 s | 2 | 286.7 | 48.19 | 156.1 | 4135 | 347 |
| peak | FixedTime, 4 paired phases, Webster plan | 0 | 118.3 | 18.47 | 57.0 | 4477 | 1 |
| peak | FixedTime, 4 paired phases, Webster plan | 1 | 119.6 | 19.44 | 58.4 | 4637 | 0 |
| peak | FixedTime, 4 paired phases, Webster plan | 2 | 111.1 | 16.91 | 50.8 | 4617 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 0 | 116.0 | 17.53 | 54.1 | 4501 | 1 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 1 | 116.1 | 18.16 | 54.6 | 4634 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 2 | 114.5 | 17.80 | 53.5 | 4594 | 0 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 0 | 152.0 | 28.47 | 87.9 | 4410 | 1 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 1 | 122.2 | 19.78 | 59.4 | 4634 | 0 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 2 | 127.4 | 21.48 | 64.6 | 4575 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 0 | 162.9 | 31.69 | 97.8 | 4366 | 1 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 1 | 136.3 | 24.18 | 72.6 | 4610 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 2 | 127.9 | 21.65 | 65.1 | 4572 | 0 |
<!-- END:tab_app_per_seed -->

: Every baseline run on the Indian 2x2 network (seeds 0–2), including the two MaxPressure
settings not chosen by the tuning.
:::

### MaxPressure Decision-Interval Sweep

::: {#tbl:app-mp-selection short="First MaxPressure tuning sweep (decision interval)"}
<!-- BEGIN:tab_app_mp_selection -->
| Interval | Rank: jinan_3x4 | Rank: hangzhou_4x4 | Rank: indian_2x2_offpeak | Rank: indian_2x2_peak | Mean rank | Mean ATT / best |
|------------|------------:|---------------:|--------------------:|------------------:|--------:|---------:|
| 5 s | 1 | 1 | 2 | 5 | 2.25 | 1.059 |
| 10 s | 3 | 3 | 3 | 2 | 2.75 | 1.028 |
| 15 s | 2 | 2 | 1 | 4 | 2.25 | 1.042 |
| 20 s | 4 | 4 | 4 | 1 | 3.25 | 1.045 |
| 30 s | 5 | 5 | 5 | 3 | 4.50 | 1.158 |
<!-- END:tab_app_mp_selection -->

: First tuning sweep (decision interval, minimum green 10 s): rank of each interval per scenario.
The 5 s and 15<!--=docs/baselines.md | mp_selection | chosen | Interval--> s settings tie on mean rank; the tie-break chose
15<!--=docs/baselines.md | mp_selection | chosen | Interval--> s, which the minimum-green sweep
(@tbl:mg-selection) later replaced.
:::

### Validation Against CoLLMLight

::: {#tbl:app-crosscheck short="Validation runs scored with CoLLMLight's metrics"}
<!-- BEGIN:tab_app_crosscheck -->
| Dataset | Run | ATT (their def.) | Throughput (their def.) | Queue (their def.) | Waiting (their def.) | CityFlow ATT | Engine seed |
|-------------|---------------------|---------:|------------:|---------:|----------:|-----------:|---------:|
| Synthetic 4x4 | CoLLMLight code: FixedTime | 1192.5 | 751 | 467.3 | 1215.6 | 1612.0 | 47 |
| Synthetic 4x4 | Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1192.5 | 751 | 467.3 | 1215.6 | 1612.0 | 47 |
| Synthetic 4x4 | CoLLMLight code: MaxPressure | 683.1 | 2505 | 468.4 | 84.8 | 1263.3 | 47 |
| Synthetic 4x4 | Ours, MaxPressure matched to theirs | 683.1 | 2505 | 468.4 | 84.8 | 1263.3 | 47 |
| Jinan 3x4 | CoLLMLight code: FixedTime | 1239.3 | 1786 | 1338.6 | 920.3 | 1258.0 | 47 |
| Jinan 3x4 | Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1239.3 | 1786 | 1338.6 | 920.3 | 1258.0 | 47 |
| Jinan 3x4 | CoLLMLight code: MaxPressure | 273.2 | 4187 | 106.6 | 38.2 | 317.8 | 47 |
| Jinan 3x4 | Ours, MaxPressure matched to theirs | 273.2 | 4187 | 106.6 | 38.2 | 317.8 | 47 |
| Hangzhou 4x4 | CoLLMLight code: FixedTime | 1002.8 | 1526 | 694.5 | 827.5 | 1054.7 | 47 |
| Hangzhou 4x4 | Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1002.8 | 1526 | 694.5 | 827.5 | 1054.7 | 47 |
| Hangzhou 4x4 | CoLLMLight code: MaxPressure | 325.3 | 2751 | 69.0 | 49.6 | 365.7 | 47 |
| Hangzhou 4x4 | Ours, MaxPressure matched to theirs | 325.3 | 2751 | 69.0 | 49.6 | 365.7 | 47 |
<!-- END:tab_app_crosscheck -->

: Validation runs scored with CoLLMLight's metric definitions: their code against ours, same
settings and CityFlow seed.
:::

### What the Models Chose in the Benchmark

::: {#tbl:app-bench-full short="Benchmark decisions replayed from the logs"}
<!-- BEGIN:tab_app_bench_full -->
| Arm (prompt) | Model | Successful calls | Kept current phase | Chose highest-pressure phase | Chose lowest-pressure phase | Kept current although another had higher pressure |
|-------------------|-----------------|-----------:|---------:|---------------:|---------------:|---------:|
| v1 (v1) | `gemma3:4b` | 333 | 86% | 4% | 51% | 95% |
| v1 (v1) | `gemma4:e4b` | 159 | 35% | 9% | 29% | 34% |
| v1 (v1) | `llama3.2:3b` | 270 | 77% | 2% | 34% | 84% |
| v1 (v1) | `qwen2.5:3b` | 159 | 34% | 18% | 25% | 34% |
| v2 (v2) | `gemma4:e4b` | 120 | 0% | 40% | 9% | 0% |
| v2 (v2) | `llama3.2:3b` | 350 | 89% | 6% | 48% | 99% |
| v2 (v2) | `qwen2.5:3b` | 251 | 88% | 6% | 49% | 100% |
| hybrid (guided) | `gemma4:e4b` | 283 | 78% | 18% | 83% | 84% |
| hybrid (guided) | `llama3.2:3b` | 286 | 79% | 4% | 86% | 86% |
| hybrid (guided) | `qwen2.5:3b` | 221 | 78% | 25% | 77% | 80% |
| v3 (v3) | `gemma4:e4b` | 122 | 4% | 57% | 9% | 3% |
| v3 (v3) | `llama3.2:3b` | 350 | 88% | 9% | 50% | 99% |
| v3 (v3) | `qwen2.5:3b` | 355 | 89% | 5% | 48% | 100% |
| hybrid_v3 (guided_v3) | `gemma4:e4b` | 151 | 28% | 78% | 22% | 23% |
| hybrid_v3 (guided_v3) | `llama3.2:3b` | 299 | 81% | 5% | 90% | 90% |
| hybrid_v3 (guided_v3) | `qwen2.5:3b` | 252 | 82% | 20% | 81% | 86% |
| guarded_v3 (guided_v3) | `gemma4:e4b` | 127 | 17% | 88% | 9% | 9% |
| guarded_v3 (guided_v3) | `llama3.2:3b` | 121 | 66% | 13% | 71% | 70% |
| guarded_v3 (guided_v3) | `qwen2.5:3b` | 114 | 75% | 26% | 72% | 72% |
<!-- END:tab_app_bench_full -->

: Benchmark decisions replayed from the logs: how often each model kept the current phase and chose
the highest- or lowest-pressure option. Pressures are MaxPressure's at the moment of each decision.
:::

### LLM Arm Under Camera Errors

::: {#tbl:app-camera-llm}
<!-- BEGIN:tab_app_camera_llm -->
| scenario | level | LLM calls | failures | guard overrides | disagrees with MP | mean latency (s) |
|---------------|--------------|----------:|-------------:|--------------:|--------------:|------------:|
| Off-peak | perfect | 2177 | 0 | 81.2% | 91.5% | 1.02 |
|  | junction | 2195 | 0 | 85.2% | 93.1% | 1.00 |
|  | crowded | 2189 | 0 | 82.5% | 92.9% | 1.00 |
| Peak | perfect | 2167 | 0 | 82.8% | 92.8% | 0.99 |
|  | junction | 2174 | 0 | 86.1% | 92.4% | 0.99 |
|  | crowded | 2175 | 0 | 85.1% | 92.6% | 0.99 |
| Emergency | perfect | 3632 | 0 | 76.3% | 86.9% | 1.03 |
|  | junction | 3646 | 0 | 78.8% | 87.8% | 1.03 |
<!-- END:tab_app_camera_llm -->

: The pre-registered LLM arm's decisions at each camera level.
:::

### Hosted Model Runs (Exploratory)

::: {#tbl:app-hosted short="Every run of the hosted model (exploratory)"}
<!-- BEGIN:tab_app_hosted -->
| Started (IST) | Run | Calls | Calls that needed retries | Failed calls → MaxPressure's choice applied | Wall time (min) |
|------------------|------------------------|---------:|------------:|------------------------|---------:|
| 2026-10-22 12:33 | indian_2x2_peak s0 | 128 | 0 (0%) | 0 (0.0%) | 5 |
| 2026-10-23 10:23 | indian_2x2_peak s0 | 736 | 286 (39%) | 11 (1.5%): retries_exhausted 10, timeout 1 | 121 |
| 2026-10-23 12:22 | indian_2x2_peak s1 | 734 | 351 (48%) | 12 (1.6%): retries_exhausted 11, timeout 1 | 135 |
| 2026-10-23 14:36 | indian_2x2_peak s2 | 735 | 417 (57%) | 16 (2.2%): retries_exhausted 16 | 150 |
| 2026-10-23 17:07 | indian_2x2_peak_amb s0 | 733 | 415 (57%) | 15 (2.0%): retries_exhausted 15 | 160 |
| 2026-10-23 19:46 | indian_2x2_peak_amb s1 | 749 | 425 (57%) | 20 (2.7%): retries_exhausted 17, timeout 3 | 170 |
| 2026-10-23 22:34 | indian_2x2_peak_amb s2 | 746 | 413 (55%) | 17 (2.3%): retries_exhausted 15, timeout 2 | 159 |
| 2026-10-24 01:13 | indian_2x2_peak_amb s3 | 731 | 405 (55%) | 24 (3.3%): retries_exhausted 21, timeout 3 | 150 |
| 2026-10-24 03:43 | indian_2x2_peak_amb s4 | 732 | 392 (54%) | 17 (2.3%): retries_exhausted 16, timeout 1 | 150 |
<!-- END:tab_app_hosted -->

: Every run of the hosted model: calls that needed retries after rate limiting, and calls that ran
out of retries (MaxPressure's choice applied).
:::

## Abbreviations {#sec:abbrev}

| Abbreviation | Meaning |
|:-------------|:--------|
| ATT | Average travel time (CityFlow's definition, @sec:metrics) |
| CoLLMLight | Cooperative LLM agents for network-wide traffic signal control (the base paper) |
| COCO | Common Objects in Context, the dataset whose object-size buckets we use |
| CVD | Colour vision deficiency |
| FT | Fixed-time signal control |
| GPU / VRAM | Graphics processing unit / its memory |
| IDD | India Driving Dataset (IIIT Hyderabad and Intel) |
| IoU | Intersection over union of two bounding boxes |
| JSON | JavaScript Object Notation, the format of the LLM's answer |
| LLM | Large language model |
| mAP50, mAP50-95 | Mean average precision at IoU $\ge 0.5$, and averaged over IoU thresholds from $0.5$ to $0.95$ |
| MP | MaxPressure signal control |
| NIM | NVIDIA Inference Microservices (hosted model API) |
| NMS | Non-maximum suppression |
| PCU | Passenger car unit |
| RL | Reinforcement learning |
| SCATS / SCOOT | Sydney Coordinated Adaptive Traffic System / Split Cycle Offset Optimisation Technique |
| TSC | Traffic signal control |
| V2X | Vehicle-to-everything communication |
| YOLO | You Only Look Once, a family of one-stage object detectors |


## Source Code {#sec:app-code}

::: code-listings
:::
