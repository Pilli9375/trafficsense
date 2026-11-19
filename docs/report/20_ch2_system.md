# Proposed System and Methodology {#sec:design}

This chapter describes what TrafficSense is made of and how a decision is made at one intersection
(@sec:architecture), how the work was carried out and checked (@sec:working), the standards followed
(@sec:standards) and the software and hardware used (@sec:system-details). Three rules, set before any code
was written because the results will be examined, shaped the design: **no invented data in the results
path**; **fail loudly** (a server that is down, an unparseable answer or an invalid setting stops the run,
and a fallback that is part of the design is counted and reported); and **every result records where it
came from** (controller, model, seed, scenario, run length, git commit, and for LLM runs the calls,
failures and latency). The full text of every section condensed here is in the repository
<https://github.com/Pilli9375/trafficsense>, in the folder `docs/report/extended/`.

## Proposed System {#sec:architecture}

@fig:architecture shows the components. The **CityFlow engine** simulates every vehicle and is the
only place where metrics are measured. An **environment wrapper** parses the road network, enforces
signal timing (a transition phase on every change, a minimum green of
10<!--=cfg.signal.min_green--> s and a maximum green of 60<!--=cfg.signal.max_green--> s; the tuned
MaxPressure and the LLM controllers use a longer minimum green of 15<!--=cfg.mp.min_green--> s) and
computes the metrics. Controllers read lane counts through an **observation layer**, which returns
the exact counts or, in the camera experiment, counts degraded by the detector's measured errors.
The LLM controllers are built on **MaxPressure's ranking** of phases, ask an **LLM agent** per
intersection, and pass its answer through a **guard** and the timing rules. Each run writes its
results to `outputs/`, from which the dashboard and this report are generated.

![System architecture. The simulator holds the exact state; controllers see it only through the
observation layer, which can add camera errors measured offline. Ambulance positions reach the
agent through a separate channel and are never noised.](figures/architecture.png){#fig:architecture width=70%}

### The Multi-Agent Decision Loop {#sec:loop}

Each signalised intersection has its own agent. Every 5<!--=cfg.mp.interval--> s of simulated time,
each intersection whose green has lasted at least the minimum green is asked for its next phase.
One decision has five steps. **Observe:** the agent receives a short text describing its own
intersection and its neighbours, and for each phase it may choose the phase's *pressure* (stopped
vehicles it would serve minus stopped vehicles on their exit roads) and *queue*; the
pre-registered controller's prompts averaged
277<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Prompt tokens--> tokens.
**Reason:** the prompt goes to a local model through Ollama's native `/api/chat` endpoint with a JSON
schema that restricts the answer to the allowed phase numbers and a short reason; sampling uses
temperature 0 and a fixed seed, a context of 2048<!--=cfg.llm.num_ctx--> tokens, at most
128<!--=cfg.llm.num_predict--> answer tokens and a timeout of 60<!--=cfg.llm.timeout_s--> s.
**Act:** the answer is parsed and checked (the phase must be one offered, the reason at most
15<!--=code.reason_words.guided_v3--> words); a failure is counted by type, and in the hybrid
controllers a failed call applies MaxPressure's choice and is reported as such. **Enforce:** the
wrapper inserts the transition and applies the green limits. **Log:** the state the agent saw,
MaxPressure's ranking, the raw answer, its latency and whether the guard intervened are written
to the run's `decisions.jsonl`. All agents share one GPU, so the calls of one round run one after
another; the simulator waits, so slow models cost wall-clock time, not simulated traffic.
Cooperation follows CoLLMLight: for each neighbour the prompt gives its current phase, how many
vehicles are stopped on its approaches towards this intersection and how many of those have green,
and how many are stopped on this intersection's road into the neighbour.

### Controller Variants {#sec:arms}

Six LLM designs ("arms") were compared (@tbl:arms). **Plain** arms let the LLM choose any green
phase. **Hybrid** arms let MaxPressure propose and the LLM decide among its two best phases and
keeping the current one. The **guarded** arm adds a check: the LLM's choice is applied only if its
pressure is close enough to the best phase's, $P(\text{LLM's phase}) \ge P_{\text{top}} - (1 - r)\,\lvert
P_{\text{top}} \rvert$ with $r$ = 0.8<!--=cfg.guard.ratio-->, i.e. within 20<!--=cfg.guard.margin-->% of
the top pressure; otherwise MaxPressure's choice is applied and the override is counted. The guard
was added because the small models in the earlier rounds preferred low-pressure phases
(@sec:res-bench). The prompt versions are in `docs/report/extended/04_prompts.md`.

