# Introduction {#sec:intro}

A traffic signal decides, many times an hour, which movements at a junction may go. A green
given to one approach is a red for the others, and every change of phase loses a few seconds to
the amber and all-red interval. Over a network of junctions these small decisions add up to the
delay that millions of people experience every day. The urban traffic-engineering literature
asks one question about it: *which phase should be green next, and for how long?*

Three families of answers exist. **Fixed-time** control repeats a plan computed in advance from
traffic counts; Webster's method [@webster1958] is the textbook way to compute one. **Actuated
and adaptive** control changes the plan using detectors, from gap-out logic to city-wide systems
such as SCATS and SCOOT [@sims1980scat; @hunt1981scoot]. **MaxPressure** [@varaiya2013maxpressure]
gives green to the phase whose waiting vehicles exceed those queued downstream by the most; it
needs no training and no forecast. Reinforcement learning has been applied to the same problem
[@wei2021survey], and since 2023 large language models (LLMs) have been tried as signal agents
[@lai2023llmlight; @wang2024lalight; @yuan2026collmlight]. An LLM agent can be told in words what its
neighbours are doing or that an ambulance is approaching, and can say why it chose a phase. The
base paper of this project, CoLLMLight [@yuan2026collmlight], places one LLM agent at each
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

**Contributions.** (1) A validated simulation pipeline: driven the way CoLLMLight's own code drives
CityFlow, our environment reproduces its FixedTime and MaxPressure throughput and queue length
exactly on all three of its datasets (@sec:simulation), and we found that CoLLMLight's FixedTime
baseline never gives north–south traffic a green. (2) A local, guarded LLM controller with honest
results: six controller designs and four local models were compared under a pre-registered rule;
the selected design reaches MaxPressure's performance but not better, and the report says so
(@sec:res-main, @sec:discussion). (3) A clear benefit for ambulances: listing approaching
ambulances in the prompt cuts their mean travel time by 31.7<!--=e.llm.amb_cut_vs_mp-->%
compared with MaxPressure (@sec:res-amb). (4) A measured camera-error study, in which the
detector's own error rates are injected into the controllers' counts (@sec:res-camera).
(5) Reproducibility by construction: every run records its provenance, and every table and
number in this report is generated from, or checked against, the result files.

**Scope.** This is a simulation study. No signal in the field was controlled, no footage from a
fixed junction camera was used (the detector is trained and tested on dash-camera images), and
the demand on the Indian network is synthetic, calibrated against measured capacity rather than
counted at a real junction. CoLLMLight's fine-tuning is not reproduced: all models are used as
released, because the question is what an off-the-shelf local model can do.

## Background and Literature Survey {#sec:literature}

