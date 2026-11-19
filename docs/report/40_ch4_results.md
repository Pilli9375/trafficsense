# Results and Discussions {#sec:results}

This chapter reports the results in the order the experiments were run: the tuning of the classical
baselines, the LLM benchmark that selected the controller, the full experiments, the ambulance
experiment, the exploratory model-size study, the camera-error experiment, the detector and the
dashboard. It then discusses what the results mean and what limits them. Every table in this chapter
is generated from the result files; the per-run tables, the design rounds and the other tables
behind these summaries are in `docs/report/extended/03_results_full.md` and
`07_full_tables.md` of <https://github.com/Pilli9375/trafficsense>.

## Baselines and Their Tuning {#sec:baselines}

An LLM controller should be compared with baselines that are as good as they can reasonably be, fixed
before the comparison. Three classical controllers were used: **FixedTime**, the 4 paired phases with
30<!--=cfg.ft.green--> s of green each (the naive plan); **Webster fixed time**, the same phases with a
cycle and splits computed per intersection by Webster's method from saturation flows measured on the
network and from the run's own flow file, a perfect count of the simulated hour that favours Webster,
since a real plan is built from older counts; and **MaxPressure**, all 8 green phases.

MaxPressure's timing was tuned in two sweeps on four scenarios (Jinan, Hangzhou, Indian off-peak and
peak; 3 seeds each), with selection rules committed before the runs: rank the settings by mean travel
time in each scenario, choose the lowest mean rank, break ties by the lowest mean ratio to the best.
The first sweep showed that what really changed was the shortest possible green, so the second fixed
the interval at 5 s and varied the minimum green (@tbl:mg-selection). A minimum green of
15<!--=mg.chosen--> s was chosen through the tie-break: the 10 s setting is best on three scenarios but
last at Indian peak. The reason is the transition: with a 10 s minimum green, 32.4<!--=i.peak.maxpressure_5s.transition-->%
of each intersection's time at peak is transition, against 24.7<!--=i.peak.maxpressure.transition-->%
with 15<!--=cfg.mp.min_green--> s. In light traffic reacting quickly wins; near capacity the green lost
to transitions costs more. No setting is best at both levels, and the pre-registered rule chose the
compromise.

