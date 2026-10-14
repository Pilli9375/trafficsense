# LLM benchmark: which local model, which decision interval

Before running the full LLM experiments, local models are compared as the cooperative signal
controller on a short, fixed run. Each **arm** is one controller design:

| Arm | Controller | Prompt | Models | Phase |
|---|---|---|---|---|
| v1 | `llm_v1` (named `llm_cooperative` when its runs were made) | v1 | gemma3:4b, gemma4:e4b, llama3.2:3b, qwen2.5:3b | 3a |
| v2 | `llm_cooperative` | v2 | gemma4:e4b, llama3.2:3b, qwen2.5:3b | 3b |
| hybrid | `llm_guided_mp` | guided | gemma4:e4b, llama3.2:3b, qwen2.5:3b | 3b |

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
| Arm | Model | Calls | Failures | Latency mean (s) | Latency p95 (s) | Prompt tokens (mean) | VRAM, nvidia-smi peak − idle (MiB) | Ollama size_vram / size (MiB) | ATT at 600 s (s) | Queue / int. (veh) | Finished trips | Switches | Differs from MaxPressure's choice | Eligible |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 | `gemma3:4b` | 333 | 0.0% (none) | 5.05 | 5.43 | 686 | 2466 | 1524 / 3308 | 197.4 | 46.35 | 316 | 45 | – | no |
| v1 | `gemma4:e4b` | 160 | 0.6% (reason_too_long 1) | 7.55 | 8.36 | 671 | 2852 | 217 / 217 | 112.2 | 19.44 | 564 | 104 | – | no |
| v1 | `llama3.2:3b` | 288 | 6.2% (reason_too_long 18) | 3.14 | 3.35 | 654 | 2280 | 2210 / 2210 | 181.1 | 40.94 | 348 | 62 | – | no |
| v1 | `qwen2.5:3b` | 159 | 0.0% (none) | 3.01 | 3.34 | 653 | 2060 | 1985 / 1985 | 141.2 | 29.15 | 465 | 105 | – | no |
| v2 | `gemma4:e4b` | 120 | 0.0% (none) | 4.85 | 5.32 | 291 | 2852 | 217 / 217 | 111.1 | 17.95 | 578 | 120 | – | no |
| v2 | `llama3.2:3b` | 351 | 0.3% (reason_too_long 1) | 1.36 | 1.52 | 285 | 2230 | 2210 / 2210 | 181.5 | 42.26 | 352 | 40 | – | yes |
| v2 | `qwen2.5:3b` | 355 | 29.3% (reason_too_long 104) | 1.47 | 1.65 | 285 | 2058 | 1985 / 1985 | 146.8 | 31.11 | 498 | 36 | – | no |
| hybrid | `gemma4:e4b` | 284 | 0.4% (reason_too_long 1) | 4.44 | 4.84 | 270 | 2850 | 217 / 217 | 125.8 | 23.38 | 546 | 62 | 82.3% (233; 209 kept current) | no |
| hybrid | `llama3.2:3b` | 287 | 0.3% (reason_too_long 1) | 1.03 | 1.13 | 260 | 2280 | 2210 / 2210 | 135.3 | 26.64 | 519 | 61 | 99.0% (283; 225 kept current) | yes |
| hybrid | `qwen2.5:3b` | 249 | 11.2% (reason_too_long 28) | 1.12 | 1.27 | 255 | 2058 | 1985 / 1985 | 123.3 | 22.05 | 570 | 74 | 75.6% (167; 159 kept current) | no |
| baseline | maxpressure | – | – | – | – | – | – | – | 92.5 | 11.85 | 623 | 115 | – | – |
| baseline | fixedtime_webster | – | – | – | – | – | – | – | 97.4 | 13.49 | 626 | 110 | – | – |
<!-- END:llm_benchmark -->

Same model across arms (ATT and queue over the same 600 s):

