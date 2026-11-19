# Slide by Slide

For each of the 18 slides: what it shows, what to say (based on the speaker notes in the deck),
one thing not to get wrong, and the question the panel is most likely to ask, with a short answer.
The speaker notes are in the PPTX; open the notes view in PowerPoint to read them while presenting.

## Slide 1: TrafficSense: An AI-Based Smart Traffic Management System

**Shows.** The title "Capstone Final Review", the project title, our supervisor Dr. Mohd Irfan,
SDP Id 3328F4C8, the four names with register numbers, and SCOPE, VIT-AP University.

**Say.** "This is our capstone final review of TrafficSense, an AI-based smart traffic management
system, developed by the four of us under Dr. Mohd Irfan. TrafficSense uses local language-model
agents to control traffic signals, tested in simulation on an Indian-style network. We will
present the problem, the method, the results and the limitations."

**Do not get wrong.** Say "tested in simulation" in the first minute.

**Likely question.** *"Is this deployed anywhere?"* No. It is a simulation study; no real signal was
controlled.

## Slide 2: Presentation Outline

**Shows.** Six parts with slide numbers: Introduction (slides 3–5), Background and Related Work
(slides 6–7), Proposed Solution (slides 8–10), Implementation and Results (slides 11–15), Summary
(slide 16), Bibliography (slide 17).

**Say.** "The presentation follows six parts: introduction, related work, the proposed solution,
implementation and results, with the results on three slides, then the summary and the
bibliography."

**Do not get wrong.** Keep it short (about 15 seconds). Do not read every line.

**Likely question.** None usually. Move on.

## Slide 3: Project Overview

**Shows.** Five points: one local LLM agent at every signalised junction, adapted from CoLLMLight
(ICLR 2026); the agents read their own and their neighbours' queues and choose the next phase; it
runs on a laptop GPU (GTX 1650, 4 GB) through Ollama; tested in the CityFlow simulator on an
Indian-style 2x2 network; a simulation study, no real signal was controlled. A figure shows the
idea.

**Say.** "TrafficSense places one local language-model agent at each signalised junction. Each
agent sees its own and its neighbours' state and chooses the next signal phase. The idea comes from
the CoLLMLight paper, adapted to run on a 4 GB laptop GPU. Everything is tested in the CityFlow
simulator on an Indian-style 2x2 grid."

**Do not get wrong.** "Adapted from" CoLLMLight, not "reproduced": we did not fine-tune a model as
CoLLMLight does.

**Likely question.** *"What did you take from CoLLMLight and what is yours?"* We took the
one-agent-per-junction structure, cooperation through neighbour information in the prompt, and its
datasets and simulator. We did not take its trained model: we used small models as released, with
tuned baselines, a guard, ambulances and camera errors.

## Slide 4: Problem Statement & Motivations

**Shows.** Four points (mixed traffic; fixed plans and no ambulance priority; weak lane discipline,
so cameras are the natural sensor; the research question) and a table of the vehicle mix: motorcycle
45.1<!--=docs/report/20_ch2_system.md | tab_mix | motorcycle | Share-->%, auto-rickshaw
17.6<!--=docs/report/20_ch2_system.md | tab_mix | auto_rickshaw | Share-->%, car
30.8<!--=docs/report/20_ch2_system.md | tab_mix | car | Share-->%, bus
1.6<!--=docs/report/20_ch2_system.md | tab_mix | bus | Share-->%, truck
4.9<!--=docs/report/20_ch2_system.md | tab_mix | truck | Share-->%.

**Say.** "Indian urban traffic is a mix of two-wheelers, auto-rickshaws, cars, buses and trucks, as
the table shows. Many junctions still run fixed plans, and ambulances have no priority. Lane
discipline is weak, so loop detectors work poorly and cameras are the natural sensor. So we ask: can
a small local language model control signals as well as the best classical method, and how does it
cope with counts from a real camera detector?"

**Do not get wrong.** The mix is of the *simulated* traffic. It comes from published 2006 Chennai
modal-share data (bicycles removed; buses and trucks split equally, an assumption). We did not count
a real junction.

