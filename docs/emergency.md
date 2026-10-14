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
* Generated with `scripts/generate_indian_flow.py --level all --seed 0 1 2 --emergency`:

  | Seed | Ambulances in the hour | In the first 600 s |
  |---|---|---|
  | 0 | 3 | none (first at t = 1670 s) |
  | 1 | 14 | one, t = 257 s, enters from the east and leaves by a free turn at the first signal |
  | 2 | 6 | one, t = 253 s, goes straight through two signals |

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
<!-- END:emergency_smoke -->

Each ambulance:

<!-- BEGIN:emergency_ambulances -->
<!-- END:emergency_ambulances -->

**What these runs can and cannot show.** Across the three 600 s windows there are two
ambulances, and only one (seed 2) passes a signal that can affect it. The runs show that
ambulances are generated, detected, measured and acted on; they say nothing about which
controller serves ambulances better. A comparison needs full-length runs (3600 s: 3, 14 and
6 ambulances for seeds 0–2) or more seeds, which has not been done yet.
