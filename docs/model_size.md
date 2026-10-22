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

## Step 2: full runs

<!-- BEGIN:model_size_full -->
(not run yet)
<!-- END:model_size_full -->
