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
