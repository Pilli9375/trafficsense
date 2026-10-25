# Introduction {#sec:intro}

## Background {#sec:intro-background}

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

## Why Indian roads {#sec:intro-india}

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

## Objectives {#sec:objectives}

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

## Contributions {#sec:contributions}

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
  (Appendix C).

## Scope {#sec:scope}

This is a simulation study. No signal in the field was controlled, no footage from a fixed
junction camera was used (the detector is trained and tested on dash-camera images), and the
demand on the Indian network is synthetic, calibrated against measured capacity rather than
counted at a real junction. CoLLMLight's fine-tuning stages (reasoning refinement and policy
optimisation) are not reproduced: all models are used as released, without training, because
the project's question is what an off-the-shelf local model can do.

## Organisation of the report {#sec:organisation}

@sec:literature reviews signal control from fixed-time plans to LLM agents, and vision-based
traffic sensing. @sec:design describes the system and the multi-agent decision loop.
@sec:simulation covers the simulator, its validation and the Indian scenario. @sec:perception
describes the detector and its error model. @sec:method sets out the experimental method,
including the pre-registration and the metrics. @sec:results presents the results and
@sec:discussion interprets them. @sec:conclusion concludes and lists future work. The
appendices give the configuration, the prompts, the reproduction steps, the hardware and the
full tables.
