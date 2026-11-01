# Results and Discussions {#sec:results}

This chapter reports the results in the order the experiments were run: the tuning of the
classical baselines, the LLM benchmark that selected the controller, the full experiments, the
ambulance experiment, the exploratory model-size study and the camera-error experiment. It then
gives the detector's evaluation and the dashboard, and discusses what the results mean and what
limits them. Every table in this chapter is generated from the result files.

## Baselines and Their Tuning {#sec:baselines}

An LLM controller should be compared with baselines that are as good as they can reasonably be,
and those must be fixed before the comparison, not after. Three classical controllers were used.

* **FixedTime**: the 4 paired phases (each pair of opposing approaches together), 30<!--=cfg.ft.green--> s of green
  each. This is the naive plan.
* **Webster fixed time**: the same 4 phases with a cycle and splits computed per intersection by
  Webster's method. Saturation flows and start-up lost times are measured on the network with the
  run's vehicle mix (mean of 30<!--=cfg.web.reps--> random-order queues), and lane demand is read from the run's own
  flow file, i.e. a perfect count of the simulated hour. This favours Webster: a real plan is built
  from older counts.
* **MaxPressure**: all 8 green phases, ties keep the current phase.

MaxPressure's timing was tuned in two sweeps on four scenarios (Jinan, Hangzhou, Indian off-peak
and peak; 3 seeds each), with selection rules committed before the runs: rank the settings by
mean travel time in each scenario, choose the lowest mean rank, break ties by the lowest mean
ratio to the best. The first sweep varied the decision interval and showed that what really
changed was the shortest possible green. The second sweep therefore fixed the interval at 5 s and
varied the minimum green (@tbl:mg-selection). A minimum green of
15<!--=mg.chosen--> s was chosen, through the tie-break: the 10 s setting is best on three
scenarios but last at Indian peak.

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

The minimum green matters because of the transition. With a 10 s minimum green MaxPressure
switches so often that 32.4<!--=i.peak.maxpressure_5s.transition-->% of each intersection's time
at peak is transition, against 24.7<!--=i.peak.maxpressure.transition-->% with 15<!--=cfg.mp.min_green--> s. In light
traffic reacting quickly wins; near capacity the green lost to transitions costs more. No
setting is best at both levels, and the pre-registered rule chose the compromise.

@tbl:baselines-indian gives all baselines on the Indian network. Off-peak, MaxPressure is clearly
best. At peak, the tuned MaxPressure and the Webster plan are effectively tied
(115.5<!--=i.peak.maxpressure.att--> s and 116.3<!--=i.peak.fixedtime_webster.att--> s), and the
30<!--=cfg.ft.green--> s FixedTime no longer drains: about 308<!--=i.peak.fixedtime.backlog--> vehicles are still waiting to enter at the end of the
hour. This tie matters for reading the LLM results: at peak, "as good as MaxPressure" is also
"as good as a well-timed fixed plan".

