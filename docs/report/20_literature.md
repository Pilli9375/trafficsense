# Literature Review {#sec:literature}

This chapter follows the history of signal control in the order the methods are used later as
baselines and as the controller under test: fixed-time plans, actuated and adaptive systems,
MaxPressure, reinforcement learning, and LLM agents. It then reviews vision-based traffic
sensing and studies of Indian traffic, which motivate the perception part and the scenario.

## Fixed-time control and Webster's method {#sec:lit-fixed}

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

## Actuated and adaptive control {#sec:lit-adaptive}

Actuated controllers extend or end a green using detectors at the stop line, within minimum and
maximum green limits [@fhwa2008timing]. They respond to the current queue but decide each
junction on its own. Adaptive systems coordinate many junctions. SCATS [@sims1980scat] selects
and adjusts plans from detector data at the stop line; SCOOT [@hunt1981scoot] models the
traffic in each link from upstream detectors and adjusts splits, cycle times and offsets
continuously. Both depend on dense, well-maintained detector networks and on lane-based traffic
models. These assumptions are hard to meet on Indian roads, where loop detectors are rare and
lanes are not followed (@sec:lit-india).

## MaxPressure {#sec:lit-mp}

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

## Reinforcement learning {#sec:lit-rl}

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

## LLM-based signal control {#sec:lit-llm}

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

## Vision-based traffic sensing {#sec:lit-vision}

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

## Indian traffic studies {#sec:lit-india}

The India Driving Dataset (IDD) [@varma2019idd] was collected to study autonomous driving in
unstructured Indian traffic. It contains classes absent from most Western datasets, such as
auto-rickshaws, and many partly occluded, densely packed road users. Traffic-engineering studies
of Indian roads show that heterogeneous vehicles change capacity and passenger-car equivalents
with road width [@chandra2003lanewidth], that microsimulation models must be calibrated for
non-lane-based traffic at signals [@mathew2010calibration], and the Indian Highway Capacity
Manual [@indohcm2017] provides capacity and level-of-service methods developed for these
conditions. The vehicle mix and dimensions of our scenario come from Indian sources
[@itrans2009; @umapathi2019pcu] (@sec:indian-scenario).

## Summary and gap {#sec:lit-gap}

::: {#tbl:lit}
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
