# Simulation and Scenario {#sec:simulation}

A controller comparison is only as good as the simulator and the scenario behind it. This chapter
first checks that our simulation pipeline gives the same answers as an independent
implementation, then describes the Indian test network, where each of its parameters comes
from, and how the classical baselines were tuned on it before the LLM controllers were tested.

## CityFlow and what it can represent {#sec:sim-limits}

CityFlow [@zhang2019cityflow] is a microscopic traffic simulator designed for signal-control
research: it moves every vehicle every second with a car-following model, is fast enough for
hour-long runs on a laptop, and is the simulator of CoLLMLight and most RL work. It is
**lane-based**: every vehicle drives in one lane and follows the vehicle in front. It cannot
represent vehicles straddling lanes, two-wheelers filtering between cars or queuing several
abreast, and it ignores vehicle width in its dynamics. Our Indian scenario therefore models the
Indian **vehicle mix** (sizes, headways, accelerations) but not Indian **driving behaviour**. Its
results describe "a lane-based simulation with an Indian vehicle mix", and capacities measured
in it are probably lower in vehicles per hour than on a real road with the same mix.

We run CityFlow with lane changing switched off. With lane changing on, CityFlow's results
depend very slightly on which read-only queries are made between steps, so two controllers that
query different things could see different traffic. With it off, the same phase sequence always
gives exactly the same run, which we verified.

## Validation against CoLLMLight's code {#sec:validation}

Before trusting any comparison, we checked our environment wrapper, signal timing and metrics
against an independent implementation: the CoLLMLight authors' own code (commit `ce204a9`).

**Method.** Their FixedTime and MaxPressure baselines were run unmodified in a separate Python
environment with their pinned library versions. Their configuration imports every agent class,
including the neural and LLM ones, so those imports were replaced by inert stubs; FixedTime and
MaxPressure never call them. Our own environment was then driven exactly as theirs: the same 4
phases, one decision every 30<!--=val.matched.interval--> s, a 5 s transition before every switch, no minimum or maximum
green, lane changing on, and **the same CityFlow seed** their run drew. Their metric definitions
differ from ours (they measure travel time per intersection approach rather than per trip, sum
queues over the network, and sample at their decision times), so every matched run was scored twice: with our
metrics and with a line-by-line reimplementation of theirs.

**Result.** @tbl:validation compares the two implementations under their metric definitions.
Throughput, queue length and waiting time are identical floating-point numbers for both
controllers on all three datasets. Average travel time under their definition is identical in
all but one of the six runs; there, and in CityFlow's own average travel time, the differences
are in the sixth significant digit or beyond. We traced them to CityFlow's lane changing: with lane changing on, extra
read-only queries alter the run in the sixth significant digit, and their environment makes
more such queries than ours. With lane changing off, the result is bit-for-bit identical whatever
is queried. We therefore consider the pipeline validated.

