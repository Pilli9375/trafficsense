# Configuration {.appendix #sec:app-config}

Every setting used in the experiments is read from YAML files in `configs/`; no setting is typed
into code. The listings below are copied from the files by the report's build script, so they are
the settings actually in force.

## Main configuration

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

## Indian 2x2 scenario

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
