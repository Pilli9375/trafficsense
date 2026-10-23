# Model size vs control quality (exploratory, added after the main results)

**Exploratory, added after the main results.** This study was planned after the full
experiments were finished. It does not change the pre-registered final LLM round
(`docs/llm_benchmark.md`) or the results and conclusions in `docs/results.md`; its runs live in
`outputs/model_size/runs/` and no earlier script reads them. Its plan was committed before any
of its runs (`scripts/run_model_size.py`, docstring). Every table and the chart are generated
from the run folders by `scripts/make_model_size.py`; `--check` fails if this page and the
data disagree.

## Question and design

With the controller held fixed, does a larger model control the signals better?

* **Controller:** `llm_guided_mp_v3` ("hybrid_v3"), the same setup as the gemma4 exploratory arm
  of the full experiments, so only the model changes. MaxPressure offers its top 2 phases plus
  keeping the current one, and the LLM picks one (prompt guided_v3, cooperative, no guard). On
  a failed call MaxPressure's choice is applied and the failure counted. Decision interval 5 s,
  min green 15 s, temperature 0, LLM seed = run seed.
* **Models** (smallest first):

| Model | Where it runs | Total parameters | Active per token | Source |
|---|---|---|---|---|
| `qwen2.5:3b` | local, Ollama (Q4_K_M) | 3.1 B | 3.1 B (dense) | Ollama `parameter_size` |
| `llama3.2:3b` | local, Ollama (Q4_K_M) | 3.2 B | 3.2 B (dense) | Ollama `parameter_size` |
| `gemma4:e4b` | local, Ollama (Q4_K_M) | 7.5 B | "E4B" = effective 4 B in Google's naming (most of the rest are per-layer embeddings) | Ollama `parameter_size`; model name |
| `llama3.1:8b` (arm A) | local, Ollama (Q4_K_M) | 8.0 B | 8.0 B (dense) | Ollama `general.parameter_count` 8,030,261,312 |
| `nvidia/nemotron-3-ultra-550b-a55b` (arm B) | **hosted**, NVIDIA NIM | 550 B (spec table: 560,524,578,816) | 55 B (Mamba2-Transformer LatentMoE) | build.nvidia.com model card (released 2026-06-04) |

  The local models are 4-bit quantized; the hosted model runs at whatever precision NVIDIA
  serves. "Size" therefore mixes parameter count with quantization and serving, and with
  architecture (dense vs mixture-of-experts). The chart orders the models by total parameters
  and labels both numbers.

* **How arm A was chosen** (rule stated before pulling it): an 8B-tagged general instruct model
  in the Ollama library from the same family as a 3B model already in the study, so mainly
  size changes. `llama3.2:3b` is pruned and distilled from Llama 3.1 8B, so `llama3.1:8b`
  qualifies and nothing else does. It is also the smallest 8B file among the candidates found
  in the registry (4692 MiB, against granite3.3:8b 4713, qwen3:8b 4983, ministral-3:8b
  5743 MiB). It has no thinking mode (capabilities: completion, tools); `think: false` is sent
  anyway, and the reasoning text returned is counted per call.
* **GPU/CPU split of arm A** (Ollama's automatic placement, as for every model; no `num_gpu`
  tuning): 2273 of 5073 MiB on the GPU, i.e. **45% on the GPU and 55% on the CPU**, at
  num_ctx 2048 on the GTX 1650 (nvidia-smi 2349 MiB used, so about 1.7 GB of VRAM stays free).
  Each benchmark run records its own split in `gpu.json`.

### The hosted arm (B)

* **Not local.** Every prompt of arm B (the intersection's queues, pressures, neighbours and
  ambulances) is sent to NVIDIA's servers. Here that is simulated traffic, but a deployment
  would send real camera-derived counts off the machine. Arm B is not an "on-device" result.
* **The hosted model can change without notice.** Each response's model id is recorded per call
  (`decisions.jsonl`, `server_model`) and per run (`summary.json`: `model`,
  `llm.server_reported_models`, and the run's timestamp; `hosted.json`: the `/models` listing
  and the date). The tables show the served id.