<!-- BEGIN:llm_compare -->
| Model | Queue / int. (v1 / v2 / hybrid) | ATT at 600 s (v1 / v2 / hybrid) | Latency p95 s (v1 / v2 / hybrid) | Failure rate (v1 / v2 / hybrid) |
|---|---|---|---|---|
| `gemma3:4b` | 46.35 / – / – | 197.4 / – / – | 5.43 / – / – | 0.0% / – / – |
| `gemma4:e4b` | 19.44 / 17.95 / 23.38 | 112.2 / 111.1 / 125.8 | 8.36 / 5.32 / 4.84 | 0.6% / 0.0% / 0.4% |
| `llama3.2:3b` | 40.94 / 42.26 / 26.64 | 181.1 / 181.5 / 135.3 | 3.35 / 1.52 / 1.13 | 6.2% / 0.3% / 0.3% |
| `qwen2.5:3b` | 29.15 / 31.11 / 22.05 | 141.2 / 146.8 / 123.3 | 3.34 / 1.65 / 1.27 | 0.0% / 29.3% / 11.2% |
<!-- END:llm_compare -->

What the models chose, replayed from each run's decision log
(`scripts/analyze_llm_decisions.py`; the replay reproduces every run's ATT exactly). Pressure
here is MaxPressure's at the moment of each decision; v2 showed it to the model:

<!-- BEGIN:llm_decisions -->
| Prompt | Model | Successful calls | Kept current phase | Chose highest-pressure phase | Chose lowest-pressure phase | Kept current although another had higher pressure |
|---|---|---|---|---|---|---|
| v1 | `gemma3:4b` | 333 | 86% | 4% | 51% | 95% |
| v1 | `gemma4:e4b` | 159 | 35% | 9% | 29% | 34% |
| v1 | `llama3.2:3b` | 270 | 77% | 2% | 34% | 84% |
| v1 | `qwen2.5:3b` | 159 | 34% | 18% | 25% | 34% |
| v2 | `gemma4:e4b` | 120 | 0% | 40% | 9% | 0% |
| v2 | `llama3.2:3b` | 350 | 89% | 6% | 48% | 99% |
| v2 | `qwen2.5:3b` | 251 | 88% | 6% | 49% | 100% |
| guided | `gemma4:e4b` | 283 | 78% | 18% | 83% | 84% |
| guided | `llama3.2:3b` | 286 | 79% | 4% | 86% | 86% |
| guided | `qwen2.5:3b` | 221 | 78% | 25% | 77% | 80% |
<!-- END:llm_decisions -->

## Selection

<!-- BEGIN:llm_selection -->
| Applied to | Eligible | Chosen | Decision interval |
|---|---|---|---|
| v1 | none | none | – |
| v2 | llama3.2:3b | llama3.2:3b | 10 s (p95 × intersections = 6.1 s) |
| hybrid | llama3.2:3b | llama3.2:3b | 5 s (p95 × intersections = 4.5 s) |
| all arms | hybrid llama3.2:3b, v2 llama3.2:3b | hybrid llama3.2:3b | 5 s (p95 × intersections = 4.5 s) |
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

### v2 findings

* **By the rule, v2 recommends `llama3.2:3b`** with a decision interval of 10 s (p95 1.52 s ×
  4 intersections = 6.1 s): it is the only eligible v2 model (1 failure in 351 calls). It is
  also **the worst-controlling v2 model**: queue 42.26 vehicles per intersection and ATT
  181.5 s, as bad as with v1 and far behind MaxPressure (11.85, 92.5 s). The rule screens on
  reliability and speed and then picks the lowest queue among what is left; with one model
  left, it picks that one whatever its queue. This is reported as the rule's result, not as a
  model worth running.
* **Shorter prompts made calls about twice as fast:** p95 1.52 s (`llama3.2:3b`) and 1.65 s
  (`qwen2.5:3b`) against 3.35 and 3.34 s with v1; `gemma4:e4b` went from 8.36 to 5.32 s. The
  prompts averaged 285–291 tokens (target < 300).
* **Precomputed pressures did not make the small models follow pressure.** `llama3.2:3b` and
  `qwen2.5:3b` kept the current phase in 89% and 88% of their successful calls, and chose the
  highest-pressure allowed phase in 6%; whenever another allowed phase had higher pressure,
  they kept the current one in 99% and 100% of those calls. With v1 `qwen2.5:3b` kept the
  phase in 34% of calls. So dropping the "switching wastes green time" warning did not stop
  the keeping; v2 made it worse for these two models. Their reasons suggest why:
  `llama3.2:3b` reads pressure as something to avoid ("Low pressure, short queues, and low
  travel time", its second most common reason); the v2 prompt defines pressure but, to stay
  neutral, does not say which way favours a phase.
* **`qwen2.5:3b` failed 29.3% of its calls** (104 of 355), every one a reason over 15 words.
  It copies the format placeholder `<at most 15 words>` into its answers ("At most 15
  vehicles are stopped, ..."; "At most 15 words: Switching to ..."; 250 of its 355 answers
  contain "at most 15"), and the failed reasons run to 16–23 words. A failed call keeps the current phase, which adds to its keeping.
* **`gemma4:e4b` is the one model that changed behaviour:** it never kept the current phase
  under v2 and chose the highest-pressure phase in 40% of its calls (v1: 9%). It has the lowest
  queue of any LLM run so far (17.95) and no failures, but is not eligible (p95 5.32 s).
* Not tested: a prompt that says higher pressure means more need for green, or a different
  reason format. Either would be a v3, i.e. another change after seeing the data, and is
  the user's decision.

## Phase 3b: hybrid `llm_guided_mp`

MaxPressure proposes, the LLM picks; designed and committed before any hybrid run
(`src/trafficsense/control/guided.py`):

* At each decision MaxPressure ranks the green phases by pressure, exactly as the default
  MaxPressure (same pressures and tie-break; the current phase is left out when keeping it
  would reach max green). The LLM is offered MaxPressure's **top 2** and **keeping the current
  phase** (always allowed here, since an intersection is only asked once min green is met),
  so 2 or 3 options.
* The prompt ("guided") lists only those options, best rank first, with pressure and queue,
  plus the neighbours as in v2; the reason is at most 15 words.
* **On a failed call MaxPressure's top choice is applied** and the failure is counted.
  An LLM that always takes the first option, or always fails, gives exactly MaxPressure's
  run (tested over 600 steps).
* Logged per decision: MaxPressure's ranking and top choice, and whether the LLM's choice
  differs from it; the benchmark table reports that rate ("Differs from MaxPressure's
  choice") and how many of those were "keep current".
* Same setup and the same selection rule as the other arms; gemma4:e4b, llama3.2:3b,
  qwen2.5:3b.

### Hybrid findings

* **By the rule over all arms, the recommendation is the hybrid with `llama3.2:3b`, decision
  interval 5 s** (p95 1.13 s × 4 = 4.5 s). Eligible were hybrid `llama3.2:3b` and v2
  `llama3.2:3b`; the hybrid has the lower queue (26.64 against 42.26). Within the hybrid arm it
  is again the only eligible model, and again the worst of its arm: `qwen2.5:3b` (22.05) and
  `gemma4:e4b` (23.38) have lower queues but fail the rule (11.2% failures; p95 4.84 s).
* **Every hybrid run controls worse than MaxPressure alone:** queue 22.05–26.64 against
  11.85, ATT 123.3–135.3 s against 92.5 s. A hybrid can only differ from MaxPressure where
  the LLM overrules it, and the LLMs overruled it in 75.6% (`qwen2.5:3b`), 82.3%
  (`gemma4:e4b`) and 99.0% (`llama3.2:3b`, which took MaxPressure's choice in 3 of 286
  successful calls) of their successful calls, mostly by keeping the current phase.
* The hybrid still helps the two small models compared with choosing freely (v2): queue
  42.26 → 26.64 for `llama3.2:3b` and 31.11 → 22.05 for `qwen2.5:3b`, because their worst
  choices are no longer on offer. For `gemma4:e4b` it is worse than v2 (17.95 → 23.38).
* **The common cause in v2 and the hybrid: the models treat low pressure as good.** In the
  hybrid every model chose the lowest-pressure option in 77–86% of the calls where the options
  differed in pressure (table above); keeping the current phase, usually the lowest-pressure
  option and listed last, was chosen in 78–79% of calls. Their reasons say so directly:
  "Current phase has negative pressure, indicating it's the best choice for now"
  (`gemma4:e4b`), "Low pressure, minimal queue impact" (`llama3.2:3b`). In v2, with 8 phases,
  `llama3.2:3b` and `qwen2.5:3b` chose the lowest-pressure phase in 48% and 49% of calls. The
  guided prompt says the options are listed "best MaxPressure rank first" but, like v2, does
  not say that higher pressure means more need for green.
* `qwen2.5:3b` again failed on long reasons (11.2%, all `reason_too_long`).
* Not tested, and each would be a change after seeing the data (the user's decision): stating
  that higher pressure means a phase needs green more, renaming "pressure" (e.g. "waiting
  vehicles that can move"), offering only MaxPressure's top 2 without "keep current", or a
  shorter reason format.
