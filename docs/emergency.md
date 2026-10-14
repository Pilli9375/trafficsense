# Emergency vehicles (ambulances)

An extension of the Indian 2x2 scenario: ambulances in the traffic, measured separately, and
controllers that can give them green. So far only **600-step smoke tests** have been run; they
check that the pieces work, not which controller is better (see the end of this page).
Tables are generated from `outputs/emergency_smoke/` by `scripts/run_emergency_smoke.py
--report-only`; `--check` fails if this page and the data disagree.

## Demand

* New flow files `data/scenarios/indian_2x2/flow_<level>_amb_s<seed>.json` (scenarios
  `indian_2x2_peak_amb`, `indian_2x2_offpeak_amb`). Each is the normal flow file of that
  level and seed, **unchanged** (same vehicles in the same order, so CityFlow gives them the
  same ids), with ambulances appended. The generator regenerates the normal flow and refuses
  to continue unless it equals the existing file; the old files are not touched.
* **Rate: 6 ambulances per hour over the whole network (ASSUMPTION**, from the Phase 3b
  spec "~6/hour"; not from a source). Poisson arrivals over the entry roads with the same
  entry weights, and routes drawn with the same turn probabilities, as the normal traffic.
* **Own seeds:** ambulance arrivals and routes come from a separate random generator seeded
  `seed + 1000` (`emergency.seed_offset`), so the normal traffic does not depend on them.
  Peak and off-peak of the same seed therefore have the same ambulances.
* Ambulance vehicle: a ~5 m van (length 5.0 m, width 1.9 m, headway 1.0 s, max
  acceleration 2.5 m/s², max deceleration 6.0 m/s²; ASSUMPTIONS) at the 12.5 m/s lane
  limit; minGap, usual acceleration and deceleration are CityFlow's defaults
  (`configs/scenarios/indian_2x2.yaml`, `emergency_vehicle_types`).
* Generated with `scripts/generate_indian_flow.py --level all --seed 0 1 2 --emergency`
  (seeds 3 and 4, for the full runs only: `--level peak --seed 3 4`, first without and then
  with `--emergency`; this also creates the normal peak flows for those seeds):

  | Seed | Ambulances in the hour | In the first 600 s |
  |---|---|---|
  | 0 | 3 | none (first at t = 1670 s) |
  | 1 | 14 | one, t = 257 s, enters from the east and leaves by a free turn at the first signal |
  | 2 | 6 | one, t = 253 s, goes straight through two signals |
  | 3 | 6 | (full runs only) |
  | 4 | 8 | (full runs only) |

  Over seeds 0–4: 37 ambulances, 29 of them **signal-relevant** (their route has at least one
  movement a signal controls; the other 8 only make free turns, which no signal affects).

**CityFlow limitation.** Nobody yields to an ambulance and, with lane changing off, it
cannot overtake: it waits in the queue like any vehicle. Only the signal can help it, which
is what the controllers below try to do. Real ambulances also use sirens, the wrong side of
the road and gaps in traffic; none of that is modelled.

## Metrics (`src/trafficsense/sim/emergency.py`)

Measured from the simulator, per ambulance, in `summary.json` under `emergency`:

