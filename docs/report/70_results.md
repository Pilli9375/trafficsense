# Results {#sec:results}

This chapter reports the results in the order the experiments were run: the LLM benchmark that
selected the controller, the full experiments, the ambulance experiment, the exploratory
model-size study, and the camera-error experiment. The baselines' tuning and their results on the
Indian network are in @sec:baselines; the detector's evaluation is in @sec:det-eval. Every table
in this chapter is generated from the result files.

## LLM benchmark and the design rounds {#sec:res-bench}

Each LLM arm was benchmarked on the same 600<!--=b.steps--> s of Indian peak traffic (seed 0) with
up to four local models (`llama3.2:3b` from the Llama 3 family [@grattafiori2024llama3], `qwen2.5:3b`
[@qwen2024qwen25], and Google's `gemma3:4b` and `gemma4:e4b`), and the pre-registered rule (@sec:prereg) was applied. @fig:bench and
@tbl:bench summarise all rounds; @tbl:bench-selection gives what the rule chose.

![Mean queue per intersection over the first 600<!--=b.steps--> s of Indian peak traffic for every arm and
model, against MaxPressure (blue line). gemma3:4b, run only in v1, is in @tbl:bench.](figures/bench.png){#fig:bench width=100%}

**Round 1 (prompt v1).** No model met the rule. `qwen2.5:3b` was just too slow
(95th-percentile latency 3.34<!--=b.v1.qwen2.5:3b.p95--> s against the
3<!--=b.rule.p95_s--> s limit) and `llama3.2:3b` failed 6.2<!--=b.v1.llama3.2:3b.fail-->% of its
calls with over-long reasons; both Gemma models were slower still. Every model controlled traffic
much worse than MaxPressure: queues of 19<!--=b.v1.gemma4:e4b.queue-->–46<!--=b.v1.gemma3:4b.queue-->
vehicles per intersection against 11.85<!--=b.base.maxpressure.queue-->. `gemma3:4b` did not fit
in the 4 GB card and was dropped after this round. Latency was mostly the time to read the long
prompt, so the next prompt was made much shorter.

**Round 2 (prompt v2 and the hybrid).** Prompt v2 gave each phase its pressure and queue directly,
in about 285<!--=docs/llm_benchmark.md | llm_benchmark | v2 & llama3.2:3b | Prompt tokens--> tokens instead of about 654<!--=docs/llm_benchmark.md | llm_benchmark | v1 & llama3.2:3b | Prompt tokens-->. The rule then chose `llama3.2:3b`, the only eligible model, which was also the
worst controller of the round (queue 42.26<!--=b.v2.llama3.2:3b.queue-->). The decision logs
showed why: given pressures, the small models **preferred low pressure**. In the hybrid arm, which
offered only MaxPressure's two best phases or keeping the current one, every model chose the
lowest-pressure option in
77<!--=docs/llm_benchmark.md | llm_decisions | hybrid (guided) & qwen2.5 | lowest-pressure-->–86<!--=docs/llm_benchmark.md | llm_decisions | hybrid (guided) & llama3.2 | lowest-pressure-->%
of the calls where the options differed. Their reasons said so directly, for example "Low pressure,
minimal queue impact". The prompts defined pressure but never said which direction is better.

**Final round (prompt v3, pre-registered as final).** Two lines of the prompts were changed: the
definition of pressure now ends "HIGHER pressure = the phase needs green MORE", and the reason
format no longer contains a placeholder that one model had copied into its answers. Three arms
were tested with this prompt: plain v3, hybrid_v3, and guarded_v3, which adds the pressure guard
(@sec:arms). The fix changed `gemma4:e4b`, which in hybrid_v3 chose the highest-pressure option in
78<!--=docs/llm_benchmark.md | llm_decisions | hybrid_v3 (guided_v3) & gemma4 | highest-pressure-->%
of its calls. It did not change the two 3 B models, which still kept the current phase in most
calls.

::: {#tbl:bench}
<!-- BEGIN:tab_bench -->
| Arm | Model | Failures | Latency p95 (s) | Queue / int. (veh) | ATT at 600 s (s) | Eligible |
|--------------|--------------------|----------------------|-----------:|---------:|---------:|------------|
| v1 | `gemma3:4b` | 0.0% (none) | 5.43 | 46.35 | 197.4 | no |
| v1 | `gemma4:e4b` | 0.6% (reason_too_long 1) | 8.36 | 19.44 | 112.2 | no |
| v1 | `llama3.2:3b` | 6.2% (reason_too_long 18) | 3.35 | 40.94 | 181.1 | no |
| v1 | `qwen2.5:3b` | 0.0% (none) | 3.34 | 29.15 | 141.2 | no |
| v2 | `gemma4:e4b` | 0.0% (none) | 5.32 | 17.95 | 111.1 | no |
| v2 | `llama3.2:3b` | 0.3% (reason_too_long 1) | 1.52 | 42.26 | 181.5 | yes |
| v2 | `qwen2.5:3b` | 29.3% (reason_too_long 104) | 1.65 | 31.11 | 146.8 | no |
| hybrid | `gemma4:e4b` | 0.4% (reason_too_long 1) | 4.84 | 23.38 | 125.8 | no |
| hybrid | `llama3.2:3b` | 0.3% (reason_too_long 1) | 1.13 | 26.64 | 135.3 | yes |
| hybrid | `qwen2.5:3b` | 11.2% (reason_too_long 28) | 1.27 | 22.05 | 123.3 | no |
| v3 | `gemma4:e4b` | 0.0% (none) | 5.22 | 15.12 | 103.1 | no |
| v3 | `llama3.2:3b` | 0.0% (none) | 1.40 | 36.62 | 163.5 | yes |
| v3 | `qwen2.5:3b` | 1.4% (reason_too_long 5) | 1.53 | 33.67 | 156.1 | yes |
| hybrid_v3 | `gemma4:e4b` | 0.0% (none) | 4.80 | 12.46 | 93.6 | no |
| hybrid_v3 | `llama3.2:3b` | 0.0% (none) | 1.19 | 28.34 | 140.8 | yes |
| hybrid_v3 | `qwen2.5:3b` | 7.7% (reason_too_long 21) | 1.32 | 21.44 | 120.0 | no |
| guarded_v3 | `gemma4:e4b` | 0.0% (none) | 4.81 | 11.56 | 91.6 | no |
| guarded_v3 | `llama3.2:3b` | 0.0% (none) | 1.18 | 11.62 | 92.2 | yes |
| guarded_v3 | `qwen2.5:3b` | 10.2% (reason_too_long 13) | 1.23 | 11.85 | 92.5 | no |
<!-- END:tab_bench -->

: LLM benchmark, all rounds: Indian 2x2 peak, seed 0, first 600<!--=b.steps--> s. MaxPressure on the same
traffic: queue 11.85<!--=b.base.maxpressure.queue--> vehicles per intersection, ATT 92.5<!--=b.base.maxpressure.att--> s. Eligible = failure rate and latency
within the pre-registered limits.
:::

### Selection {#sec:llm-selection}

By the pre-registered rule the final round selected **`llm_guarded_mp` with `llama3.2:3b`** and a
decision interval of 5 s (95th-percentile latency times four intersections:
4.7<!--=b.final.round_p95x4--> s). Its queue in the benchmark, 11.62<!--=b.guarded_v3.llama3.2:3b.queue-->,
was slightly below MaxPressure's, but the guard had replaced most of the model's answers: the
applied phase differed from MaxPressure's in only 15<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Guard replaced | 2--> of 121<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Guard replaced | 3--> decisions. As pre-registered, this
controller went to the full experiments whatever its benchmark result, and design work on the LLM
controller stopped. The best-performing LLM-led controller, `gemma4:e4b`, was not eligible because
of its latency (95th percentile 4.80<!--=b.hybrid_v3.gemma4:e4b.p95--> s).

::: {#tbl:bench-selection}
<!-- BEGIN:tab_bench_selection -->
| Applied to | Eligible | Chosen | Decision interval |
|-------------------------|-------------------------|-------------------------|-------------------------|
| v1 | none | none | – |
| v2 | llama3.2:3b | llama3.2:3b | 10 s (p95 × intersections = 6.1 s) |
| hybrid | llama3.2:3b | llama3.2:3b | 5 s (p95 × intersections = 4.5 s) |
| v3 | llama3.2:3b, qwen2.5:3b | qwen2.5:3b | 10 s (p95 × intersections = 6.1 s) |
| hybrid_v3 | llama3.2:3b | llama3.2:3b | 5 s (p95 × intersections = 4.8 s) |
| guarded_v3 | llama3.2:3b | llama3.2:3b | 5 s (p95 × intersections = 4.7 s) |
| Phase 3b: all of v1, v2, hybrid | hybrid llama3.2:3b, v2 llama3.2:3b | hybrid llama3.2:3b | 5 s (p95 × intersections = 4.5 s) |
| Final decision (final-round arms) | guarded_v3 llama3.2:3b, hybrid_v3 llama3.2:3b, v3 llama3.2:3b, v3 qwen2.5:3b | guarded_v3 llama3.2:3b (`llm_guarded_mp`); queue 11.62 vs MaxPressure 11.85 | 5 s (p95 × intersections = 4.7 s) |
<!-- END:tab_bench_selection -->

: What the pre-registered rule selected in each round and in the final decision.
:::

## Full experiments {#sec:res-main}

@tbl:full-off, @tbl:full-peak and @tbl:full-jinan give the results of the full experiments, and
@fig:att shows the travel times side by side.

![Average travel time of every controller in the three scenarios (mean ± std over three seeds).
The two LLM arms are close to MaxPressure everywhere; FixedTime fails at peak.](figures/att.png){#fig:att width=100%}

::: {#tbl:full-off}
<!-- BEGIN:tab_full_off -->
| Controller | Seeds | ATT (s) | Queue / int. (veh) | Waiting / vehicle (s) | Finished trips | ATT vs MaxPressure |
|---------------------|--------:|-------------:|--------------:|------------:|------------:|-------------:|
| MaxPressure | 3 | 88.1 ± 1.0 | 4.94 ± 0.23 | 29.8 ± 0.9 | 2332 ± 36 | +0.0% |
| Webster fixed time | 3 | 100.4 ± 4.1 | 6.82 ± 0.52 | 41.1 ± 3.9 | 2320 ± 36 | +13.9% |
| FixedTime (4 phases, 30 s) | 3 | 121.5 ± 0.2 | 10.58 ± 0.17 | 63.7 ± 0.5 | 2316 ± 28 | +37.8% |
| LLM, pre-registered (guarded, `llama3.2:3b`) | 3 | 89.0 ± 0.8 | 5.08 ± 0.18 | 30.6 ± 0.6 | 2327 ± 41 | +0.9% |
| LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 3 | 90.5 ± 1.2 | 5.37 ± 0.28 | 32.3 ± 1.1 | 2323 ± 34 | +2.7% |
<!-- END:tab_full_off -->

: Indian 2x2, off-peak (2375<!--=cal.offpeak--> veh/h), 3600<!--=cfg.steps--> s, mean ± std over seeds 0–2.
:::

::: {#tbl:full-peak}
<!-- BEGIN:tab_full_peak -->
| Controller | Seeds | ATT (s) | Queue / int. (veh) | Waiting / vehicle (s) | Finished trips | ATT vs MaxPressure |
|---------------------|--------:|-------------:|--------------:|-------------:|-----------:|-------------:|
| MaxPressure | 3 | 115.5 ± 0.9 | 17.83 ± 0.32 | 54.1 ± 0.5 | 4576 ± 68 | +0.0% |
| Webster fixed time | 3 | 116.3 ± 4.6 | 18.27 ± 1.28 | 55.4 ± 4.0 | 4577 ± 87 | +0.7% |
| FixedTime (4 phases, 30 s) | 3 | 279.9 ± 9.9 | 44.44 ± 0.75 | 144.0 ± 1.6 | 4166 ± 93 | +142.3% |
| LLM, pre-registered (guarded, `llama3.2:3b`) | 3 | 116.1 ± 2.9 | 17.97 ± 0.85 | 54.5 ± 2.5 | 4582 ± 77 | +0.5% |
| LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 3 | 113.7 ± 0.3 | 17.33 ± 0.44 | 52.6 ± 0.5 | 4577 ± 77 | -1.5% |
<!-- END:tab_full_peak -->

: Indian 2x2, peak (4750<!--=cal.peak--> veh/h), 3600<!--=cfg.steps--> s, mean ± std over seeds 0–2.
:::

::: {#tbl:full-jinan}
<!-- BEGIN:tab_full_jinan -->
| Controller | Seeds | ATT (s) | Queue / int. (veh) | Waiting / vehicle (s) | Finished trips | ATT vs MaxPressure |
|---------------------|--------:|-------------:|--------------:|-------------:|-----------:|-------------:|
| MaxPressure | 3 | 300.9 ± 0.0 | 5.62 ± 0.00 | 55.7 ± 0.0 | 4130 ± 0 | +0.0% |
| Webster fixed time | 3 | 416.1 ± 0.0 | 16.42 ± 0.00 | 162.6 ± 0.0 | 3965 ± 0 | +38.3% |
| FixedTime (4 phases, 30 s) | 3 | 423.0 ± 0.0 | 17.76 ± 0.00 | 176.2 ± 0.0 | 3968 ± 0 | +40.6% |
| LLM, pre-registered (guarded, `llama3.2:3b`) | 3 | 303.2 ± 1.1 | 5.81 ± 0.12 | 57.7 ± 1.2 | 4134 ± 5 | +0.8% |
<!-- END:tab_full_jinan -->

: Jinan 3x4 (CoLLMLight's real-world flow), 3600<!--=cfg.steps--> s, seeds 0–2. The flow file is fixed, so the
deterministic baselines are identical on every seed.
:::

**The pre-registered controller matches MaxPressure but does not beat it.** Its ATT is
+0.9<!--=f.off.llm.vs_mp-->% off-peak, +0.5<!--=f.peak.llm.vs_mp-->% at peak and
+0.8<!--=f.jinan.llm.vs_mp-->% on Jinan relative to MaxPressure. Paired by seed (@fig:paired,
@tbl:paired), it is behind MaxPressure on all 3<!--=p.off.llm.higher--> off-peak seeds, all
3<!--=p.jinan.llm.higher--> Jinan seeds and 2<!--=p.peak.llm.higher--> of the 3 peak seeds, by
0.2<!--=p.off.llm.s2-->–3.5<!--=p.jinan.llm.s0--> s.

![ATT minus MaxPressure's ATT on the same seed, for the two LLM arms. Each dot is one seed; left of
zero is faster than MaxPressure.](figures/paired.png){#fig:paired width=100%}

::: {#tbl:paired}
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

: Paired comparison: each LLM arm's ATT minus MaxPressure's on the same seed.
:::

**Why so close: the guard does most of the work** (@tbl:llm-stats). The model's own answer
differs from MaxPressure's choice in
87<!--=l.amb.llm.differs-->–93<!--=l.peak.llm.differs-->% of calls, but the guard replaces most of
these answers (76<!--=l.amb.llm.guard-->–83<!--=l.peak.llm.guard-->% of calls), so the applied
phase differs from MaxPressure's in only 10<!--=l.peak.llm.applied-->–11<!--=l.jinan.llm.applied-->%
of calls. Every remaining difference is a decision the guard judged "close enough", and on average
those cost a little. The arm never failed a call off-peak or at peak and runs in real time: mean
latency 1.02<!--=l.peak.llm.lat-->–1.10<!--=l.jinan.llm.lat--> s per call for a 5 s decision
interval.

**The exploratory `gemma4:e4b` arm** is the only LLM arm that beats MaxPressure anywhere, and only
under heavy traffic. At peak its ATT is lower on all 3<!--=p.peak.gem.lower--> seeds (paired differences
−0.6<!--=p.peak.gem.s2--> to −2.6<!--=p.peak.gem.s0--> s
(−1.5<!--=f.peak.gem.vs_mp-->% on the mean); off-peak it is worse on every seed
(+2.7<!--=f.off.gem.vs_mp-->%). It departs from MaxPressure more off-peak
(32.0<!--=l.off.gem.applied-->% of calls) than at peak (20.9<!--=l.peak.gem.applied-->%), and
off-peak those departures cost time. With three seeds and no significance test this is a lead, not
a demonstrated improvement. The arm is also not real-time on this GPU: 4.54<!--=l.peak.gem.lat--> s
per call on average, so an hour of traffic took 3.2<!--=l.peak.gem.wall_h--> hours over three seeds,
against 0.6<!--=l.peak.llm.wall_h--> hours for the main arm.

::: {#tbl:llm-stats}
<!-- BEGIN:tab_llm_stats -->
| Scenario | Arm | Calls | Failures | Latency mean (s) | p95 per run (s) | Answer differs from MaxPressure | Guard replaced it | Applied phase differs |
|--------------|----------------|------:|----------------|-------:|--------:|----------:|----------:|-------:|
| Indian 2x2 off-peak | LLM, pre-registered (guarded, `llama3.2:3b`) | 2177 | 0.0% (none) | 1.05 | 1.21–1.22 | 91.5% | 81.2% | 10.4% |
| Indian 2x2 off-peak | LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 2802 | 0.1% (reason_too_long 4) | 4.61 | 4.92–5.02 | 32.1% | – (no guard) | 32.0% |
| Indian 2x2 peak | LLM, pre-registered (guarded, `llama3.2:3b`) | 2167 | 0.0% (none) | 1.02 | 1.19–1.19 | 92.8% | 82.8% | 10.0% |
| Indian 2x2 peak | LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 2541 | 0.1% (reason_too_long 3) | 4.54 | 4.79–4.98 | 20.9% | – (no guard) | 20.9% |
| Jinan 3x4 | LLM, pre-registered (guarded, `llama3.2:3b`) | 6665 | 0.0% (reason_too_long 1) | 1.10 | 1.28–1.36 | 89.0% | 77.8% | 11.1% |
| Peak + ambulances | LLM, pre-registered (guarded, `llama3.2:3b`) | 3632 | 0.0% (none) | 1.06 | 1.24–1.24 | 86.9% | 76.3% | 10.6% |
| Peak + ambulances | LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 4146 | 0.0% (reason_too_long 2) | 4.72 | 5.02–5.15 | 20.4% | – (no guard) | 20.4% |
<!-- END:tab_llm_stats -->

: LLM decision statistics, pooled over the seeds of each scenario. "Answer differs" is over
successful calls; "applied phase differs" over all calls.
:::

## Ambulances {#sec:res-amb}

@tbl:emergency and @tbl:ambulances give the emergency experiment: peak traffic plus
ambulances, seeds 0–4, with the primary metric the mean travel time of the
29<!--=e.mp.amb_n--> signal-relevant ambulances.

::: {#tbl:emergency}
<!-- BEGIN:tab_emergency -->
| Controller | ATT (s) | Queue / int. (veh) | Finished trips |
|----------------------------------|----------------------:|-----------------------:|-------------------:|
| MaxPressure | 115.7 ± 2.3 | 17.97 ± 0.86 | 4605 ± 66 |
| Webster fixed time | 115.2 ± 2.7 | 18.01 ± 0.64 | 4606 ± 73 |
| MaxPressure + preemption | 116.0 ± 0.7 | 18.08 ± 0.41 | 4606 ± 61 |
| LLM, pre-registered (guarded, `llama3.2:3b`) | 116.4 ± 3.1 | 18.16 ± 0.72 | 4604 ± 64 |
| LLM, exploratory (hybrid_v3, `gemma4:e4b`) | 112.9 ± 1.9 | 17.11 ± 0.30 | 4610 ± 70 |
<!-- END:tab_emergency -->

: Emergency scenario, normal traffic: mean ± std over seeds 0–4.
:::

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

**Both LLM arms get most of the benefit of preemption** (@fig:ambulance). Mean ambulance travel
time is 130.1<!--=e.mp.amb--> s under MaxPressure and 123.5<!--=e.web.amb--> s under the Webster
plan, which ignore ambulances; 88.9<!--=e.llm.amb--> s under the pre-registered LLM arm; and
81.2<!--=e.pre.amb--> s under rule-based preemption. The difference comes almost entirely from
time spent stopped: 62.3<!--=e.mp.amb_stop--> s under MaxPressure, 21.2<!--=e.llm.amb_stop--> s
under the main LLM arm. Ambulance by ambulance, the main arm is 7.7<!--=e.llm.vs_pre--> s slower
than preemption on average (12<!--=e.llm.vs_pre_faster--> faster, 15<!--=e.llm.vs_pre_slower-->
slower); the exploratory `gemma4:e4b` arm is only 1.1<!--=e.gem.vs_pre--> s slower. Part of the
main arm's benefit is by design: a phase serving a listed ambulance is exempt from the guard, so
when the model picks it, it is applied.

![Mean travel time of the signal-relevant ambulances, split into time stopped (solid) and time
moving (light).](figures/ambulance.png){#fig:ambulance width=100%}

**Normal traffic does not pay for the priority.** Network ATT under the main arm is
116.4<!--=e.llm.att--> s against MaxPressure's 115.7<!--=e.mp.att--> s, a difference well inside
the seed-to-seed spread (±2.3<!--=e.mp.att_sd--> s).

## Model size (exploratory) {#sec:res-size}

*Exploratory, planned after the main results.* With the controller fixed to the unguarded hybrid
(hybrid_v3), only the model was changed, from 3 B local models to a hosted 550<!--=m.size.nemo--> B
mixture-of-experts model (Nemotron 3 Ultra [@nemotron3ultra], 55<!--=m.active.nemo--> B parameters active per token).
@tbl:model-size and @fig:model-size give the results.

::: {#tbl:model-size}
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
ambulances. Grey: models worse than MaxPressure on every seed.](figures/model_size.png){#fig:model-size width=100%}

1. **Below some size the LLM makes the hybrid controller worse.** With either 3 B model the hybrid
   is far behind MaxPressure on every seed (ATT +51.0<!--=m.peak.qwen.vs_mp-->% and
   +81.4<!--=m.peak.llama3b.vs_mp-->% at peak). Without the guard, their preference for keeping
   the current phase is applied.
2. **From `gemma4:e4b` upwards, ATT is MaxPressure's within seed noise.** `gemma4:e4b`,
   `llama3.1:8b` and the 550<!--=m.size.nemo--> B model are within a few percent of MaxPressure;
   only gemma4 is better on every peak seed.
3. **Following pressure grows with size, but not strictly with parameter count.** `gemma4:e4b`
   follows pressure in 80<!--=m.peak.gem.follows-->% of calls, `llama3.1:8b` in
   62<!--=m.peak.llama8b.follows-->%, the hosted model in 99<!--=m.peak.nemo.follows-->%: away
   from ambulances it nearly copies MaxPressure. Model family and training matter as much as size.
4. **Ambulances show the clearest effect of size** (@tbl:model-size-amb). `gemma4:e4b` and the
   hosted model bring the signal-relevant ambulances through about as fast as preemption, without
   preempting: when an ambulance is in view they leave MaxPressure's choice and give it green.

::: {#tbl:model-size-amb}
<!-- BEGIN:tab_model_size_amb -->
| Controller / model | Signal-relevant ambulances finished | Travel time, mean (s) | Stopped time, mean (s) | vs MaxPressure, paired | vs MaxPressure + preemption, paired |
|----------------------|----------------:|---------:|----------:|--------------------|--------------------|
| `qwen2.5:3b` | 29 of 29 | 148.5 | 77.5 | +18.4 s (11 faster, 18 slower, of 29) | +67.3 s (3 faster, 26 slower, of 29) |
| `llama3.2:3b` | 29 of 29 | 161.8 | 86.4 | +31.7 s (13 faster, 16 slower, of 29) | +80.6 s (5 faster, 24 slower, of 29) |
| `gemma4:e4b` | 29 of 29 | 82.2 | 15.3 | -47.9 s (27 faster, 2 slower, of 29) | +1.1 s (16 faster, 12 slower, of 29) |
| `llama3.1:8b` | 29 of 29 | 97.0 | 29.7 | -33.1 s (23 faster, 6 slower, of 29) | +15.8 s (9 faster, 19 slower, of 29) |
| nemotron-3-ultra-550b | 29 of 29 | 83.4 | 16.5 | -46.7 s (28 faster, 1 slower, of 29) | +2.3 s (14 faster, 14 slower, of 29) |
| MaxPressure (baseline) | 29 of 29 | 130.1 | 62.3 | +0.0 s (0 faster, 0 slower, of 29) | +48.9 s (1 faster, 28 slower, of 29) |
| MaxPressure + preemption (baseline) | 29 of 29 | 81.2 | 14.1 | -48.9 s (28 faster, 1 slower, of 29) | +0.0 s (0 faster, 0 slower, of 29) |
<!-- END:tab_model_size_amb -->

: Exploratory: signal-relevant ambulances under each model (emergency scenario, 5 seeds), paired
with MaxPressure and with preemption.
:::

The hosted model's runs depended on an API that throttled the account heavily during the full
runs: many calls were retried several times, and calls that ran out of retries were counted as
failures and fell back to MaxPressure's choice (Appendix E). Its prompts also leave the machine,
so it is not an on-device option.

## Camera errors {#sec:res-camera}

The camera-error experiment repeated the main comparisons with the controllers' counts degraded by
the detector's measured errors (@sec:error-model), while the simulator stayed exact. Ambulance
positions were not noised (GPS / V2X assumption). @tbl:camera-off and @tbl:camera-peak give the
main block and @fig:camera the paired changes.

::: {#tbl:camera-off}
<!-- BEGIN:tab_camera_off -->
| controller | level | ATT (s) | ATT vs perfect, paired (s; range; %) | queue / int. (veh) | waiting / veh (s) | finished trips |
|-------------------|-----------|------------:|-------------------|------------:|-----------:|-----------:|
| MaxPressure | perfect | 88.1 ± 1.0 | – | 4.94 ± 0.23 | 29.8 ± 0.9 | 2332 ± 36 |
|  | junction | 92.4 ± 0.5 | +4.3 (+3.7 to +4.7); +4.8% | 5.64 ± 0.16 | 33.9 ± 0.4 | 2323 ± 35 |
|  | crowded | 95.4 ± 1.7 | +7.3 (+6.4 to +8.8); +8.2% | 6.15 ± 0.34 | 37.0 ± 1.5 | 2320 ± 38 |
| Webster fixed-time | perfect | 100.4 ± 4.1 | – | 6.82 ± 0.52 | 41.1 ± 3.9 | 2320 ± 36 |
|  | junction | 100.4 ± 4.1 | +0.0 (+0.0 to +0.0); +0.0% | 6.82 ± 0.52 | 41.1 ± 3.9 | 2320 ± 36 |
|  | crowded | 100.4 ± 4.1 | +0.0 (+0.0 to +0.0); +0.0% | 6.82 ± 0.52 | 41.1 ± 3.9 | 2320 ± 36 |
| LLM arm (guarded llama3.2:3b) | perfect | 89.0 ± 0.8 | – | 5.08 ± 0.18 | 30.6 ± 0.6 | 2327 ± 41 |
|  | junction | 93.5 ± 0.6 | +4.5 (+3.8 to +4.9); +5.1% | 5.82 ± 0.21 | 35.0 ± 0.7 | 2321 ± 35 |
|  | crowded | 95.3 ± 0.3 | +6.4 (+5.5 to +7.5); +7.2% | 6.13 ± 0.09 | 36.9 ± 0.4 | 2318 ± 35 |
<!-- END:tab_camera_off -->

: Camera errors, Indian 2x2 off-peak, 3 seeds. The paired change is against perfect counts on the
same seed.
:::

::: {#tbl:camera-peak}
<!-- BEGIN:tab_camera_peak -->
| controller | level | ATT (s) | ATT vs perfect, paired (s; range; %) | queue / int. (veh) | waiting / veh (s) | finished trips |
|-------------------|-----------|------------:|-------------------|-------------:|-----------:|-----------:|
| MaxPressure | perfect | 115.5 ± 0.9 | – | 17.83 ± 0.32 | 54.1 ± 0.5 | 4576 ± 68 |
|  | junction | 118.2 ± 1.8 | +2.7 (+1.2 to +4.3); +2.3% | 18.62 ± 0.21 | 56.5 ± 1.6 | 4584 ± 80 |
|  | crowded | 120.6 ± 1.4 | +5.1 (+3.5 to +7.7); +4.4% | 19.37 ± 0.67 | 58.8 ± 1.4 | 4582 ± 84 |
| Webster fixed-time | perfect | 116.3 ± 4.6 | – | 18.27 ± 1.28 | 55.4 ± 4.0 | 4577 ± 87 |
|  | junction | 116.3 ± 4.6 | +0.0 (+0.0 to +0.0); +0.0% | 18.27 ± 1.28 | 55.4 ± 4.0 | 4577 ± 87 |
|  | crowded | 116.3 ± 4.6 | +0.0 (+0.0 to +0.0); +0.0% | 18.27 ± 1.28 | 55.4 ± 4.0 | 4577 ± 87 |
| LLM arm (guarded llama3.2:3b) | perfect | 116.1 ± 2.9 | – | 17.97 ± 0.85 | 54.5 ± 2.5 | 4582 ± 77 |
|  | junction | 117.9 ± 1.7 | +1.8 (-0.5 to +3.2); +1.6% | 18.52 ± 0.28 | 56.2 ± 1.4 | 4571 ± 77 |
|  | crowded | 121.7 ± 1.2 | +5.6 (+3.6 to +9.6); +4.9% | 19.69 ± 0.74 | 59.7 ± 1.3 | 4577 ± 81 |
<!-- END:tab_camera_peak -->

: Camera errors, Indian 2x2 peak, 3 seeds.
:::

![Left and centre: paired change in ATT against perfect counts for each controller and camera
level (bar: range over seeds). Right: MaxPressure with only missed vehicles (uniform detection
probability, line) and with the camera levels (markers) at their effective detection
rates.](figures/camera.png){#fig:camera width=100%}

* **Every count-based controller gets slower.** With the junction camera MaxPressure's ATT rises
  by 4.8<!--=c.off.mp.junction.pct-->% off-peak and 2.3<!--=c.peak.mp.junction.pct-->% at peak, and
  with crowded / far detection by 8.2<!--=c.off.mp.crowded.pct-->% and
  4.4<!--=c.peak.mp.crowded.pct-->%; every seed is worse. The LLM arm degrades by about as much
  (junction +5.1<!--=c.off.llm.junction.pct-->% / +1.6<!--=c.peak.llm.junction.pct-->%), which is
  expected: the guard's pressures come from the same noisy counts.
* **The Webster plan is unaffected**: it never reads counts, and its runs are identical at every
  level.
* **At peak the advantage of adaptive control disappears.** With perfect counts MaxPressure and
  Webster were level at peak; with junction-camera counts MaxPressure's mean ATT
  (118.2<!--=c.peak.mp.junction.att--> s) falls behind Webster's (116.3<!--=c.peak.web.junction.att--> s).
  Off-peak MaxPressure stays ahead, with a smaller margin.

**Missed vehicles alone cost little** (@tbl:camera-sweep). With half of all vehicles missed and no
false detections, MaxPressure loses only 3.0<!--=c.sweep.off.p50.pct-->% off-peak and
2.4<!--=c.sweep.peak.p50.pct-->% at peak. When every vehicle is missed with the same probability,
every phase's expected pressure shrinks by the same factor, so the ranking is unchanged on
average; only the added randomness costs. The junction camera is different: it detects
92<!--=c.peff.off.junction.pct-->% of vehicles, yet off-peak it costs +4.8<!--=c.off.mp.junction.pct-->%,
whereas detecting 90<!--=c.sweep.off.p90.level_pct-->% of vehicles with nothing else wrong costs 0.0<!--=c.sweep.off.p90.pct-->%. What
the camera adds are phantom vehicles: about 0.7<!--=c.phantoms_per_road--> per road and snapshot,
all counted as stopped.

::: {#tbl:camera-sweep}
<!-- BEGIN:tab_camera_sweep -->
| p_detect (all classes, no false detections) | Off-peak: MaxPressure ATT (s) | Peak: MaxPressure ATT (s) |
|---------------------------|------------------------------------:|-----------------------------------|
| 1.00 | 88.1 ± 1.0 | 115.5 ± 0.9 |
| 0.90 | 88.1 ± 0.8 (-0.0%) | 117.7 ± 1.5 (+1.8%) |
| 0.80 | 89.7 ± 0.3 (+1.8%) | 116.6 ± 1.3 (+0.9%) |
| 0.70 | 89.6 ± 0.7 (+1.6%) | 117.5 ± 1.2 (+1.7%) |
| 0.60 | 90.2 ± 1.5 (+2.4%) | 118.5 ± 1.4 (+2.5%) |
| 0.50 | 90.8 ± 0.8 (+3.0%) | 118.3 ± 0.7 (+2.4%) |
<!-- END:tab_camera_sweep -->

: MaxPressure with every class detected with the same probability, no false detections and exact
labels (mean ± std over 3 seeds, change against perfect counts in brackets).
:::

**Decomposition (post-hoc).** To test that explanation, the junction level was re-run with one
error component at a time (@tbl:decomposition, @fig:decomposition). Off-peak, false detections
alone cost +3.8<!--=c.dec.false.off.pct-->% of the +4.8<!--=c.dec.all.off.pct-->%, misses
+0.8<!--=c.dec.misses.off.pct-->% and class confusion nearly nothing, and the three add up to the
whole effect. At peak no single component explains the +2.3<!--=c.dec.all.peak.pct-->%: the
components sum to only +0.4<!--=c.dec.sum.peak.pct-->%, so either they interact near capacity or
part of the peak effect is chance; three seeds cannot tell which. Class confusion alone has no
measurable effect because these controllers read class-free counts.

::: {#tbl:decomposition}
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

![Post-hoc decomposition: MaxPressure's ATT change with one junction-camera error component at a
time.](figures/decomposition.png){#fig:decomposition width=100%}

**Ambulances under camera errors** (@tbl:camera-emergency). Preemption keeps its advantage
(81.2<!--=c.amb.pre.perfect.amb--> s → 84.5<!--=c.amb.pre.junction.amb--> s) because it reads
ambulance positions from the separate channel. The LLM arm's ambulances are
11.0<!--=c.amb.llm.junction.amb_d--> s slower on average with junction-camera counts, but individual
ambulances move by tens of seconds in either direction between paired runs, so this is not
distinguishable from zero with 29<!--=e.mp.amb_n--> ambulances.

::: {#tbl:camera-emergency}
<!-- BEGIN:tab_camera_emergency -->
| controller | level | ATT (s) | ATT vs perfect, paired (s; range; %) | ambulances finished | ambulance travel time (s) | ambulance vs perfect, paired (s) |
|------------------|----------|-----------:|------------------|-----------:|----------:|------------------|
| MaxPressure | perfect | 115.7 ± 2.3 | – | 29 / 29 | 130.1 | – |
|  | junction | 117.6 ± 2.4 | +1.8 (-1.9 to +7.1); +1.6% | 29 / 29 | 135.9 | +5.8 (n 29; 14 slower, 13 faster) |
| Webster fixed-time | perfect | 115.2 ± 2.7 | – | 29 / 29 | 123.5 | – |
|  | junction | 115.2 ± 2.7 | +0.0 (+0.0 to +0.0); +0.0% | 29 / 29 | 123.5 | +0.0 (n 29; 0 slower, 0 faster) |
| MaxPressure + preemption | perfect | 116.0 ± 0.7 | – | 29 / 29 | 81.2 | – |
|  | junction | 117.2 ± 2.3 | +1.1 (-0.8 to +5.1); +1.0% | 29 / 29 | 84.5 | +3.3 (n 29; 16 slower, 12 faster) |
| LLM arm (guarded llama3.2:3b) | perfect | 116.4 ± 3.1 | – | 29 / 29 | 88.9 | – |
|  | junction | 120.2 ± 1.8 | +3.8 (-0.3 to +9.6); +3.3% | 29 / 29 | 99.9 | +11.0 (n 29; 17 slower, 11 faster) |
<!-- END:tab_camera_emergency -->

: Emergency scenario under junction-camera counts (5 seeds). Ambulance positions are not noised.
:::

## Detector {#sec:res-detector}

The detector results are given in full in @sec:det-eval. In summary, YOLOv8n trained on IDD
reaches mAP50 0.563<!--=d.test.map50--> and mAP50-95 0.375<!--=d.test.map5095--> on held-out drives,
with high precision and moderate recall; its errors are dominated by small, distant objects. The
dashboard runs the same weights on video (@fig:screen-detection).

![Dashboard, Live Detection page: the trained detector on a clip of IDD test frames, with boxes,
per-class counts and the measured speed on the GTX 1650.](figures/screen_detection.png){#fig:screen-detection width=92%}
