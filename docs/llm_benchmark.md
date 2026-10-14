# LLM benchmark: which local model, which decision interval

Before running the full LLM experiments, four local models are compared as the cooperative
controller (`llm_cooperative`) on a short, fixed run. Every number below is generated from
`outputs/llm_benchmark/` by `scripts/benchmark_llm.py --report-only`;
`scripts/benchmark_llm.py --check` fails if this document and the data disagree.

## Setup

* Indian 2x2 at peak demand, seed 0, 600 steps (the first 10 minutes of the hour).
* Decision interval 5 s and min green 15 s, the tuned MaxPressure's timing
  (`docs/baselines.md`, section 2), so the LLM and MaxPressure differ only in how they choose a
  phase. Max green 60 s, 5 s transitions, all 8 phases offered.
* Ollama, native `/api/chat` with a JSON-schema `format`; temperature 0, seed 0, context
  2048 tokens, `think: false`, 60 s timeout (`configs/default.yaml`, `llm`). What the
  prompt contains is documented in `src/trafficsense/llm/prompt.py`.
* GTX 1650 (4 GB). Before each model every loaded model is unloaded and the GPU must be
  idle (≤ 300 MiB used); the model is then loaded with one warm-up call. VRAM is the
  nvidia-smi peak during the run minus that idle baseline.
* Baselines on the same 600 s: the default MaxPressure and the Webster plan.
* ATT is CityFlow's average travel time at t = 600 s, which includes vehicles still in the
  network; it is comparable between the rows here, not with the 3600 s tables elsewhere.

**Selection rules**, written into the script's docstring and committed before the benchmark
was run:

1. A model is eligible if fewer than 2% of its calls failed and its p95 latency is under 3 s.
2. Among eligible models, the lowest mean queue per intersection; tie-break the lower ATT.
   If none is eligible, the rule recommends nothing.
3. Decision interval: the shortest multiple of the 5 s transition that is at least the chosen
   model's p95 latency × 4 intersections. On one GPU the calls of a decision round run one
   after another, so this is the shortest interval at which a round fits in real time.

## Results

<!-- BEGIN:llm_benchmark -->
| Model | Calls | Failures | Latency mean (s) | Latency p95 (s) | Prompt tokens (mean) | VRAM, nvidia-smi peak − idle (MiB) | Ollama size_vram / size (MiB) | ATT at 600 s (s) | Queue / int. (veh) | Finished trips | Eligible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `gemma3:4b` | 333 | 0.0% (none) | 5.05 | 5.43 | 686 | 2466 | 1524 / 3308 | 197.4 | 46.35 | 316 | no |
| `gemma4:e4b` | 160 | 0.6% (reason_too_long 1) | 7.55 | 8.36 | 671 | 2852 | 217 / 217 | 112.2 | 19.44 | 564 | no |
| `llama3.2:3b` | 288 | 6.2% (reason_too_long 18) | 3.14 | 3.35 | 654 | 2280 | 2210 / 2210 | 181.1 | 40.94 | 348 | no |
| `qwen2.5:3b` | 159 | 0.0% (none) | 3.01 | 3.34 | 653 | 2060 | 1985 / 1985 | 141.2 | 29.15 | 465 | no |
| maxpressure (baseline) | – | – | – | – | – | – | – | 92.5 | 11.85 | 623 | – |
| fixedtime_webster (baseline) | – | – | – | – | – | – | – | 97.4 | 13.49 | 626 | – |
<!-- END:llm_benchmark -->

What the table shows:

* **No model meets the pre-registered rule, so the rule recommends nothing.** `qwen2.5:3b`
  has no failures but its p95 latency is 3.34 s (limit < 3 s); `llama3.2:3b` is about as fast
  (3.35 s) but 6.2% of its answers failed, all with a reason over 25 words; both Gemma models
  are too slow (p95 5.4 and 8.4 s).
* **Every model controls traffic much worse than both baselines** over these 600 s: queue
  19–46 vehicles per intersection against 11.85 (MaxPressure) and 13.49 (Webster), ATT
  112–197 s against 92.5 and 97.4 s. This is one seed and 10 minutes, and the LLM controller
  is untuned (one prompt, written before any run), but the gap is large.
* **Latency is mostly prompt reading.** On the GTX 1650 a 3B model reads an uncached prompt at
  about 200 tokens/s and writes at about 60 tokens/s (measured with `qwen2.5:3b` before the
  benchmark); a ~650-token prompt whose shared system part (~200 tokens) is cached costs
  about 2.2 s to read and 0.6 s to answer. Shorter prompts would cut latency roughly in
  proportion.
* **Where the model sits matters.** `gemma3:4b` does not fit the 4 GB card: Ollama puts
  1524 of 3308 MiB on the GPU, the rest on the CPU, hence 5 s per call. For `gemma4:e4b`
  Ollama's `/api/ps` reports a size of 217 MiB, which cannot be right (nvidia-smi shows
  2852 MiB in use during the run); only the nvidia-smi figure is used.
* **Observation, not verified: the models that switch more do better.** Over the 600 s
  MaxPressure switched 115 times and Webster 110 (all 4 intersections). `gemma4:e4b` (104
  switches) and `qwen2.5:3b` (105) are the two best models; `llama3.2:3b` (62) and
  `gemma3:4b` (45) kept the current phase in 72% and 86% of their calls and are the two
  worst. `gemma3:4b` chose phase 7 or 8 (the S or N approach alone) in 85% of its calls,
  often with a reason that contradicts the numbers it was given (e.g. "N cross-turn is
  empty, maintain current phase"). The system prompt warns that switching too often wastes
  green time, which may push models towards keeping; this has not been tested.
* Fewer calls means more switching: after a switch an intersection is not asked again for
  20 s (5 s transition + 15 s min green), so `qwen2.5:3b` made 159 calls and `gemma3:4b` 333.
* `gemma3:4b` was run twice (the first attempt crashed afterwards in the VRAM sampler and
  was discarded): same calls, failures and p95, as expected at temperature 0 with a fixed
  seed.

## Selection

<!-- BEGIN:llm_selection -->
| Item | Value |
|---|---|
| Model rule | eligible: failure rate < 2% and p95 latency < 3.0 s; then lowest mean queue per intersection, tie-break lower ATT |
| Eligible models | none |
| Chosen model | none (no model meets the rule) |
| Decision-interval rule | shortest multiple of 5 s >= p95 latency x 4 intersections |
| Recommended decision interval | – |
<!-- END:llm_selection -->
