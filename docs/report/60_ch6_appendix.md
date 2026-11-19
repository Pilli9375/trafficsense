# Appendix {#sec:appendix}

The appendix gives what is needed to find, check and repeat the work: where the code is and how to
reproduce the results (@sec:app-repro), the main configuration (@sec:app-config) and the abbreviations
(@sec:abbrev). The report prints no source code. The full tables, the prompts, the configuration files and
the long derivations that did not fit the page limit are in `docs/report/extended/` of the repository.

## Source Code and Reproducibility {#sec:app-repro}

**The complete source code** (simulator wrapper, controllers, prompts, detector pipeline, dashboard,
tests and report tooling), the configuration and the result files are in the project repository,
<https://github.com/Pilli9375/trafficsense>. The code this report was built from is commit
`@@COMMIT@@`. Every run records its own commit, model, seed, scenario and run length in its
`summary.json`, and every table and number in this report is generated from, or checked against, the
files in `outputs/` by `scripts/make_report.py --check`. The project runs in WSL2 Ubuntu 22.04 with
Python 3.10; the batch scripts are resumable, and @tbl:repro lists the commands, run from the
repository root, that reproduce the results.

::: {#tbl:repro}
| Command | Reproduces |
|:----------------------------------------|:----------------------------|
| `pip install -e ".[dev]" -c requirements-lock.txt`, then `pytest -q` | the environment (setup steps: README) and the test suite |
| `python scripts/run_full_experiments.py` | the baselines and the LLM arms of Sections 4.1 to 4.4 |
| `python scripts/run_camera_error.py`, `python scripts/run_model_size.py --full` | camera errors and the exploratory model-size study |
| `python scripts/train_detector.py --full`, then `python scripts/eval_detector.py --stage val` and `--stage test` | the detector and its error model |
| `python scripts/make_report.py --check`, `python scripts/build_report.py` | the checks of every number, and this report |

: Commands that reproduce the results. The full list is in the extended material.
:::

To test these steps, the repository was cloned into an empty folder and set up from the README alone, and
every deterministic result was run again: all 42<!--=r.det_runs_identical--> of the
42<!--=r.det_runs--> runs of the fixed-time, Webster, MaxPressure and preemption controllers came out
identical in every metric, and a 600<!--=b.steps--> s run of the pre-registered LLM arm repeated the
committed run exactly, in all 121<!--=r.llm_identical_answers--> answers. LLM runs are not guaranteed to be
bit-for-bit repeatable on a GPU, which is why every decision is logged and replayable. The IDD dataset, the
detector weights and the hosted model's API key are not in the repository.

## Main Configuration {#sec:app-config}

Every setting used in the experiments is read from YAML files in `configs/`; no setting is typed into
code. @tbl:config summarises the main ones, copied from those files by the report's script. The files themselves are
reproduced in full in the extended material of the repository, in the folder
`docs/report/extended/` (file `05_configuration.md`).

::: {#tbl:config}
<!-- BEGIN:tab_config_summary -->
| Setting | Value | Read from |
|---------------------------------|---------------------------------|---------------------------------|
| Run length | 3600 s | configs/default.yaml |
| Decision interval (MaxPressure, preemption, LLM arms) | 5 s | configs/default.yaml |
| Minimum / maximum green, every controller | 10 s / 60 s | configs/default.yaml |
| Minimum green of MaxPressure and the LLM arms | 15 s | configs/default.yaml |
| FixedTime green per phase | 30 s | configs/default.yaml |
| Webster cycle length, allowed range | 60 to 180 s | configs/default.yaml |
| LLM sampling: temperature, context, answer tokens, timeout | 0, 2048 tokens, 128 tokens, 60 s | configs/default.yaml |
| Guard: a phase is accepted at this share of the top pressure | 0.8 | configs/default.yaml |
| Ambulance detection range | 150 m | configs/default.yaml |
| Demand, off-peak / peak | 2375 / 4750 veh/h | configs/scenarios/indian_2x2.yaml |
| Ambulances | 6 per hour over the network | configs/scenarios/indian_2x2.yaml |
| Detector: image size, batch, epochs (early-stopping patience) | 640 px, 8, 50 (10) | configs/default.yaml |
<!-- END:tab_config_summary -->

: Main configuration of the experiments.
:::

## Abbreviations {#sec:abbrev}

| Abbreviation | Meaning |
|:-------------|:--------|
| ATT | Average travel time (CityFlow's definition, @sec:method) |
| CoLLMLight | Cooperative LLM agents for network-wide traffic signal control (the base paper) |
| COCO | Common Objects in Context, the dataset whose object-size buckets we use |
| IDD | India Driving Dataset (IIIT Hyderabad and Intel) |
| IoU | Intersection over union of two bounding boxes |
| JSON | JavaScript Object Notation, the format of the LLM's answer |
| LLM | Large language model |
| mAP50, mAP50-95 | Mean average precision at IoU $\ge 0.5$, and averaged over IoU thresholds from $0.5$ to $0.95$ |
| RL | Reinforcement learning |
| SCATS / SCOOT | Sydney Coordinated Adaptive Traffic System / Split Cycle Offset Optimisation Technique |
| V2X | Vehicle-to-everything communication |
| YOLO | You Only Look Once, a family of one-stage object detectors |
