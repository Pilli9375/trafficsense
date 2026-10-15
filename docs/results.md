# Full experiments: results

The full-length (3600 s) experiments of Phase 3c. The plan below was committed before any run
(`scripts/run_full_experiments.py`). Every table is generated from the run folders by
`scripts/make_results.py`; `scripts/make_results.py --check` fails if this page and the data
disagree.

## Plan (pre-registered)

**Arms**

* **Main: `llm_guarded_mp` with `llama3.2:3b`, decision interval 5 s, min green 15 s.** The
  pick of the pre-registered final LLM design round (`docs/llm_benchmark.md`). It is MaxPressure
  with a guard: the LLM chooses among MaxPressure's top 2 and keeping the current phase, and
  its choice is applied only if its pressure is close to the best (≥ 0.8 × the top phase's).
* **Exploratory, NOT selected by the rule: `llm_guided_mp_v3` (hybrid_v3) with `gemma4:e4b`,
  5 s, min green 15 s.** Included because it is the only model whose decisions follow pressure
  after the v3 prompt fix (in the benchmark its answers differed from MaxPressure's choice in
  23% of calls, against 98% for `llama3.2:3b`) and it failed the selection rule only on latency
  (p95 4.80 s against the 3 s limit). It is unguarded, so it shows what an LLM that actually
  makes the decisions does. On this GPU it is not real-time: the interval rule would need a
  20 s decision interval; it runs at 5 s because the simulation pauses during calls.
* **Baselines:** `maxpressure` (5 s, min green 15 s), `fixedtime_webster`, `fixedtime` (4 paired
  phases, 30 s green); `preemption_mp` on the emergency scenario only.
* LLM runs use the run seed as the LLM sampling seed. At temperature 0 the answer should not
  depend on it.

**Runs (3600 s)**

1. Indian 2x2 off-peak and peak, seeds 0–2: all three baselines, main and exploratory arms.
2. Jinan 3x4, seeds 0–2: the three baselines and the main arm only. `gemma4:e4b` is too slow
   for 12 intersections (~4.5 s per call and about 3× the calls of the 2x2 grid: ~3.5 h per run).
   Jinan's flow file is fixed, so the deterministic baselines give the same result on every seed.
   The prompts were frozen after the final design round; they say "Indian city" on Jinan too.
3. Emergency, the pre-registered design in `docs/emergency.md`: `indian_2x2_peak_amb`, seeds
   0–4, `maxpressure`, `fixedtime_webster`, `preemption_mp`, the main arm, and the exploratory
   arm (added by the user after that design was committed).

67 runs, estimated ~17 h on the GTX 1650 (baselines and the main arm first, ~4 h; the gemma4
runs last). The batch is resumable: finished runs are skipped.

**As run:** all 67 runs finished on 2026-10-15/16 in one pass of about 16.5 h, with no
interruption (`outputs/full/batch.log`). Every run is from a clean tree: one (off-peak
MaxPressure, seed 0) at the pre-registration commit 694dc0c, the other 66 at 159d480, which
only adds the "Batch stopped" log line to the batch script.

## Results

Mean ± std over seeds, 3600 s. ATT is CityFlow's average travel time over all generated
vehicles (including those still driving or waiting to enter at the end).

### Indian 2x2, off-peak

<!-- BEGIN:results_indian_2x2_offpeak -->
| Controller | Seeds | ATT (s) | Queue / int. (veh) | Waiting / vehicle (s) | Finished trips | ATT vs MaxPressure |
|---|---|---|---|---|---|---|
| MaxPressure | 3 | 88.1 ± 1.0 | 4.94 ± 0.23 | 29.8 ± 0.9 | 2332 ± 36 | +0.0% |
| Webster fixed time | 3 | 100.4 ± 4.1 | 6.82 ± 0.52 | 41.1 ± 3.9 | 2320 ± 36 | +13.9% |
| FixedTime (4 phases, 30 s) | 3 | 121.5 ± 0.2 | 10.58 ± 0.17 | 63.7 ± 0.5 | 2316 ± 28 | +37.8% |
| LLM main: guarded hybrid, `llama3.2:3b` | 3 | 89.0 ± 0.8 | 5.08 ± 0.18 | 30.6 ± 0.6 | 2327 ± 41 | +0.9% |
| LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | 3 | 90.5 ± 1.2 | 5.37 ± 0.28 | 32.3 ± 1.1 | 2323 ± 34 | +2.7% |
<!-- END:results_indian_2x2_offpeak -->

### Indian 2x2, peak

<!-- BEGIN:results_indian_2x2_peak -->
| Controller | Seeds | ATT (s) | Queue / int. (veh) | Waiting / vehicle (s) | Finished trips | ATT vs MaxPressure |
|---|---|---|---|---|---|---|
| MaxPressure | 3 | 115.5 ± 0.9 | 17.83 ± 0.32 | 54.1 ± 0.5 | 4576 ± 68 | +0.0% |
| Webster fixed time | 3 | 116.3 ± 4.6 | 18.27 ± 1.28 | 55.4 ± 4.0 | 4577 ± 87 | +0.7% |
| FixedTime (4 phases, 30 s) | 3 | 279.9 ± 9.9 | 44.44 ± 0.75 | 144.0 ± 1.6 | 4166 ± 93 | +142.3% |
| LLM main: guarded hybrid, `llama3.2:3b` | 3 | 116.1 ± 2.9 | 17.97 ± 0.85 | 54.5 ± 2.5 | 4582 ± 77 | +0.5% |
| LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | 3 | 113.7 ± 0.3 | 17.33 ± 0.44 | 52.6 ± 0.5 | 4577 ± 77 | -1.5% |
<!-- END:results_indian_2x2_peak -->

### Jinan 3x4

<!-- BEGIN:results_jinan_3x4 -->
| Controller | Seeds | ATT (s) | Queue / int. (veh) | Waiting / vehicle (s) | Finished trips | ATT vs MaxPressure |
|---|---|---|---|---|---|---|
| MaxPressure | 3 | 300.9 ± 0.0 | 5.62 ± 0.00 | 55.7 ± 0.0 | 4130 ± 0 | +0.0% |
| Webster fixed time | 3 | 416.1 ± 0.0 | 16.42 ± 0.00 | 162.6 ± 0.0 | 3965 ± 0 | +38.3% |
| FixedTime (4 phases, 30 s) | 3 | 423.0 ± 0.0 | 17.76 ± 0.00 | 176.2 ± 0.0 | 3968 ± 0 | +40.6% |
| LLM main: guarded hybrid, `llama3.2:3b` | 3 | 303.2 ± 1.1 | 5.81 ± 0.12 | 57.7 ± 1.2 | 4134 ± 5 | +0.8% |
<!-- END:results_jinan_3x4 -->

**Jinan: why the LLM arm varies across seeds although the flow is fixed.** The baselines give
the same result on every seed, as expected. The three LLM runs see the same traffic and use
temperature 0, yet their decision logs split early (seed 0 vs seed 2 at decision 32, t = 40 s;
seed 0 vs seed 1 at decision 154, t = 200 s), and after the first different phase the traffic
differs too. The cause is the server, not the seed setting: in a manual check (not saved to
`outputs/`) two fresh 45 s runs with LLM seeds 0 and 2 made identical decisions, while the
raw answer text of a 45 s rerun with seed 0 differed in a few calls from the batch's seed-0 run.
Ollama on the GPU is not bit-for-bit deterministic at temperature 0, so LLM runs cannot be
reproduced exactly; every decision is logged in the run's `decisions.jsonl`, so a run can be
replayed (`scripts/analyze_llm_decisions.py` does this for the benchmark runs).

### Emergency (Indian 2x2 peak + ambulances, seeds 0–4)

Normal traffic:

<!-- BEGIN:results_emergency -->
| Controller | ATT (s) | Queue / int. (veh) | Finished trips |
|---|---|---|---|
| maxpressure | 115.7 ± 2.3 | 17.97 ± 0.86 | 4605 ± 66 |
| fixedtime_webster | 115.2 ± 2.7 | 18.01 ± 0.64 | 4606 ± 73 |
| preemption_mp | 116.0 ± 0.7 | 18.08 ± 0.41 | 4606 ± 61 |
| llm_guarded_mp | 116.4 ± 3.1 | 18.16 ± 0.72 | 4604 ± 64 |
| llm_guided_mp_v3 | 112.9 ± 1.9 | 17.11 ± 0.30 | 4610 ± 70 |
<!-- END:results_emergency -->

Ambulances (signal-relevant: their route crosses a movement a signal controls; the primary
metric is their mean travel time, pooled over seeds):

<!-- BEGIN:results_emergency_ambulances -->
| Controller | Relevant ambulances finished / total | Travel time mean (s) | Median (s) | Stopped mean (s) | All ambulances: travel time mean (s) | Per ambulance vs preemption_mp (s) |
|---|---|---|---|---|---|---|
| maxpressure | 29 / 29 | 130.1 | 126.0 | 62.3 | 110.1 | 48.9 (1 faster, 28 slower of 29) |
| fixedtime_webster | 29 / 29 | 123.5 | 123.0 | 55.0 | 104.9 | 42.3 (4 faster, 25 slower of 29) |
| preemption_mp | 29 / 29 | 81.2 | 80.0 | 14.1 | 71.8 | – |
| llm_guarded_mp | 29 / 29 | 88.9 | 87.0 | 21.2 | 77.8 | 7.7 (12 faster, 15 slower of 29) |
| llm_guided_mp_v3 | 29 / 29 | 82.2 | 78.0 | 15.3 | 72.6 | 1.1 (16 faster, 12 slower of 29) |
<!-- END:results_emergency_ambulances -->

### Paired by seed

Each seed has its own flow file, and every controller sees the same flow on the same seed, so
the fairest comparison is per seed. Negative = lower (better) ATT than MaxPressure.

<!-- BEGIN:results_paired -->
| Scenario | Controller | ATT minus MaxPressure, per seed (s) | Seeds with lower / higher ATT than MaxPressure |
|---|---|---|---|
| indian_2x2_offpeak | Webster fixed time | +17.25 / +12.49 / +7.06 | 0 lower, 3 higher of 3 |
| indian_2x2_offpeak | FixedTime (4 phases, 30 s) | +34.48 / +33.05 / +32.52 | 0 lower, 3 higher of 3 |
| indian_2x2_offpeak | LLM main: guarded hybrid, `llama3.2:3b` | +0.92 / +1.36 / +0.18 | 0 lower, 3 higher of 3 |
| indian_2x2_offpeak | LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | +2.30 / +2.09 / +2.70 | 0 lower, 3 higher of 3 |
| indian_2x2_peak | Webster fixed time | +2.27 / +3.46 / -3.46 | 1 lower, 2 higher of 3 |
| indian_2x2_peak | FixedTime (4 phases, 30 s) | +175.19 / +159.67 / +158.20 | 0 lower, 3 higher of 3 |
| indian_2x2_peak | LLM main: guarded hybrid, `llama3.2:3b` | +0.81 / +2.42 / -1.63 | 1 lower, 2 higher of 3 |
| indian_2x2_peak | LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | -2.61 / -2.15 / -0.61 | 3 lower, 0 higher of 3 |
| jinan_3x4 | Webster fixed time | +115.20 / +115.20 / +115.20 | 0 lower, 3 higher of 3 |
| jinan_3x4 | FixedTime (4 phases, 30 s) | +122.04 / +122.04 / +122.04 | 0 lower, 3 higher of 3 |
| jinan_3x4 | LLM main: guarded hybrid, `llama3.2:3b` | +3.52 / +1.96 / +1.35 | 0 lower, 3 higher of 3 |
| indian_2x2_peak_amb | Webster fixed time | +4.08 / +0.82 / -6.57 / +2.04 / -2.98 | 2 lower, 3 higher of 5 |
| indian_2x2_peak_amb | Preemption (rule-based) | +1.33 / +0.01 / -1.71 / +3.18 / -1.28 | 2 lower, 3 higher of 5 |
| indian_2x2_peak_amb | LLM main: guarded hybrid, `llama3.2:3b` | +6.72 / +1.31 / -0.50 / +0.92 / -5.03 | 2 lower, 3 higher of 5 |
| indian_2x2_peak_amb | LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | +1.85 / -3.43 / -6.23 / -0.80 / -5.73 | 4 lower, 1 higher of 5 |
<!-- END:results_paired -->

### LLM decisions

Pooled over the seeds of each scenario. "LLM's answer differs" is over successful calls;
"Applied phase differs" is over all calls (a failed call applies MaxPressure's choice).

<!-- BEGIN:results_llm -->
| Scenario | Arm | Calls | Failures | Latency mean (s) | p95 per run (s) | LLM's answer differs from MaxPressure | Guard replaced the answer | Applied phase differs from MaxPressure | Wall time, all seeds (h) |
|---|---|---|---|---|---|---|---|---|---|
| indian_2x2_offpeak | LLM main: guarded hybrid, `llama3.2:3b` | 2177 | 0.0% (none) | 1.05 | 1.21–1.22 | 91.5% | 81.2% | 10.4% | 0.6 |
| indian_2x2_offpeak | LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | 2802 | 0.1% (reason_too_long 4) | 4.61 | 4.92–5.02 | 32.1% | – (no guard) | 32.0% | 3.6 |
| indian_2x2_peak | LLM main: guarded hybrid, `llama3.2:3b` | 2167 | 0.0% (none) | 1.02 | 1.19–1.19 | 92.8% | 82.8% | 10.0% | 0.6 |
| indian_2x2_peak | LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | 2541 | 0.1% (reason_too_long 3) | 4.54 | 4.79–4.98 | 20.9% | – (no guard) | 20.9% | 3.2 |
| jinan_3x4 | LLM main: guarded hybrid, `llama3.2:3b` | 6665 | 0.0% (reason_too_long 1) | 1.10 | 1.28–1.36 | 89.0% | 77.8% | 11.1% | 2.0 |
| indian_2x2_peak_amb | LLM main: guarded hybrid, `llama3.2:3b` | 3632 | 0.0% (none) | 1.06 | 1.24–1.24 | 86.9% | 76.3% | 10.6% | 1.1 |
| indian_2x2_peak_amb | LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b` | 4146 | 0.0% (reason_too_long 2) | 4.72 | 5.02–5.15 | 20.4% | – (no guard) | 20.4% | 5.4 |
<!-- END:results_llm -->

### Reproducibility

Each baseline run that has an earlier run with the same scenario, controller, parameters, seed
and flow file (`outputs/indian_2x2/runs`, `outputs/baselines/runs`) is compared with it:

<!-- BEGIN:results_reproduction -->
| Baseline runs compared with an earlier identical run | Identical metrics |
|---|---|
| 27 | 27 of 27 |
<!-- END:results_reproduction -->

## What this means

Plain-language reading of the tables above. Every number here is in a table on this page.

**1. The pre-registered LLM controller is MaxPressure with small changes, and it is slightly
worse.** `llama3.2:3b`'s own answer differs from MaxPressure's choice in 87–93% of calls, so
the model is still not following pressure. The guard throws most of those answers away
(76–83% of calls), so the phase actually applied differs from MaxPressure's in only 10–11% of
calls. The result is close to MaxPressure: ATT +0.9% off-peak, +0.5% at peak, +0.8% on Jinan.
Paired by seed it is behind MaxPressure on all 3 off-peak seeds, all 3 Jinan seeds and 2 of 3
peak seeds, by 0.2–3.5 s. Read honestly: the guard makes the LLM safe, not useful. Every
remaining difference from MaxPressure is a decision the guard judged "close enough", and on
average those cost a little.

**2. The exploratory `gemma4:e4b` arm (NOT selected by the rule) is the only LLM arm that
beats MaxPressure anywhere, and only under heavy traffic.** At peak it has lower ATT than
MaxPressure on all 3 seeds (−0.6 to −2.6 s; −1.5% on the mean), and on the emergency scenario
(the same peak demand plus ambulances) on 4 of 5 seeds (−2.4% ATT on the mean: 112.9 vs
115.7 s). Off-peak it is worse on all 3 seeds (+2.1 to +2.7 s, +2.7%). It departs from
MaxPressure more off-peak (32% of calls) than at peak (21%), and off-peak those departures
cost time. These are small differences over 3–5 seeds, with no significance test
(none was pre-registered), so they are a lead, not a demonstrated improvement. This arm was
not chosen by the pre-registered rule, and it is not real-time on this GPU: mean latency
4.5–4.7 s and p95 4.8–5.2 s per call, for a 5 s decision interval (the simulation waited for
it). A 3600 s run took 1.1–1.2 h of wall time, against about 12 min for the main arm.

**3. With ambulances, both LLM arms get most of the benefit of rule-based preemption.** Mean
travel time of the 29 signal-relevant ambulances: MaxPressure 130.1 s, Webster 123.5 s,
rule-based preemption 81.2 s, the main LLM arm 88.9 s, the exploratory gemma4 arm 82.2 s.
Ambulance by ambulance, the main arm is 7.7 s slower than preemption on average (12 faster, 15
slower of 29), gemma4 1.1 s slower (16 faster, 12 slower). For the main arm, part of this is
by design: a phase that serves a listed ambulance is exempt from the guard, so when llama
picks it, it is applied. Normal traffic does not pay for the priority: on the mean, no arm's ATT is more than 0.7 s
above MaxPressure's (seed-to-seed std 2.3 s).

**4. The baselines behave as in earlier phases.** MaxPressure is best off-peak and on Jinan;
at peak MaxPressure and the Webster plan are effectively tied (115.5 vs 116.3 s; Webster wins
one of three seeds), as already explained in `docs/indian_scenario.md` (steady Poisson demand
and perfect counts favour Webster; transitions cost more near capacity). 30 s FixedTime fails
at peak. Every baseline run that repeats an earlier run gives identical metrics (27 of 27).

**5. Reproducibility of the LLM runs.** At temperature 0 the Ollama server is still not
bit-for-bit deterministic on the GPU (see the Jinan note above), so rerunning an LLM run gives
a slightly different run. All LLM decisions, with the raw model output, are logged per run, so
the runs can be inspected and replayed.

**Bottom line for the project.** A 3–4 B model running locally on a 4 GB GPU did not beat
MaxPressure as a signal controller in the pre-registered design. The selected, guarded
controller performs about as well as MaxPressure (0.5–0.9% worse) and runs in real time; a
slower, unguarded model that follows pressure shows a small gain at peak that would need more
seeds, and a faster GPU, to confirm. Where the LLM adds clear value is in reacting to
information MaxPressure does not use: listing ambulances in the prompt cuts their mean travel
time from 130.1 s to 82–89 s, close to the 81.2 s of a hand-written preemption rule.
