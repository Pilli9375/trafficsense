# LLM benchmark: which local model, which decision interval

Before running the full LLM experiments, local models are compared as the cooperative signal
controller on a short, fixed run. Each **arm** is one controller design:

| Arm | Controller | Prompt | Models | Phase |
|---|---|---|---|---|
| v1 | `llm_v1` (named `llm_cooperative` when its runs were made) | v1 | gemma3:4b, gemma4:e4b, llama3.2:3b, qwen2.5:3b | 3a |
| v2 | `llm_cooperative` | v2 | gemma4:e4b, llama3.2:3b, qwen2.5:3b | 3b |

`gemma3:4b` is left out from Phase 3b on: it does not fit in the 4 GB card (see the v1
findings). Every number below is generated from
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

**Selection rules**, written into the script's docstring and committed before the Phase 3a
benchmark was run, and kept unchanged for Phase 3b:

1. A model is eligible if fewer than 2% of its calls failed and its p95 latency is under 3 s.
2. Among eligible models, the lowest mean queue per intersection; tie-break the lower ATT.
   If none is eligible, the rule recommends nothing.
   The rule is applied within each arm, and once every arm is complete, over all (arm,
   model) pairs together; that pair is the recommended controller and model.
3. Decision interval: the shortest multiple of the 5 s transition that is at least the chosen
   model's p95 latency × 4 intersections. On one GPU the calls of a decision round run one
   after another, so this is the shortest interval at which a round fits in real time.

## Results

<!-- BEGIN:llm_benchmark -->
| Arm | Model | Calls | Failures | Latency mean (s) | Latency p95 (s) | Prompt tokens (mean) | VRAM, nvidia-smi peak − idle (MiB) | Ollama size_vram / size (MiB) | ATT at 600 s (s) | Queue / int. (veh) | Finished trips | Switches | Eligible |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 | `gemma3:4b` | 333 | 0.0% (none) | 5.05 | 5.43 | 686 | 2466 | 1524 / 3308 | 197.4 | 46.35 | 316 | 45 | no |
| v1 | `gemma4:e4b` | 160 | 0.6% (reason_too_long 1) | 7.55 | 8.36 | 671 | 2852 | 217 / 217 | 112.2 | 19.44 | 564 | 104 | no |
| v1 | `llama3.2:3b` | 288 | 6.2% (reason_too_long 18) | 3.14 | 3.35 | 654 | 2280 | 2210 / 2210 | 181.1 | 40.94 | 348 | 62 | no |
| v1 | `qwen2.5:3b` | 159 | 0.0% (none) | 3.01 | 3.34 | 653 | 2060 | 1985 / 1985 | 141.2 | 29.15 | 465 | 105 | no |
| v2 | `gemma4:e4b` | not run |  |  |  |  |  |  |  |  |  |  |  |
| v2 | `llama3.2:3b` | not run |  |  |  |  |  |  |  |  |  |  |  |
| v2 | `qwen2.5:3b` | not run |  |  |  |  |  |  |  |  |  |  |  |
| baseline | maxpressure | – | – | – | – | – | – | – | 92.5 | 11.85 | 623 | 115 | – |
| baseline | fixedtime_webster | – | – | – | – | – | – | – | 97.4 | 13.49 | 626 | 110 | – |
<!-- END:llm_benchmark -->

Same model across arms (ATT and queue over the same 600 s):

<!-- BEGIN:llm_compare -->
| Model | Queue / int. (v1 / v2) | ATT at 600 s (v1 / v2) | Latency p95 s (v1 / v2) | Failure rate (v1 / v2) |
|---|---|---|---|---|
| `gemma3:4b` | 46.35 / – | 197.4 / – | 5.43 / – | 0.0% / – |
| `gemma4:e4b` | 19.44 / – | 112.2 / – | 8.36 / – | 0.6% / – |
| `llama3.2:3b` | 40.94 / – | 181.1 / – | 3.35 / – | 6.2% / – |
| `qwen2.5:3b` | 29.15 / – | 141.2 / – | 3.34 / – | 0.0% / – |
<!-- END:llm_compare -->

## Selection

<!-- BEGIN:llm_selection -->
| Applied to | Eligible | Chosen | Decision interval |
|---|---|---|---|
| v1 | none | none | – |
| v2 | arm incomplete | – | – |
| all arms | not every arm is complete | – | – |
<!-- END:llm_selection -->

## Phase 3a: prompt v1

The first prompt (`prompt.py`, v1): for each of the 8 phases, every movement's queue, moving
and downstream counts; vehicle types per approach; each neighbour's phase and queues towards
and from us; rules that say switching "wastes green time"; a reason of at most 25 words.


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

## Phase 3b: prompt v2

A second, fair attempt at the plain LLM controller, designed after the v1 findings and
committed before any v2 run:

* **Shorter: under 300 tokens** (system and user message together, as the server counts
  them; v1 was about 650). Measured during development at one simulator state (t = 300 s,
  all 4 intersections): 281–286 tokens with `qwen2.5:3b`, 285 with `llama3.2:3b`, 294–299
  with `gemma4:e4b`. The benchmark reports the mean over all calls.
* **No arithmetic needed:** one line per phase with its **pressure** and **queue**. Pressure
  is MaxPressure's (stopped vehicles the phase serves minus stopped vehicles on their exit
  lanes), without the free turns; every green phase serves all free turns, so this lowers
  every phase by the same amount and keeps MaxPressure's ranking (tested). The per-movement
  breakdown and the vehicle-type counts are dropped to stay under the token target.
* **Neutral rules:** the transition is stated as a fact ("changing phase starts a 5 s
  transition in which only free turns move"); the v1 advice that switching "wastes green
  time" is gone.
* **Reason of at most 15 words** (v1: 25); the JSON schema caps it at 120 characters.
* Neighbours as in v1 (phase, stopped vehicles heading to us and how many of them have
  green, stopped vehicles on our road into them), in a shorter wording.

Everything else is unchanged: same scenario, seed, 600 steps, timing, Ollama options, GPU
procedure and selection rule.
