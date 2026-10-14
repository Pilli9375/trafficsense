# Baselines: tuned MaxPressure and Webster FixedTime

The LLM controller will be compared against these baselines, so they must be tuned before
that comparison, not after. Every table below is generated from the files in
`outputs/baselines/` by `scripts/make_baseline_tables.py`; `make_baseline_tables.py --check`
fails if this document and the data disagree. Metric definitions are those in `CLAUDE.md`
(ATT includes time spent waiting to enter the network).

## 1. MaxPressure decision interval

`scripts/tune_maxpressure.py` runs MaxPressure with `decision_interval` 5, 10, 15, 20 and
30 s on Jinan 3x4, Hangzhou 4x4 and Indian 2x2 (off-peak and peak), seeds 0–2, 3600 steps.
Every other setting is unchanged: min green 10 s, max green 60 s, all 8 phases, ties keep
the current phase.

**Selection rule**, written into the script's docstring and committed (`8414f9a`) before the
sweep was run:

1. Each of the 4 scenarios counts once; its score is the mean ATT over the 3 seeds.
2. Within a scenario the intervals are ranked by score (1 = lowest ATT).
3. The chosen interval has the lowest mean rank over the 4 scenarios.
4. Tie-break: the lowest mean of (score / best score in that scenario); then the shorter
   interval.

Throughput and transition time are reported but not used to choose.

### Results

Mean ± std over seeds 0, 1, 2. On Jinan and Hangzhou the flow file is fixed and the controller
is deterministic, so the three seeds give identical results (std 0). The Indian scenario has a
different flow file per seed. The demand levels here are the ones in force when the sweep was
run (off-peak 2375, peak 4750 veh/h; section 3 re-checks them).

"Shortest possible green" follows from the decision grid: MaxPressure only decides when
simulation time is a multiple of the interval, so after a switch (5 s transition) the next
chance to switch again is the first grid point at least 10 s (min green) into the new green.
This is measured in `tests/test_baselines.py`, not just derived.

**Jinan 3x4**

<!-- BEGIN:mp_sweep_jinan_3x4 -->
| Decision interval | Shortest possible green | ATT (s) | Throughput | Waiting to enter at 3600 s | Queue / int. (veh) | Time in transition | ATT rank |
|---|---|---|---|---|---|---|---|
| 5 s | 10 s | 295.9 ± 0.0 | 4135 ± 0 | 0.0 ± 0.0 | 4.94 ± 0.00 | 0.319 ± 0.000 | 1 |
| 10 s | 15 s | 301.7 ± 0.0 | 4134 ± 0 | 0.0 ± 0.0 | 5.68 ± 0.00 | 0.239 ± 0.000 | 3 |
| 15 s | 10 s | 297.0 ± 0.0 | 4149 ± 0 | 0.0 ± 0.0 | 5.06 ± 0.00 | 0.311 ± 0.000 | 2 |
| 20 s | 15 s | 306.8 ± 0.0 | 4121 ± 0 | 0.0 ± 0.0 | 6.20 ± 0.00 | 0.239 ± 0.000 | 4 |
| 30 s | 25 s | 325.8 ± 0.0 | 4097 ± 0 | 0.0 ± 0.0 | 8.22 ± 0.00 | 0.160 ± 0.000 | 5 |
<!-- END:mp_sweep_jinan_3x4 -->

**Hangzhou 4x4**