**Likely question.** *"Where does this vehicle mix come from?"* From published modal-share data for
Chennai, with bicycles removed; the vehicle lengths are Indian averages. Every parameter and its
source is in the scenario configuration file.

## Slide 5: Objectives & Expected Impact

**Shows.** Objectives: build a local multi-agent LLM controller for a 4 GB GPU on a simulator
validated against CoLLMLight's code; compare it with tuned MaxPressure and Webster plans under a
plan fixed in advance, with and without ambulances; measure a YOLOv8n detector on Indian images and
test how its errors hurt each controller. Expected impact: honest evidence of where a small LLM
agent helps and where it does not; reproducible results, every number checked against the result
files and shown in a dashboard.

**Say.** "Our objectives were to build and validate the pipeline, compare the LLM agents with tuned
baselines under a plan fixed in advance, and train a detector on Indian street images and inject its
measured errors. The expected impact is honest evidence about when a small local LLM agent helps and
when it does not."

**Do not get wrong.** "Expected impact" is *honest evidence*, not "reduce city traffic by X%". We
make no claim about real cities.

**Likely question.** *"Did you meet the objectives?"* Yes, all six in the report's list: validated
pipeline, Indian network with tuned baselines, pre-registered comparison, the ambulance benefit,
the camera-error study, and a dashboard and report generated from the data.

## Slide 6: Related Work & Their Limitations

**Shows.** A table of five approaches and their limits: fixed time (Webster) cannot react;
actuated / adaptive systems (SCATS, SCOOT) need dense, well-kept detectors and lane-based models;
MaxPressure is a local rule with no explanation and cannot use extra context; reinforcement
learning needs long training per network and is hard to explain; LLM agents (LLMLight, LA-Light,
CoLLMLight) usually use large hosted or fine-tuned models, untuned baselines and exact counts.

**Say.** Follow the table row by row, one sentence each. End with: "So three questions were open:
can a small local model match a tuned MaxPressure under a fixed plan; does its ability to use extra
context help in a concrete case; and how do realistic camera errors change the comparison?"

**Do not get wrong.** SCATS and SCOOT are real city systems (from Sydney and the UK). We did not
run them. They are discussed, not tested.

**Likely question.** *"Why not reinforcement learning?"* RL needs long training for each network
and its decisions are hard to explain; our question was specifically about off-the-shelf language
models. We did not run an RL baseline.

## Slide 7: Improvements over Existing Solutions

**Shows.** Five differences: tuned baselines first (MaxPressure and Webster tuned before any LLM
run); local off-the-shelf models of 3–4 B parameters, no fine-tuning, no hosted API; a guard keeps
the LLM's choice close to MaxPressure's ranking; context MaxPressure cannot use (ambulances listed
in the prompt); real camera errors from a detector trained on Indian images.

**Say.** "Our comparison differs from earlier work in five ways", then the five points.

**Do not get wrong.** These are improvements in *how fairly and realistically we tested*, not
claims that our controller beats the others.

**Likely question.** *"Why is tuning the baselines first so important?"* If the baseline is weak,
any new method looks good. Tuning first, and fixing the plan in advance, makes the comparison
honest.

## Slide 8: System Architecture / Model Diagram / UML diagrams

**Shows.** The architecture diagram (from the report): CityFlow engine, observation layer (exact or
camera-noised counts), MaxPressure ranking, LLM agent per junction, guard, signal timing rules, an
ambulance channel that is never noised, and the outputs folder feeding the dashboard and report.

**Say.** "The CityFlow engine simulates every vehicle and is the only place where metrics are
measured. Controllers read lane counts through an observation layer, which returns exact counts or
counts degraded by the detector's measured errors. The LLM controllers build on MaxPressure's
ranking, ask an LLM agent for each intersection, and pass its answer through a guard and the signal
timing rules. Ambulance positions reach the agent through a separate channel and are never noised.
Each run writes its results to the outputs folder, from which the dashboard and the report are
generated."

**Do not get wrong.** The camera noise touches only what the *controller sees*. The simulator stays
exact, so the measures are always true.

