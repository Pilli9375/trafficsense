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
<!-- END:llm_benchmark -->

## Selection

<!-- BEGIN:llm_selection -->
<!-- END:llm_selection -->