<!-- BEGIN:mp_sweep_hangzhou_4x4 -->
| Decision interval | Shortest possible green | ATT (s) | Throughput | Waiting to enter at 3600 s | Queue / int. (veh) | Time in transition | ATT rank |
|---|---|---|---|---|---|---|---|
| 5 s | 10 s | 331.1 ± 0.0 | 2740 ± 0 | 0.0 ± 0.0 | 1.67 ± 0.00 | 0.270 ± 0.000 | 1 |
| 10 s | 15 s | 334.7 ± 0.0 | 2732 ± 0 | 0.0 ± 0.0 | 1.94 ± 0.00 | 0.212 ± 0.000 | 3 |
| 15 s | 10 s | 334.3 ± 0.0 | 2735 ± 0 | 0.0 ± 0.0 | 1.84 ± 0.00 | 0.250 ± 0.000 | 2 |
| 20 s | 15 s | 340.7 ± 0.0 | 2721 ± 0 | 0.0 ± 0.0 | 2.25 ± 0.00 | 0.204 ± 0.000 | 4 |
| 30 s | 25 s | 363.6 ± 0.0 | 2699 ± 0 | 0.0 ± 0.0 | 3.47 ± 0.00 | 0.153 ± 0.000 | 5 |
<!-- END:mp_sweep_hangzhou_4x4 -->

**Indian 2x2, off-peak**

<!-- BEGIN:mp_sweep_indian_2x2_offpeak -->
| Decision interval | Shortest possible green | ATT (s) | Throughput | Waiting to enter at 3600 s | Queue / int. (veh) | Time in transition | ATT rank |
|---|---|---|---|---|---|---|---|
| 5 s | 10 s | 82.0 ± 0.8 | 2332 ± 37 | 0.0 ± 0.0 | 3.91 ± 0.17 | 0.319 ± 0.003 | 2 |
| 10 s | 15 s | 87.8 ± 0.7 | 2327 ± 35 | 0.0 ± 0.0 | 4.89 ± 0.18 | 0.246 ± 0.001 | 3 |
| 15 s | 10 s | 81.3 ± 0.3 | 2332 ± 38 | 0.0 ± 0.0 | 3.80 ± 0.07 | 0.314 ± 0.003 | 1 |
| 20 s | 15 s | 90.5 ± 0.9 | 2327 ± 39 | 0.0 ± 0.0 | 5.32 ± 0.19 | 0.240 ± 0.001 | 4 |
| 30 s | 25 s | 106.7 ± 1.9 | 2321 ± 36 | 0.0 ± 0.0 | 8.04 ± 0.42 | 0.164 ± 0.001 | 5 |
<!-- END:mp_sweep_indian_2x2_offpeak -->

**Indian 2x2, peak**

<!-- BEGIN:mp_sweep_indian_2x2_peak -->
| Decision interval | Shortest possible green | ATT (s) | Throughput | Waiting to enter at 3600 s | Queue / int. (veh) | Time in transition | ATT rank |
|---|---|---|---|---|---|---|---|
| 5 s | 10 s | 142.4 ± 18.3 | 4516 ± 131 | 0.3 ± 0.6 | 25.84 ± 5.22 | 0.324 ± 0.001 | 5 |
| 10 s | 15 s | 116.2 ± 1.8 | 4584 ± 78 | 0.3 ± 0.6 | 18.03 ± 0.41 | 0.246 ± 0.001 | 2 |
| 15 s | 10 s | 133.8 ± 15.9 | 4540 ± 116 | 0.3 ± 0.6 | 23.24 ± 4.60 | 0.321 ± 0.002 | 4 |
| 20 s | 15 s | 115.9 ± 1.7 | 4580 ± 82 | 0.3 ± 0.6 | 17.91 ± 0.33 | 0.244 ± 0.002 | 1 |
| 30 s | 25 s | 129.7 ± 3.2 | 4567 ± 89 | 0.3 ± 0.6 | 22.57 ± 0.88 | 0.164 ± 0.000 | 3 |
<!-- END:mp_sweep_indian_2x2_peak -->

### Selection

<!-- BEGIN:mp_selection -->
| Interval | Rank: jinan_3x4 | Rank: hangzhou_4x4 | Rank: indian_2x2_offpeak | Rank: indian_2x2_peak | Mean rank | Mean ATT / best |  |
|---|---|---|---|---|---|---|---|
| 5 s | 1 | 1 | 2 | 5 | 2.25 | 1.059 |  |
| 10 s | 3 | 3 | 3 | 2 | 2.75 | 1.028 |  |
| 15 s | 2 | 2 | 1 | 4 | 2.25 | 1.042 | **chosen** |
| 20 s | 4 | 4 | 4 | 1 | 3.25 | 1.045 |  |
| 30 s | 5 | 5 | 5 | 3 | 4.50 | 1.158 |  |
<!-- END:mp_selection -->