::: {#tbl:mg-selection short="Pre-registered selection of MaxPressure's minimum green"}
<!-- BEGIN:tab_mg_selection -->
| Min green | Jinan | Hangzhou | Off-peak | Peak | Mean rank | Mean ATT / best | Chosen |
|------------|-----------:|--------------:|--------------:|----------:|----------:|-----------:|-------------|
| 10 s | 1 | 1 | 1 | 4 | 1.75 | 1.058 |  |
| 15 s | 2 | 2 | 2 | 1 | 1.75 | 1.026 | chosen |
| 20 s | 3 | 3 | 3 | 2 | 2.75 | 1.072 |  |
| 25 s | 4 | 4 | 4 | 3 | 3.75 | 1.139 |  |
<!-- END:tab_mg_selection -->

: Pre-registered selection of MaxPressure's minimum green (decision interval 5 s): rank of each
setting by mean travel time per scenario, mean rank, and the tie-break.
:::

On the Indian network (@tbl:full-summary below) MaxPressure is clearly best off-peak. At peak the
tuned MaxPressure and the Webster plan are effectively tied (115.5<!--=i.peak.maxpressure.att--> s and
116.3<!--=i.peak.fixedtime_webster.att--> s), and the 30<!--=cfg.ft.green--> s FixedTime no longer drains:
about 308<!--=i.peak.fixedtime.backlog--> vehicles are still waiting to enter at the end of the hour.
This tie matters for reading the LLM results: at peak, "as good as MaxPressure" is also "as good as a
well-timed fixed plan".

## LLM Benchmark and the Design Rounds {#sec:res-bench}

Each LLM arm was benchmarked on the same 600<!--=b.steps--> s of Indian peak traffic (seed 0) with up
to four local models (`llama3.2:3b` [@grattafiori2024llama3], `qwen2.5:3b` [@qwen2024qwen25], and
Google's `gemma3:4b` and `gemma4:e4b`), and the pre-registered rule (@sec:prereg) was applied
(@fig:bench).

![Mean queue per intersection over the first 600<!--=b.steps--> s of Indian peak traffic for every arm
and model, against MaxPressure (blue line). gemma3:4b, run only in v1, is in the extended
tables.](figures/bench.png){#fig:bench short="LLM benchmark: mean queue of every arm and model" width=78%}

**Round 1 (prompt v1).** No model met the rule. `qwen2.5:3b` was just too slow (95th-percentile
latency 3.34<!--=b.v1.qwen2.5:3b.p95--> s against the 3<!--=b.rule.p95_s--> s limit), `llama3.2:3b`
failed 6.2<!--=b.v1.llama3.2:3b.fail-->% of its calls with over-long reasons, and both Gemma models
were slower still. Every model controlled traffic much worse than MaxPressure (queues of
19<!--=b.v1.gemma4:e4b.queue-->–46<!--=b.v1.gemma3:4b.queue--> vehicles per intersection against
11.85<!--=b.base.maxpressure.queue-->); `gemma3:4b` did not fit the 4 GB card and was dropped. Latency
was mostly the time to read the long prompt, so the next prompt was made much shorter.
**Round 2 (prompt v2 and the hybrid).** Prompt v2 gave each phase its pressure and queue directly, in
about 285<!--=docs/llm_benchmark.md | llm_benchmark | v2 & llama3.2:3b | Prompt tokens--> tokens instead
of 654<!--=docs/llm_benchmark.md | llm_benchmark | v1 & llama3.2:3b | Prompt tokens-->. The decision
logs showed that, given pressures, the small models **preferred low pressure**: in the hybrid arm
every model chose the lowest-pressure option in
77<!--=docs/llm_benchmark.md | llm_decisions | hybrid (guided) & qwen2.5 | lowest-pressure-->–86<!--=docs/llm_benchmark.md | llm_decisions | hybrid (guided) & llama3.2 | lowest-pressure-->%
of the calls where the options differed, and their reasons said so ("Low pressure, minimal queue
impact"). The prompts defined pressure but never said which direction is better.
**Final round (prompt v3, pre-registered as final).** Two lines were changed: the definition of
pressure now ends "HIGHER pressure = the phase needs green MORE", and a placeholder that one model had
copied into its answers was removed. The fix changed `gemma4:e4b`, which in hybrid_v3 chose the
highest-pressure option in 78<!--=docs/llm_benchmark.md | llm_decisions | hybrid_v3 (guided_v3) & gemma4 | highest-pressure-->%
of its calls, but not the two 3B models (@tbl:bench-final).

::: {#tbl:bench-final short="LLM benchmark, final round"}
<!-- BEGIN:tab_bench_final -->
| Arm | Model | Failures | Latency p95 (s) | Queue / int. (veh) | ATT at 600 s (s) | Eligible |
|---------------|---------------------|-------------------:|-----------:|---------:|---------:|-------------|
| v3 | `gemma4:e4b` | 0.0% (none) | 5.22 | 15.12 | 103.1 | no |
| v3 | `llama3.2:3b` | 0.0% (none) | 1.40 | 36.62 | 163.5 | yes |
| v3 | `qwen2.5:3b` | 1.4% (reason_too_long 5) | 1.53 | 33.67 | 156.1 | yes |
| hybrid_v3 | `gemma4:e4b` | 0.0% (none) | 4.80 | 12.46 | 93.6 | no |
| hybrid_v3 | `llama3.2:3b` | 0.0% (none) | 1.19 | 28.34 | 140.8 | yes |
| hybrid_v3 | `qwen2.5:3b` | 7.7% (reason_too_long 21) | 1.32 | 21.44 | 120.0 | no |
| guarded_v3 | `gemma4:e4b` | 0.0% (none) | 4.81 | 11.56 | 91.6 | no |
| guarded_v3 | `llama3.2:3b` | 0.0% (none) | 1.18 | 11.62 | 92.2 | yes |
| guarded_v3 | `qwen2.5:3b` | 10.2% (reason_too_long 13) | 1.23 | 11.85 | 92.5 | no |
<!-- END:tab_bench_final -->

: LLM benchmark, final round: Indian 2x2 peak, seed 0, first 600<!--=b.steps--> s. MaxPressure on the
same traffic: queue 11.85<!--=b.base.maxpressure.queue--> vehicles per intersection, ATT
92.5<!--=b.base.maxpressure.att--> s. Eligible = failure rate and latency within the pre-registered
limits. The earlier rounds are in the extended tables.
:::

**Selection.** By the pre-registered rule the final round selected **`llm_guarded_mp` with
`llama3.2:3b`** and a decision interval of 5 s (95th-percentile latency times four intersections:
4.7<!--=b.final.round_p95x4--> s). Its benchmark queue, 11.62<!--=b.guarded_v3.llama3.2:3b.queue-->, was
slightly below MaxPressure's, but the guard had replaced most of the model's answers: the applied phase
differed from MaxPressure's in only 15<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Guard replaced | 2--> of
121<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Guard replaced | 3--> decisions.
As pre-registered, this controller went to the full experiments whatever its benchmark result, and
design work on the LLM controller stopped. The best-performing LLM-led controller, `gemma4:e4b`, was
not eligible because of its latency (95th percentile 4.80<!--=b.hybrid_v3.gemma4:e4b.p95--> s).

## Full Experiments {#sec:res-main}

@tbl:full-summary and @fig:att give the results of the full experiments: the Indian 2x2 network at
off-peak and peak demand, and Jinan 3x4 with CoLLMLight's real-world flow, three seeds each.

::: {#tbl:full-summary short="Full experiments: ATT of every controller"}
<!-- BEGIN:tab_full_summary -->
| Controller | Off-peak: ATT (s) (vs MaxPressure) | Peak: ATT (s) (vs MaxPressure) | Jinan 3x4: ATT (s) (vs MaxPressure) |
|------------------------------|--------------------------:|--------------------:|--------------------:|
| MaxPressure | 88.1 ± 1.0 (+0.0%) | 115.5 ± 0.9 (+0.0%) | 300.9 ± 0.0 (+0.0%) |
| Webster fixed time | 100.4 ± 4.1 (+13.9%) | 116.3 ± 4.6 (+0.7%) | 416.1 ± 0.0 (+38.3%) |
| FixedTime (4 phases, 30 s) | 121.5 ± 0.2 (+37.8%) | 279.9 ± 9.9 (+142.3%) | 423.0 ± 0.0 (+40.6%) |
| LLM, pre-registered (guarded, `llama3.2:3b`) | 89.0 ± 0.8 (+0.9%) | 116.1 ± 2.9 (+0.5%) | 303.2 ± 1.1 (+0.8%) |
| LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 90.5 ± 1.2 (+2.7%) | 113.7 ± 0.3 (-1.5%) | not run |
<!-- END:tab_full_summary -->

: Average travel time, mean ± std over seeds 0–2, 3600<!--=cfg.steps--> s, with the change against
MaxPressure in brackets. Off-peak is 2375<!--=cal.offpeak--> veh/h and peak 4750<!--=cal.peak--> veh/h.
The Jinan flow file is fixed, so the deterministic baselines are identical on every seed. Queue,
waiting time and throughput are in the extended tables.
:::

![Average travel time of every controller in the three scenarios (mean ± std over three seeds). The
two LLM arms are close to MaxPressure everywhere; FixedTime fails at
peak.](figures/att.png){#fig:att short="Average travel time of every controller" width=82%}

**The pre-registered controller matches MaxPressure but does not beat it.** Its ATT is
+0.9<!--=f.off.llm.vs_mp-->% off-peak, +0.5<!--=f.peak.llm.vs_mp-->% at peak and
+0.8<!--=f.jinan.llm.vs_mp-->% on Jinan relative to MaxPressure. Paired by seed (@tbl:paired), it is
behind MaxPressure on all 3<!--=p.off.llm.higher--> off-peak seeds, all 3<!--=p.jinan.llm.higher--> Jinan
seeds and 2<!--=p.peak.llm.higher--> of the 3 peak seeds, by
0.2<!--=p.off.llm.s2-->–3.5<!--=p.jinan.llm.s0--> s.

::: {#tbl:paired short="Paired comparison with MaxPressure"}
<!-- BEGIN:tab_paired -->
| Scenario | Controller | ATT minus MaxPressure, per seed (s) | Seeds lower / higher than MaxPressure |
|-----------------------|--------------------------|--------------------------|--------------------------|
| Indian 2x2 off-peak | LLM, pre-registered (guarded, `llama3.2:3b`) | +0.92 / +1.36 / +0.18 | 0 lower, 3 higher of 3 |
| Indian 2x2 off-peak | LLM, exploratory (hybrid_v3, `gemma4:e4b`) | +2.30 / +2.09 / +2.70 | 0 lower, 3 higher of 3 |
| Indian 2x2 peak | LLM, pre-registered (guarded, `llama3.2:3b`) | +0.81 / +2.42 / -1.63 | 1 lower, 2 higher of 3 |
| Indian 2x2 peak | LLM, exploratory (hybrid_v3, `gemma4:e4b`) | -2.61 / -2.15 / -0.61 | 3 lower, 0 higher of 3 |
| Jinan 3x4 | LLM, pre-registered (guarded, `llama3.2:3b`) | +3.52 / +1.96 / +1.35 | 0 lower, 3 higher of 3 |
| Peak + ambulances | Preemption (rule-based) | +1.33 / +0.01 / -1.71 / +3.18 / -1.28 | 2 lower, 3 higher of 5 |
| Peak + ambulances | LLM, pre-registered (guarded, `llama3.2:3b`) | +6.72 / +1.31 / -0.50 / +0.92 / -5.03 | 2 lower, 3 higher of 5 |
| Peak + ambulances | LLM, exploratory (hybrid_v3, `gemma4:e4b`) | +1.85 / -3.43 / -6.23 / -0.80 / -5.73 | 4 lower, 1 higher of 5 |
<!-- END:tab_paired -->

: Paired comparison: each arm's ATT minus MaxPressure's on the same seed.
:::

**Why so close: the guard does most of the work.** The model's own answer differs from MaxPressure's
choice in 87<!--=l.amb.llm.differs-->–93<!--=l.peak.llm.differs-->% of calls, but the guard replaces
most of these answers (76<!--=l.amb.llm.guard-->–83<!--=l.peak.llm.guard-->% of calls), so the applied
phase differs from MaxPressure's in only 10<!--=l.peak.llm.applied-->–11<!--=l.jinan.llm.applied-->% of
calls. Every remaining difference is a decision the guard judged "close enough", and on average those
cost a little. The arm never failed a call off-peak or at peak and runs in real time: mean latency
1.02<!--=l.peak.llm.lat-->–1.10<!--=l.jinan.llm.lat--> s per call for a 5 s decision interval.

**The exploratory `gemma4:e4b` arm** is the only LLM arm that beats MaxPressure anywhere, and only
under heavy traffic. At peak its ATT is lower on all 3<!--=p.peak.gem.lower--> seeds (paired differences
−0.6<!--=p.peak.gem.s2--> to −2.6<!--=p.peak.gem.s0--> s, −1.5<!--=f.peak.gem.vs_mp-->% on the mean);
off-peak it is worse on every seed (+2.7<!--=f.off.gem.vs_mp-->%). It departs from MaxPressure more
off-peak (32.0<!--=l.off.gem.applied-->% of calls) than at peak (20.9<!--=l.peak.gem.applied-->%), and
off-peak those departures cost time. With three seeds and no significance test this is a lead, not a
demonstrated improvement. The arm is also not real-time on this GPU: 4.54<!--=l.peak.gem.lat--> s per
call on average, so an hour of traffic took 3.2<!--=l.peak.gem.wall_h--> hours over three seeds, against
0.6<!--=l.peak.llm.wall_h--> hours for the main arm.

## Ambulances {#sec:res-amb}

The emergency experiment is peak traffic plus ambulances, seeds 0–4; the primary metric is the mean
travel time of the 29<!--=e.mp.amb_n--> signal-relevant ambulances (@tbl:ambulances, @fig:ambulance).

::: {#tbl:ambulances}
<!-- BEGIN:tab_ambulances -->
| Controller | Finished | Travel time (s) | Median (s) | Stopped (s) | Per ambulance vs preemption (s) |
|-------------------------|-------------:|-----------:|-----------:|------------:|-------------------------|
| MaxPressure | 29 / 29 | 130.1 | 126.0 | 62.3 | 48.9 (1 faster, 28 slower of 29) |
| Webster fixed time | 29 / 29 | 123.5 | 123.0 | 55.0 | 42.3 (4 faster, 25 slower of 29) |
| MaxPressure + preemption | 29 / 29 | 81.2 | 80.0 | 14.1 | – |
| LLM, pre-registered (guarded, `llama3.2:3b`) | 29 / 29 | 88.9 | 87.0 | 21.2 | 7.7 (12 faster, 15 slower of 29) |
| LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 29 / 29 | 82.2 | 78.0 | 15.3 | 1.1 (16 faster, 12 slower of 29) |
<!-- END:tab_ambulances -->

: Signal-relevant ambulances, pooled over seeds 0–4. The last column compares each ambulance with
the same ambulance under rule-based preemption.
:::

**Both LLM arms get most of the benefit of preemption.** Mean ambulance travel time is
130.1<!--=e.mp.amb--> s under MaxPressure and 123.5<!--=e.web.amb--> s under the Webster plan, which
ignore ambulances; 88.9<!--=e.llm.amb--> s under the pre-registered LLM arm; and
81.2<!--=e.pre.amb--> s under rule-based preemption. The difference comes almost entirely from time
spent stopped: 62.3<!--=e.mp.amb_stop--> s under MaxPressure, 21.2<!--=e.llm.amb_stop--> s under the main
LLM arm. Ambulance by ambulance, the main arm is 7.7<!--=e.llm.vs_pre--> s slower than preemption on
average (12<!--=e.llm.vs_pre_faster--> faster, 15<!--=e.llm.vs_pre_slower--> slower); the exploratory
`gemma4:e4b` arm is only 1.1<!--=e.gem.vs_pre--> s slower. Part of the main arm's benefit is by design:
a phase serving a listed ambulance is exempt from the guard. **Normal traffic does not pay for the
priority:** network ATT under the main arm is 116.4<!--=e.llm.att--> s against MaxPressure's
115.7<!--=e.mp.att--> s, well inside the seed-to-seed spread (±2.3<!--=e.mp.att_sd--> s).

![Mean travel time of the signal-relevant ambulances, split into time stopped (solid) and time
moving (light).](figures/ambulance.png){#fig:ambulance short="Travel time of the signal-relevant ambulances" width=78%}

## Model Size (Exploratory) {#sec:res-size}

*Exploratory, planned after the main results.* With the controller fixed to the unguarded hybrid
(hybrid_v3), only the model was changed, from 3B local models to a hosted 550<!--=m.size.nemo--> B
mixture-of-experts model (Nemotron 3 Ultra [@nemotron3ultra], 55<!--=m.active.nemo--> B parameters
active per token); @tbl:model-size and @fig:model-size give the results.

::: {#tbl:model-size short="Exploratory model-size study"}
<!-- BEGIN:tab_model_size -->
| Model | Total params (B) | ATT (s), mean ± std | ATT vs MaxPressure, mean (range over seeds) | Seeds worse than MaxPressure | Follows pressure | Answer differs from MaxPressure | Failed calls |
|------------------|-------:|----------:|----------------|----------:|--------:|----------:|----------------|
| `qwen2.5:3b` | 3.1 | 174.4 ± 2.8 | +51.0% (+47.6 to +53.5) | 3 of 3 | 17% | 83% | 308 of 5229 (5.9%): reason_too_long 308 |
| `llama3.2:3b` | 3.2 | 209.6 ± 8.9 | +81.4% (+74.1 to +86.1) | 3 of 3 | 2% | 99% | 0 of 5393 (0.0%) |
| `gemma4:e4b` | 7.5 | 113.7 ± 0.3 | -1.5% (-2.2 to -0.5) | 0 of 3 | 80% | 21% | 3 of 2541 (0.1%): reason_too_long 3 |
| `llama3.1:8b` | 8 | 117.1 ± 2.6 | +1.4% (-1.4 to +4.3) | 2 of 3 | 62% | 43% | 0 of 2207 (0.0%) |
| nemotron-3-ultra-550b | 550 | 114.8 ± 3.6 | -0.6% (-3.1 to +3.9) | 1 of 3 | 99% | 2% | 39 of 2205 (1.8%): retries_exhausted 37, timeout 2 |
| MaxPressure (baseline) | – | 115.5 ± 0.9 | +0.0% | – | – | – | – |
<!-- END:tab_model_size -->

: Exploratory model-size study, Indian 2x2 peak, 3 seeds. "Follows pressure" = share of answers
that are the highest-pressure option. Failed calls apply MaxPressure's choice.
:::

![Exploratory: the same hybrid controller with five models. Left: ATT relative to MaxPressure at
peak (dot: mean; bar: range over seeds). Right: mean travel time of the 29<!--=e.mp.amb_n--> signal-relevant
ambulances. Grey: models worse than MaxPressure on every seed.](figures/model_size.png){#fig:model-size short="Exploratory: one hybrid controller with five models" width=88%}

Below some size the LLM makes the hybrid controller worse: with either 3B model it is far behind
MaxPressure on every seed (ATT +51.0<!--=m.peak.qwen.vs_mp-->% and +81.4<!--=m.peak.llama3b.vs_mp-->%
at peak), because without the guard their preference for keeping the current phase is applied. From
`gemma4:e4b` upwards ATT is MaxPressure's within seed noise; only gemma4 is better on every peak
seed. Following pressure grows with size, but not strictly with parameter count:
`gemma4:e4b` follows it in 80<!--=m.peak.gem.follows-->% of calls, `llama3.1:8b` in
62<!--=m.peak.llama8b.follows-->%, the hosted model in 99<!--=m.peak.nemo.follows-->%, so away from
ambulances it nearly copies MaxPressure; model family and training matter as much as size. Ambulances
show the clearest effect of size: `gemma4:e4b` and the hosted model bring the signal-relevant
ambulances through about as fast as preemption, without preempting (the per-model table is in the
extended material). The hosted model's runs depended on an API that throttled the account heavily:
calls that ran out of retries were counted as failures and fell back to MaxPressure's choice, and its
prompts leave the machine, so it is not an on-device option.

## Camera Errors {#sec:res-camera}

The camera-error experiment repeated the main comparisons with the controllers' counts degraded by the
detector's measured errors (@sec:perception), while the simulator stayed exact and ambulance positions
were not noised (GPS / V2X assumption). @tbl:camera-summary and @fig:camera give the main block.

::: {#tbl:camera-summary short="Camera errors: ATT and its paired change"}
<!-- BEGIN:tab_camera_summary -->
| Controller | Counts | Off-peak: ATT (s) | Off-peak: change vs perfect | Peak: ATT (s) | Peak: change vs perfect |
|-----------------------|-------------|--------------:|----------------:|--------------:|----------------:|
| MaxPressure | perfect | 88.1 ± 1.0 | – | 115.5 ± 0.9 | – |
|  | junction | 92.4 ± 0.5 | +4.3 s (+4.8%) | 118.2 ± 1.8 | +2.7 s (+2.3%) |
|  | crowded | 95.4 ± 1.7 | +7.3 s (+8.2%) | 120.6 ± 1.4 | +5.1 s (+4.4%) |
| Webster fixed-time | perfect | 100.4 ± 4.1 | – | 116.3 ± 4.6 | – |
|  | junction | 100.4 ± 4.1 | +0.0 s (+0.0%) | 116.3 ± 4.6 | +0.0 s (+0.0%) |
|  | crowded | 100.4 ± 4.1 | +0.0 s (+0.0%) | 116.3 ± 4.6 | +0.0 s (+0.0%) |
| LLM arm (guarded llama3.2:3b) | perfect | 89.0 ± 0.8 | – | 116.1 ± 2.9 | – |
|  | junction | 93.5 ± 0.6 | +4.5 s (+5.1%) | 117.9 ± 1.7 | +1.8 s (+1.6%) |
|  | crowded | 95.3 ± 0.3 | +6.4 s (+7.2%) | 121.7 ± 1.2 | +5.6 s (+4.9%) |
<!-- END:tab_camera_summary -->

: Camera errors, Indian 2x2, 3 seeds: ATT and its paired change against perfect counts on the same
seed. "junction" and "crowded" are the two camera levels of @sec:perception.
:::

![Left and centre: paired change in ATT against perfect counts for each controller and camera level
(bar: range over seeds). Right: MaxPressure with only missed vehicles (uniform detection probability,
line) and with the camera levels (markers) at their effective detection
rates.](figures/camera.png){#fig:camera short="Paired ATT change under camera errors" width=88%}

**Every count-based controller gets slower.** With the junction camera MaxPressure's ATT rises by
4.8<!--=c.off.mp.junction.pct-->% off-peak and 2.3<!--=c.peak.mp.junction.pct-->% at peak, and with
crowded / far detection by 8.2<!--=c.off.mp.crowded.pct-->% and 4.4<!--=c.peak.mp.crowded.pct-->%; every
seed is worse. The LLM arm degrades by about as much (junction +5.1<!--=c.off.llm.junction.pct-->% /
+1.6<!--=c.peak.llm.junction.pct-->%), as expected, since the guard's pressures come from the same noisy
counts. The Webster plan is unaffected: it never reads counts. At peak the advantage of adaptive
control disappears: with junction-camera counts MaxPressure's mean ATT
(118.2<!--=c.peak.mp.junction.att--> s) falls behind Webster's (116.3<!--=c.peak.web.junction.att--> s).

**Missed vehicles alone cost little.** With half of all vehicles missed and no false detections,
MaxPressure loses only 3.0<!--=c.sweep.off.p50.pct-->% off-peak and 2.4<!--=c.sweep.peak.p50.pct-->% at
peak: when every vehicle is missed with the same probability, every phase's expected pressure shrinks by
the same factor and the ranking is unchanged on average. The junction camera detects
92<!--=c.peff.off.junction.pct-->% of vehicles, yet off-peak it costs
+4.8<!--=c.off.mp.junction.pct-->%, whereas detecting 90<!--=c.sweep.off.p90.level_pct-->% with nothing
else wrong costs 0.0<!--=c.sweep.off.p90.pct-->%. What the camera adds are phantom vehicles: about
0.7<!--=c.phantoms_per_road--> per road and snapshot, all counted as stopped.

**Decomposition (post-hoc).** To test that explanation, the junction level was re-run with one error
component at a time (@tbl:decomposition). Off-peak, false detections alone cost
+3.8<!--=c.dec.false.off.pct-->% of the +4.8<!--=c.dec.all.off.pct-->%, misses
+0.8<!--=c.dec.misses.off.pct-->% and class confusion nearly nothing, and the three add up to the whole
effect. At peak no single component explains the +2.3<!--=c.dec.all.peak.pct-->%: the components sum to
only +0.4<!--=c.dec.sum.peak.pct-->%, so either they interact near capacity or part of the peak effect
is chance; three seeds cannot tell which. Class confusion alone has no measurable effect because these
controllers read class-free counts.

::: {#tbl:decomposition short="Post-hoc decomposition of the junction-camera errors"}
<!-- BEGIN:tab_decomposition -->
| junction-camera errors | Off-peak: ATT vs perfect, paired (s; range; %) | Peak: ATT vs perfect, paired (s; range; %) | realised detection rate | phantoms per road and snapshot |
|------------------------|------------------------|------------------------|-------------:|------------:|
| (a) misses only | +0.7 (-0.6 to +1.7); +0.8% | +0.7 (+0.3 to +1.2); +0.6% | 0.920 | 0.000 |
| (b) false detections only | +3.4 (+2.8 to +3.7); +3.8% | -0.3 (-1.8 to +1.0); -0.3% | 1.000 | 0.688 |
| (c) class confusion only | +0.1 (-1.1 to +1.0); +0.2% | +0.1 (-1.6 to +1.4); +0.1% | 1.000 | 0.000 |
| (d) all (main batch junction level) | +4.3 (+3.7 to +4.7); +4.8% | +2.7 (+1.2 to +4.3); +2.3% | 0.921 | 0.690 |
| sum of (a) + (b) + (c) | +4.3; +4.8% | +0.4; +0.4% |  |  |
<!-- END:tab_decomposition -->

: Post-hoc decomposition of the junction-camera errors (MaxPressure, 3 seeds): one component
switched on at a time. Each component draws its own random numbers, so they need not add up.
:::

**Ambulances under camera errors.** Preemption keeps its advantage
(81.2<!--=c.amb.pre.perfect.amb--> s → 84.5<!--=c.amb.pre.junction.amb--> s) because it reads ambulance
positions from the separate channel. The LLM arm's ambulances are
11.0<!--=c.amb.llm.junction.amb_d--> s slower on average with junction-camera counts, but individual
ambulances move by tens of seconds in either direction between paired runs, so this is not
distinguishable from zero with 29<!--=e.mp.amb_n--> ambulances.

## Detector {#sec:res-detector}

The confidence threshold was chosen on the validation split as the one that maximises the mean F1 over
the 7 classes: 0.3<!--=d.conf--> (mean F1 0.620<!--=d.f1-->). On each test image, detections are matched
greedily to the unmatched ground-truth box with the highest IoU of at least
0.5<!--=d.match_iou-->, ignoring the class: a match with the same class is a true positive, a match with
another class a **confusion**, an unmatched detection a **false detection**, an unmatched box a
**miss**. Confidence intervals come from 1,000<!--=d.bootstrap_reps--> bootstrap resamples of whole
drives, not frames. On the test split the detector reaches mAP50 0.563<!--=d.test.map50--> and mAP50-95
0.375<!--=d.test.map5095--> (validation: 0.602<!--=d.val.map50--> and 0.403<!--=d.val.map5095-->);
@tbl:det-classes gives the per-class numbers. Precision is high (few false detections) and recall is
moderate: the detector undercounts.

::: {#tbl:det-classes short="Detector on the test split, per class"}
<!-- BEGIN:tab_det_classes -->
| Class | Boxes | mAP50 | mAP50-95 | Precision | Recall | Miss rate | False det. / image |
|-----------------|-----------:|----------:|------------:|-------------:|-----------:|----------:|----------:|
| car | 24,843 | 0.637 | 0.442 | 83.9% | 54.9% | 43.2% | 0.222 |
| motorcycle | 25,489 | 0.630 | 0.373 | 81.9% | 56.2% | 43.4% | 0.271 |
| autorickshaw | 7,782 | 0.652 | 0.461 | 82.0% | 56.0% | 40.2% | 0.070 |
| bus | 4,915 | 0.664 | 0.502 | 82.3% | 56.9% | 36.8% | 0.039 |
| truck | 7,077 | 0.576 | 0.412 | 72.9% | 48.3% | 46.3% | 0.079 |
| bicycle | 569 | 0.339 | 0.193 | 61.0% | 24.8% | 55.4% | 0.006 |
| person | 18,078 | 0.444 | 0.241 | 79.1% | 35.5% | 63.6% | 0.149 |
| all | 88,753 | 0.563 | 0.375 |  |  |  |  |
<!-- END:tab_det_classes -->

: Detector on the test split (official IDD validation set), per class. mAP from Ultralytics;
precision, recall, miss rate and false detections from our matching at confidence ≥ 0.3<!--=d.conf-->.
Recall = 1 − miss rate − confusion rate.
:::

**Most misses are small, distant objects.** Small boxes are most of the ground truth, and the detector
misses 59<!--=d.size.motorcycle.small-->–76<!--=d.size.person.small-->% of them, against
1<!--=d.size.autorickshaw.large-->–22<!--=d.size.bicycle.large-->% of large boxes; this is the cost of
running at 640<!--=cfg.imgsz--> pixels. One camera group dominates the test set: the `highquality_16k`
camera supplies 3,633<!--=d.camera.hq.images--> images but 64,381<!--=d.camera.hq.gt--> of the boxes,
74<!--=d.camera.hq.small-->% of them small, so the overall rates mostly describe crowded scenes with
distant objects. Confusions are few and plausible (bicycles are labelled motorcycles; buses, trucks and
auto-rickshaws are confused with each other and with cars), and `person` has the highest miss rate,
partly because pedestrians are small and possibly because the model was taught not to fire on riders.
The miss rate by size and class is in the extended tables.

## Dashboard {#sec:res-dashboard}

The dashboard (@sec:dashboard) presents these results; its four pages are shown in
@fig:screen-overview, @fig:screen-detection, @fig:screen-replay and @fig:screen-results, taken by a
script with the dashboard reading the committed result files.

![Dashboard, Overview page. The headline is the pre-registered arm's ambulance result; exploratory
numbers are labelled as such.](figures/screen_overview.png){#fig:screen-overview short="Dashboard, Overview page" width=66%}

![Dashboard, Live Detection page: the trained detector on a clip of IDD test frames, with boxes,
per-class counts and the measured speed on the GTX 1650.](figures/screen_detection.png){#fig:screen-detection short="Dashboard, Live Detection page" width=66%}

![Dashboard, Network Replay page: MaxPressure (left) and the pre-registered LLM arm (right) on the
same traffic, one ambulance's trip. Replays re-drive the simulator with each run's logged decisions and
are kept only if they reproduce the run's metrics exactly.](figures/screen_replay.png){#fig:screen-replay short="Dashboard, Network Replay page" width=66%}

![Dashboard, Results page, Signal control tab (Indian 2x2 peak): average travel time of each controller
and the paired comparison by seed, labelled as pre-registered and without a significance
test.](figures/screen_results.png){#fig:screen-results short="Dashboard, Results page" width=66%}

## Discussion {#sec:discussion}

**Why the LLM agents match MaxPressure but do not beat it.** Three observations explain the main
result. First, an LLM that reads pressure correctly becomes MaxPressure: in the hybrid controllers the
LLM is shown the same information MaxPressure uses, and the largest model tested, the hosted Nemotron 3
Ultra, chose the highest-pressure option in 99<!--=m.peak.nemo.follows-->% of its calls, with an ATT
within seed noise of MaxPressure's (@sec:res-size). For steady demand on a small grid, serving the
largest pressure is close to the best a one-step rule can do; to beat it an agent must use information
MaxPressure does not have, or plan over more than one decision, and neither was asked of the agents in
the pre-registered design. Second, small models misread the task: with prompts v2 and guided, the 3B
models treated low pressure as good and kept the current phase, and the v3 fix changed `gemma4:e4b` but
not them, so without a guard the controller is far worse than MaxPressure (@tbl:model-size). Third, the
guard converts a poor model into MaxPressure with noise: the pre-registered controller's answers differ
from MaxPressure's in about nine of ten calls, but the guard replaces most of them, and what remains are
choices within 20<!--=cfg.guard.margin-->% of the top pressure, which off-peak cost a little on every
seed. The guard made the LLM safe to deploy, not useful. For `gemma4:e4b`, faster on every peak seed, we
have not identified the mechanism; one untested hypothesis is that its departures keep a phase still
discharging a long queue, avoiding a transition.

**Why the LLM agents help ambulances.** This is the one case where the agent has information
MaxPressure lacks: the prompt lists each approaching ambulance, its distance and the phases that serve
it. A one-sentence instruction was enough to cut ambulance travel time by
31.7<!--=e.llm.amb_cut_vs_mp-->% compared with MaxPressure, mostly by removing time stopped at a red; the
serving phase is always among the options and is exempt from the guard. A hand-written preemption rule
did slightly better, so for a single, well-defined rule a rule is simpler, faster and verifiable. The case
for an LLM agent is flexibility, not performance: the same mechanism could carry rules that are awkward to
hard-code, such as a road closure or a school zone, but this project tested only the ambulance case.

**What the camera study means.** Adaptive control is only as good as its counts: with a real detector's
errors every count-based controller lost a few percent, and at peak its advantage over a well-timed fixed
plan disappeared. Three lessons follow. False detections hurt more than misses: missing vehicles uniformly
scales every pressure down, while a phantom vehicle adds pressure where there is none, so for signal
control precision matters more than recall, and temporal smoothing should help (each snapshot here is
independent, the worst case). Camera placement matters: the junction level costs about half as much as the
crowded / far level. And a fixed plan is a robust fallback where detection is unreliable, at night or in
heavy rain. These conclusions rest on a proxy, the detector's errors on dash-camera images.

**Relation to the base paper.** CoLLMLight reports that cooperative LLM agents outperform existing
methods. Our results neither confirm nor contradict that claim, because the settings differ: it fine-tunes
its model and uses an asynchronous reasoning architecture, while we used small models as released; we
compared against baselines tuned on the test networks; its FixedTime baseline does not serve north–south
traffic; and its metric definitions differ from CityFlow's. What our results do show is that, without
fine-tuning, a 3–4 B model is not enough to improve on a tuned MaxPressure, and that the clearest value of
an LLM agent appears when it is given information a classical controller cannot use.

## Threats to Validity {#sec:threats}

**Internal validity.** Three seeds per scenario (five with ambulances) are few, and no significance test
was pre-registered; differences of one or two percent are within seed noise and are reported as such. LLM
runs are not bit-for-bit repeatable on the GPU, although every decision is logged and replayable. Prompt
v3 was a post-hoc fix, the `gemma4:e4b` arm and the model-size study were added after the plans were
fixed, and the camera decomposition was post-hoc; all are labelled. The hosted model's runs were affected
by heavy API throttling, which turned some decisions into MaxPressure fallbacks.
**Construct validity.** ATT counts time spent waiting to enter the network, which penalises controllers
that block entries; this is intended but makes ATT differ from definitions used elsewhere, including
CoLLMLight's (@sec:simulation). The ambulance metric assumes that nobody yields and that ambulances cannot
overtake, so it measures only what the signal can do. The camera layer draws independent snapshots and does
not model occlusion between lanes or ambulance detection.
**External validity.** CityFlow is lane-based and cannot represent lane-free Indian driving
(@sec:simulation). The Indian network is a 2 × 2 grid with synthetic, steady demand; its vehicle mix comes
from one city in one year; and the turning shares are assumptions. Jinan provides one real-world flow.
Latencies are specific to a GTX 1650. The results show what a small local model does on this network; they
do not show how a deployed system would perform on a real junction.
