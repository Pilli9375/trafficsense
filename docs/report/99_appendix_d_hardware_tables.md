# Hardware and Software {#sec:app-hw}

All experiments ran on one laptop.

| Component | Used |
|:-----------------|:------------------------------------------------------------|
| GPU | NVIDIA GeForce GTX 1650, 4 GB (local LLMs and detector training; never both at once) |
| CPU | AMD Ryzen 5 4600H |
| Memory | 16 GB RAM |
| Operating system | Windows with WSL2 Ubuntu 22.04 |
| Python | Python 3.10 (CityFlow does not build on Python 3.13) |
| Simulator | CityFlow, built from source |
| LLM server | Ollama, native `/api/chat` endpoint with JSON-schema structured output |
| Local models | `llama3.2:3b`, `qwen2.5:3b`, `gemma4:e4b`, `gemma3:4b` (round 1 only), `llama3.1:8b` (exploratory), 4-bit quantised |
| Hosted model | `nvidia/nemotron-3-ultra-550b-a55b` through NVIDIA's API (exploratory) |
| Detector | Ultralytics YOLOv8n, PyTorch with CUDA |
| Dashboard | Streamlit, Plotly, Playwright (screenshots and layout tests) |
| Report | pandoc, Tectonic (LaTeX), matplotlib |

The GTX 1650 limits the work in two ways that shape the results: `gemma3:4b` does not fit in its
memory and runs partly on the CPU, and the stronger `gemma4:e4b` needs several seconds per call, too
slow for real-time control of four intersections.

# Full Tables {#sec:app-tables}

## Every baseline run on the Indian network