::: {#tbl:arms}
| Arm | Controller | What the LLM chooses | Prompt |
|:-------------|:--------------------|:------------------------|:--------------------------------|
| v1 | `llm_v1` | any green phase | v1: per-movement counts, vehicle types, neighbours |
| v2 | `llm_cooperative` | any green phase | v2: shorter; pressure and queue per phase |
| hybrid | `llm_guided_mp` | MaxPressure's top 2 or keep current | guided |
| v3 | `llm_v3` | any green phase | v3 = v2 with two lines fixed |
| hybrid_v3 | `llm_guided_mp_v3` | MaxPressure's top 2 or keep current | guided_v3 |
| guarded_v3 | `llm_guarded_mp` | as hybrid_v3, then the guard | guided_v3 |

: The LLM controller designs. The pre-registered final design round compared the last three.
:::

### Ambulance Handling {#sec:ambulance-design}

An ambulance on an incoming lane within 150<!--=cfg.amb.range--> m of the stop line is detected. For
the hybrid and guarded arms the prompt lists each detected ambulance with its movement, its
distance and the phases that serve it, and the system prompt adds one sentence: ambulances, if
listed, must get through quickly. If no offered phase serves the ambulance, the best-ranked phase
that does is added to the options, and in the guarded arm such a phase is exempt from the guard. The
non-LLM competitor, `preemption_mp`, is MaxPressure with a rule that gives green to the
highest-pressure phase serving a detected ambulance. Ambulance positions are assumed to come from
a separate channel (GPS or V2X) and are not passed through the camera-noise layer.

### Camera-Noise Observation Layer {#sec:camera-design}

To test controllers on realistic counts without changing the traffic, the observation layer can
replace the engine's lane counts with noisy ones. Each time a controller observes, a fresh snapshot
is drawn for the whole network: each vehicle is detected with a class-dependent probability, a
detected vehicle may be given another class, and each road gains a random number of phantom stopped
vehicles. All rates come from the detector's measured errors (@sec:perception). The simulator
stays exact, so every metric is still measured from the true traffic.

### Dashboard {#sec:dashboard}

A Streamlit dashboard presents the results. It reads only files in `outputs/`, every chart and
number carries a source chip naming its file, and a test fails if a number shown does not appear in
the files the page read. Its four pages (headline result, live detection on video, a side-by-side
replay of two controllers, the result tables) are shown in @sec:res-dashboard.

## Working Methodology {#sec:working}

The work proceeded in steps, each checked before the next relied on it: the simulation pipeline was
validated against the CoLLMLight authors' code (@sec:simulation); an Indian-style network was
built with a source for every parameter and demand calibrated by a rule fixed in advance
(@sec:indian-scenario), and the baselines were tuned on it before any LLM run; a detector was
trained on Indian street images and its errors turned into an error model (@sec:perception); and
the experimental method and the pre-registration fixed scenarios, seeds, metrics and decision rules
in advance (@sec:method, @sec:prereg).

### Simulation and Validation {#sec:simulation}

CityFlow [@zhang2019cityflow] is a microscopic simulator designed for signal-control research and
is the simulator of CoLLMLight and most RL work. It is **lane-based**: it cannot represent vehicles
straddling lanes or two-wheelers filtering between cars, so our Indian scenario models the Indian
**vehicle mix** but not Indian **driving behaviour** (@sec:simulation). We run it with lane
changing switched off, so that the same phase sequence always gives exactly the same run, which we
verified by re-running every deterministic experiment from a fresh copy of the repository.

Before trusting any comparison we checked our environment wrapper, signal timing and metrics
against the CoLLMLight authors' own code (commit `ce204a9`), run unmodified in a separate
environment. Our environment was driven exactly as theirs (the same phases, one decision every
30<!--=val.matched.interval--> s, a 5 s transition, the same CityFlow seed) and every matched run was
scored with our metrics and with a line-by-line reimplementation of theirs. @tbl:validation shows
that throughput, queue length and waiting time are identical on all three datasets for both
controllers; average travel time is identical in all but one run, and elsewhere differs in the sixth
significant digit or beyond. These matched runs need lane changing on, where CityFlow is not exactly
repeatable even in their own code, so the remaining differences are within the simulator's own noise
and we consider the pipeline validated. The validation also showed that CoLLMLight's FixedTime agent
computes its next phase as `(cur_phase + 1) % 4` on a 1–4 index and the environment adds 1 again, so
it alternates between the two east–west phases and north–south traffic never gets a green; we use only
our own, correct fixed-time controllers. The walk-through and the table of the bug are in
`docs/report/extended/02_system_and_method.md`.

::: {#tbl:validation short="Our environment against CoLLMLight's code"}
<!-- BEGIN:tab_validation -->
| Dataset | Controller | ATT | Throughput | Queue | Waiting | CityFlow ATT |
|-----------------|---------------|-------------|--------------|-------------|-------------|--------------:|
| synthetic_4x4 | Fixedtime | identical | identical | identical | identical | 3.1e-07 rel. |
| synthetic_4x4 | MaxPressure | 3.7e-06 rel. | identical | identical | identical | 9.9e-07 rel. |
| Jinan 3x4 | Fixedtime | identical | identical | identical | identical | 1.8e-07 rel. |
| Jinan 3x4 | MaxPressure | identical | identical | identical | identical | 1.4e-06 rel. |
| hangzhou_4x4 | Fixedtime | identical | identical | identical | identical | identical |
| hangzhou_4x4 | MaxPressure | identical | identical | identical | identical | 4.6e-06 rel. |
<!-- END:tab_validation -->

: Our environment against CoLLMLight's code, both driven the same way and scored with their
metric definitions. "identical" means equal floating-point numbers; otherwise the relative
difference is shown. "CityFlow ATT" is the engine's own average travel time.
:::

### Scenario {#sec:indian-scenario}

The test network is a 2 × 2 grid generated with CityFlow's own grid generator: intersections
200<!--=scn.roadnet.spacing_m--> m apart, entry and exit roads 200<!--=scn.roadnet.boundary_road_m--> m
long, three lanes per direction (one per turn) 3.0<!--=scn.roadnet.lane_width_m--> m wide, a speed limit
of 12.5<!--=scn.roadnet.lane_max_speed_mps--> m/s, phase 0 a 5 s transition (free turns only) and phases
1–8 green. India drives on the left and the generator builds right-hand traffic, but a square grid is
mirror-symmetric, so CityFlow's right turn (kerb side, allowed in every phase) plays the role of India's
**free left turn** and its left turn (protected phase) plays the role of India's **right turn**. Each
vehicle type has its own length, gap, headway, speed and acceleration (@tbl:mix); the shares are the 2006
modal share of Chennai traffic [@itrans2009] with bicycles removed, buses and trucks split equally (an
assumption), and the lengths are Indian averages [@umapathi2019pcu]. The other values are assumptions
chosen to be plausible and not tuned to favour any controller; every parameter and its source is in
`configs/scenarios/indian_2x2.yaml` and the extended material.

::: {#tbl:mix}
<!-- BEGIN:tab_mix -->
| Type | Share | Length (m) | Width (m) | minGap (m) | headwayTime (s) | maxSpeed (m/s) |
|--------------------|----------:|-----------:|----------:|-----------:|-----------------:|--------------:|
| motorcycle | 45.1% | 1.67 | 0.7 | 1.0 | 1.0 | 12.5 |
| auto_rickshaw | 17.6% | 3.2 | 1.4 | 1.5 | 1.5 | 11.1 |
| car | 30.8% | 3.72 | 1.44 | 2.5 | 1.5 | 12.5 |
| bus | 1.6% | 10.1 | 2.43 | 2.5 | 2.0 | 11.1 |
| truck | 4.9% | 7.5 | 2.35 | 2.5 | 2.0 | 11.1 |
<!-- END:tab_mix -->

: Vehicle types of the Indian scenario. Share = normalised share of all vehicles.
:::

Vehicles arrive as a Poisson process on each of the 8 entry roads; east–west is the major road
(entry weight 1.0<!--=scn.entry_weights.W--> against 0.6<!--=scn.entry_weights.N--> for north–south),
and at each intersection a vehicle goes straight with probability
0.60<!--=scn.turn_probabilities.go_straight-->, takes the free turn with
0.25<!--=scn.turn_probabilities.turn_right--> and the right turn with
0.15<!--=scn.turn_probabilities.turn_left--> (assumptions). Each seed gives a different flow file.
The demand levels were set by a rule fixed before it was run: saturation flows were measured in the
simulator, MaxPressure was swept over total demands from
1000<!--=docs/indian_scenario.md | sweep | 1000 & 0.05 | Demand--> to
14000<!--=docs/indian_scenario.md | sweep | 14000 | Demand--> vehicles per hour on three seeds, and the
network "drains" if at most 2<!--=cal.rule.backlog_pct-->% of the vehicles are still waiting to enter
at the end of the hour and it empties within 900<!--=cal.rule.drain_s--> s. The lowest swept demand
that does not drain is $R^*$ = 5500<!--=cal.r_star--> veh/h; the **peak** level is the largest
draining demand at or below 0.9<!--=cal.rule.peak_fraction--> × $R^*$, 4750<!--=cal.peak--> veh/h, and
the **off-peak** level is 0.5<!--=cal.rule.offpeak_over_peak--> × peak, 2375<!--=cal.offpeak--> veh/h.
"Near capacity" here means near the capacity of MaxPressure as configured, not of the intersections
(@sec:baselines). The **emergency scenario** adds ambulances to the peak flow files at
6<!--=scn.emergency.veh_per_hour--> per hour over the whole network (an assumption), drawn from a
separate random generator so that normal traffic does not depend on them. Over seeds 0–4 there are
37<!--=e.mp.amb_all_n--> ambulances, of which 29<!--=e.mp.amb_n--> are **signal-relevant**: their
route crosses at least one movement a signal controls. CityFlow has no notion of yielding and the
ambulance cannot overtake, so only the signal can help it, which is what the controllers are tested
on. The calibration sweep and the capacity table are in the extended material.

### Perception {#sec:perception}

A deployed system would count vehicles with a camera and a detector. The perception part has a
narrow, measurable purpose: train a detector on real Indian street images, measure its errors in the
terms a signal controller cares about (missed vehicles, invented vehicles, wrong classes), and turn
them into an error model for the simulation experiment of @sec:res-camera. The detector does not
control signals directly.

We use the detection part of the **India Driving Dataset** (IDD) [@varma2019idd], filmed from a
moving vehicle, not from a pole at a junction. Seven classes are kept (car, motorcycle,
autorickshaw, bus, truck, bicycle, person); IDD's `rider` boxes are dropped, so that a two-wheeler is
not counted twice. IDD's official test labels are withheld, so our **test** split is the official
validation split, and our **validation** split is 10<!--=cfg.det.val_pct-->% of the official training
*drives*, chosen with a fixed seed; splitting by drive, not frame, stops near-duplicate consecutive
frames from leaking into training. The test split was evaluated once, after every choice, including
the confidence threshold, had been frozen on validation. Images are 640<!--=cfg.imgsz--> pixels on
the long side, which fits the GTX 1650, so distant objects are small and errors are reported by
object size. The detector is YOLOv8n [@jocher2023yolov8] from COCO weights, trained with batch
8<!--=cfg.det.batch--> and mixed precision off (GTX 16-series cards produce invalid losses with it)
for up to 50<!--=cfg.det.epochs--> epochs with early stopping after
10<!--=cfg.det.patience--> epochs; the run took 13.3<!--=d.train_h--> hours and its best epoch was
49<!--=d.best_epoch-->, so validation accuracy was still rising slowly.

The measurements become the **camera error model** (`outputs/perception/error_model.json`, read by
the simulation, never typed into code): each class's detection probability, the probability of each
predicted class given the true class, and a Poisson count of false detections per road and snapshot.
Two levels are defined (@tbl:camera-params): **junction**, which uses detection rates on medium and
large objects, since queued vehicles near a stop line are close to a pole camera, and **crowded /
far**, which uses rates over all objects and is dominated by distant ones. *Limitation:* these are the
errors of our detector on dash-camera images; a pole camera sees from a different height and angle, so
the model is a measured *proxy*, and the two levels bracket a range rather than predict one value.

::: {#tbl:camera-params short="Camera error parameters per detector class"}
<!-- BEGIN:tab_camera_params -->
| detector class | junction p_detect | crowded p_detect | false det. per road and snapshot |
|-----------------------------------|---------------------:|---------------------:|---------------------:|
| car | 0.936 | 0.568 | 0.222 |
| motorcycle | 0.913 | 0.567 | 0.271 |
| autorickshaw | 0.944 | 0.598 | 0.070 |
| bus | 0.907 | 0.632 | 0.039 |
| truck | 0.832 | 0.537 | 0.079 |
| bicycle (label only) | – | – | 0.006 |
<!-- END:tab_camera_params -->

: Camera error parameters used in the simulation, per detector class.
:::

### Experimental Method {#sec:method}

Every run simulates 3600<!--=cfg.steps--> s. The Indian off-peak and peak scenarios and Jinan 3x4 use
seeds 0, 1 and 2; the emergency scenario uses seeds 0–4. On the Indian network each seed is a
different flow file; Jinan has one fixed flow file, so the deterministic baselines give identical
results on every seed and only the LLM runs vary there. LLM runs use the run seed as the sampling
seed at temperature 0; even so, Ollama on a GPU is not bit-for-bit deterministic, so every decision
is logged and each run can be replayed exactly from its log. The full experiments comprise
67<!--=f.runs--> runs and the camera-error experiment 130<!--=c.runs--> runs.

All metrics are measured from the simulator. **Average travel time (ATT)**, the primary metric, is
CityFlow's `get_average_travel_time()` at the end of the run: it averages over every vehicle
generated so far, from its scheduled start, *including time spent waiting to enter the network*, so a
controller that blocks an entry cannot hide the delay it causes. **Queue length** is the number of
waiting vehicles (speed below 0.1<!--=code.stop_speed--> m/s) on an intersection's incoming lanes,
averaged over seconds and intersections; **waiting time** is the seconds each vehicle spends below that
speed; **throughput** is the vehicles that finished their trip; **ambulance travel time** is finish
time minus scheduled start for each signal-relevant ambulance. For LLM runs we also record calls,
failures by type, mean and 95th-percentile latency, and how often the answer, the guard and the
applied phase differ from MaxPressure's. Results are mean ± sample standard deviation over seeds;
since every controller sees the same flow file on the same seed, comparisons are **paired by seed**.

Fairness safeguards: MaxPressure, preemption and all LLM arms decide on the same 5<!--=cfg.mp.interval--> s
grid with the same minimum and maximum green; all controllers see the same traffic; MaxPressure and
Webster were tuned (@sec:baselines) before any LLM run, and Webster's plan uses a perfect count of the
simulated demand; batch runs refuse to start from a git tree with uncommitted changes; and each
baseline run that repeats an earlier one was compared with it, 27<!--=f.reproduced--> of
27<!--=f.reproduced_of--> being identical in every metric. With three seeds (five with ambulances) a
significance test has little power and none was pre-registered: a difference is called a result only
when it has the same sign on every seed and is large compared with the seed-to-seed spread, and
smaller differences are described as "within seed noise".

### Pre-registration {#sec:prereg}

**Pre-registration** means writing down the design of an experiment and the rule that decides its
outcome *before* running it, and committing it to version control so the order can be checked
[@nosek2018prereg]. It separates confirmatory results from exploratory ones. Every major step was
pre-registered (@tbl:prereg).

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

**The model-selection rule.** Each LLM benchmark run is a 600<!--=b.steps--> s run of the Indian peak
scenario, seed 0. A model is **eligible** if fewer than 2<!--=b.rule.fail_pct-->% of its calls failed
and its 95th-percentile latency is below 3<!--=b.rule.p95_s--> s; among eligible models the one with the
lowest mean queue per intersection is chosen, ties broken by travel time. The decision interval is the
shortest multiple of the 5 s transition that is at least the chosen model's 95th-percentile latency
times the number of intersections, so that a full round of decisions fits in real time on one GPU.

**Deviations and additions, stated openly.** Four things were not part of the original plans and are
labelled wherever they appear. (1) **Prompt v3 is a post-hoc fix:** after the first rounds showed that
the prompts never said which direction of pressure is better, two lines were changed; the final design
round, which used v3, was itself pre-registered and declared final. (2) **The `gemma4:e4b` hybrid arm
is exploratory:** it failed the selection rule only on latency and was added to the full experiments,
at the user's request, after their plan was fixed; it is labelled "exploratory, NOT selected by the
rule" in every table. (3) **The model-size study** was planned after the main results and is
exploratory. (4) **The camera-error decomposition** (one error source at a time) was added after the
camera results had been read, to test an explanation offered for them; it is post-hoc.

## Standards {#sec:standards}

TrafficSense is a simulation and software study that controls no signal in the field, so no standard
for traffic-signal equipment applies. @tbl:standards lists the formats and practices it does follow;
each is used by the code itself, so a departure would break a run, a test or a check.

::: {#tbl:standards}
| Area | Standard or convention | Where and how it is used |
|:---------------|:--------------------------------|:------------------------------------------------|
| Road network and demand | CityFlow's road-network and flow file formats (JSON) | The Indian 2x2 network and its flows are generated in these formats and run by the unmodified engine |
| Data interchange, LLM output | JSON (RFC 8259) and JSON Lines for result files and logs; JSON Schema through Ollama's `format` field | Every `summary.json` and `decisions.jsonl`; an LLM answer must be an allowed phase and a short reason, and our code checks it again |
| Detector data and metrics | IDD annotations in Pascal VOC XML and the YOLO label format; COCO-style mAP at IoU $0.5$ and averaged over IoU $0.5$ to $0.95$, COCO's object-size buckets | `perception/idd.py`; @sec:res-detector |
| Experiment design | Pre-registration [@nosek2018prereg] | Every study (@sec:prereg) |
| Licences | The licences and terms of use of every tool, dataset and model | Chapter 3; the dataset and the model weights are not redistributed |

: Standards, formats and conventions followed.
:::

## System Details {#sec:system-details}

This section lists the software the system is built from and the hardware it ran on. The complete
source code, the configuration and the instructions to run it are at
<https://github.com/Pilli9375/trafficsense>.

### Software Details {#sec:software}

@tbl:software lists the software. Python package versions are those pinned in the repository's lock
file (`requirements-lock.txt`), the environment every committed result was checked with; the Ollama
version is the one every local LLM run recorded. The controllers, the observation layer, the
experiment scripts and the dashboard are the project's own Python code, available at the repository
link above.

::: {#tbl:software}
<!-- BEGIN:tab_software -->
| Component | Software | Version | Used for |
|------------------|---------------------------------|------------------------|------------------------|
| Operating system | Ubuntu in WSL2 on Windows 11 | 22.04.5 | everything below |
| Language | Python | 3.10.12 | all project code |
| Simulator | CityFlow, built from source | commit `81ee0f4` | traffic simulation |
| LLM server | Ollama, native `/api/chat` with a JSON schema | 0.40.3 | local LLM agents |
| Local LLMs | `llama3.2:3b` (selected), `qwen2.5:3b`, `gemma4:e4b`; `gemma3:4b` (round 1 only); `llama3.1:8b` (model-size study) | 4-bit quantised Ollama builds | signal-control agents |
| Hosted LLM | `nvidia/nemotron-3-ultra-550b-a55b`, NVIDIA's API | as served | exploratory model-size study |
| Detector | Ultralytics (YOLOv8n); PyTorch, torchvision (CUDA build) | 8.4.183; 2.14.1+cu126, 0.29.1+cu126 | training and inference |
| Libraries | NumPy, PyYAML, requests, OpenCV, Pillow | 2.2.6, 6.0.3, 2.34.2, 5.0.0.93, 12.3.0 | metrics, `configs/*.yaml`, API calls, images and video |
| Charts | Matplotlib, Plotly | 3.10.9, 7.1.0 | report figures, dashboard charts |
| Dashboard | Streamlit | 1.65.0 | the four dashboard pages |
| Tests | pytest, Playwright (Chromium) | 9.1.1, 1.64.1 | test suite, dashboard layout tests |
| Report | pandoc, LibreOffice, pypdfium2 | 3.12.1, 25.8.6.2, 5.14.0 | this report (Word file and PDF) |
<!-- END:tab_software -->

: Software used, with versions.
:::

### Hardware Details {#sec:hardware}

All experiments, the detector training and this report ran on one laptop (@tbl:hardware); a second laptop
was used only to check that the setup can be reproduced from the README. **There is no field hardware:**
every experiment is a simulation, and the detector was trained and tested on recorded images. The GTX 1650
limits the work: `gemma3:4b` does not fit in its memory, `gemma4:e4b` needs several seconds per call, too
slow for real-time control of four intersections, and the LLM and the detector never shared the GPU.

::: {#tbl:hardware}
<!-- BEGIN:tab_hardware -->
|  | Project laptop | Second laptop |
|----------------------------|------------------------------------|------------------------------------|
| CPU, memory | AMD Ryzen 5 4600H, 16 GB | AMD Ryzen 9 5900HS, 16 GB |
| GPU | NVIDIA GTX 1650, 4 GB | NVIDIA RTX 3050 Ti, 4 GB |
| Operating system | Windows 11 Home, WSL2, Ubuntu 22.04.5 LTS | Windows 11, WSL2, Ubuntu 22.04 |
<!-- END:tab_hardware -->

: Hardware. The second laptop's values are as reported by the project owner.
:::