::: {#tbl:validation}
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

The validation also corrected one of our own earlier claims. We had written that CityFlow's
average travel time leaves out vehicles that never entered the network. It does not: it averages
over every generated vehicle, timed from its scheduled start, including vehicles still waiting
to enter. A unit test now reproduces the engine's number from the flow file, and every metric
description was corrected.

## A bug in CoLLMLight's FixedTime baseline {#sec:fixedtime-bug}

CoLLMLight's fixed-time agent computes its next action as `(cur_phase + 1) % 4`, where `cur_phase`
is CityFlow's phase index (1–4). Actions, however, are numbered from 0 and the environment adds 1
again. Phase 1 therefore leads to phase 3 and phase 3 back to phase 1: the controller alternates
between the two east–west phases, and **north–south traffic never gets a green**. Their own action
log confirms it for every intersection over the whole hour. @tbl:fixedtime-bug shows what this
does to the numbers: a correct 4-phase cycle on the same 30<!--=val.matched.interval--> s grid has a far lower travel time on
the two real-world datasets. Any comparison with CoLLMLight's published fixed-time numbers must
take this into account; we use only our own, correct fixed-time controllers.

::: {#tbl:fixedtime-bug}
<!-- BEGIN:tab_fixedtime_bug -->
| Dataset | Controller | CityFlow ATT (s) | ATT, CoLLMLight's definition (s) | Throughput, CoLLMLight's definition |
|------------------|---------------------------|--------------:|-------------------:|-------------------:|
| Synthetic 4x4 | CoLLMLight's FixedTime (bug: E-W only) | 1612.0 | 1192.5 | 751 |
| Synthetic 4x4 | CoLLMLight's MaxPressure | 1263.3 | 683.1 | 2505 |
| Synthetic 4x4 | Correct 4-phase FixedTime, same 30 s grid | 1420.6 | 875.6 | 1724 |
| Jinan 3x4 | CoLLMLight's FixedTime (bug: E-W only) | 1258.0 | 1239.3 | 1786 |
| Jinan 3x4 | CoLLMLight's MaxPressure | 317.8 | 273.2 | 4187 |
| Jinan 3x4 | Correct 4-phase FixedTime, same 30 s grid | 479.6 | 441.2 | 4027 |
| Hangzhou 4x4 | CoLLMLight's FixedTime (bug: E-W only) | 1054.7 | 1002.8 | 1526 |
| Hangzhou 4x4 | CoLLMLight's MaxPressure | 365.7 | 325.3 | 2751 |
| Hangzhou 4x4 | Correct 4-phase FixedTime, same 30 s grid | 667.9 | 616.0 | 2450 |
<!-- END:tab_fixedtime_bug -->

: CoLLMLight's FixedTime (which serves east–west only) against a correct 4-phase cycle with the
same 30<!--=val.matched.interval--> s decisions, and their MaxPressure for reference. One run per dataset, CoLLMLight's
settings.
:::

The validation also showed why the Synthetic 4x4 dataset is unusual. One of its entry roads
carries 2660<!--=docs/validation.md | capacity | Demand needing its straight lane | veh / h-->
vehicles per hour that all need a single straight lane, whose stop line discharges at most
1440<!--=docs/validation.md | capacity | Stop-line saturation flow | veh / h--> vehicles per hour
even with a permanent green. No signal plan can clear it, so a large entry queue is a property of
the dataset. For this reason the comparisons in this report use Jinan 3x4 (real flow) and our
Indian network, and use Synthetic 4x4 only for validation.

## The Indian 2x2 scenario {#sec:indian-scenario}

### Network

The test network (@fig:network, @tbl:network) is a 2 × 2 grid generated with CityFlow's own grid
generator. India drives on the left and the generator builds right-hand traffic, but a square grid
is mirror-symmetric: a right-hand network is the mirror image of a left-hand one, and the
simulation is the same with the turn labels swapped. CityFlow's right turn (kerb side, allowed in
every phase) plays the role of India's **free left turn**, and its left turn (across opposing
traffic, protected phase) plays the role of India's **right turn**.