**Indian roads.** Indian urban traffic differs from the traffic for which most signal-control
methods were developed. The vehicle mix is heterogeneous: two-wheelers are
45.1<!--=docs/indian_scenario.md | mix | motorcycle | Share (config-->% and auto-rickshaws
17.6<!--=docs/indian_scenario.md | mix | auto_rickshaw | Share (config-->% of vehicles in the
modal-share data we use [@itrans2009], and vehicles differ widely in length and acceleration
[@chandra2003lanewidth; @indohcm2017]. Lane discipline is weak, so loop detectors work poorly and
cameras are the natural sensor [@mathew2010calibration]. Many junctions still run fixed plans, and
emergency vehicles have no priority. The simulator we use, CityFlow [@zhang2019cityflow], is
lane-based and cannot reproduce lane-free driving; this is stated wherever it matters
(@sec:simulation, @sec:threats).

**Fixed-time and adaptive control.** A fixed-time plan is cheap and predictable but cannot react to
the traffic present. Webster [@webster1958] computes its cycle length and green splits from the flow
ratio of each phase; we use his method as a strong baseline and give it an unfair advantage, since its
plan is computed from the exact demand of the simulated hour. Actuated controllers extend or end a
green using stop-line detectors [@fhwa2008timing]; SCATS [@sims1980scat] and SCOOT
[@hunt1981scoot] coordinate many junctions, but depend on dense, well-maintained detectors and on
lane-based traffic models, which are hard to meet on Indian roads.

**MaxPressure.** Tassiulas and Ephremides [@tassiulas1992] showed that serving the queues with the
largest back-pressure keeps a network stable whenever any policy can; Varaiya
[@varaiya2013maxpressure] carried this to traffic signals. The pressure of a phase is the sum, over
the movements it serves, of the queue on the incoming lane minus the queue on the outgoing lane,
and the phase with the highest pressure gets green. MaxPressure is local, needs no forecast or
training, and its timing parameters matter in practice, so we tune them (@sec:baselines). It is the
main baseline of this project, and the hybrid LLM controllers use its ranking of phases.

**Reinforcement learning.** RL learns a policy by trial and error in a simulator. IntelliLight
[@wei2018intellilight] used real traffic data; PressLight [@wei2019presslight] used pressure as the
reward; CoLight [@wei2019colight] let each agent weigh its neighbours with graph attention; MPLight
[@chen2020mplight] scaled to thousands of signals. These methods need long training per network and
their decisions are hard to explain, which motivated the move to language models.

**LLM-based signal control.** LLMLight [@lai2023llmlight] described one intersection in a prompt and
asked an LLM to choose a phase with step-by-step reasoning; LA-Light [@wang2024lalight] put an LLM
over a set of tools so it could handle rare events such as emergencies. **CoLLMLight**
[@yuan2026collmlight], the base paper, argues that independent agents ignore the interaction between
neighbouring intersections: each agent gets a cooperative reasoning module over its neighbours'
states, run asynchronously so that reasoning does not delay decisions, and a model fine-tuned for
concise reasoning. We take from it the one-agent-per-intersection structure, the cooperation through
neighbour information in the prompt, and its datasets and simulator. We do not take the trained
model: our agents use off-the-shelf models of 3–4 B parameters through Ollama [@ollama] on a 4 GB
GPU, and we compare against tuned baselines under a plan fixed in advance (@sec:prereg).

**Vision and Indian traffic data.** Cameras count and classify vehicles without cutting the road
surface [@buch2011review]; one-stage YOLO detectors [@redmon2016yolo; @jocher2023yolov8] run in real
time on modest hardware. For signal control the relevant quantity is not mAP but the error in the
**counts** a controller receives: missed vehicles, invented vehicles and wrong classes. The India
Driving Dataset (IDD) [@varma2019idd] contains the Indian road users, such as auto-rickshaws, that
Western datasets lack. Our perception study measures these count errors on Indian images and then
measures their effect on control, a link the detection literature usually does not test.

**Gap.** Published LLM controllers are usually evaluated with large hosted or fine-tuned models,
against baselines not tuned for the test network, and with exact simulator counts as input. Three
questions are therefore open, and this project addresses them: whether a small local model, without
fine-tuning, matches a tuned MaxPressure under a fixed evaluation plan; whether the LLM's ability to
use extra context helps in a concrete case (ambulances); and how realistic camera errors change the
comparison. The full survey, with the formulas and a comparison table of the controller families,
is in the extended material ([`docs/report/extended/01_literature_survey.md`](https://github.com/Pilli9375/trafficsense/blob/main/docs/report/extended/01_literature_survey.md)).

## Organization of the Report {#sec:organisation}

The report follows the college's capstone thesis format; the source code is not printed in it but
is available in full at <https://github.com/Pilli9375/trafficsense>, and the material that does not
fit in the page limit is in `docs/report/extended/` of the same repository.

* **Chapter 1** states the objectives, reviews the background and literature, and lists each team
  member's contribution.
* **Chapter 2** describes the proposed system, the working methodology (simulator and its
  validation, the Indian scenario, the perception part, the experimental method and the
  pre-registration), the standards followed and the software and hardware used.
* **Chapter 3** lists every tool and component with its licence and cost.
* **Chapter 4** presents and discusses the results, including the threats to validity.
* **Chapter 5** concludes and lists future work.
* **Chapter 6**, the appendix, gives the repository link and the commit of the code, the commands
  that reproduce the results, the main configuration and the abbreviations.

The references and the team's biodata follow.

## Team Contributions {#sec:team}

@tbl:team gives each member's role and the parts of the project each was responsible for. Every
entry names a feature or file in the repository; the project's results are given only in the later
chapters, from the result files.

::: {#tbl:team}
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Name              | Register    | Role            | Contribution                                            |
|                   | No.         |                 |                                                         |
+===================+=============+=================+=========================================================+
| C Bhargav Kumar   | 23BCE8195   | Computer vision | - Chose the detector, YOLOv8n, and set up its training  |
|                   |             | and machine     |   on the 4 GB GPU (`scripts/train_detector.py`).        |
|                   |             | learning lead   | - Defined the mapping of IDD's labels to our seven      |
|                   |             |                 |   classes and built the inference pipeline              |
|                   |             |                 |   (`perception/`).                                      |
|                   |             |                 | - Ran the detector evaluation whose measured errors are |
|                   |             |                 |   the inputs of the camera error model.                 |
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Achalla Akul      | 23BCE8015   | System          | - Overall architecture: simulator, observation layer,   |
| Lakhan            |             | architect and   |   controllers, result files (@fig:architecture).        |
|                   |             | multi-agent     | - The cooperative LLM controller and its guard, the     |
|                   |             | lead            |   prompts and the structured output (`control/`,        |
|                   |             |                 |   `llm/`).                                              |
|                   |             |                 | - CityFlow integration, the Indian 2x2 network and      |
|                   |             |                 |   flows, ambulance priority (`sim/`).                   |
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Darsi Amit        | 23BCE8288   | Frontend and    | - The Streamlit dashboard and its four pages            |
|                   |             | dashboard lead  |   (`dashboard/`).                                       |
|                   |             |                 | - Live Detection and Network Replay views.              |
|                   |             |                 | - Reading only from `outputs/`, with a source chip on   |
|                   |             |                 |   every number.                                         |
+-------------------+-------------+-----------------+---------------------------------------------------------+
| Mylapalli         | 23BCE9470   | Data            | - Dataset acquisition: CoLLMLight's road networks and   |
| Abhishek Raj      |             | engineering and |   flows, and IDD, converted to YOLO format with         |
|                   |             | integration     |   drive-level splits.                                   |
|                   |             | lead            | - Integration and configuration across modules          |
|                   |             |                 |   (`configs/`, `experiment.py`).                        |
|                   |             |                 | - The pytest suite, README, git and GitHub maintenance, |
|                   |             |                 |   environment and requirements.                         |
+-------------------+-------------+-----------------+---------------------------------------------------------+

: Team contributions. Paths are under `src/trafficsense/` unless prefixed `scripts/` or `configs/`.
:::

The project was developed with the help of an AI coding assistant (Claude Code), working under
the team's direction: the team decided what to build and how to evaluate it, reviewed the code and
the text, ran the experiments and checked the results, and is responsible for all of the work
presented in this report.