* **Travel time:** finish time minus scheduled start (the flow file's start time), the same
  convention as CityFlow's ATT (entry delay included). Only for ambulances that finished.
* **Stopped time:** seconds with speed < 0.1 m/s while in the network (the same threshold as
  the queue and waiting-time metrics).
* **Entry wait:** first step in the network minus scheduled start.
* Means are over the ambulances that finished; ambulances still driving at the end are
  listed with their time so far. Ambulances also count in the normal network metrics (ATT,
  queue, throughput) like any vehicle.

## Controllers

All act on the same 5 s decision grid after the same 15 s minimum green (the tuned
MaxPressure's timing), so they differ only in how they choose.

* `maxpressure`: the default MaxPressure; ignores ambulances.
* `fixedtime_webster`: the Webster plan; ignores ambulances. Its demand counts include the
  ambulances in the flow file (6 of ~4800 vehicles).
* `preemption_mp`, **rule-based preemption, the non-LLM competitor:** MaxPressure, except that
  when an ambulance is on an incoming lane within **150 m of the stop line (ASSUMPTION**,
  `emergency.detection_range_m`; lanes are 176–188 m, and at 12.5 m/s 150 m is 12 s, enough
  for one 5 s decision step and the 5 s transition) the nearest such ambulance gets green.
  Among the phases that serve its movement, the one with the highest pressure is chosen, so
  if the current phase serves it, it is kept. Ambulances on a free turn are ignored: every
  phase serves them. It does not cut a green before the minimum or hold it past the maximum.
* `llm_guided_mp` with ambulances: as in the benchmark (MaxPressure's top 2 or keeping the
  current phase), plus, for each ambulance detected exactly as above, its movement, distance
  and serving phases in the prompt, one sentence in the system prompt ("Ambulances, if listed,
  must get through quickly: give green to a phase that serves them."), and the best-ranked
  phase serving it added to the options if it is not there yet. On a failed call MaxPressure's
  top choice is applied.

Detection (`detect` in `emergency.py`): distance to the stop line = lane length − distance
driven on the lane, with lane length = road length − the widths of the intersections at both
ends (checked against stopped vehicles in `tests/test_emergency.py`); the ambulance's
movement comes from its route.

## Smoke tests (600 steps)

Design, committed before any run (`scripts/run_emergency_smoke.py`): `indian_2x2_peak_amb`,
seeds 0–2, 600 steps, the four controllers above. `llm_guided_mp` uses the model the
selection rule picks in the benchmark's hybrid arm (`docs/llm_benchmark.md`), or, if it picks
none, the hybrid-arm model with the lowest failure rate (ties: lower p95 latency); decision
interval 5 s, min green 15 s.

<!-- BEGIN:emergency_smoke -->
| Controller | Seed | ATT at 600 s (s) | Queue / int. (veh) | Finished trips | Ambulances scheduled / finished | Ambulance travel time, mean (s) | Ambulance stopped time, mean (s) | Controller notes |
|---|---|---|---|---|---|---|---|---|
| maxpressure | 0 | 92.5 | 11.85 | 623 | 0 / 0 | – | – | – |
| maxpressure | 1 | 92.5 | 13.23 | 656 | 1 / 1 | 37.0 | 0.0 | – |
| maxpressure | 2 | 102.0 | 16.23 | 680 | 1 / 1 | 101.0 | 31.0 | – |
| fixedtime_webster | 0 | 97.4 | 13.49 | 626 | 0 / 0 | – | – | – |
| fixedtime_webster | 1 | 96.5 | 14.64 | 654 | 1 / 1 | 37.0 | 0.0 | – |
| fixedtime_webster | 2 | 101.0 | 15.91 | 685 | 1 / 1 | 123.0 | 59.0 | – |
| preemption_mp | 0 | 92.5 | 11.85 | 623 | 0 / 0 | – | – | 0 preemption decisions (0 differ from MaxPressure) |
| preemption_mp | 1 | 92.5 | 13.23 | 656 | 1 / 1 | 37.0 | 0.0 | 0 preemption decisions (0 differ from MaxPressure) |
| preemption_mp | 2 | 104.2 | 17.03 | 672 | 1 / 1 | 77.0 | 12.0 | 2 preemption decisions (1 differ from MaxPressure) |
| llm_guided_mp | 0 | 133.8 | 25.80 | 545 | 0 / 0 | – | – | `llama3.2:3b`: 270 calls, 0.0% failed, p95 1.19 s, 96.3% differ from MaxPressure; 0 decisions with an ambulance in view (0 gave it green) |
| llm_guided_mp | 1 | 124.5 | 25.19 | 592 | 1 / 1 | 37.0 | 0.0 | `llama3.2:3b`: 271 calls, 0.0% failed, p95 1.21 s, 97.4% differ from MaxPressure; 0 decisions with an ambulance in view (0 gave it green) |
| llm_guided_mp | 2 | 139.6 | 30.27 | 584 | 1 / 1 | 250.0 | 156.0 | `llama3.2:3b`: 274 calls, 0.0% failed, p95 1.29 s, 96.7% differ from MaxPressure; 24 decisions with an ambulance in view (11 gave it green) |
<!-- END:emergency_smoke -->

Each ambulance:

<!-- BEGIN:emergency_ambulances -->
| Controller | Seed | Ambulance | Scheduled start (s) | Route (roads) | Travel time (s) | Stopped (s) | Entry wait (s) |
|---|---|---|---|---|---|---|---|
| maxpressure | 1 | `flow_4796_0` | 257 | road_3_2_2 → road_2_2_1 | 37 | 0 | 3 |
| maxpressure | 2 | `flow_4795_0` | 253 | road_3_2_2 → road_2_2_2 → road_1_2_2 | 101 | 31 | 1 |
| fixedtime_webster | 1 | `flow_4796_0` | 257 | road_3_2_2 → road_2_2_1 | 37 | 0 | 3 |
| fixedtime_webster | 2 | `flow_4795_0` | 253 | road_3_2_2 → road_2_2_2 → road_1_2_2 | 123 | 59 | 1 |
| preemption_mp | 1 | `flow_4796_0` | 257 | road_3_2_2 → road_2_2_1 | 37 | 0 | 3 |
| preemption_mp | 2 | `flow_4795_0` | 253 | road_3_2_2 → road_2_2_2 → road_1_2_2 | 77 | 12 | 1 |
| llm_guided_mp | 1 | `flow_4796_0` | 257 | road_3_2_2 → road_2_2_1 | 37 | 0 | 3 |
| llm_guided_mp | 2 | `flow_4795_0` | 253 | road_3_2_2 → road_2_2_2 → road_1_2_2 | 250 | 156 | 1 |
<!-- END:emergency_ambulances -->

**What these runs can and cannot show.** Across the three 600 s windows there are two
ambulances, and only one (seed 2) passes a signal that can affect it. The runs show that
ambulances are generated, detected, measured and acted on; they say nothing about which
controller serves ambulances better. A comparison needs full-length runs (3600 s: 3, 14 and
6 ambulances for seeds 0–2) or more seeds, which has not been done yet.

What the smoke tests show (one ambulance per run at most; observations, not results):

* **The pieces work.** Ambulances are generated, tracked and measured; the seed 1 ambulance,
  which leaves by a free turn, takes 37 s under every controller (no signal can affect it),
  and seed 0 has none in the window, so `preemption_mp` equals MaxPressure there exactly.
* **Seed 2, the one ambulance a signal can help** (east to west, straight through
  intersection_2_2 and intersection_1_2): travel time 77 s with `preemption_mp` (12 s
  stopped), 101 s with MaxPressure (31 s), 123 s with Webster (59 s) and 250 s with
  `llm_guided_mp` (156 s). Preemption changed 1 of MaxPressure's decisions
  (`preemptions.jsonl`), at a small cost to the rest of the traffic in this run (queue 17.03
  against 16.23).
* **`llm_guided_mp` (`llama3.2:3b`, the rule's choice) did not help the ambulance.** It had
  it in view in 24 decisions and gave it green in 11. Its decision log shows it switching
  intersection_2_2 away from the ambulance's phase while the ambulance was 46 m from the stop
  line (t = 330 s), then keeping phase 2 until max green ended it (t = 390 s) while the
  ambulance waited 17 m from the stop line from t = 350 s, with reasons such as "S+N straight, low queue and pressure, suitable for ambulances".
  This is the misreading found in the benchmark (`docs/llm_benchmark.md`, hybrid findings):
  the model prefers low pressure. As in the benchmark, it overruled MaxPressure in 96–97% of
  its calls and its queues (25.19–30.27) are about twice MaxPressure's.

## Full runs (pre-registered, not run yet)

Design and analysis committed before any run (`scripts/run_emergency_experiments.py`):

* `indian_2x2_peak_amb`, **seeds 0–4, 3600 s**, ambulances at 6/h (ASSUMPTION): 37 ambulances,
  29 signal-relevant.
* Controllers `maxpressure`, `fixedtime_webster`, `preemption_mp`, and **the LLM arm chosen by
  the final LLM design round** (`docs/llm_benchmark.md`, final decision): its controller and
  model, with the rule's decision interval and a 15 s minimum green. If the final round
  chooses no LLM controller, only the other three run. If it chooses the plain controller
  (`llm_v3`), that runs as is, without ambulance information in its prompt (only the hybrid
  and guarded arms list ambulances).
  **Resolved:** the final round chose `llm_guarded_mp` with `llama3.2:3b`, decision interval
  5 s (`docs/llm_benchmark.md`). Its prompt lists ambulances, and a phase serving a listed
  ambulance is exempt from the guard, so the guard cannot block ambulance priority. In the
  benchmark this controller applied MaxPressure's choice in 106 of its 121 decisions.
* **Primary ambulance metric:** mean travel time of the signal-relevant ambulances that
  finished, pooled over the 5 seeds; also the median, the mean stopped time and how many did
  not finish by t = 3600 s. All 37 ambulances are reported too.
* The same ambulances run under every controller, so each controller is also compared with
  `preemption_mp` ambulance by ambulance (mean difference; how many faster, how many slower).
* Normal traffic: ATT, mean queue per intersection and finished trips, mean ± std over the
  5 seeds.
* No significance test is pre-registered; with 29 relevant ambulances the numbers are
  reported as measured, with their spread.

Normal traffic (mean ± std over seeds 0–4):

<!-- BEGIN:emergency_full -->
<!-- END:emergency_full -->

Ambulances:

<!-- BEGIN:emergency_full_ambulances -->
<!-- END:emergency_full_ambulances -->