**Likely question.** *"Does the detector run inside the simulation?"* No. The detector was
evaluated offline on IDD images; its measured error *rates* are applied to the simulator's counts.
The detector does not control signals directly.

## Slide 9: Key Components/Features & Modules

**Shows.** Five modules: simulator and wrapper; controllers (FixedTime, Webster, MaxPressure,
rule-based preemption, LLM arms); LLM agent and guard; perception (YOLOv8n on IDD, its measured
errors become a camera-noise layer); dashboard (Streamlit, reads only `outputs/`, a source chip on
every number). A figure shows the observe, reason, act loop.

**Say.** "The agent observes its state and its neighbours', reasons with the local model, and acts
by returning a phase and a short reason. The wrapper then enforces the transition and the green
limits, and every decision is logged."

**Do not get wrong.** An "arm" means one controller design in the comparison (like an arm of a
medical trial). Six LLM designs were tried; the final round compared three.

**Likely question.** *"What is the source chip?"* A small "source" button next to every number on
the dashboard that opens the file it came from and the git commit that last changed it.

## Slide 10: Algorithms Used/Technologies, Frameworks, and Tools Used

**Shows.** A table. Algorithms: MaxPressure and a Webster fixed-time plan; the guarded hybrid LLM
controller (MaxPressure proposes, LLM decides); YOLOv8n vehicle detection; the camera error model
(misses, false detections, confusions); a pre-registered, seed-paired comparison. Tools: CityFlow
and Python; Ollama with local `llama3.2:3b`; Ultralytics YOLOv8 and the India Driving Dataset;
Streamlit; pytest, git and GitHub.

**Say.** Follow the notes: algorithms first, then the tools.

**Do not get wrong.** "Hybrid" = MaxPressure proposes its top two phases (or keeping the current
one), the LLM decides among them, then the guard checks.

**Likely question.** *"Why Ollama?"* It runs models locally on our own laptop, with no internet
and no paid API, and its native chat endpoint can force the answer into a JSON format.

## Slide 11: Dataset Descriptions / Input – Output Descriptions

**Shows.** Traffic: the Indian 2x2 network (one flow file per seed) and Jinan 3x4 from CoLLMLight.
Camera data: IDD with 7 classes; test split = official validation set. Agent input and output. A
table of scenarios: off-peak 2375<!--=cal.offpeak--> veh/h, peak 4750<!--=cal.peak--> veh/h, peak +
ambulances (4750<!--=cal.peak--> + 6<!--=scn.emergency.veh_per_hour--> per hour), Jinan 3x4 with a
fixed real-world flow.

**Say.** "Off-peak demand is 2375 vehicles per hour and peak demand is 4750, set by a rule fixed
before it was run." Explain the rule if asked (see below).