::: {#tbl:baselines-indian short="All baselines on the Indian 2x2 network"}
<!-- BEGIN:tab_baselines_indian -->
| Level | Controller | ATT (s) | Queue / int. (veh) | Finished trips | Waiting to enter at end | Share of time in transition |
|-----------|--------------------|-------------:|-------------:|-----------:|-------------:|--------------:|
| off-peak | FixedTime, 4 paired phases, 30 s | 121.5 ± 0.2 | 10.58 ± 0.17 | 2316 ± 28 | 0.0 ± 0.0 | 0.142 ± 0.000 |
| off-peak | FixedTime, all 8 phases, 30 s | 129.3 ± 1.3 | 11.88 ± 0.42 | 2298 ± 28 | 0.0 ± 0.0 | 0.142 ± 0.000 |
| off-peak | FixedTime, 4 paired phases, Webster plan | 100.4 ± 4.1 | 6.82 ± 0.52 | 2320 ± 36 | 0.0 ± 0.0 | 0.326 ± 0.006 |
| off-peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 88.1 ± 1.0 | 4.94 ± 0.23 | 2332 ± 36 | 0.0 ± 0.0 | 0.246 ± 0.001 |
| off-peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 81.3 ± 0.3 | 3.80 ± 0.07 | 2332 ± 38 | 0.0 ± 0.0 | 0.314 ± 0.003 |
| off-peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 82.0 ± 0.8 | 3.91 ± 0.17 | 2332 ± 37 | 0.0 ± 0.0 | 0.319 ± 0.003 |
| peak | FixedTime, 4 paired phases, 30 s | 279.9 ± 9.9 | 44.44 ± 0.75 | 4166 ± 93 | 307.7 ± 20.5 | 0.142 ± 0.000 |
| peak | FixedTime, all 8 phases, 30 s | 291.9 ± 7.3 | 47.67 ± 0.62 | 4113 ± 88 | 331.0 ± 18.3 | 0.142 ± 0.000 |
| peak | FixedTime, 4 paired phases, Webster plan | 116.3 ± 4.6 | 18.27 ± 1.28 | 4577 ± 87 | 0.3 ± 0.6 | 0.227 ± 0.004 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 115.5 ± 0.9 | 17.83 ± 0.32 | 4576 ± 68 | 0.3 ± 0.6 | 0.247 ± 0.001 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 133.8 ± 15.9 | 23.24 ± 4.60 | 4540 ± 116 | 0.3 ± 0.6 | 0.321 ± 0.002 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 142.4 ± 18.3 | 25.84 ± 5.22 | 4516 ± 131 | 0.3 ± 0.6 | 0.324 ± 0.001 |
<!-- END:tab_baselines_indian -->

: All baselines on the Indian 2x2 network, mean ± std over seeds 0–2, 3600<!--=cfg.steps--> s. The
default MaxPressure is the tuned one (5 s interval, 15<!--=cfg.mp.min_green--> s minimum green).
:::

## LLM Benchmark and the Design Rounds {#sec:res-bench}

Each LLM arm was benchmarked on the same 600<!--=b.steps--> s of Indian peak traffic (seed 0) with
up to four local models (`llama3.2:3b` from the Llama 3 family [@grattafiori2024llama3], `qwen2.5:3b`
[@qwen2024qwen25], and Google's `gemma3:4b` and `gemma4:e4b`), and the pre-registered rule (@sec:prereg) was applied. @fig:bench and
@tbl:bench summarise all rounds; @tbl:bench-selection gives what the rule chose.

![Mean queue per intersection over the first 600<!--=b.steps--> s of Indian peak traffic for every arm and
model, against MaxPressure (blue line). gemma3:4b, run only in v1, is in @tbl:bench.](figures/bench.png){#fig:bench short="LLM benchmark: mean queue of every arm and model" width=100%}

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
of its calls. It did not change the two 3B models, which still kept the current phase in most
calls.

::: {#tbl:bench short="LLM benchmark, all rounds"}
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

::: {#tbl:bench-selection short="What the pre-registered rule selected in each round"}
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

## Full Experiments {#sec:res-main}

@tbl:full-off, @tbl:full-peak and @tbl:full-jinan give the results of the full experiments, and
@fig:att shows the travel times side by side.

![Average travel time of every controller in the three scenarios (mean ± std over three seeds).
The two LLM arms are close to MaxPressure everywhere; FixedTime fails at peak.](figures/att.png){#fig:att short="Average travel time of every controller" width=100%}

::: {#tbl:full-off short="Full experiments, Indian 2x2 off-peak"}
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

::: {#tbl:full-peak short="Full experiments, Indian 2x2 peak"}
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

::: {#tbl:full-jinan short="Full experiments, Jinan 3x4"}
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
zero is faster than MaxPressure.](figures/paired.png){#fig:paired short="Paired ATT difference of the LLM arms from MaxPressure" width=100%}

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

::: {#tbl:llm-stats short="LLM decision statistics"}
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

::: {#tbl:emergency short="Emergency scenario, normal traffic"}
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
moving (light).](figures/ambulance.png){#fig:ambulance short="Travel time of the signal-relevant ambulances" width=100%}

**Normal traffic does not pay for the priority.** Network ATT under the main arm is
116.4<!--=e.llm.att--> s against MaxPressure's 115.7<!--=e.mp.att--> s, a difference well inside
the seed-to-seed spread (±2.3<!--=e.mp.att_sd--> s).

## Model Size (Exploratory) {#sec:res-size}

*Exploratory, planned after the main results.* With the controller fixed to the unguarded hybrid
(hybrid_v3), only the model was changed, from 3B local models to a hosted 550<!--=m.size.nemo--> B
mixture-of-experts model (Nemotron 3 Ultra [@nemotron3ultra], 55<!--=m.active.nemo--> B parameters active per token).
@tbl:model-size and @fig:model-size give the results.

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
ambulances. Grey: models worse than MaxPressure on every seed.](figures/model_size.png){#fig:model-size short="Exploratory: one hybrid controller with five models" width=100%}

1. **Below some size the LLM makes the hybrid controller worse.** With either 3B model the hybrid
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

::: {#tbl:model-size-amb short="Exploratory: ambulances under each model"}
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
failures and fell back to MaxPressure's choice (@sec:app-tables). Its prompts also leave the machine,
so it is not an on-device option.

## Camera Errors {#sec:res-camera}

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
rates.](figures/camera.png){#fig:camera short="Paired ATT change under camera errors" width=100%}

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

::: {#tbl:camera-sweep short="MaxPressure with uniform detection and no false detections"}
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

![Post-hoc decomposition: MaxPressure's ATT change with one junction-camera error component at a
time.](figures/decomposition.png){#fig:decomposition short="Post-hoc decomposition of MaxPressure's ATT change" width=100%}

**Ambulances under camera errors** (@tbl:camera-emergency). Preemption keeps its advantage
(81.2<!--=c.amb.pre.perfect.amb--> s → 84.5<!--=c.amb.pre.junction.amb--> s) because it reads
ambulance positions from the separate channel. The LLM arm's ambulances are
11.0<!--=c.amb.llm.junction.amb_d--> s slower on average with junction-camera counts, but individual
ambulances move by tens of seconds in either direction between paired runs, so this is not
distinguishable from zero with 29<!--=e.mp.amb_n--> ambulances.

::: {#tbl:camera-emergency short="Emergency scenario under junction-camera counts"}
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

**Operating point.** A detector outputs boxes with confidence scores; a controller needs a yes/no
decision per box. The confidence threshold was chosen on the validation split as the one that
maximises the mean F1 score over the 7 classes: 0.3<!--=d.conf--> (mean F1
0.620<!--=d.f1-->). The F1 curve is flat around this value, so the exact choice matters little.

**Matching.** On each test image, detections (sorted by confidence) are matched greedily to the
unmatched ground-truth box with the highest IoU of at least 0.5<!--=d.match_iou-->, ignoring the
class. A match with the same class is a true positive; a match with another class is a
**confusion**; an unmatched detection is a **false detection**; an unmatched ground-truth box is a
**miss**. Confidence intervals come from 1,000<!--=d.bootstrap_reps--> bootstrap resamples of
whole drives, not frames, so that correlated frames do not make them look tighter than they are.

**Results.** On the test split the detector reaches mAP50 0.563<!--=d.test.map50--> and mAP50-95
0.375<!--=d.test.map5095--> (validation: 0.602<!--=d.val.map50--> and
0.403<!--=d.val.map5095-->). @tbl:det-classes gives the per-class numbers. Precision is high
(few false detections) and recall is moderate: the detector undercounts.

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

**Most misses are small, distant objects** (@fig:det-size, @tbl:det-sizes). Small boxes are most
of the ground truth, and the detector misses
59<!--=d.size.motorcycle.small-->–76<!--=d.size.person.small-->% of them, against
1<!--=d.size.autorickshaw.large-->–22<!--=d.size.bicycle.large-->% of large boxes. This is the
cost of running at 640<!--=cfg.imgsz--> pixels named above. One camera group dominates the test set: the
`highquality_16k` camera supplies 3,633<!--=d.camera.hq.images--> images but
64,381<!--=d.camera.hq.gt--> of the boxes, 74<!--=d.camera.hq.small-->% of them small. The
overall per-class rates therefore mostly describe crowded scenes with distant objects. Confusions
are few and plausible: bicycles are labelled motorcycles, and buses, trucks and auto-rickshaws are
confused with each other and with cars. `person` has the highest miss rate, partly because
pedestrians are small and possibly because the model was taught not to fire on riders.

![Miss rate by object size on the test split. Sizes are COCO's buckets measured in the
640<!--=cfg.imgsz-->-pixel image.](figures/det_size.png){#fig:det-size width=100%}

::: {#tbl:det-sizes short="Miss rate by object size"}
<!-- BEGIN:tab_det_sizes -->
| class | Small: miss rate (boxes) | Medium | Large |
|-------------------------|-------------------------:|------------------------:|------------------------:|
| car | 65.4% (15,489) | 9.1% (6,065) | 1.3% (3,289) |
| motorcycle | 59.0% (17,565) | 10.1% (6,250) | 3.8% (1,674) |
| autorickshaw | 63.6% (4,646) | 7.8% (2,106) | 1.1% (1,030) |
| bus | 70.8% (2,199) | 19.2% (1,141) | 2.1% (1,575) |
| truck | 73.0% (3,712) | 22.4% (1,820) | 10.2% (1,545) |
| bicycle | 71.9% (334) | 33.8% (198) | 21.6% (37) |
| person | 75.7% (14,180) | 20.7% (3,288) | 12.0% (610) |
<!-- END:tab_det_sizes -->

: Miss rate by object size (number of ground-truth boxes in brackets), test split.
:::

## Dashboard {#sec:res-dashboard}

The dashboard (@sec:dashboard) presents these results; its four pages are shown in
@fig:screen-overview, @fig:screen-detection, @fig:screen-replay and @fig:screen-results. The
screenshots were taken by a script with the dashboard reading the committed result files
(`docs/screenshots/`).

![Dashboard, Overview page. The headline is the pre-registered arm's ambulance
result; exploratory numbers are labelled as such.](figures/screen_overview.png){#fig:screen-overview short="Dashboard, Overview page" width=92%}

![Dashboard, Live Detection page: the trained detector on a clip of IDD test frames, with boxes,
per-class counts and the measured speed on the GTX 1650.](figures/screen_detection.png){#fig:screen-detection short="Dashboard, Live Detection page" width=92%}

![Dashboard, Network Replay page: MaxPressure (left) and the pre-registered LLM arm (right) on
the same traffic, one ambulance's trip. Replays re-drive the simulator with each run's logged
decisions and are kept only if they reproduce the run's metrics exactly.](figures/screen_replay.png){#fig:screen-replay short="Dashboard, Network Replay page" width=92%}

![Dashboard, Results page, Signal control tab (Indian 2x2 peak). Average travel time of each
controller and the paired comparison by seed, labelled as pre-registered and without a
significance test; the other tabs show the ambulance, model-size (exploratory), camera-error and
detector results.](figures/screen_results.png){#fig:screen-results short="Dashboard, Results page" width=92%}

## Discussion {#sec:discussion}

### Why the LLM Agents Match MaxPressure but Do Not Beat It {#sec:disc-why}

Three observations together explain the main result.

**First, an LLM that reads pressure correctly becomes MaxPressure.** In the hybrid controllers the
LLM is shown each option's pressure and queue, the same information MaxPressure uses. The largest
model tested, the hosted Nemotron 3 Ultra, chose the highest-pressure option in
99<!--=m.peak.nemo.follows-->% of its calls, and its ATT is within seed noise of MaxPressure's
(@sec:res-size). This is the expected end point: for steady demand on a small grid, serving the
largest pressure is close to the best a one-step rule can do, and the extra information in the
prompt, the neighbours' queues, rarely points to a better phase. To beat MaxPressure an agent
must use information MaxPressure does not have, or plan over more than one decision. Neither was
asked of the agents in the pre-registered design.

**Second, small models misread the task.** With prompts v2 and guided, the 3B models treated low
pressure as good and kept the current phase most of the time, and their reasons said so in words
(@sec:res-bench). The v3 fix, which states which direction of pressure is better, changed
`gemma4:e4b` but not the 3B models. A model of this size follows the surface of the prompt
("keep", "low queue") more than its stated rule. Without a guard their choices are applied and
the controller is far worse than MaxPressure (@tbl:model-size).

**Third, the guard converts a poor model into MaxPressure with noise.** The pre-registered
controller's answers differ from MaxPressure's in about nine of ten calls, but the guard replaces
most of them, and the applied phase differs in about one in ten. What remains are choices within
20<!--=cfg.guard.margin-->% of the top pressure. Off-peak, when queues are short, such a choice
gives green to a slightly smaller queue and costs a little; this is the small, consistent
deficit seen on every off-peak seed. The guard therefore made the LLM safe to deploy, not useful.

The exploratory `gemma4:e4b` arm follows pressure in most calls and departs from MaxPressure in
about one call in five at peak, where it was faster on every seed. We have not identified the
mechanism. One hypothesis is that its departures more often keep a phase that is still discharging
a long queue, avoiding a transition; this was not tested, and with three seeds the gain itself
needs confirmation.

### Why the LLM Agents Help Ambulances {#sec:disc-amb}

The ambulance experiment is the one case where the agent has information MaxPressure lacks:
the prompt lists each approaching ambulance, its distance and the phases that serve it. A
one-sentence instruction was enough for the pre-registered arm to cut ambulance travel time by
31.7<!--=e.llm.amb_cut_vs_mp-->% compared with MaxPressure, mostly by removing time stopped at a
red. Two design choices helped: the phase that serves the ambulance is always among the options,
and it is exempt from the guard. Normal traffic was not measurably slowed, because ambulances are
rare and each priority decision affects one intersection for a short time.

A hand-written preemption rule did slightly better. This is the honest comparison for a
deployment decision: for a single, well-defined rule like "give green to the ambulance", a rule
is simpler, faster and verifiable. The case for an LLM agent is flexibility, not performance. The
same mechanism, a sentence in the system prompt and a line in the observation, can carry rules
that are awkward to hard-code: a road closure, a school zone at certain hours, a police
instruction, priority for a bus that is late. This project tested only the ambulance case.

### What the Camera Study Means {#sec:disc-camera}

Adaptive control is only as good as its counts. With counts degraded by the errors of a real
detector, every count-based controller lost a few percent of travel time, and at peak its
advantage over a well-timed fixed plan, already small with exact counts, disappeared. Three
lessons follow for a deployment.

1. **False detections hurt more than misses.** Missing vehicles uniformly scales every pressure
   down and barely changes the ranking. A phantom vehicle adds pressure where there is none and
   changes the decision directly. For signal control a detector's precision matters more than
   its recall, the opposite of the usual emphasis, and temporal smoothing or tracking that rejects
   one-frame detections should help (each snapshot here is independent, the worst case).
2. **Camera placement matters.** The junction level, which assumes queued vehicles are close
   enough to be medium or large in the image, costs about half as much as the crowded / far
   level.
3. **A fixed plan is a robust fallback.** Webster's plan does not depend on counts at all. Where
   detection is unreliable, at night or in heavy rain, a controller should fall back to a good
   fixed plan rather than act on bad counts.

These conclusions rest on a proxy: the detector's errors on dash-camera images. The same detector
on a pole-mounted camera could be better (closer, less occlusion) or worse (unfamiliar viewpoint).

### Relation to the Base Paper {#sec:disc-collmlight}

CoLLMLight reports that cooperative LLM agents outperform existing methods. Our results neither
confirm nor contradict that claim, because the settings differ in ways that matter: CoLLMLight
fine-tunes its model in several stages and uses an asynchronous reasoning architecture, while we
used small models as released; we compared against MaxPressure and Webster tuned on the test
networks; and we found that CoLLMLight's own fixed-time baseline does not serve north–south
traffic. Its metric definitions also differ from CityFlow's, so numbers cannot be compared
directly. What our results do show is that, without fine-tuning, a 3–4 B model is not enough to
improve on a tuned MaxPressure, and that the clearest value of an LLM agent appears when it is
given information a classical controller cannot use.

## Threats to Validity {#sec:threats}

**Internal validity.** Three seeds per scenario (five with ambulances) are few, and no significance
test was pre-registered; differences of one or two percent are within seed noise and are reported
as such. LLM runs are not bit-for-bit repeatable on the GPU, although every decision is logged
and replayable. Prompt v3 was a post-hoc fix, the `gemma4:e4b` arm and the model-size study were
added after the plans were fixed, and the camera decomposition was post-hoc; all are labelled. The
hosted model's runs were affected by heavy API throttling, which turned some decisions into
MaxPressure fallbacks.

**Construct validity.** ATT counts time spent waiting to enter the network, which penalises
controllers that block entries; this is intended but makes ATT differ from definitions used
elsewhere, including CoLLMLight's (@sec:validation). The ambulance metric assumes that nobody yields
and that ambulances cannot overtake, so it measures only what the signal can do. The camera layer
draws independent snapshots and does not model occlusion between lanes or ambulance detection.

**External validity.** CityFlow is lane-based and cannot represent lane-free Indian driving
(@sec:sim-limits). The Indian network is a 2 × 2 grid with synthetic, steady demand; its vehicle
mix comes from one city in one year; and the turning shares are assumptions. Jinan provides one
real-world flow. Latencies are specific to a GTX 1650. The results show what a small local
model does on this network; they do not show how a deployed system would perform on a real
junction.