::: {#tbl:app-per-seed}
<!-- BEGIN:tab_app_per_seed -->
| Level | Controller | Seed | ATT (s) | Queue / int. | Waiting (s) | Throughput | Waiting to enter |
|---------|-----------------------------------------|-----:|------:|------:|--------:|-----------:|--------:|
| offpeak | FixedTime, 4 paired phases, 30 s | 0 | 121.6 | 10.44 | 64.1 | 2285 | 0 |
| offpeak | FixedTime, 4 paired phases, 30 s | 1 | 121.2 | 10.53 | 63.1 | 2325 | 0 |
| offpeak | FixedTime, 4 paired phases, 30 s | 2 | 121.6 | 10.77 | 63.9 | 2338 | 0 |
| offpeak | FixedTime, all 8 phases, 30 s | 0 | 128.3 | 11.49 | 70.6 | 2267 | 0 |
| offpeak | FixedTime, all 8 phases, 30 s | 1 | 128.8 | 11.82 | 70.9 | 2304 | 0 |
| offpeak | FixedTime, all 8 phases, 30 s | 2 | 130.7 | 12.33 | 73.1 | 2322 | 0 |
| offpeak | FixedTime, 4 paired phases, Webster plan | 0 | 104.4 | 7.33 | 45.0 | 2280 | 0 |
| offpeak | FixedTime, 4 paired phases, Webster plan | 1 | 100.7 | 6.85 | 41.1 | 2329 | 0 |
| offpeak | FixedTime, 4 paired phases, Webster plan | 2 | 96.1 | 6.28 | 37.2 | 2350 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 0 | 87.2 | 4.72 | 29.0 | 2291 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 1 | 88.2 | 4.94 | 29.6 | 2347 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 2 | 89.1 | 5.17 | 30.7 | 2358 | 0 |
| offpeak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 0 | 81.0 | 3.73 | 22.9 | 2289 | 0 |
| offpeak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 1 | 81.6 | 3.82 | 22.9 | 2345 | 0 |
| offpeak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 2 | 81.3 | 3.86 | 22.9 | 2362 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 0 | 81.2 | 3.72 | 22.9 | 2290 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 1 | 82.2 | 3.92 | 23.5 | 2345 | 0 |
| offpeak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 2 | 82.7 | 4.07 | 24.1 | 2361 | 0 |
| peak | FixedTime, 4 paired phases, 30 s | 0 | 291.2 | 43.64 | 144.8 | 4061 | 325 |
| peak | FixedTime, 4 paired phases, 30 s | 1 | 275.8 | 44.54 | 142.3 | 4238 | 285 |
| peak | FixedTime, 4 paired phases, 30 s | 2 | 272.7 | 45.14 | 145.1 | 4198 | 313 |
| peak | FixedTime, all 8 phases, 30 s | 0 | 300.3 | 46.98 | 156.2 | 4016 | 335 |
| peak | FixedTime, all 8 phases, 30 s | 1 | 288.7 | 47.83 | 153.6 | 4188 | 311 |
| peak | FixedTime, all 8 phases, 30 s | 2 | 286.7 | 48.19 | 156.1 | 4135 | 347 |
| peak | FixedTime, 4 paired phases, Webster plan | 0 | 118.3 | 18.47 | 57.0 | 4477 | 1 |
| peak | FixedTime, 4 paired phases, Webster plan | 1 | 119.6 | 19.44 | 58.4 | 4637 | 0 |
| peak | FixedTime, 4 paired phases, Webster plan | 2 | 111.1 | 16.91 | 50.8 | 4617 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 0 | 116.0 | 17.53 | 54.1 | 4501 | 1 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 1 | 116.1 | 18.16 | 54.6 | 4634 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 2 | 114.5 | 17.80 | 53.5 | 4594 | 0 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 0 | 152.0 | 28.47 | 87.9 | 4410 | 1 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 1 | 122.2 | 19.78 | 59.4 | 4634 | 0 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 2 | 127.4 | 21.48 | 64.6 | 4575 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 0 | 162.9 | 31.69 | 97.8 | 4366 | 1 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 1 | 136.3 | 24.18 | 72.6 | 4610 | 0 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 2 | 127.9 | 21.65 | 65.1 | 4572 | 0 |
<!-- END:tab_app_per_seed -->

: Every baseline run on the Indian 2x2 network (seeds 0–2), including the two MaxPressure
settings not chosen by the tuning.
:::

## MaxPressure decision-interval sweep

::: {#tbl:app-mp-selection}
<!-- BEGIN:tab_app_mp_selection -->
| Interval | Rank: jinan_3x4 | Rank: hangzhou_4x4 | Rank: indian_2x2_offpeak | Rank: indian_2x2_peak | Mean rank | Mean ATT / best |
|------------|------------:|---------------:|----------------------:|-------------------:|-------:|--------:|
| 5 s | 1 | 1 | 2 | 5 | 2.25 | 1.059 |
| 10 s | 3 | 3 | 3 | 2 | 2.75 | 1.028 |
| 15 s | 2 | 2 | 1 | 4 | 2.25 | 1.042 |
| 20 s | 4 | 4 | 4 | 1 | 3.25 | 1.045 |
| 30 s | 5 | 5 | 5 | 3 | 4.50 | 1.158 |
<!-- END:tab_app_mp_selection -->

: First tuning sweep (decision interval, minimum green 10 s): rank of each interval per scenario.
The 5 s and 15<!--=docs/baselines.md | mp_selection | chosen | Interval--> s settings tie on mean rank; the tie-break chose
15<!--=docs/baselines.md | mp_selection | chosen | Interval--> s, which the minimum-green sweep
(@tbl:mg-selection) later replaced.
:::

## Validation against CoLLMLight

::: {#tbl:app-crosscheck}
<!-- BEGIN:tab_app_crosscheck -->
| Dataset | Run | ATT (their def.) | Throughput (their def.) | Queue (their def.) | Waiting (their def.) | CityFlow ATT | Engine seed |
|-----------|---------------------------------------|------:|----------:|------:|-------:|--------:|------:|
| Synthetic 4x4 | CoLLMLight code: FixedTime | 1192.5 | 751 | 467.3 | 1215.6 | 1612.0 | 47 |
| Synthetic 4x4 | Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1192.5 | 751 | 467.3 | 1215.6 | 1612.0 | 47 |
| Synthetic 4x4 | CoLLMLight code: MaxPressure | 683.1 | 2505 | 468.4 | 84.8 | 1263.3 | 47 |
| Synthetic 4x4 | Ours, MaxPressure matched to theirs | 683.1 | 2505 | 468.4 | 84.8 | 1263.3 | 47 |
| Jinan 3x4 | CoLLMLight code: FixedTime | 1239.3 | 1786 | 1338.6 | 920.3 | 1258.0 | 47 |
| Jinan 3x4 | Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1239.3 | 1786 | 1338.6 | 920.3 | 1258.0 | 47 |
| Jinan 3x4 | CoLLMLight code: MaxPressure | 273.2 | 4187 | 106.6 | 38.2 | 317.8 | 47 |
| Jinan 3x4 | Ours, MaxPressure matched to theirs | 273.2 | 4187 | 106.6 | 38.2 | 317.8 | 47 |
| Hangzhou 4x4 | CoLLMLight code: FixedTime | 1002.8 | 1526 | 694.5 | 827.5 | 1054.7 | 47 |
| Hangzhou 4x4 | Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1002.8 | 1526 | 694.5 | 827.5 | 1054.7 | 47 |
| Hangzhou 4x4 | CoLLMLight code: MaxPressure | 325.3 | 2751 | 69.0 | 49.6 | 365.7 | 47 |
| Hangzhou 4x4 | Ours, MaxPressure matched to theirs | 325.3 | 2751 | 69.0 | 49.6 | 365.7 | 47 |
<!-- END:tab_app_crosscheck -->

: Validation runs scored with CoLLMLight's metric definitions: their code against ours, same
settings and CityFlow seed.
:::

## What the models chose in the benchmark

::: {#tbl:app-bench-full}
<!-- BEGIN:tab_app_bench_full -->
| Arm (prompt) | Model | Successful calls | Kept current phase | Chose highest-pressure phase | Chose lowest-pressure phase | Kept current although another had higher pressure |
|------------------|----------------|---------:|-------:|--------------:|-------------:|------------------:|
| v1 (v1) | `gemma3:4b` | 333 | 86% | 4% | 51% | 95% |
| v1 (v1) | `gemma4:e4b` | 159 | 35% | 9% | 29% | 34% |
| v1 (v1) | `llama3.2:3b` | 270 | 77% | 2% | 34% | 84% |
| v1 (v1) | `qwen2.5:3b` | 159 | 34% | 18% | 25% | 34% |
| v2 (v2) | `gemma4:e4b` | 120 | 0% | 40% | 9% | 0% |
| v2 (v2) | `llama3.2:3b` | 350 | 89% | 6% | 48% | 99% |
| v2 (v2) | `qwen2.5:3b` | 251 | 88% | 6% | 49% | 100% |
| hybrid (guided) | `gemma4:e4b` | 283 | 78% | 18% | 83% | 84% |
| hybrid (guided) | `llama3.2:3b` | 286 | 79% | 4% | 86% | 86% |
| hybrid (guided) | `qwen2.5:3b` | 221 | 78% | 25% | 77% | 80% |
| v3 (v3) | `gemma4:e4b` | 122 | 4% | 57% | 9% | 3% |
| v3 (v3) | `llama3.2:3b` | 350 | 88% | 9% | 50% | 99% |
| v3 (v3) | `qwen2.5:3b` | 355 | 89% | 5% | 48% | 100% |
| hybrid_v3 (guided_v3) | `gemma4:e4b` | 151 | 28% | 78% | 22% | 23% |
| hybrid_v3 (guided_v3) | `llama3.2:3b` | 299 | 81% | 5% | 90% | 90% |
| hybrid_v3 (guided_v3) | `qwen2.5:3b` | 252 | 82% | 20% | 81% | 86% |
| guarded_v3 (guided_v3) | `gemma4:e4b` | 127 | 17% | 88% | 9% | 9% |
| guarded_v3 (guided_v3) | `llama3.2:3b` | 121 | 66% | 13% | 71% | 70% |
| guarded_v3 (guided_v3) | `qwen2.5:3b` | 114 | 75% | 26% | 72% | 72% |
<!-- END:tab_app_bench_full -->

: Benchmark decisions replayed from the logs: how often each model kept the current phase and chose
the highest- or lowest-pressure option. Pressures are MaxPressure's at the moment of each decision.
:::

## LLM arm under camera errors

::: {#tbl:app-camera-llm}
<!-- BEGIN:tab_app_camera_llm -->
| scenario | level | LLM calls | failures | guard overrides | disagrees with MP | mean latency (s) |
|----------------|--------------|----------:|-------------:|---------------:|---------------:|------------:|
| Off-peak | perfect | 2177 | 0 | 81.2% | 91.5% | 1.02 |
|  | junction | 2195 | 0 | 85.2% | 93.1% | 1.00 |
|  | crowded | 2189 | 0 | 82.5% | 92.9% | 1.00 |
| Peak | perfect | 2167 | 0 | 82.8% | 92.8% | 0.99 |
|  | junction | 2174 | 0 | 86.1% | 92.4% | 0.99 |
|  | crowded | 2175 | 0 | 85.1% | 92.6% | 0.99 |
| Emergency | perfect | 3632 | 0 | 76.3% | 86.9% | 1.03 |
|  | junction | 3646 | 0 | 78.8% | 87.8% | 1.03 |
<!-- END:tab_app_camera_llm -->

: The pre-registered LLM arm's decisions at each camera level.
:::

## Hosted model runs (exploratory)

::: {#tbl:app-hosted}
<!-- BEGIN:tab_app_hosted -->
| Started (IST) | Run | Calls | Calls that needed retries | Failed calls → MaxPressure's choice applied | Wall time (min) |
|---------------|--------------------|------:|----------:|---------------------------------------|------:|
| 2026-10-22 12:33 | indian_2x2_peak s0 | 128 | 0 (0%) | 0 (0.0%) | 5 |
| 2026-10-23 10:23 | indian_2x2_peak s0 | 736 | 286 (39%) | 11 (1.5%): retries_exhausted 10, timeout 1 | 121 |
| 2026-10-23 12:22 | indian_2x2_peak s1 | 734 | 351 (48%) | 12 (1.6%): retries_exhausted 11, timeout 1 | 135 |
| 2026-10-23 14:36 | indian_2x2_peak s2 | 735 | 417 (57%) | 16 (2.2%): retries_exhausted 16 | 150 |
| 2026-10-23 17:07 | indian_2x2_peak_amb s0 | 733 | 415 (57%) | 15 (2.0%): retries_exhausted 15 | 160 |
| 2026-10-23 19:46 | indian_2x2_peak_amb s1 | 749 | 425 (57%) | 20 (2.7%): retries_exhausted 17, timeout 3 | 170 |
| 2026-10-23 22:34 | indian_2x2_peak_amb s2 | 746 | 413 (55%) | 17 (2.3%): retries_exhausted 15, timeout 2 | 159 |
| 2026-10-24 01:13 | indian_2x2_peak_amb s3 | 731 | 405 (55%) | 24 (3.3%): retries_exhausted 21, timeout 3 | 150 |
| 2026-10-24 03:43 | indian_2x2_peak_amb s4 | 732 | 392 (54%) | 17 (2.3%): retries_exhausted 16, timeout 1 | 150 |
<!-- END:tab_app_hosted -->

: Every run of the hosted model: calls that needed retries after rate limiting, and calls that ran
out of retries (MaxPressure's choice applied).
:::
