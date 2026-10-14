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