**Do not get wrong.** The Indian demand is **synthetic** (generated), calibrated against the
measured capacity of MaxPressure on the network, not counted on a real road. Jinan's flow is
real-world (from CoLLMLight's data).

**Likely question.** *"How did you choose the demand?"* By a pre-registered rule: we swept demand
and found the lowest level at which the network no longer drains, 5500<!--=cal.r_star--> veh/h. Peak
is the largest draining demand at or below 0.9<!--=cal.rule.peak_fraction--> of that, 4750<!--=cal.peak--> veh/h; off-peak is half
of peak, 2375<!--=cal.offpeak--> veh/h.

## Slide 12: Parameters Descriptions (if any)

**Shows.** Two tables. Simulation and control: run length 3600<!--=cfg.steps--> s, decision interval
5<!--=cfg.mp.interval--> s, minimum green 15<!--=cfg.mp.min_green--> s, maximum green
60<!--=cfg.signal.max_green--> s, guard margin 20<!--=cfg.guard.margin-->% of top. LLM and detector:
temperature 0 with a fixed seed, context / answer 2048<!--=cfg.llm.num_ctx--> /
128<!--=cfg.llm.num_predict--> tokens, call timeout 60<!--=cfg.llm.timeout_s--> s, ambulance range
150<!--=cfg.amb.range--> m, detector input 640<!--=cfg.imgsz--> px with batch 8.

**Say.** Read the notes. Explain *temperature 0*: the model always picks its most likely answer,
so it behaves as predictably as possible.

**Do not get wrong.** The 15 s minimum green is for MaxPressure and the LLM arms (chosen by the
tuning rule). The general default for other controllers is 10<!--=cfg.signal.min_green--> s.

**Likely question.** *"Why a 5-second decision interval?"* By the pre-registered rule: the shortest
multiple of the 5 s transition that is at least the model's 95th-percentile latency times four
junctions (4.7<!--=b.final.round_p95x4--> s), so a full round of decisions fits in real time on one
GPU.

## Slide 13: Experimental Outcomes (Tables/Figures/User Interface Snaps): (a) Baselines and the LLM controllers

**Shows.** The main results table: average travel time (seconds, mean ± spread over three seeds,
and the change against MaxPressure).

| ATT (s) | Off-peak | Peak | Jinan 3x4 |
|:--|:--|:--|:--|
| MaxPressure | 88.1<!--=f.off.mp.att--> ± 1.0<!--=f.off.mp.att_sd--> | 115.5<!--=f.peak.mp.att--> ± 0.9<!--=f.peak.mp.att_sd--> | 300.9<!--=f.jinan.mp.att--> ± 0.0<!--=f.jinan.mp.att_sd--> |
| Webster plan | 100.4<!--=f.off.web.att--> ± 4.1<!--=f.off.web.att_sd--> (+13.9<!--=f.off.web.vs_mp-->%) | 116.3<!--=f.peak.web.att--> ± 4.6<!--=f.peak.web.att_sd--> (+0.7<!--=f.peak.web.vs_mp-->%) | 416.1<!--=f.jinan.web.att--> ± 0.0<!--=f.jinan.web.att_sd--> (+38.3<!--=f.jinan.web.vs_mp-->%) |
| FixedTime 30 s | 121.5<!--=f.off.ft.att--> ± 0.2<!--=f.off.ft.att_sd--> (+37.8<!--=f.off.ft.vs_mp-->%) | 279.9<!--=f.peak.ft.att--> ± 9.9<!--=f.peak.ft.att_sd--> (+142.3<!--=f.peak.ft.vs_mp-->%) | 423.0<!--=f.jinan.ft.att--> ± 0.0<!--=f.jinan.ft.att_sd--> (+40.6<!--=f.jinan.ft.vs_mp-->%) |
| LLM pre-registered | 89.0<!--=f.off.llm.att--> ± 0.8<!--=f.off.llm.att_sd--> (+0.9<!--=f.off.llm.vs_mp-->%) | 116.1<!--=f.peak.llm.att--> ± 2.9<!--=f.peak.llm.att_sd--> (+0.5<!--=f.peak.llm.vs_mp-->%) | 303.2<!--=f.jinan.llm.att--> ± 1.1<!--=f.jinan.llm.att_sd--> (+0.8<!--=f.jinan.llm.vs_mp-->%) |
| LLM exploratory | 90.5<!--=f.off.gem.att--> ± 1.2<!--=f.off.gem.att_sd--> (+2.7<!--=f.off.gem.vs_mp-->%) | 113.7<!--=f.peak.gem.att--> ± 0.3<!--=f.peak.gem.att_sd--> (−1.5<!--=f.peak.gem.vs_mp-->%) | not run |

**Say.** "The pre-registered LLM controller, `llama3.2:3b` guided and guarded by MaxPressure, is
within 0.5<!--=f.peak.llm.vs_mp--> to 0.9<!--=f.off.llm.vs_mp--> percent of MaxPressure but does not improve on it, because the guard replaces most
of the model's answers. At peak, MaxPressure and the Webster plan are effectively tied, so being as
good as MaxPressure there also means being as good as a well-timed fixed plan. The gemma4:e4b arm is
exploratory: it was added after the plan was fixed, it is faster than MaxPressure only at peak, and
with three seeds and no significance test that is a lead, not a demonstrated improvement."

**How to read it.** Lower is better. A "+" means slower than MaxPressure. Paired by seed, the
pre-registered LLM is behind MaxPressure on all 3<!--=p.off.llm.higher--> off-peak seeds, all
3<!--=p.jinan.llm.higher--> Jinan seeds and 2<!--=p.peak.llm.higher--> of the 3 peak seeds. At peak
the 30 s FixedTime plan no longer drains: about 308<!--=i.peak.fixedtime.backlog--> vehicles are
still waiting to enter at the end of the hour.

**Do not get wrong.** **Never** say the LLM beats MaxPressure. The −1.5<!--=f.peak.gem.vs_mp-->% is from the *exploratory*
gemma4 arm, at peak only, and it is slower off-peak.

**Likely question.** *"So what is the point if it does not beat MaxPressure?"* It shows that a small
local model, safely guarded, can run a junction as well as the best classical rule, in real time,
and it adds value where MaxPressure has no input, as the ambulance results on the next slide show.

## Slide 14: Experimental Outcomes (Tables/Figures/User Interface Snaps): (b) Ambulances and camera errors

**Shows.** Two tables. Ambulance travel time at peak (29<!--=e.mp.amb_n--> signal-relevant
ambulances): MaxPressure 130.1<!--=e.mp.amb--> s (stopped 62.3<!--=e.mp.amb_stop--> s); MaxPressure
+ preemption rule 81.2<!--=e.pre.amb--> s (14.1<!--=e.pre.amb_stop--> s); LLM guarded,
pre-registered 88.9<!--=e.llm.amb--> s (21.2<!--=e.llm.amb_stop--> s); LLM gemma4:e4b,
exploratory 82.2<!--=e.gem.amb--> s (15.3<!--=e.gem.amb_stop--> s). Camera errors (change in ATT
against perfect counts, off-peak / peak):

| Controller | Junction camera | Crowded / far camera |
|:--|:--|:--|
| MaxPressure | +4.8<!--=c.off.mp.junction.pct-->% / +2.3<!--=c.peak.mp.junction.pct-->% | +8.2<!--=c.off.mp.crowded.pct-->% / +4.4<!--=c.peak.mp.crowded.pct-->% |
| LLM guarded | +5.1<!--=c.off.llm.junction.pct-->% / +1.6<!--=c.peak.llm.junction.pct-->% | +7.2<!--=c.off.llm.crowded.pct-->% / +4.9<!--=c.peak.llm.crowded.pct-->% |
| Webster plan | +0.0<!--=c.off.web.junction.pct-->% / +0.0<!--=c.peak.web.junction.pct-->% | +0.0<!--=c.off.web.crowded.pct-->% / +0.0<!--=c.peak.web.crowded.pct-->% |

**Say.** "With ambulances listed in its prompt, the pre-registered LLM controller cut their mean
travel time from 130.1<!--=e.mp.amb--> seconds under MaxPressure to 88.9<!--=e.llm.amb--> seconds, close to rule-based preemption at
81.2<!--=e.pre.amb--> seconds, mostly by removing time stopped at a red. Normal traffic does not pay for the priority.
When the detector's measured errors are put into the counts, every count-based controller gets
slower, while the Webster plan, which never reads counts, is unaffected. The errors are those of our
detector on dash-camera images, so the junction-camera level is a proxy."

**Do not get wrong.** Preemption is still the best for ambulances. The LLM is *close to* it, not
better. And the camera numbers are a *proxy*.

**Likely question.** *"Why is the LLM worse than the simple preemption rule?"* Preemption always
gives the ambulance green; the LLM only usually does. Ambulance by ambulance, the LLM is
7.7<!--=e.llm.vs_pre--> s slower on average (12<!--=e.llm.vs_pre_faster--> faster,
15<!--=e.llm.vs_pre_slower--> slower). For one well-defined rule, a rule is simpler and verifiable;
the LLM's case is flexibility.

## Slide 15: Experimental Outcomes (Tables/Figures/User Interface Snaps): (c) Detector results and dashboard

**Shows.** YOLOv8n on held-out IDD drives: mAP50 0.563<!--=d.test.map50-->, mAP50-95
0.375<!--=d.test.map5095-->; high precision, moderate recall: it undercounts, mostly small distant
objects; the dashboard reads only the result files. Two screenshots: the Live Detection page and the
Overview page.

**Say.** "The detector was trained on the India Driving Dataset and reaches mAP50 of 0.563<!--=d.test.map50--> on
held-out drives, with a confidence threshold frozen on the validation split before the single test
evaluation. Precision is high and recall is moderate, so the detector undercounts, and most misses
are small, distant objects at 640 pixels. The dashboard has four pages; the Live Detection page shows
the detector on a clip of IDD test frames, and the Overview page shows the headline result with
exploratory numbers labelled as such."

**Do not get wrong.** mAP50 0.563<!--=d.test.map50--> is not a percentage of correct answers ("accuracy"). It is an average precision score over seven
classes (see Part 4).

**Likely question.** *"Is 0.563<!--=d.test.map50--> good?"* For a nano-sized model at 640 pixels on crowded Indian dash
camera scenes, it is reasonable, but it misses many small, distant objects (it misses
59<!--=d.size.motorcycle.small-->–76<!--=d.size.person.small-->% of small boxes against
1<!--=d.size.autorickshaw.large-->–22<!--=d.size.bicycle.large-->% of large ones). What matters for
signal control is its *count errors*, which we measured and injected.

## Slide 16: Key Findings

**Shows.** Key findings (the pre-registered LLM matches MaxPressure, +0.5<!--=f.peak.llm.vs_mp--> to +0.9<!--=f.off.llm.vs_mp-->% ATT, but does not
beat it; ambulances 130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s, preemption 81.2<!--=e.pre.amb--> s; camera errors add 2.3<!--=c.peak.mp.junction.pct-->–4.8<!--=c.off.mp.junction.pct-->% to
MaxPressure), limitations (simulation only; junction-camera errors are a dash-camera proxy; 3 seeds,
no significance test; lane-based simulator; the model-size study and the gemma4 arm are
exploratory), and future directions (memory and tool-using agents, fine-tuning small models, real
junction-camera footage, field testing in shadow mode).

**Say.** Follow the notes: the controller matches but does not beat MaxPressure; its clearest
benefit is for ambulances; camera errors cost a few percent, mostly through false detections; then
the limitations and future work.

**Do not get wrong.** Say the limitations calmly and fully. They are a strength of the project,
not a weakness.

**Likely question.** *"What is shadow mode?"* Running the agent beside an existing signal
controller, only logging what it *would* have done, before it is ever allowed to switch a real
signal.

## Slide 17: Bibliography

**Shows.** Eight main references, numbered as in the report: Webster [1], Varaiya (MaxPressure) [4],
LLMLight [6], LA-Light [7], CoLLMLight [8], CityFlow [13], Ultralytics YOLOv8 [23], IDD [24].

**Say.** "These are the main references, numbered as in the report. Webster and Varaiya give the
classical baselines; LLMLight, LA-Light and CoLLMLight are the language-model controllers our work
builds on. CityFlow is the simulator, YOLOv8 the detector and the India Driving Dataset its training
data. The full list is in the report."

**Do not get wrong.** CoLLMLight is our **base paper**.

**Likely question.** *"Which paper is your base paper?"* CoLLMLight: cooperative LLM agents for
network-wide traffic signal control, ICLR 2026.

## Slide 18: Thank You (GitHub Link)

**Shows.** The closing slide with the GitHub link: <https://github.com/Pilli9375/trafficsense>.

**Say.** "Thank you for your time. The complete source code, the report and every result file are
in the project repository. The link is on the slide, and we are happy to take questions."

**Do not get wrong.** Then go to the dashboard demo if it is planned after the slides (see Part 6),
or take questions.

**Likely question.** *"Can we run it ourselves?"* Yes. The README gives the setup steps;
`make_report.py --check` verifies every number against the result files. A fresh copy of the
repository reproduced all 42<!--=r.det_runs_identical--> of 42<!--=r.det_runs--> deterministic runs
exactly.
