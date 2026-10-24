# Camera-error experiment: how much do realistic detector errors hurt each controller?

Phase 4c. Sections 1–6 are the design, committed **before any run** (pre-registration).
Results are added below them afterwards, generated from the run files by
`scripts/make_camera_error.py` (`--check` verifies them).

## 1. Question and idea

Every earlier experiment gave the controllers exact vehicle counts read from the simulator.
A real junction would count vehicles with a camera and a detector, which misses some
vehicles, invents some, and mislabels some. Here the controllers see counts with the
errors our own detector makes (docs/perception.md section 8, `outputs/perception/error_model.json`),
while **the simulator itself stays exact**: vehicles move as before, and every metric is
still measured from the engine. Only what the controllers *observe* changes.

## 2. Observation-noise layer (`src/trafficsense/sim/observation.py`)

Controllers read lane counts only through `TrafficEnv.lane_view()` (MaxPressure's pressures
via `get_state`, the LLM prompt via `prompt.observe`). At level `perfect` this returns the
engine's own counts, exactly as before; a test checks that a noisy level with p_detect = 1
and no false detections gives identical counts and an identical run.

At a noisy level there is **one camera per road** (a road is an approach of the intersection
it leads to). Whenever a controller observes at a simulator step, a fresh snapshot is drawn
for the whole network and cached for that step, so all intersections deciding at the same
second see the same snapshot. The next observation draws again: no vehicle stays "blind".

For each vehicle on a lane:

1. it is **detected** with probability `p_detect[class]`;
2. a detected vehicle gets a **label** drawn from the measured label probabilities
   `P(label | true class, detected)` (the normalised rows of the confusion matrix). It is
   counted as a vehicle only if the label is a vehicle class (car, motorcycle,
   autorickshaw, bus, truck, bicycle). A vehicle labelled `person` is lost from the count;
3. it counts as **stopped** (queue) if its speed is below 0.1 m/s, CityFlow's own waiting
   definition.

Then, per road and per vehicle class j, a **Poisson(false_det[j])** number of phantom
vehicles is added, each on a uniformly chosen lane of the road and counted as stopped.
ASSUMPTION: false positives of a fixed camera are mostly static clutter (parked vehicles,
structures), and a stopped phantom is the case that changes queue-based decisions most. The
rate is the measured false detections per image, read as per camera frame.

Draws come from a numpy `Generator` seeded with `SeedSequence([run seed, crc32(level)])`.
Each run's `summary.json` (`observation`) records the level, every parameter, the source
file and its sha256, the seed, the number of snapshots and the **realised** detection rate
per class and false detections per road and snapshot. `noise.jsonl` logs every snapshot
(true vehicles, detected, lost to a non-vehicle label, phantoms added, per class).

### 2.1 Vehicle types → detector classes

| simulator type (configs/scenarios/indian_2x2.yaml) | detector class |
|---|---|
| motorcycle | motorcycle |
| auto_rickshaw | autorickshaw |
| car | car |
| bus | bus |
| truck | truck |
| ambulance | **not noised** (see 2.2) |

The simulator has no bicycles and no pedestrians. Detector labels `bicycle` (from
confusion or false detections) are counted as vehicles; `person` is not.

### 2.2 Ambulances are not noised

IDD has no ambulance class, so we have no measured error for ambulances. **Ambulance
positions are assumed to come from a separate channel (GPS / V2X) and are never noised:**
`preemption_mp` and the LLM arm's ambulance list read them from the engine as before
(`sim/emergency.py`), and an ambulance in a queue is counted exactly. This is stated with
every emergency result.

### 2.3 What the class confusion can and cannot affect

MaxPressure, preemption and the guarded LLM arm all decide from **class-free counts**
(pressure = stopped vehicles in − stopped vehicles out). The main arm's prompt
(`guided_v3`) shows pressure and queue only, **no vehicle-type counts**. So label confusion
matters here only through vehicles lost to the `person` label; the type mix it produces is
computed (`LaneView.type_counts`, used by the v1/v2 prompts) but no controller in this
experiment reads it. We state this rather than claim an effect of confusion.

## 3. Noise levels

| level | p_detect per class | labels | false detections |
|---|---|---|---|
| `perfect` | exact counts (no noise layer) | exact | none |
| `junction` ("junction camera") | measured on **medium + large** test objects, pooled over their ground truth: queued vehicles near the stop line are close to the camera | measured | measured, all sizes |
| `crowded` ("crowded / far") | measured on **all** test objects | measured | measured |
| `uniform_pX` (sweep) | X for every class, X = 1.0, 0.9, 0.8, 0.7, 0.6, 0.5 | exact | none |

