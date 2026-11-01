# Introduction {#sec:intro}

A traffic signal decides, many times an hour, which movements at a junction may go. Each
decision has a cost: a green given to one approach is a red for the others, and every change
of phase loses a few seconds to the amber and all-red interval in which no conflicting traffic
moves. Over a network of junctions these small decisions add up to the delay that millions of
people experience every day. A large part of the urban traffic-engineering literature is
therefore about one question: *which phase should be green next, and for how long?*

The classical answers fall into three groups. **Fixed-time** control repeats a timing plan
computed in advance from traffic counts; Webster's method [@webster1958] is still the textbook
way to compute such a plan. **Actuated and adaptive** control changes the plan using detectors,
from simple gap-out logic to city-wide systems such as SCATS and SCOOT
[@sims1980scat; @hunt1981scoot]. **MaxPressure** control [@varaiya2013maxpressure] gives green,
at each decision, to the phase whose waiting vehicles exceed the vehicles queued downstream of
them by the most. It needs no training and no demand forecast, and it has a proof of maximum
stability. In the last decade, reinforcement learning (RL) has been applied to the same problem
[@wei2021survey], and since 2023 large language models (LLMs) have been tried as signal agents
[@lai2023llmlight; @wang2024lalight; @yuan2026collmlight].

The appeal of an LLM agent is not raw optimisation power. It is that the agent works with
information in the form people use: it can be told, in words, what its neighbours are doing,
that an ambulance is approaching, or that a road is closed, and it can say why it chose a phase.
The base paper of this project, CoLLMLight [@yuan2026collmlight], places one LLM agent at each
intersection and lets the agents cooperate by sharing their neighbours' states in the prompt.

## Objectives {#sec:objectives}

The objectives of this project are:

1. Build a multi-agent signal-control system in which each intersection is controlled by a
   local LLM agent that observes its own state and its neighbours', reasons, and acts, adapted
   from CoLLMLight to run on a 4 GB laptop GPU.
2. Validate the simulation pipeline against an independent implementation before trusting any
   result from it.
3. Build an Indian-style test network with a documented source for every parameter, and tune
   strong classical baselines (MaxPressure, a Webster fixed-time plan) on it **before** the LLM
   controllers are compared with them.
4. Compare the LLM agents with these baselines under a plan fixed in advance, on normal traffic
   and on traffic with ambulances.
5. Train a vehicle detector on Indian street images, measure its errors, and test how much
   those errors hurt each controller when they are injected into its observations.
6. Present the results in a dashboard that reads only the result files.

### Contributions {#sec:contributions}

* **A validated simulation pipeline.** Driven the way CoLLMLight's own code drives CityFlow, our
  environment reproduces their FixedTime and MaxPressure throughput and queue length exactly on
  all three of their datasets, and their waiting time to within CityFlow's own run-to-run noise
  (@sec:validation). We also found that CoLLMLight's
  FixedTime baseline never gives north–south traffic a green (@sec:fixedtime-bug).
* **A local, guarded LLM controller with honest results.** Six controller designs and four
  local models were compared under a pre-registered rule; the selected design reaches
  MaxPressure's performance but not better (@sec:res-main). We report this negative result as
  it is, together with the analysis of why small models misread pressure (@sec:disc-why).
* **A clear benefit for ambulances.** Listing approaching ambulances in the prompt cuts their mean
  travel time by 31.7<!--=e.llm.amb_cut_vs_mp-->% compared with MaxPressure, close to a
  hand-written preemption rule (@sec:res-amb).
* **A measured camera-error study.** The detector's own error rates, measured on held-out drives,
  are injected into the controllers' counts while the simulator stays exact. A post-hoc
  decomposition separates misses, false detections and class confusion (@sec:res-camera).
* **Reproducibility by construction.** Every run records its provenance; every table and
  number in this report is generated from, or checked against, the result files by a script
  (@sec:app-repro).

### Scope {#sec:scope}

This is a simulation study. No signal in the field was controlled, no footage from a fixed
junction camera was used (the detector is trained and tested on dash-camera images), and the
demand on the Indian network is synthetic, calibrated against measured capacity rather than
counted at a real junction. CoLLMLight's fine-tuning stages (reasoning refinement and policy
optimisation) are not reproduced: all models are used as released, without training, because
the project's question is what an off-the-shelf local model can do.