![The Indian 2x2 network, drawn from its CityFlow road-network file. East–west is the major
road.](figures/network.png){#fig:network width=48%}

::: {#tbl:network}
<!-- BEGIN:tab_network -->
| Parameter | Value | Source |
|----------------------------------|-------------------------------:|----------------------------------|
| Grid | 2 × 2 signalised intersections | project specification |
| Spacing between intersections | 200 m | project specification |
| Entry and exit roads | 200 m | assumption (same as spacing) |
| Lanes per direction | 3 (one per turn) | CityFlow generator layout |
| Lane width | 3.0 m | project specification |
| Speed limit | 12.5 m/s (45 km/h) | assumption within the 11–13 m/s range |
| Centre to stop line | 12 m | assumption (three lanes plus margin) |
| Phases | 0 = 5 s transition (free turns only); 1–8 green | CityFlow generator |
| Minimum / maximum green | 10 s / 60 s (MaxPressure and LLM arms: minimum 15 s) | configs/default.yaml |
<!-- END:tab_network -->

: Network and signal parameters of the Indian 2x2 scenario (`configs/scenarios/indian_2x2.yaml`).
:::

### Vehicles

Each vehicle type has its own length, gap, headway, speed and acceleration (@tbl:mix). The shares
are the 2006 modal share of Chennai traffic [@itrans2009], with bicycles removed (not modelled)
and buses and trucks split equally (an assumption). Lengths and widths are the average Indian
dimensions given by Umapathi and Khatawkar [@umapathi2019pcu]. The car's gap, headway and
accelerations are CityFlow's defaults; the other types' values are assumptions chosen to be
plausible (small vehicles follow closer and accelerate faster) and were not tuned to favour any
controller.

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

### Demand

Vehicles arrive as a Poisson process on each of the 8 entry roads. East–west is the major road:
each east or west entry has weight 1.0<!--=scn.entry_weights.W--> and each north or south entry
0.6<!--=scn.entry_weights.N-->. At every intersection a vehicle goes straight with probability
0.60<!--=scn.turn_probabilities.go_straight-->, takes the free (left) turn with
0.25<!--=scn.turn_probabilities.turn_right--> and the right turn with
0.15<!--=scn.turn_probabilities.turn_left-->; these shares are assumptions. Each seed produces a
different flow file, so seeds give genuinely different traffic.

### Demand calibration {#sec:calibration}

The demand levels were not chosen by eye. The goal was an off-peak level that is clearly below
capacity and a peak level near capacity that still drains. A three-step procedure, fixed before
it was run, set them:

1. **Measure capacity.** Saturation flows were measured in the simulator with the vehicle mix by
   letting a queue discharge after a long red (@tbl:capacity).
2. **Sweep demand under MaxPressure.** For total demands from
   1000<!--=docs/indian_scenario.md | sweep | 1000 & 0.05 | Demand--> to
   14000<!--=docs/indian_scenario.md | sweep | 14000 | Demand--> vehicles per hour and three
   seeds, MaxPressure ran for an hour and then until the network emptied (@fig:calibration).
3. **Apply the rule.** The network "drains" if at most 2<!--=cal.rule.backlog_pct-->% of the vehicles are still waiting to
   enter at the end of the hour and it empties within 900<!--=cal.rule.drain_s--> s after arrivals stop, on every seed.
   The lowest swept demand that does not drain is
   $R^*$ = 5500<!--=cal.r_star--> veh/h. Peak is the largest swept demand at or below 0.9<!--=cal.rule.peak_fraction--> × $R^*$
   that drains, 4750<!--=cal.peak--> veh/h; off-peak is 0.5<!--=cal.rule.offpeak_over_peak--> × peak,
   2375<!--=cal.offpeak--> veh/h.

![Demand calibration under MaxPressure: average travel time and the backlog left at the end of
the hour, against total demand. The dashed lines mark the chosen off-peak and peak levels and
$R^*$.](figures/calibration.png){#fig:calibration width=100%}

::: {#tbl:capacity}
<!-- BEGIN:tab_capacity -->
| Quantity (mixed traffic, measured) | Value |
|--------------------------------------------------------------|-------------------------------------:|
| Saturation flow, straight lane | 2103 veh/h |
| Saturation flow, protected-turn lane (Indian right turn) | 2024 veh/h |
| Start-up lost time (mean of both lanes) | 1.88 s |
| Entry admission limit (CityFlow insertion) | 1341 veh/h |
<!-- END:tab_capacity -->

: Capacity of the Indian network with its vehicle mix, measured in the simulator.
:::

"Near capacity" here means near the capacity **of MaxPressure as configured**, not of the
intersections. A controller-independent check with Webster's critical flow ratio shows that the
peak level uses only about
0.55<!--=docs/indian_scenario.md | webster_reference | Peak, 4750 | Value | 1--> of Webster's
capacity limit. MaxPressure breaks down earlier because it switches often and every switch costs
5 s of transition: under the earlier 10 s minimum green, a third of each intersection's time was
transition (@sec:baselines). This is why a well-timed fixed plan can keep up with MaxPressure at
peak.

## Emergency scenario {#sec:emergency-scenario}

The emergency scenarios add ambulances to the normal flow files of the peak level without
changing any other vehicle. Ambulances arrive at 6<!--=scn.emergency.veh_per_hour--> per hour over
the whole network (an assumption), with routes drawn like the normal traffic, from a random
generator seeded separately so that the normal traffic does not depend on them. An ambulance is a
5<!--=scn.emergency_vehicle_types.ambulance.length--> m van at the 12.5<!--=scn.emergency_vehicle_types.ambulance.maxSpeed--> m/s
lane limit. Over seeds 0–4 there are 37<!--=e.mp.amb_all_n--> ambulances, of which
29<!--=e.mp.amb_n--> are **signal-relevant**: their route crosses at least one movement a signal
controls (the others only make free turns, which no signal affects). CityFlow has no notion of
yielding: other vehicles do not pull over and, with lane changing off, the ambulance cannot
overtake. Only the signal can help it, which is exactly what the controllers are tested on.

## Baselines and their tuning {#sec:baselines}

An LLM controller should be compared with baselines that are as good as they can reasonably be,
and those must be fixed before the comparison, not after. Three classical controllers were used.

* **FixedTime**: the 4 paired phases (each pair of opposing approaches together), 30<!--=cfg.ft.green--> s of green
  each. This is the naive plan.
* **Webster fixed time**: the same 4 phases with a cycle and splits computed per intersection by
  Webster's method. Saturation flows and start-up lost times are measured on the network with the
  run's vehicle mix (mean of 30<!--=cfg.web.reps--> random-order queues), and lane demand is read from the run's own
  flow file, i.e. a perfect count of the simulated hour. This favours Webster: a real plan is built
  from older counts.
* **MaxPressure**: all 8 green phases, ties keep the current phase.

MaxPressure's timing was tuned in two sweeps on four scenarios (Jinan, Hangzhou, Indian off-peak
and peak; 3 seeds each), with selection rules committed before the runs: rank the settings by
mean travel time in each scenario, choose the lowest mean rank, break ties by the lowest mean
ratio to the best. The first sweep varied the decision interval and showed that what really
changed was the shortest possible green. The second sweep therefore fixed the interval at 5 s and
varied the minimum green (@tbl:mg-selection). A minimum green of
15<!--=mg.chosen--> s was chosen, through the tie-break: the 10 s setting is best on three
scenarios but last at Indian peak.

::: {#tbl:mg-selection}
<!-- BEGIN:tab_mg_selection -->
| Min green | Jinan | Hangzhou | Off-peak | Peak | Mean rank | Mean ATT / best | Chosen |
|------------|-----------:|--------------:|--------------:|----------:|----------:|-----------:|-------------|
| 10 s | 1 | 1 | 1 | 4 | 1.75 | 1.058 |  |
| 15 s | 2 | 2 | 2 | 1 | 1.75 | 1.026 | chosen |
| 20 s | 3 | 3 | 3 | 2 | 2.75 | 1.072 |  |
| 25 s | 4 | 4 | 4 | 3 | 3.75 | 1.139 |  |
<!-- END:tab_mg_selection -->

: Pre-registered selection of MaxPressure's minimum green (decision interval 5 s): rank of each
setting by mean travel time per scenario, mean rank, and the tie-break.
:::

The minimum green matters because of the transition. With a 10 s minimum green MaxPressure
switches so often that 32.4<!--=i.peak.maxpressure_5s.transition-->% of each intersection's time
at peak is transition, against 24.7<!--=i.peak.maxpressure.transition-->% with 15<!--=cfg.mp.min_green--> s. In light
traffic reacting quickly wins; near capacity the green lost to transitions costs more. No
setting is best at both levels, and the pre-registered rule chose the compromise.

@tbl:baselines-indian gives all baselines on the Indian network. Off-peak, MaxPressure is clearly
best. At peak, the tuned MaxPressure and the Webster plan are effectively tied
(115.5<!--=i.peak.maxpressure.att--> s and 116.3<!--=i.peak.fixedtime_webster.att--> s), and the
30<!--=cfg.ft.green--> s FixedTime no longer drains: about 308<!--=i.peak.fixedtime.backlog--> vehicles are still waiting to enter at the end of the
hour. This tie matters for reading the LLM results: at peak, "as good as MaxPressure" is also
"as good as a well-timed fixed plan".

::: {#tbl:baselines-indian}
<!-- BEGIN:tab_baselines_indian -->
| Level | Controller | ATT (s) | Queue / int. (veh) | Finished trips | Waiting to enter at end | Share of time in transition |
|-----------|--------------------|-------------:|-------------:|-----------:|-------------:|--------------:|
| off-peak | FixedTime, 4 paired phases, 30 s | 121.5 ± 0.2 | 10.58 ± 0.17 | 2316 ± 28 | 0.0 ± 0.0 | 0.142 ± 0.000 |
| off-peak | FixedTime, all 8 phases, 30 s | 129.3 ± 1.3 | 11.88 ± 0.42 | 2298 ± 28 | 0.0 ± 0.0 | 0.142 ± 0.000 |
| off-peak | FixedTime, 4 paired phases, Webster plan | 100.4 ± 4.1 | 6.82 ± 0.52 | 2320 ± 36 | 0.0 ± 0.0 | 0.326 ± 0.006 |
| off-peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 88.1 ± 1.0 | 4.94 ± 0.23 | 2332 ± 36 | 0.0 ± 0.0 | 0.246 ± 0.001 |
| off-peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 81.3 ± 0.3 | 3.80 ± 0.07 | 2332 ± 38 | 0.0 ± 0.0 | 0.314 ± 0.003 |
| off-peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 82.0 ± 0.8 | 3.91 ± 0.17 | 2332 ± 37 | 0.0 ± 0.0 | 0.319 ± 0.003 |
| peak | FixedTime, 4 paired phases, 30 s | 279.9 ± 9.9 | 44.44 ± 0.75 | 4166 ± 93 | 307.7 ± 20.5 | 0.142 ± 0.000 |
| peak | FixedTime, all 8 phases, 30 s | 291.9 ± 7.3 | 47.67 ± 0.62 | 4113 ± 88 | 331.0 ± 18.3 | 0.142 ± 0.000 |
| peak | FixedTime, 4 paired phases, Webster plan | 116.3 ± 4.6 | 18.27 ± 1.28 | 4577 ± 87 | 0.3 ± 0.6 | 0.227 ± 0.004 |
| peak | MaxPressure (8 phases, 5 s, min 15 / max 60) | 115.5 ± 0.9 | 17.83 ± 0.32 | 4576 ± 68 | 0.3 ± 0.6 | 0.247 ± 0.001 |
| peak | MaxPressure (8 phases, 15 s, min 10 / max 60) | 133.8 ± 15.9 | 23.24 ± 4.60 | 4540 ± 116 | 0.3 ± 0.6 | 0.321 ± 0.002 |
| peak | MaxPressure (8 phases, 5 s, min 10 / max 60) | 142.4 ± 18.3 | 25.84 ± 5.22 | 4516 ± 131 | 0.3 ± 0.6 | 0.324 ± 0.001 |
<!-- END:tab_baselines_indian -->

: All baselines on the Indian 2x2 network, mean ± std over seeds 0–2, 3600<!--=cfg.steps--> s. The
default MaxPressure is the tuned one (5 s interval, 15<!--=cfg.mp.min_green--> s minimum green).
:::