**15 s is the new default** (`controllers.maxpressure` in `configs/default.yaml`). The old
5 s setting stays available as controller `maxpressure_5s`.

What the results show:

* **The choice was decided by the tie-break.** 5 s and 15 s have the same mean rank (2.25).
  15 s wins because where it loses it loses by less (mean ATT / best 1.042 vs 1.059): 5 s is
  last at Indian peak. It is not a clear winner, and this document does not claim it is.
* **10 s has the best mean ATT / best (1.028)** but ranks 3rd on three scenarios, so the
  pre-registered rank rule does not choose it. Under a "lowest mean ATT / best" rule 10 s
  would have been chosen; the rule was fixed in advance and is not changed after the fact.
* **The results pair up 5 s with 15 s and 10 s with 20 s**, not in interval order. These are
  exactly the pairs with the same shortest possible green (10 s and 15 s), and they spend
  almost the same share of time in the transition phase (about 0.31–0.32 vs 0.24 on Jinan and
  on both Indian levels). So what the sweep mostly varies is **how short a green can be**,
  which sets how often the signal can switch and how much time is lost to 5 s transitions.
* **Light vs heavy traffic pull in opposite directions.** On Jinan, Hangzhou and Indian
  off-peak, the settings that can switch sooner (5 s, 15 s) are best. At Indian peak the
  settings that switch less (10 s, 20 s) are best by a wide margin (ATT about 116 s vs 134–142 s),
  with much smaller seed spread. Near capacity, the green lost to transitions costs more than
  reacting a few seconds sooner gains, which is the same pattern seen between the 5 s and the
  CoLLMLight-matched 30 s MaxPressure on Synthetic 4x4 (`docs/validation.md`, section 4).
* **30 s is worst or near-worst everywhere** except Indian peak, where it is 3rd.
* No run had a forced (max-green) switch.

Because the sweep effectively varies the shortest green, a direct sweep of `min_green` (kept
at 10 s here, as specified) might find a better setting. That was not done; it would change
the experiment design.

## 2. Webster-tuned FixedTime

Controller `fixedtime_webster` (`src/trafficsense/control/webster.py`, where the method is
written out in full). It cycles the same 4 paired phases as `fixedtime`, but each
intersection gets its own cycle length and green splits, computed once at the start of the
run by Webster's method (Webster, 1958, *Traffic signal settings*, Road Research Technical
Paper 39):

| Quantity | Formula / source |
|---|---|
| Lane demand q (veh/h) | vehicles routed over the lane in the run's flow file, first 3600 s |
| Saturation flow s (veh/h) and start-up lost time l (s) | **measured**: queue discharge on the scenario's roadnet with the flow file's vehicle mix (900 s red, then green); a straight line fitted to cumulative departures over green s 10–70 gives s (slope) and l (where it crosses zero); mean of 30 random-order queues |
| Flow ratio of phase i | y_i = max over its non-right-turn lanes of q / s |
| Critical flow ratio | Y = Σ y_i (right turns run in every phase and are excluded) |
| Lost time per cycle | L = n (T + l), n = 4 phases, T = 5 s transition (red for every non-right movement) |
| Optimum cycle | C0 = (1.5 L + 5) / (1 − Y), clipped to 60–180 s; Y ≥ 1 → 180 s |
| Green of phase i | G_i = l + (C − L) y_i / Y, clipped to min green 10 s / max green 60 s (the rest shared by y), rounded to whole seconds |

