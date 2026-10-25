# Experimental Methodology {#sec:method}

A comparison between a new controller and established ones is easy to bias without meaning to:
by tuning the new method until it wins, by choosing the scenario or the metric after seeing the
results, or by comparing against a weak baseline. This chapter describes the safeguards used and
defines every metric.

## Pre-registration {#sec:prereg}

**Pre-registration** means writing down the design of an experiment and the rule that decides
its outcome *before* running it, and committing that to version control so the order can be
checked [@nosek2018prereg]. It separates confirmatory results, which test a fixed hypothesis,
from exploratory ones, which suggest new hypotheses. Every major step of this project was
pre-registered, and each study's document records the commit at which its plan was fixed
(@tbl:prereg).

::: {#tbl:prereg}
| Study | Fixed before any of its runs |
|:-------------------|:-----------------------------------------------------------|
| Demand calibration | the "drains" criterion, the rule for $R^*$, peak and off-peak |
| MaxPressure tuning | the swept settings and the rank-based selection rule with its tie-break (commits `8414f9a`, `c7a6e34`) |
| LLM benchmark | the setup and the model-selection rule; reused unchanged in every round |
| Final LLM design round | the three arms, and that its pick goes to the full experiments even if worse than MaxPressure |
| Full experiments | arms, scenarios, seeds, run length and analysis (commit `694dc0c`) |
| Emergency experiment | ambulance rate, seeds, controllers and the primary metric |
| Detector | class mapping, splits, image size, training settings; threshold frozen on validation (`876076d`) before the single test evaluation |
| Camera-error experiment | noise model, levels, runs, analysis and checks (`91aa214`) |
| Model-size study | models, runs and tables, committed before its runs, but the study itself was added after the main results (exploratory) |

: What was fixed in advance for each study. Commit hashes refer to the project's git history.
:::

**The model-selection rule.** Each LLM benchmark run is a 600<!--=b.steps--> s run of the Indian
peak scenario, seed 0. A model is **eligible** if fewer than 2<!--=b.rule.fail_pct-->% of its
calls failed and its 95th-percentile latency is below 3<!--=b.rule.p95_s--> s; among eligible
models the one with the lowest mean queue per intersection is chosen, ties broken by travel
time. The decision interval is then the shortest multiple of the 5 s transition that is at
least the chosen model's 95th-percentile latency times the number of intersections, so that a
full round of decisions fits in real time on one GPU.

**Deviations and additions, stated openly.** Four things were not part of the original plans and
are labelled wherever they appear:

1. **Prompt v3 is a post-hoc fix.** After the first rounds showed that the prompts never said
   which direction of pressure is better, two lines were changed (@sec:res-bench). The final
   design round, which used v3, was itself pre-registered and declared final.
2. **The `gemma4:e4b` hybrid arm is exploratory.** It failed the selection rule only on latency
   and was added to the full experiments, at the user's request, after their plan was fixed. It
   is labelled "exploratory, NOT selected by the rule" in every table.
3. **The model-size study** was planned after the main results and is exploratory.
4. **The camera-error decomposition** (one error source at a time) was added after the camera
   results had been read, to test an explanation offered for them; it is post-hoc.

## Scenarios, seeds and run length {#sec:seeds}

Every run simulates 3600<!--=cfg.steps--> s. The Indian off-peak and peak scenarios and Jinan 3x4
use seeds 0, 1 and 2; the emergency scenario uses seeds 0–4 because ambulances are few. On the
Indian network each seed is a different flow file, so seeds differ in traffic. Jinan has one
fixed flow file, so the deterministic baselines give identical results on every seed; only the
LLM runs vary there. LLM runs use the run seed as the sampling seed at temperature 0. Even so,
Ollama on a GPU is not bit-for-bit deterministic: a repeated run gives slightly different
answers in a few calls, after which the traffic diverges. Every decision is logged, so each LLM
run can be replayed exactly from its log, and the dashboard's replays are checked to reproduce
their runs' metrics.

The full experiments comprise 67<!--=f.runs--> runs (Indian off-peak and peak: all baselines and
both LLM arms; Jinan: baselines and the main arm; emergency: five controllers on five seeds). The
camera-error experiment comprises 130<!--=c.runs--> runs.

## Metrics {#sec:metrics}

All traffic metrics are measured from the simulator, never estimated.

* **Average travel time (ATT)**: CityFlow's `get_average_travel_time()` at the end of the run. It
  averages over every vehicle generated so far, from its scheduled start to its arrival or to the
  end of the run, *including time spent waiting to enter the network*. A controller that blocks
  an entry therefore cannot hide the delay it causes. ATT is the primary metric.
* **Queue length**: at each second, the number of waiting vehicles (speed below 0.1<!--=code.stop_speed--> m/s) on an
  intersection's incoming lanes; averaged over seconds and intersections.
* **Waiting time**: per vehicle, the seconds spent with speed below 0.1<!--=code.stop_speed--> m/s, averaged over
  vehicles.
* **Throughput**: vehicles that finished their trip within the hour.
* **Ambulance travel time**: finish time minus scheduled start, per signal-relevant ambulance
  (the same convention as ATT), pooled over seeds; also its median and the time it spent
  stopped. Each controller is also compared with preemption ambulance by ambulance.
* **LLM decision statistics**: calls, failures by type, mean and 95th-percentile latency, how
  often the LLM's answer differs from MaxPressure's choice, how often the guard overrode it, and
  how often the *applied* phase differs from MaxPressure's. These describe decisions; they are
  not traffic metrics.
* **Detector metrics**: mAP50 and mAP50-95 (Ultralytics), and precision, recall, miss rate and
  false detections per image from our own matching (@sec:det-eval).

Results are given as mean ± sample standard deviation over seeds. Because every controller sees
the same flow file on the same seed, the most informative comparison is **paired by seed**: each
arm's ATT minus MaxPressure's ATT on the same seed.

## Fairness of the comparison {#sec:fairness}

* **Same timing.** MaxPressure, preemption and all LLM arms decide on the same 5<!--=cfg.mp.interval--> s
  grid with the same 15<!--=cfg.mp.min_green--> s minimum green and
  60<!--=cfg.signal.max_green--> s maximum green, so they differ only in how they choose a phase.
* **Same traffic.** All controllers see the same flow file on the same seed, and ambulances are
  appended to the normal flow without changing any other vehicle.
* **Baselines tuned first.** MaxPressure and Webster were tuned (@sec:baselines) before any LLM
  run, and Webster's plan uses a perfect count of the simulated demand.
* **Clean runs.** Batch runs refuse to start from a git tree with uncommitted changes, so every
  result can be traced to a commit. In the LLM benchmark, every loaded model was unloaded and the
  GPU had to be idle before each model was tested.
* **Repeatability of baselines.** Every baseline run of the full experiments that repeats an
  earlier run (same scenario, controller, settings, seed and flow file) was compared with it:
  27<!--=f.reproduced--> of 27<!--=f.reproduced_of--> are identical in every metric.

## Statistical treatment {#sec:stats}

With three seeds per scenario (five with ambulances) a significance test has little power, and
none was pre-registered. Differences are therefore reported as measured, with their spread and,
for paired comparisons, the result on each seed. A difference is called a result only when it
has the same sign on every seed and is large compared with the seed-to-seed spread; smaller
differences are described as "within seed noise".