For information, the values `noise_params()` computes from `error_model.json`
(sha256 of the file is recorded in every run):

| class | junction p_detect | crowded p_detect | false det. per road and snapshot |
|---|---:|---:|---:|
| car | 0.936 | 0.568 | 0.222 |
| motorcycle | 0.913 | 0.567 | 0.271 |
| autorickshaw | 0.944 | 0.598 | 0.070 |
| bus | 0.907 | 0.632 | 0.039 |
| truck | 0.832 | 0.537 | 0.079 |
| bicycle | (not in the simulator) | | 0.006 |

False detections use the overall rate at both levels; we did not split them by size.
Caveat from perception.md: IDD is filmed from a moving vehicle, so these are a measured
proxy for an intersection camera, not its true error.

## 4. Runs (3,600 s each; `scripts/run_camera_error.py`, 130 runs)

| block | scenarios, seeds | levels | controllers |
|---|---|---|---|
| main | indian_2x2_offpeak, indian_2x2_peak; seeds 0–2 | perfect, junction, crowded | maxpressure, fixedtime_webster, main LLM arm |
| sweep | same | uniform p 1.0 … 0.5 | maxpressure |
| emergency | indian_2x2_peak_amb; seeds 0–4 | perfect (reference), junction | maxpressure, fixedtime_webster, preemption_mp, main LLM arm |

- **Main LLM arm:** `llm_guarded_mp` with llama3.2:3b on the local GPU, 5 s decisions, min
  green 15 s, LLM seed = run seed: the main arm of the full experiments.
- **preemption_mp** runs on the emergency scenario only: without ambulances it is
  MaxPressure by construction.
- **fixedtime_webster** plans its timings offline from the flow file and never reads
  counts at run time, so it should be unaffected. This is checked, not assumed: its
  runs must be identical at every level, with 0 snapshots drawn.
- **perfect is re-run** with this code for every controller, so each noisy run has a paired
  perfect run from the same commit (same scenario, seed and flow file).
- Estimated time: ~6.4 h (LLM runs ~770 s each, measured in the full experiments).

*Execution note, added after the design commit (`91aa214`) and before any result was looked
at:* the first start of the batch hung after 11 runs, at the start of run 12 (Webster,
off-peak, seed 1, crowded). The main thread and a newly created thread that had used no CPU
both waited on a futex, which points to CityFlow's worker-thread start-up. Each run now
executes in its own process with a timeout (5 / 10 / 60 min for MaxPressure / Webster /
LLM runs) and is killed and retried, at most twice, if it hangs
(`trafficsense.experiment.run_experiment_isolated`). Every hang is logged in
`outputs/camera_error/batch.log`. One completed run of that first start (MaxPressure,
off-peak, seed 1, crowded, 06:33) was recorded as `git_dirty` because analysis scripts
written meanwhile were not committed yet; the batch ignores dirty runs and makes it again.
The runs and the analysis are unchanged.

## 5. Analysis (fixed now)

- **Primary:** per scenario and controller, ATT at each level, mean ± std over seeds, and
  the **paired** change against perfect (same seed): mean and range over seeds, in seconds
  and in %.
- **Secondary:** queue per intersection, waiting time per vehicle, throughput, at each
  level.
- **Sweep:** MaxPressure ATT against p_detect, per scenario (mean ± std over seeds), with
  the junction and crowded levels marked at their mean p_detect.
- **Emergency:** ATT and the travel time of signal-relevant ambulances, perfect vs
  junction, per controller, paired by ambulance.
- **LLM arm:** call failures per level (should stay 0), guard override rate per level,
  disagreement with MaxPressure, descriptive only.
- **Checks reported with the results:** (a) `uniform_p1.00` MaxPressure runs identical to
  the perfect runs; (b) Webster identical across levels with 0 snapshots; (c) the
  deterministic perfect runs reproduce the full-experiment runs (outputs/full,
  outputs/emergency) exactly; (d) realised detection rates within ±0.01 of the targets.
- With 3 (or 5) seeds no significance test is claimed; differences are shown with their
  per-seed range.
- One chart: MaxPressure ATT vs p_detect (sweep), plus each controller at the three
  levels.

## 6. What this experiment does not cover

Tracking over time (a real counter could smooth detections across frames; here each
snapshot is independent), errors in ambulance detection, camera placement, occlusion
between lanes, and night or rain. The size split is the only distance proxy.