Why random-order queues: with the periodic feed used for the capacity table in
`docs/indian_scenario.md`, every measurement builds the same regular interleaving of
vehicle types, and the start-up lost time came out anywhere from 3.3 to 5.7 s depending on
which types happened to lead the queue (one queue per seed's mix). Over random queues a
single measurement ranges from about −2 to 7 s, so 30 are averaged (measurement seed 0,
independent of the run seed). Jinan and Hangzhou have a single vehicle type, so every queue
is the same and one measurement is exact. Every number used in a plan, and the plan itself,
is stored in each run's `summary.json` (`provenance.controller_params`).

Using the run's own flow file as the demand equals a perfect traffic count of the simulated
hour. That **favours** this controller: a real Webster plan is built from earlier counts.

### Plans

Ranges over intersections (and seeds; each Indian seed has its own flow file, so its own
measured mix and plan):

<!-- BEGIN:webster_plans -->
| Scenario | s straight (veh/h) | s protected turn (veh/h) | Start-up lost time (s) | L (s) | Y | C0 (s) | Cycle run (s) | Plans at cycle_min | Plans with Y ≥ 1 | Greens clipped to min/max |
|---|---|---|---|---|---|---|---|---|---|---|
| jinan_3x4 | 1459 | 1396 | 0.46 | 21.8 | 0.22–0.43 | 48–66 | 60–66 | 18 / 36 | 0 / 36 | 111 / 144 |
| hangzhou_4x4 | 1459 | 1396 | 0.46 | 21.8 | 0.14–0.45 | 44–69 | 60–69 | 42 / 48 | 0 / 48 | 186 / 192 |
| indian_2x2_offpeak | 2073–2098 | 2000–2023 | 1.94–2.05 | 27.8–28.2 | 0.22–0.25 | 60–63 | 60–63 | 1 / 12 | 0 / 12 | 36 / 48 |
| indian_2x2_peak | 2096–2116 | 2017–2036 | 2.00–2.11 | 28.0–28.5 | 0.44–0.48 | 84–91 | 84–91 | 0 / 12 | 0 / 12 | 23 / 48 |
<!-- END:webster_plans -->

### Jinan 3x4 and Hangzhou 4x4: all baselines

Seeds 0, 1, 2 (identical results: fixed flow file, deterministic controllers).

**Jinan 3x4**

<!-- BEGIN:compare_jinan_3x4 -->
| Controller | ATT (s) | Throughput | Queue / int. (veh) | Waiting time / vehicle (s) | Time in transition |
|---|---|---|---|---|---|
| FixedTime, 4 paired phases, 30 s | 423.0 ± 0.0 | 3968 ± 0 | 17.76 ± 0.00 | 176.2 ± 0.0 | 0.142 ± 0.000 |
| FixedTime, Webster plan | 416.1 ± 0.0 | 3965 ± 0 | 16.42 ± 0.00 | 162.6 ± 0.0 | 0.325 ± 0.000 |
| MaxPressure, 15 s (tuned default) | 297.0 ± 0.0 | 4149 ± 0 | 5.06 ± 0.00 | 50.1 ± 0.0 | 0.311 ± 0.000 |
| MaxPressure, 5 s | 295.9 ± 0.0 | 4135 ± 0 | 4.94 ± 0.00 | 49.0 ± 0.0 | 0.319 ± 0.000 |
<!-- END:compare_jinan_3x4 -->

**Hangzhou 4x4**

<!-- BEGIN:compare_hangzhou_4x4 -->
| Controller | ATT (s) | Throughput | Queue / int. (veh) | Waiting time / vehicle (s) | Time in transition |
|---|---|---|---|---|---|
| FixedTime, 4 paired phases, 30 s | 580.6 ± 0.0 | 2438 ± 0 | 13.00 ± 0.00 | 258.9 ± 0.0 | 0.142 ± 0.000 |
| FixedTime, Webster plan | 549.8 ± 0.0 | 2439 ± 0 | 11.80 ± 0.00 | 232.5 ± 0.0 | 0.330 ± 0.000 |
| MaxPressure, 15 s (tuned default) | 334.3 ± 0.0 | 2735 ± 0 | 1.84 ± 0.00 | 35.6 ± 0.0 | 0.250 ± 0.000 |
| MaxPressure, 5 s | 331.1 ± 0.0 | 2740 ± 0 | 1.67 ± 0.00 | 32.2 ± 0.0 | 0.270 ± 0.000 |
<!-- END:compare_hangzhou_4x4 -->

What the tables show:

* **On these two networks the Webster plan is mostly "every phase at min green".** With 4
  phases, a 10 s min green and 5 s transitions, no cycle can be shorter than
  4 × (10 + 5) = 60 s, which is also the 60 s floor. Webster's optimum C0 is below 60 s on
  half of Jinan's and most of Hangzhou's intersections (Y is low, 0.14–0.45), so those plans
  run 60 s cycles of four 10 s greens; most other greens are clipped too. The method is applied
  as specified; the minimum-green constraint leaves it little room on lightly loaded
  intersections.
* **Webster improves on 30 s FixedTime only a little** (ATT 416.1 vs 423.0 s on Jinan,
  549.8 vs 580.6 s on Hangzhou), despite perfect demand counts, and loses far more time to
  transitions (33% vs 14%) because its cycles are short.
* **MaxPressure is far better than either FixedTime plan** (about 297 and 334 s). A likely
  reason, **not verified**: Webster's formula assumes steady demand, and these real flows are
  not steady. Jinan's arrivals fall from 937 vehicles in the first 10 minutes to 500 in the
  last; Hangzhou's peak in minutes 10–20 (659 vs 424–514 in the others). A fixed plan cannot
  follow that, while MaxPressure reacts to the queues. The Indian 2x2 flows have steady
  Poisson demand, the setting Webster was derived for (results in `docs/indian_scenario.md`).
* **On Indian 2x2 the picture differs.** Demand is steady and heavier, so at peak C0 is
  84–91 s and the splits follow demand (E–W straight 25–30 s, N–S straight 18–23 s, both
  protected-turn phases at the 10 s minimum). There the Webster plan beats MaxPressure (next section).

## 3. All baselines on all datasets

ATT (s), mean over seeds 0, 1, 2; the best per column in bold. Full tables: section 2 above
(Jinan, Hangzhou) and `docs/indian_scenario.md` (Indian 2x2, with queue, waiting time,
throughput and backlog).

<!-- BEGIN:overview -->
| Controller (ATT, s) | jinan_3x4 | hangzhou_4x4 | indian_2x2_offpeak | indian_2x2_peak |
|---|---|---|---|---|
| FixedTime, 4 paired phases, 30 s | 423.0 | 580.6 | 121.5 | 279.9 |
| FixedTime, Webster plan | 416.1 | 549.8 | 100.4 | **116.3** |
| MaxPressure, 15 s (tuned default) | 297.0 | 334.3 | **81.3** | 133.8 |
| MaxPressure, 5 s | **295.9** | **331.1** | 82.0 | 142.4 |
<!-- END:overview -->

* **No single baseline is best everywhere.** MaxPressure is best on Jinan, Hangzhou and
  Indian off-peak. At Indian peak the Webster plan is best (116.3 s, against 133.8 s for the
  tuned MaxPressure), ahead on every seed.
* At Indian peak the Webster plan also matches the best MaxPressure setting of the sweep
  (10 s and 20 s intervals, about 116 s), which the pre-registered rule did not choose.
  The explanation in section 1 applies: near the capacity of the switching pattern, fewer
  switches (less time in 5 s transitions) win. It is likely, but **not verified**, that a
  MaxPressure with a longer minimum green would close this gap.
* **For the LLM comparison:** the LLM controller should be compared with the best baseline
  per scenario and level, not only with MaxPressure. At Indian peak that is the Webster plan,
  which also has an unfair advantage: perfect counts of steady demand.