* **Why Nemotron 3 Ultra and not DeepSeek.** The plan first named
  `deepseek-ai/deepseek-v4.1-flash` (552 B total). On 2026-10-22 it answered 0 of 7 calls
  (timeouts of 120–300 s, 11:35–12:23 IST), although it is listed and the key works. The
  user's second choice, `nvidia/nemotron-3-super-120b-a12b`, answers "404 not found for
  account". Of the large models that answered a one-call scan, the user chose Nemotron 3 Ultra
  (550 B / 55 B active). Record: `outputs/model_size/probes/20261022_endpoint_availability.json`.
* **Settings, from probes** (`scripts/probe_hosted.py`, records in `outputs/model_size/probes/`):
  * reasoning is on by default (first call: 287 reasoning characters, 75 s). It is switched
    off with `chat_template_kwargs: {enable_thinking: false}` (0 reasoning characters);
  * structured output: OpenAI `response_format` json_schema is accepted and gives valid JSON;
    `nvext.guided_json` is rejected (HTTP 400). Every answer is still validated by
    `prompt.parse_response`, as for the local models;
  * temperature 0 like every other model here (NVIDIA's examples use 1.0);
  * `seed` is accepted. As with Ollama on a GPU, temperature 0 is not a promise of
    bit-for-bit repeatable answers.
* **Rate limits of the key** (measured; NIM sends no rate-limit headers, and a 429 says only
  "Too Many Requests", without Retry-After):
  * 5 sequential calls: all 200, 0.7–2.2 s;
  * a burst of 50 one-token calls on 8 threads: 23 succeeded and 27 got 429. The first 429
    came 0.6 s in; about 18–20 requests were accepted at once, then roughly one per 0.5–0.7 s;
  * sequential calls paced at up to 60/min for 90 s: 46 calls (about 30/min, since each call
    takes time), 45 succeeded and 1 got 429. Median latency 0.73 s, maximum 18.6 s.
  
  The client therefore limits itself to **30 requests per minute**, counting every attempt.
  It retries HTTP 429/5xx and dropped connections up to 5 times with exponential backoff
  (2, 4, 8, … s, at most 60 s, or the server's Retry-After if longer). Retries are counted
  separately from failures: a decision fails only if it ends without a valid answer. A
  timeout (60 s) is a failure and is not retried, as for Ollama.
* **API key setup** (for anyone reproducing arm B). Put the key in a file `.env` at the repo
  root, which is gitignored (`git check-ignore .env` must print `.env`; a test checks it):

  ```bash
  printf 'NVIDIA_API_KEY=%s\n' "$(read -rsp 'NVIDIA API key: ' k; echo "$k")" > .env
  chmod 600 .env
  ```

  `read -s` keeps the key off the screen and out of the shell history. The client reads the
  key from the environment or `.env` and only ever puts it in the HTTP Authorization header;
  it is never printed, logged or written to `outputs/`.

### Steps

1. **Benchmark** (600 s, `indian_2x2_peak`, seed 0) for arms A and B; the other models'
   benchmark runs with this setup already exist. Then stop for the user's go.
2. **Full runs** (3600 s) after the go: `indian_2x2_peak` seeds 0–2 and `indian_2x2_peak_amb`
   (emergency) seeds 0–4 for `qwen2.5:3b`, `llama3.2:3b`, `llama3.1:8b` and Nemotron 3 Ultra
   (32 runs; gemma4's exist). `llama3.2:3b`'s full runs in `docs/results.md` used the guarded
   controller, so they are not reused here. Local models one at a time on an otherwise idle
   GPU; the hosted model last.
3. **Report:** the tables below and a chart of control quality against model size.

No selection rule, no significance test, no tuning: with 3 and 5 seeds per scenario the numbers
are reported as measured, with their spread.

## Step 1: benchmark (600 s, Indian 2x2 peak, seed 0)

"Follows pressure" = share of successful calls whose answer is the highest-pressure allowed
phase, from a replay of the run that reproduces its ATT exactly
(`scripts/analyze_llm_decisions.py`). It describes the decisions; it is not a simulator metric.
"Latency" is the answered request; "whole call" adds rate-limit waits, backoff and retried
attempts (recorded only by runs of this study). The earlier runs (qwen2.5, llama3.2, gemma4)
are reused from the final design round.

GPU memory: nvidia-smi peak minus idle is measured during the run. Ollama's `/api/ps` numbers
are shown as reported, but for `gemma4:e4b` they cannot be right: 217 MiB for a model whose
file is 6278 MiB, the same anomaly as in `docs/llm_benchmark.md`. So its GPU/CPU split is
unknown; nvidia-smi saw 2852 MiB.

<!-- BEGIN:model_size_bench -->
| Model | Where | Parameters total / active (B) | GPU memory: nvidia-smi peak − idle (Ollama size_vram / size), MiB | Calls | Failures | Retries | Latency mean / p95 (s) | Whole call p95 (s) | ATT at 600 s (s) | ATT vs MaxPressure | Queue / int. (veh) | Follows pressure | Answer differs from MaxPressure | Wall time (min) | Model id the server returned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen2.5:3b` | local (Ollama) | 3.1 / 3.1 (dense) | 2058 (1985 / 1985) | 273 | 7.7% (reason_too_long 21) | – | 1.13 / 1.32 | – | 120.0 | +29.7% | 21.44 | 20% | 80% | 5 | `qwen2.5:3b` |
| `llama3.2:3b` | local (Ollama) | 3.2 / 3.2 (dense) | 2280 (2210 / 2210) | 299 | 0.0% (none) | – | 1.03 / 1.19 | – | 140.8 | +52.1% | 28.34 | 5% | 98% | 5 | `llama3.2:3b` |
| `gemma4:e4b` | local (Ollama) | 7.5 / E4B: effective 4 | 2852 (217 / 217) | 151 | 0.0% (none) | – | 4.45 / 4.80 | – | 93.6 | +1.2% | 12.46 | 78% | 23% | 11 | `gemma4:e4b` |
| `llama3.1:8b` | local (Ollama) | 8 / 8.0 (dense) | 2368 (2274 / 5073) | 127 | 0.0% (none) | 0 | 3.70 / 4.48 | 4.48 | 94.3 | +1.9% | 12.53 | 61% | 44% | 8 | `llama3.1:8b` |
| `nvidia/nemotron-3-ultra-550b-a55b` | hosted (NIM) | 550 / 55 (MoE) | – | 128 | 0.0% (none) | 0 | 2.30 / 6.79 | 7.36 | 92.4 | -0.1% | 11.79 | 99% | 2% | 5 | `nvidia/nemotron-3-ultra-550b-a55b` |
| MaxPressure (baseline) | – | – | – | – | – | – | – | – | 92.5 | +0.0% | 11.85 | – | – | – | – |
<!-- END:model_size_bench -->

## Step 2: full runs (3600 s)

Indian 2x2 peak (seeds 0–2) and the same peak with ambulances (`indian_2x2_peak_amb`, the
emergency scenario of `docs/emergency.md`, seeds 0–4). `gemma4:e4b`'s runs and the baselines
are those of the full experiments; the other models' runs are this study's. "ATT vs
MaxPressure" is the mean over seeds of each run's difference from MaxPressure on the same seed.
"Follows pressure" and "differs from MaxPressure" are pooled over all successful calls of the
model's runs, counted from `decisions.jsonl`, which records MaxPressure's pressures at every
decision. On the benchmark runs this count equals the replay's. When a call fails, MaxPressure's
choice is applied, and the failure is counted. A model whose runs are not all finished is
listed without numbers.

**Indian 2x2 peak (3 seeds)**

<!-- BEGIN:model_size_full -->
| Model | Total params (B) | ATT (s), mean ± std | ATT vs MaxPressure, mean (range over seeds) | Seeds worse than MaxPressure | Queue / int. (veh) | Follows pressure | Answer differs from MaxPressure | Failed calls → MaxPressure's choice applied | Retries | Wall time / run (min) | Model id the server returned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen2.5:3b` | 3.1 | 174.4 ± 2.8 | +51.0% (+47.6 to +53.5) | 3 of 3 | 36.52 ± 1.37 | 17% | 83% | 308 of 5229 (5.9%): reason_too_long 308 | 0 | 33 | `qwen2.5:3b` |
| `llama3.2:3b` | 3.2 | 209.6 ± 8.9 | +81.4% (+74.1 to +86.1) | 3 of 3 | 46.86 ± 2.22 | 2% | 99% | 0 of 5393 (0.0%) | 0 | 31 | `llama3.2:3b` |
| `gemma4:e4b` | 7.5 | 113.7 ± 0.3 | -1.5% (-2.2 to -0.5) | 0 of 3 | 17.33 ± 0.44 | 80% | 21% | 3 of 2541 (0.1%): reason_too_long 3 | – | 64 | `gemma4:e4b` |
| `llama3.1:8b` | 8 | 117.1 ± 2.6 | +1.4% (-1.4 to +4.3) | 2 of 3 | 18.34 ± 1.10 | 62% | 43% | 0 of 2207 (0.0%) | 0 | 44 | `llama3.1:8b` |
| `nvidia/nemotron-3-ultra-550b-a55b` | 550 | 114.8 ± 3.6 | -0.6% (-3.1 to +3.9) | 1 of 3 | 17.60 ± 1.31 | 99% | 2% | 39 of 2205 (1.8%): retries_exhausted 37, timeout 2 | 2560 | 136 | `nvidia/nemotron-3-ultra-550b-a55b` |
| MaxPressure (baseline) | – | 115.5 ± 0.9 | +0.0% | – | 17.83 ± 0.32 | – | – | – | – | – | – |
<!-- END:model_size_full -->

**Emergency scenario (peak with ambulances, 5 seeds)**

<!-- BEGIN:model_size_full_amb -->
| Model | Total params (B) | ATT (s), mean ± std | ATT vs MaxPressure, mean (range over seeds) | Seeds worse than MaxPressure | Queue / int. (veh) | Follows pressure | Answer differs from MaxPressure | Failed calls → MaxPressure's choice applied | Retries | Wall time / run (min) | Model id the server returned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen2.5:3b` | 3.1 | 183.5 ± 2.7 | +58.7% (+54.0 to +64.8) | 5 of 5 | 40.09 ± 0.33 | 11% | 90% | 206 of 10031 (2.1%): reason_too_long 206 | 0 | 41 | `qwen2.5:3b` |
| `llama3.2:3b` | 3.2 | 197.8 ± 3.8 | +71.0% (+65.1 to +76.2) | 5 of 5 | 43.63 ± 1.30 | 4% | 98% | 0 of 8013 (0.0%) | 0 | 29 | `llama3.2:3b` |
| `gemma4:e4b` | 7.5 | 112.9 ± 1.9 | -2.4% (-5.3 to +1.6) | 1 of 5 | 17.11 ± 0.30 | 81% | 20% | 2 of 4146 (0.0%): reason_too_long 2 | – | 65 | `gemma4:e4b` |
| `llama3.1:8b` | 8 | 115.5 ± 1.8 | -0.1% (-2.6 to +1.2) | 3 of 5 | 17.92 ± 0.58 | 71% | 33% | 2 of 3619 (0.1%): reason_too_long 2 | 0 | 46 | `llama3.1:8b` |
| `nvidia/nemotron-3-ultra-550b-a55b` | 550 | not finished (0 of 5 seeds) |  |  |  |  |  |  |  |  |  |
| MaxPressure (baseline) | – | 115.7 ± 2.3 | +0.0% | – | 17.97 ± 0.86 | – | – | – | – | – | – |
| MaxPressure + preemption (baseline) | – | 116.0 ± 0.7 | – | – | 18.08 ± 0.41 | – | – | – | – | – | – |
<!-- END:model_size_full_amb -->

**Ambulances (emergency scenario).** The primary ambulance metric of `docs/emergency.md`:
travel time of the signal-relevant ambulances (routes through at least one signal), pooled over
the 5 seeds. "Paired" compares the same ambulance (same seed and vehicle) under the two
controllers. None of the hybrid_v3 runs preempt. The LLM sees the ambulances in its prompt and
picks among MaxPressure's top two phases or keeping the current one.

<!-- BEGIN:model_size_ambulances -->
| Controller / model | Signal-relevant ambulances finished | Travel time, mean (s) | Stopped time, mean (s) | vs MaxPressure, paired | vs MaxPressure + preemption, paired |
|---|---|---|---|---|---|
| `qwen2.5:3b` | 29 of 29 | 148.5 | 77.5 | +18.4 s (11 faster, 18 slower, of 29) | +67.3 s (3 faster, 26 slower, of 29) |
| `llama3.2:3b` | 29 of 29 | 161.8 | 86.4 | +31.7 s (13 faster, 16 slower, of 29) | +80.6 s (5 faster, 24 slower, of 29) |
| `gemma4:e4b` | 29 of 29 | 82.2 | 15.3 | -47.9 s (27 faster, 2 slower, of 29) | +1.1 s (16 faster, 12 slower, of 29) |
| `llama3.1:8b` | 29 of 29 | 97.0 | 29.7 | -33.1 s (23 faster, 6 slower, of 29) | +15.8 s (9 faster, 19 slower, of 29) |
| `nvidia/nemotron-3-ultra-550b-a55b` | not finished (0 of 5 seeds) |  |  |  |  |
| MaxPressure (baseline) | 29 of 29 | 130.1 | 62.3 | +0.0 s (0 faster, 0 slower, of 29) | +48.9 s (1 faster, 28 slower, of 29) |
| MaxPressure + preemption (baseline) | 29 of 29 | 81.2 | 14.1 | -48.9 s (28 faster, 1 slower, of 29) | +0.0 s (0 faster, 0 slower, of 29) |
<!-- END:model_size_ambulances -->

## Chart

![Control quality vs model size: ATT vs MaxPressure, ambulance travel time and share of
pressure-following decisions, per model ordered by total parameters](figures/model_size.svg)

Models are ordered by total parameters; the spacing is not to scale. The hosted model is
mixture-of-experts, with 55 B parameters active per token, and the local models are 4-bit
quantized. "Size" therefore mixes several things (see the sizes table above). The tables above
hold the numbers.

## Hosted API reliability (arm B)

The benchmark run (2026-10-22) needed no retries. During the full runs (from 2026-10-23) NVIDIA's
endpoint throttled the key far below what the probes measured the day before. Many calls got
HTTP 429 (sometimes 503) several times before being answered, and the server answered only a
few calls per minute, well below the client's own 30/min limit. Three things follow:

* **Waiting does not change the traffic.** The simulator stands still while a call is in
  progress, so throttling stretches wall time but not the simulated traffic.
* **Calls that ran out of retries are failures.** After 5 retries with backoff (or a 60 s
  timeout), MaxPressure's choice is applied for that decision. These are counted as failures,
  apart from the retries, in the tables above and below.
* **The batch was left unchanged.** Every arm B run uses the pre-registered settings (30/min,
  5 retries), so the eight full runs stay comparable with each other. A run under heavier
  throttling simply has more MaxPressure fallbacks, and the table shows how many.

<!-- BEGIN:model_size_hosted -->
| Started (IST) | Run | Sim steps | Calls | Calls that needed retries | Retries (HTTP status) | Failed calls → MaxPressure's choice applied | Wall time (min) | Wall s per sim s | Client waits: rate limiter + backoff (min) | Model id the server returned |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-22 12:33 | indian_2x2_peak s0 | 600 | 128 | 0 (0%) | 0 | 0 (0.0%) | 5 | 0.54 | 0 | `nvidia/nemotron-3-ultra-550b-a55b` |
| 2026-10-23 10:23 | indian_2x2_peak s0 | 3600 | 736 | 286 (39%) | 718 (429: 714, 503: 4) | 11 (1.5%): retries_exhausted 10, timeout 1 | 121 | 2.02 | 75 | `nvidia/nemotron-3-ultra-550b-a55b` |
| 2026-10-23 12:22 | indian_2x2_peak s1 | 3600 | 734 | 351 (48%) | 854 (429: 849, 503: 5) | 12 (1.6%): retries_exhausted 11, timeout 1 | 135 | 2.25 | 86 | `nvidia/nemotron-3-ultra-550b-a55b` |
| 2026-10-23 14:36 | indian_2x2_peak s2 | 3600 | 735 | 417 (57%) | 988 (429: 985, 503: 3) | 16 (2.2%): retries_exhausted 16 | 150 | 2.51 | 97 | `nvidia/nemotron-3-ultra-550b-a55b` |

4 of 9 arm B runs finished.
<!-- END:model_size_hosted -->