## Background and Literature Survey {#sec:literature}

This section first explains what makes Indian urban traffic different. It then follows the
history of signal control in the order the methods are used later as baselines and as the
controller under test: fixed-time plans, actuated and adaptive systems, MaxPressure,
reinforcement learning, and LLM agents. It closes with vision-based traffic sensing and studies
of Indian traffic, which motivate the perception part and the scenario.

### Why Indian Roads {#sec:intro-india}

Indian urban traffic differs from the traffic for which most signal-control methods were
developed in three ways that matter here.

1. **The vehicle mix is heterogeneous.** Two-wheelers and three-wheelers make up most of the
   stream. In the modal-share data we use for the simulation (Chennai, as reported in
   [@itrans2009]), motorised two-wheelers are 45.1<!--=docs/indian_scenario.md | mix | motorcycle | Share (config-->%
   of vehicles after normalisation, and auto-rickshaws
   17.6<!--=docs/indian_scenario.md | mix | auto_rickshaw | Share (config-->%. Vehicles differ
   widely in length, acceleration and the space they occupy, which changes how fast a queue
   discharges [@chandra2003lanewidth; @indohcm2017].
2. **Lane discipline is weak.** Two-wheelers filter between larger vehicles and queue several
   abreast at the stop line [@mathew2010calibration]. Loop detectors that count vehicles per lane
   work poorly; cameras are the natural sensor.
3. **Many junctions still run fixed plans or manual control**, and emergency vehicles are delayed
   at signals with no priority system.

These points shape the project. The controllers are tested on a network with an Indian vehicle
mix; the counts they receive are, in one experiment, degraded with the errors of a real
detector trained on Indian street images; and emergency vehicles are part of the evaluation.
They also limit it: the simulator we use, CityFlow [@zhang2019cityflow], is lane-based and cannot
reproduce lane-free driving. This is stated wherever it matters
(@sec:sim-limits, @sec:threats).

### Fixed-Time Control and Webster's Method {#sec:lit-fixed}

A fixed-time controller repeats a cycle of phases with fixed green times. It is cheap, needs no
detectors and is predictable, which is why it remains common. Its weakness is equally simple:
the plan cannot react to the traffic actually present, so green is wasted on empty approaches
while queues grow elsewhere.

Webster [@webster1958] gave the standard way to compute a good fixed plan. For each phase *i*
the flow ratio $y_i = q_i / s_i$ compares the demand $q_i$ on its critical lane with the lane's
saturation flow $s_i$ (the rate at which a queue discharges during green). With
$Y = \sum_i y_i$ and $L$ the total lost time per cycle, the delay-minimising cycle length is

$$C_0 = \frac{1.5\,L + 5}{1 - Y},$$

and the effective green is shared between phases in proportion to $y_i$. The formula assumes
steady, random arrivals; when demand changes during the period, a plan computed from average
counts is no longer optimal. We use Webster's method as a strong fixed-time baseline and give it
an unfair advantage: its plan is computed from the exact demand of the simulated hour
(@sec:baselines).

### Actuated and Adaptive Control {#sec:lit-adaptive}

Actuated controllers extend or end a green using detectors at the stop line, within minimum and
maximum green limits [@fhwa2008timing]. They respond to the current queue but decide each
junction on its own. Adaptive systems coordinate many junctions. SCATS [@sims1980scat] selects
and adjusts plans from detector data at the stop line; SCOOT [@hunt1981scoot] models the
traffic in each link from upstream detectors and adjusts splits, cycle times and offsets
continuously. Both depend on dense, well-maintained detector networks and on lane-based traffic
models. These assumptions are hard to meet on Indian roads, where loop detectors are rare and
lanes are not followed (@sec:lit-india).

### MaxPressure {#sec:lit-mp}

MaxPressure comes from the theory of scheduling in queueing networks. Tassiulas and Ephremides
[@tassiulas1992] showed that serving, at every step, the set of queues with the largest
"back-pressure" (the difference between a queue and the queue downstream of it) keeps a network
stable whenever any policy can. Varaiya [@varaiya2013maxpressure] carried this result to traffic
signals. For a phase $p$ that serves movements $(l, m)$ from incoming lane $l$ to outgoing lane
$m$, the pressure is

$$P(p) = \sum_{(l, m) \in p} \big(x_l - x_m\big),$$

where $x$ is the number of queued vehicles. At each decision the controller gives green to the
phase with the highest pressure. MaxPressure is local (each junction needs only its own and its
immediate downstream queues), needs no demand forecast and no training, and maximises the
throughput the network can sustain. It does not by itself choose how often to decide or how
short a green may be; those timing parameters matter in practice, and we tune them
(@sec:baselines). MaxPressure is the main baseline of this project, and the hybrid LLM
controllers use its ranking of phases.

### Reinforcement Learning {#sec:lit-rl}

RL learns a policy that maps an observed traffic state to a phase by trial and error in a
simulator, rewarded for short queues or delays. Early work used tabular methods on single
junctions [@abdulhai2003rl]; deep RL followed [@genders2016deep]. IntelliLight
[@wei2018intellilight] tested deep RL on real traffic data. PressLight [@wei2019presslight] used
MaxPressure's pressure as the reward and coordinated an arterial; CoLight [@wei2019colight] used
graph attention so that each agent weighs information from its neighbours; MPLight
[@chen2020mplight] scaled pressure-based RL to thousands of signals by sharing parameters. These
methods were developed on CityFlow [@zhang2019cityflow], the simulator used here, and on the
same Jinan and Hangzhou datasets. The survey by Wei et al. [@wei2021survey] summarises the field.

RL controllers can outperform hand-designed rules in simulation, but they need long training per
network, their decisions are hard to explain, and they may not transfer to traffic unlike the
training traffic. These limits motivated the move to language models.

### LLM-Based Signal Control {#sec:lit-llm}

LLMs bring general knowledge and the ability to follow instructions written in natural
language. LLMLight [@lai2023llmlight] described the traffic state of one intersection in a
prompt and asked an LLM to choose a phase with step-by-step reasoning; it also fine-tuned a
model for the task. LA-Light [@wang2024lalight] placed an LLM over a set of tools (perception,
decision support, evaluation) so that the model could handle rare situations such as
emergencies or sensor faults, while conventional algorithms handled normal operation.

**CoLLMLight** [@yuan2026collmlight], the base paper of this project, argues that independent LLM
agents ignore the interaction between neighbouring intersections. It gives each intersection
an LLM agent with a spatiotemporal-aware cooperative reasoning module that analyses the
neighbours' states and produces cooperative suggestions, runs this reasoning in an asynchronous
decision architecture so that multi-step reasoning does not delay real-time decisions, and
trains the model with a cost-aware cooperation optimisation: adaptive reasoning optimisation
teaches the model to reason concisely, and policy refinement rewards both good decisions and
short reasoning. Their code (which we use for validation, @sec:validation) runs on CityFlow
with the Jinan, Hangzhou, New York and Synthetic networks.

What we take from CoLLMLight is the multi-agent structure (one agent per intersection), the
cooperation through neighbour information in each agent's prompt, and its datasets and
simulator. What we do not take is the trained model and the fine-tuning: our agents use
off-the-shelf models of 3–4 B parameters through Ollama [@ollama] on a 4 GB GPU, because the
question here is what a deployable local model can do without training. A second difference is
in evaluation: we compare with tuned baselines under a plan fixed in advance (@sec:prereg).

### Vision-Based Traffic Sensing {#sec:lit-vision}

Cameras can count, classify and track vehicles without cutting the road surface, which makes
them the usual sensor for adaptive control in mixed traffic [@buch2011review]. One-stage
detectors of the YOLO family [@redmon2016yolo] are fast enough for real-time use on modest
hardware; YOLOv8 [@jocher2023yolov8] is the version used here. Detectors are evaluated with mean
average precision (mAP) over intersection-over-union thresholds, and their accuracy falls sharply
for small objects, which COCO [@lin2014coco] measures with its small / medium / large size
buckets. For signal control the relevant quantity is not mAP but the error in the **counts** a
controller receives: missed vehicles, invented vehicles and wrong classes. Visual sensing has
also been proposed to detect emergency vehicles and give them priority [@nellore2016emergency].
Our perception study measures these count errors on Indian images and then measures their effect
on control, a link that the detection literature usually does not test.

### Indian Traffic Studies {#sec:lit-india}

The India Driving Dataset (IDD) [@varma2019idd] was collected to study autonomous driving in
unstructured Indian traffic. It contains classes absent from most Western datasets, such as
auto-rickshaws, and many partly occluded, densely packed road users. Traffic-engineering studies
of Indian roads show that heterogeneous vehicles change capacity and passenger-car equivalents
with road width [@chandra2003lanewidth], that microsimulation models must be calibrated for
non-lane-based traffic at signals [@mathew2010calibration], and the Indian Highway Capacity
Manual [@indohcm2017] provides capacity and level-of-service methods developed for these
conditions. The vehicle mix and dimensions of our scenario come from Indian sources
[@itrans2009; @umapathi2019pcu] (@sec:indian-scenario).

### Summary and Gap {#sec:lit-gap}

::: {#tbl:lit short="Families of signal controllers compared"}
| Method | Reacts to traffic | Coordinates neighbours | Needs training | Explains decisions | Uses extra context, e.g. an ambulance |
|:-------------------------|:-----------|:--------------------|:---------------|:-------------|:---------------|
| Fixed time, Webster | no | through offsets only | no | the plan is fixed | no |
| Actuated, SCATS, SCOOT | yes | SCATS and SCOOT do | calibration | partly | through special modules |
| MaxPressure | yes | implicitly, through downstream queues | no | the pressures | no |
| RL: PressLight, CoLight, MPLight | yes | CoLight does | yes, per network | no | only if in the state |
| LLM agents: LLMLight, CoLLMLight | yes | CoLLMLight does | optional fine-tuning | yes, in words | yes, in the prompt |

: How the families of signal controllers compare on the properties this project cares about.
:::

Published LLM controllers are usually evaluated with large hosted or fine-tuned models, against
baselines whose settings are not tuned for the test network, and with exact simulator counts as
input. Three questions are therefore open, and this project addresses them: whether a small
local model, without fine-tuning, matches a tuned MaxPressure under a fixed evaluation plan;
whether the LLM's ability to use extra context helps in a concrete case (ambulances); and how
realistic camera errors change the comparison.

## Organization of the Report {#sec:organisation}

The report follows the college's capstone thesis format.

* **Chapter 1** states the objectives, reviews the background and literature, from fixed-time
  plans to LLM agents and vision-based traffic sensing, and lists each team member's
  contribution.
* **Chapter 2** describes the proposed system (architecture, the multi-agent decision loop, the
  controller designs, ambulance handling, the camera-noise layer and the dashboard) and the
  working methodology: the simulator and its validation, the Indian scenario, the perception
  part, the experimental method and the pre-registration. It closes with the standards followed
  and the software and hardware used.
* **Chapter 3** lists every tool and component with its licence and cost.
* **Chapter 4** presents the results (baselines, the LLM benchmark and design rounds, the full
  experiments, ambulances, the exploratory model-size study, camera errors, the detector and the
  dashboard) and discusses them, including the threats to validity.
* **Chapter 5** concludes and lists future work.
* **Chapter 6**, the appendix, gives the configuration, the prompts, the reproduction steps, the
  full tables, the abbreviations and listings of the key source files.

The references, the team's biodata and the note on the accompanying CD follow.

## Team Contributions {#sec:team}

@tbl:team gives each member's role and the parts of the project each was responsible for. Every
entry names a file or feature that exists in the project repository; the numbers and results of
the project are given only in the later chapters, from the result files.

::: {#tbl:team}
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Name              | Register    | Role            | Contribution                                            |
|                   | No.         |                 |                                                         |
+===================+=============+=================+=========================================================+
| C Bhargav Kumar   | 23BCE8195   | Computer vision | - Chose the detector, YOLOv8n, and set up its training  |
|                   |             | and machine     |   on the 4 GB GPU (batch size from a probe run, mixed   |
|                   |             | learning lead   |   precision off): `scripts/train_detector.py`.          |
|                   |             |                 | - Defined the mapping of IDD's labels to our seven      |
|                   |             |                 |   classes (`perception/idd.py`) and built the           |
|                   |             |                 |   inference pipeline used by the evaluation and the     |
|                   |             |                 |   Live Detection page (`perception/detector.py`).       |
|                   |             |                 | - Ran the detector evaluation whose measured errors are |
|                   |             |                 |   the inputs of the camera error model:                 |
|                   |             |                 |   `scripts/eval_detector.py`, `outputs/perception/`.    |
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Achalla Akul      | 23BCE8015   | System          | - Overall architecture: simulator, observation layer,   |
| Lakhan            |             | architect and   |   controllers, result files, dashboard                  |
|                   |             | multi-agent     |   (@fig:architecture).                                  |
|                   |             | lead            | - The cooperative LLM controller and its guard:         |
|                   |             |                 |   `control/llm.py`, `control/guided.py`.                |
|                   |             |                 | - The prompts (v1 to v3, guided) and the JSON-schema    |
|                   |             |                 |   structured output: `llm/prompt.py`, `llm/client.py`.  |
|                   |             |                 | - CityFlow integration and the Indian 2x2 network and   |
|                   |             |                 |   flows: `sim/env.py`, `sim/roadnet.py`,                |
|                   |             |                 |   `scripts/generate_indian_roadnet.py`,                 |
|                   |             |                 |   `scripts/generate_indian_flow.py`.                    |
|                   |             |                 | - Ambulance priority in the LLM arms and the preemption |
|                   |             |                 |   baseline: `sim/emergency.py`,                         |
|                   |             |                 |   `control/preemption.py`.                              |
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Darsi Amit        | 23BCE8288   | Frontend and    | - The Streamlit dashboard and its four pages:           |
|                   |             | dashboard lead  |   `dashboard/app.py`, `dashboard/screens/`.             |
|                   |             |                 | - Theme and charts: `dashboard/theme.py`,               |
|                   |             |                 |   `dashboard/ui.py`, `dashboard/views/results.py`.      |
|                   |             |                 | - The Live Detection and Network Replay views:          |
|                   |             |                 |   `dashboard/views/detection.py`,                       |
|                   |             |                 |   `dashboard/views/replay.py`.                          |
|                   |             |                 | - Reading only from `outputs/`, with a source chip on   |
|                   |             |                 |   every number: `dashboard/data.py`,                    |
|                   |             |                 |   `tests/test_dashboard.py`.                            |
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Mylapalli         | 23BCE9470   | Data            | - Dataset research and acquisition: CoLLMLight's road   |
| Abhishek Raj      |             | engineering and |   networks and flows                                    |
|                   |             | integration     |   (`scripts/fetch_collmlight_data.sh`) and IDD.         |
|                   |             | lead            | - Conversion of IDD into YOLO format and the            |
|                   |             |                 |   drive-level splits: `scripts/prepare_idd.py`,         |
|                   |             |                 |   `scripts/resize_idd.py`.                              |
|                   |             |                 | - Integration and configuration across modules:         |
|                   |             |                 |   `configs/default.yaml`, `config.py`, `experiment.py`, |
|                   |             |                 |   `scripts/run_experiment.py`.                          |
|                   |             |                 | - The pytest suite, with test doubles for LLM calls     |
|                   |             |                 |   that exist only inside `tests/`.                      |
|                   |             |                 | - README, git and GitHub maintenance, environment and   |
|                   |             |                 |   requirements: `pyproject.toml`,                       |
|                   |             |                 |   `requirements-lock.txt`.                              |
+-------------------+-------------+-----------------+---------------------------------------------------------+

: Team contributions. Paths are under `src/trafficsense/` unless they start with `scripts/`,
`tests/`, `configs/` or `outputs/`.
:::

The project was developed with the help of an AI coding assistant (Claude Code), working under
the team's direction: the team decided what to build and how to evaluate it, reviewed the code and
the text, ran the experiments and checked the results, and is responsible for all of the work
presented in this report.
