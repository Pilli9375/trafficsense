# Simulator validation

This document checks that TrafficSense's simulator wrapper, signal timing and metrics are
correct by comparing against an independent implementation: the CoLLMLight authors' own
code (github.com/usail-hkust/CoLLMLight, commit `ce204a9`). Every table below is generated
from the JSON files in `outputs/validation/` by `scripts/validation/make_tables.py`;
`make_tables.py --check` fails if this document and the data disagree.

## Verdict

**The simulator is validated.** When our environment is driven exactly the way CoLLMLight's
code drives CityFlow (same phases, same 30 s decision grid, same CityFlow seed, lane changing
on), it reproduces CoLLMLight's own reported throughput, queue length and waiting time
**bit-for-bit** for FixedTime and MaxPressure on all three datasets (Synthetic 4x4, Jinan 3x4,
Hangzhou 4x4). Their ATT is identical in 5 of 6 runs; every other difference is at most
5×10⁻⁶ relative and is explained below. Remaining differences between
our numbers and theirs come from three known, explained sources: different settings, different
metric definitions, and a bug in CoLLMLight's FixedTime. None of them is a fault in our simulator.

Our numbers compared with CoLLMLight's own code ("identical" = equal as floating-point
numbers; otherwise the relative difference):

<!-- BEGIN:exactness -->
| Dataset | Controller | ATT | Throughput | Queue | Waiting | CityFlow ATT |
|---|---|---|---|---|---|---|
| synthetic_4x4 | Fixedtime | identical | identical | identical | identical | 3.1e-07 rel. |
| synthetic_4x4 | MaxPressure | 3.7e-06 rel. | identical | identical | identical | 9.9e-07 rel. |
| jinan_3x4 | Fixedtime | identical | identical | identical | identical | 1.8e-07 rel. |
| jinan_3x4 | MaxPressure | identical | identical | identical | identical | 1.4e-06 rel. |
| hangzhou_4x4 | Fixedtime | identical | identical | identical | identical | identical |
| hangzhou_4x4 | MaxPressure | identical | identical | identical | identical | 4.6e-06 rel. |
<!-- END:exactness -->

## 1. Cross-check against CoLLMLight's own baselines

### How it was run

* **Their code, unmodified.** `scripts/validation/run_collmlight_baseline.py` runs their
  `run_fixedtime.py` / `run_maxpressure.py` in a separate virtualenv with their pinned numpy
  (1.26.4) and pandas (2.2.2). Their `utils/config.py` imports every agent class, including the
  TensorFlow / torch / LLM ones, so those imports are replaced by inert stubs. FixedTime and
  MaxPressure never call them and the stubs produce no data. Their `run_maxpressure.py` has no
  Synthetic 4x4 branch, so for that one case the harness builds the same config dicts that
  script builds, using the Synthetic paths from their `run_fixedtime.py`.
* **Their settings** (read from their code): 4 phases (W-E straight, N-S straight, W-E left,
  N-S left); one action every 30 s (`MIN_ACTION_TIME`); 5 s of phase 0 before every switch;
  no minimum or maximum green; FixedTime "30 s per phase"; `laneChange: true`; CityFlow seed
  drawn with `np.random.randint(0, 100)` on every reset (we seed numpy and record the seed).
* **Our code with matched settings.** `scripts/validation/run_matched.py` runs our env and
  controllers with the same phases, 30 s grid, `np.argmax` tie-break, no max green,
  lane changing on and **the same CityFlow seed their run drew**. Each run is scored with
  our metrics *and* with a line-by-line reimplementation of CoLLMLight's metric code
  (`scripts/validation/collmlight_metrics.py`), so like is compared with like.

### Their metric definitions differ from ours

| Metric | CoLLMLight | TrafficSense |
|---|---|---|
| ATT | Per vehicle, the sum over intersections of time from first appearing on an incoming lane to leaving it; vehicles still on a lane at the end count up to 3600. **Excludes** time queued to enter the network and time on exit roads. | `engine.get_average_travel_time()`: every generated vehicle, from its scheduled start, **including** time queued to enter the network. |
| Queue | Waiting vehicles on all incoming lanes, **summed over the network**, sampled every 30 s. | Same count, **per intersection**, sampled every second. |
| Waiting time | Mean *current* stop length of the vehicles stopped at that moment (resets when a vehicle moves), sampled every 30 s. | Total seconds stopped per vehicle, averaged over all vehicles that entered. |
| Throughput | Vehicles that have left every intersection approach they entered (includes vehicles on exit roads, and lane-change shadow copies). | Vehicles that finished their trip. |

Because of these definitions, the same simulation gives very different-looking numbers
(e.g. their ATT 683 s vs CityFlow ATT 1263 s for one MaxPressure run). Tables below show both.

### Result: Synthetic 4x4 (their metric definitions)

<!-- BEGIN:crosscheck_synthetic -->
| Run | ATT (their def.) | Throughput (their def.) | Queue (their def., network total) | Waiting (their def.) | CityFlow ATT | Engine seed |
|---|---|---|---|---|---|---|
| CoLLMLight code: FixedTime | 1192.5 | 751 | 467.3 | 1215.6 | 1612.0 | 47 |
| Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1192.5 | 751 | 467.3 | 1215.6 | 1612.0 | 47 |
| CoLLMLight code: MaxPressure | 683.1 | 2505 | 468.4 | 84.8 | 1263.3 | 47 |
| Ours, MaxPressure matched to theirs | 683.1 | 2505 | 468.4 | 84.8 | 1263.3 | 47 |
<!-- END:crosscheck_synthetic -->

Throughput, queue and waiting time are identical. ATT (their definition) and CityFlow ATT
differ in the 4th–6th significant digit; see "Why ATT differs by a hair" below.

### CoLLMLight's FixedTime only serves East-West traffic

Their `FixedtimeAgent` computes the next action as `(cur_phase + 1) % 4`, where `cur_phase`
is the CityFlow phase index (1–4), but actions are 0-based and the env adds 1 again. So phase
1 → action 2 → phase 3, and phase 3 → action 0 → phase 1. Their own action log
(`state_action.json`) confirms all 16 intersections alternate `ETWT` / `ELWL` for the whole
hour (60 / 60 of 120 actions): **north-south traffic never gets a green**. Their FixedTime
numbers on these datasets therefore describe a broken baseline. A correct 4-phase cycle on
the same 30 s grid ("Ours: FixedTime, 4 phases, 30 s grid") is shown in the tables below.

### Why ATT differs by a hair

With `laneChange: true`, CityFlow's results depend very slightly on which read-only API calls
are made between steps (`get_vehicle_info`, `get_vehicle_distance`, ...): the same run with
different extra calls gave CityFlow ATT 1611.787 / 1611.979 / 1611.981 s. With
`laneChange: false` the result is bit-for-bit identical whatever is called (checked:
1293.49050 s in all three cases). Their env makes more such calls than ours, which fully
accounts for the ~0.0005 s gap. This is one reason our default is `lane_change: false`.

### Seed sensitivity of their code (Synthetic 4x4)

<!-- BEGIN:seeds -->
| CoLLMLight model | numpy seed | Engine seed drawn | ATT (their def.) | Throughput (their def.) | Queue (their def.) | CityFlow ATT |
|---|---|---|---|---|---|---|
| Fixedtime | 0 | 47 | 1192.5377 | 751 | 467.2667 | 1611.9803 |
| Fixedtime | 1 | 12 | 1192.5377 | 751 | 467.2667 | 1611.9797 |
| Fixedtime | 2 | 15 | 1192.5377 | 751 | 467.2667 | 1611.9796 |
| MaxPressure | 0 | 47 | 683.1030 | 2505 | 468.4333 | 1263.2965 |
| MaxPressure | 1 | 12 | 683.1042 | 2505 | 468.4333 | 1263.2986 |
| MaxPressure | 2 | 15 | 683.1042 | 2505 | 468.4333 | 1263.2986 |
<!-- END:seeds -->

Different numpy seeds draw different CityFlow seeds, but the flow file is fixed and lane
changing barely happens in this roadnet (each lane serves exactly one turn), so their results
do not change at the printed precision.

### Correction to an earlier claim

The Phase 1 summary said CityFlow's ATT leaves out vehicles that never entered the network.
That was wrong. `get_average_travel_time()` averages over **every generated vehicle**, timed
from its scheduled start, including those still queued to enter.
`tests/test_metrics.py::test_cityflow_att_includes_vehicles_waiting_to_enter` reproduces the
engine's number from the flow file to 1e-6 s. The metric notes in the code and in every
`summary.json` were corrected (commit `72288a4`).

## 2. Demand on Synthetic 4x4

From `scripts/validation/flow_demand.py` (all 8000 vehicles, one vehicle type: 5 m long,
11.1 m/s, 2 s headway, 2.5 m min gap).

<!-- BEGIN:demand -->
| Entry road | Vehicles / h | Share | Turn at first intersection |
|---|---|---|---|
| road_2_5_3 | 2765 | 34.6% | go_straight 2660, turn_right 105 |
| road_1_0_1 | 1452 | 18.1% | go_straight 1452 |
| road_3_5_3 | 860 | 10.8% | go_straight 847, turn_right 13 |
| road_2_0_1 | 842 | 10.5% | turn_left 734, go_straight 103, non_adjacent 5 |
| road_5_1_2 | 663 | 8.3% | go_straight 416, turn_left 130, turn_right 117 |
| road_3_0_1 | 544 | 6.8% | turn_left 544 |
| road_4_0_1 | 503 | 6.3% | turn_left 370, go_straight 133 |
| road_0_2_0 | 141 | 1.8% | turn_left 74, go_straight 67 |
| road_0_3_0 | 118 | 1.5% | go_straight 82, turn_left 36 |
| road_0_4_0 | 112 | 1.4% | turn_left 112 |
<!-- END:demand -->

Demand over time is flat (10-minute bins):

<!-- BEGIN:demand_time -->
| Start time | Vehicles |
|---|---|
| 0-10 min | 1277 |
| 10-20 min | 1315 |
| 20-30 min | 1377 |
| 30-40 min | 1299 |
| 40-50 min | 1378 |
| 50-60 min | 1354 |
<!-- END:demand_time -->

Five vehicles have a U-turn route (`road_2_0_1 → road_2_1_3`) with no movement between the
two roads; CityFlow treats route roads as waypoints and finds a path, so their first turn is
listed as `non_adjacent`.

### Can road_2_5_3 carry its demand?

In these roadnets each incoming lane serves exactly one turn (lane 0 left, 1 straight,
2 right), so the 2660 vehicles going straight from `road_2_5_3` all need **one** lane.

<!-- BEGIN:capacity -->
| Quantity | veh / h |
|---|---|
| Demand on road_2_5_3 (all lanes) | 2765 |
| Demand needing its straight lane | 2660 |
| Most the entry lane can admit, measured (permanent green, 1 veh/s fed; CityFlow insertion limit) | 1200 |
| Stop-line saturation flow, measured (queue discharge after a long red) | 1440 |
| Steady car-following flow, ESTIMATE from vehicle parameters | 1346 |
| Demand / entry-lane admission limit | 2.22 |
| Demand / stop-line saturation flow | 1.85 |
<!-- END:capacity -->

Two different limits are measured (`trafficsense.sim.capacity`):

* **Entry admission (1200 veh/h).** A CityFlow run that holds every signal on the route green
  and feeds 1 vehicle/s along a straight route, counting finished vehicles in minutes 20–60.
  Because the route starts at the network edge, this is limited by how CityFlow *inserts*
  vehicles, not by the signal: a waiting vehicle enters the lane at speed 0 only once the
  previous one, also starting from standstill, is `length + minGap` = 7.5 m ahead
  (`Lane::available` in CityFlow). At 2 m/s² that takes 3 steps, hence exactly 3600 / 3 = 1200.
* **Stop-line saturation flow (1440 veh/h).** Hold the lane red for 900 s, then green, and
  count vehicles leaving the queue in green seconds 10–70. This is the rate a green phase
  can serve.

The estimate is steady car-following flow
`maxSpeed / (length + minGap + maxSpeed × headwayTime)` and is only a cross-check.

**Correction (Phase 2):** this table previously reported only the 1200 veh/h figure, labelled
as "straight-lane capacity". That label was wrong: 1200 veh/h is the entry
lane's admission limit, and the stop line itself can discharge 1440 veh/h. The conclusion
does not change. **Even with a permanent green, this lane can carry only about half of its
demand** (it can admit 45% of it, and its stop line could serve 54%). No signal plan can clear
it, so a large entry queue on Synthetic 4x4 is a property of the dataset, not of our simulator
or controllers. This is why only ~2200–2900 of the 8000 vehicles enter the network within the
hour.

## 3. FixedTime phases

Default FixedTime now cycles the **4 paired phases** (opposing approaches together:
W-E straight, N-S straight, W-E left, N-S left), detected from the roadnet as the green
phases whose two non-right movements come from opposite approaches, and checked to serve
every non-right movement exactly once. The previous 8-phase cycle is kept as controller
`fixedtime_all_phases`.

On Jinan and Hangzhou the 4-phase plan is better than the 8-phase plan (CityFlow ATT
423.0 vs 434.8 s and 580.6 vs 590.5 s). On Synthetic 4x4 it is slightly *worse*
(1460.3 vs 1441.7 s; throughput 1400 vs 1552; see section 4). Both give every movement the same share of green (30 s of every 140 s vs
2 × 30 s of every 280 s). Cycle length is not the reason: the 8-phase plan with 15 s greens
(160 s cycle) is still better than the 4-phase plan, and the 4-phase plan with 60 s greens is
worse. The difference therefore comes from the phase structure. The likely explanation, **not
verified**, is that Synthetic demand is strongly one-directional, and the single-approach
phases (e.g. N straight + N left) serve a heavy approach without sharing the green with a
light opposing one. The Phase 1 summary called the 4-phase plan "a stronger baseline"; that
holds on the two real-world datasets but not on Synthetic 4x4.

## 4. All datasets: our controllers vs CoLLMLight's code

Rows marked "CoLLMLight code" come from their code; their queue and waiting-time definitions
cannot be converted to ours, so those cells are blank. "Matched" rows use their settings
(lane changing on, their CityFlow seed); "default" rows use `configs/default.yaml`
(lane changing off, seed 0).

### Synthetic 4x4 (`anon_4_4_synthetic_8000.json`)

<!-- BEGIN:all_synthetic -->
| Run | ATT (CityFlow) | Queue / intersection | Waiting time / vehicle | Throughput (finished trips) | ATT (CoLLMLight def.) | Throughput (CoLLMLight def.) |
|---|---|---|---|---|---|---|
| CoLLMLight code: FixedTime | 1612.0 | – | – | – | 1192.5 | 751 |
| CoLLMLight code: MaxPressure | 1263.3 | – | – | – | 683.1 | 2505 |
| Ours: FixedTime, 4 phases, 30 s grid (matched, correct cycle) | 1420.6 | 31.7 | 758.4 | 1708 | 875.6 | 1724 |
| Ours: MaxPressure matched | 1263.3 | 29.2 | 540.2 | 2470 | 683.1 | 2505 |
| Ours default: FixedTime (4 paired phases, 30 s) | 1460.3 | 32.1 | 866.4 | 1400 | 970.7 | 1433 |
| Ours default: FixedTime all 8 phases | 1441.7 | 31.1 | 783.9 | 1552 | 892.4 | 1576 |
| Ours default: MaxPressure (8 phases, 5 s, min 10 / max 60) | 1293.5 | 25.9 | 522.5 | 2271 | 679.6 | 2297 |
<!-- END:all_synthetic -->

### Jinan 3x4 (`anon_3_4_jinan_real_2000.json`)

<!-- BEGIN:crosscheck_jinan -->
| Run | ATT (their def.) | Throughput (their def.) | Queue (their def., network total) | Waiting (their def.) | CityFlow ATT | Engine seed |
|---|---|---|---|---|---|---|
| CoLLMLight code: FixedTime | 1239.3 | 1786 | 1338.6 | 920.3 | 1258.0 | 47 |
| Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1239.3 | 1786 | 1338.6 | 920.3 | 1258.0 | 47 |
| CoLLMLight code: MaxPressure | 273.2 | 4187 | 106.6 | 38.2 | 317.8 | 47 |
| Ours, MaxPressure matched to theirs | 273.2 | 4187 | 106.6 | 38.2 | 317.8 | 47 |
<!-- END:crosscheck_jinan -->

<!-- BEGIN:all_jinan -->
| Run | ATT (CityFlow) | Queue / intersection | Waiting time / vehicle | Throughput (finished trips) | ATT (CoLLMLight def.) | Throughput (CoLLMLight def.) |
|---|---|---|---|---|---|---|
| CoLLMLight code: FixedTime | 1258.0 | – | – | – | 1239.3 | 1786 |
| CoLLMLight code: MaxPressure | 317.8 | – | – | – | 273.2 | 4187 |
| Ours: FixedTime, 4 phases, 30 s grid (matched, correct cycle) | 479.6 | 23.9 | 236.3 | 3942 | 441.2 | 4027 |
| Ours: MaxPressure matched | 317.8 | 7.5 | 73.9 | 4115 | 273.2 | 4187 |
| Ours default: FixedTime (4 paired phases, 30 s) | 423.0 | 17.8 | 176.2 | 3968 | 380.9 | 4039 |
| Ours default: FixedTime all 8 phases | 434.8 | 18.9 | 187.8 | 3991 | 393.9 | 4032 |
| Ours default: MaxPressure (8 phases, 5 s, min 10 / max 60) | 295.9 | 4.9 | 49.0 | 4135 | 248.9 | 4200 |
<!-- END:all_jinan -->

### Hangzhou 4x4 (`anon_4_4_hangzhou_real.json`)

<!-- BEGIN:crosscheck_hangzhou -->
| Run | ATT (their def.) | Throughput (their def.) | Queue (their def., network total) | Waiting (their def.) | CityFlow ATT | Engine seed |
|---|---|---|---|---|---|---|
| CoLLMLight code: FixedTime | 1002.8 | 1526 | 694.5 | 827.5 | 1054.7 | 47 |
| Ours, replaying their FixedTime (phases 1,3 on a 30 s grid) | 1002.8 | 1526 | 694.5 | 827.5 | 1054.7 | 47 |
| CoLLMLight code: MaxPressure | 325.3 | 2751 | 69.0 | 49.6 | 365.7 | 47 |
| Ours, MaxPressure matched to theirs | 325.3 | 2751 | 69.0 | 49.6 | 365.7 | 47 |
<!-- END:crosscheck_hangzhou -->

<!-- BEGIN:all_hangzhou -->
| Run | ATT (CityFlow) | Queue / intersection | Waiting time / vehicle | Throughput (finished trips) | ATT (CoLLMLight def.) | Throughput (CoLLMLight def.) |
|---|---|---|---|---|---|---|
| CoLLMLight code: FixedTime | 1054.7 | – | – | – | 1002.8 | 1526 |
| CoLLMLight code: MaxPressure | 365.7 | – | – | – | 325.3 | 2751 |
| Ours: FixedTime, 4 phases, 30 s grid (matched, correct cycle) | 667.9 | 18.4 | 362.3 | 2368 | 616.0 | 2450 |
| Ours: MaxPressure matched | 365.7 | 3.6 | 70.0 | 2702 | 325.3 | 2751 |
| Ours default: FixedTime (4 paired phases, 30 s) | 580.6 | 13.0 | 258.9 | 2438 | 516.0 | 2480 |
| Ours default: FixedTime all 8 phases | 590.5 | 13.6 | 270.9 | 2412 | 527.3 | 2446 |
| Ours default: MaxPressure (8 phases, 5 s, min 10 / max 60) | 331.1 | 1.7 | 32.2 | 2740 | 285.7 | 2789 |
<!-- END:all_hangzhou -->

### What the tables show

* On every dataset our MaxPressure beats FixedTime by a wide margin, in both settings and
  under both metric definitions.
* Our default MaxPressure (8 phases, 5 s decisions) beats the matched one (4 phases, 30 s
  decisions) on Jinan (295.9 vs 317.8 s) and Hangzhou (331.1 vs 365.7 s), but **not** on
  Synthetic 4x4 (1293.5 vs 1263.3 s). The default switches about twice as often, so its
  signals spend roughly twice as much time in the 5 s transition phase (measured: 22% vs 11%
  of intersection-time on Synthetic, 32% vs 16% on Jinan, 27% vs 15% on Hangzhou). The likely
  explanation, **not verified**: on the oversaturated Synthetic network the green time lost
  to transitions matters more than reacting faster, while on the lighter real-world networks
  reacting faster wins. (The two settings also differ in lane changing and seed, which the
  cross-check shows to be a very small effect.)
* CoLLMLight's FixedTime is far worse than a correct 4-phase cycle on the same 30 s grid
  (e.g. Jinan CityFlow ATT 1258.0 vs 479.6 s), because of the bug above.

### Published numbers

The CoLLMLight repository (README and all tracked files at `ce204a9`) contains **no**
FixedTime / MaxPressure result tables, so there are no repository numbers to compare with.
The papers (CoLLMLight, ICLR 2026, openreview.net/forum?id=KeJqoEVOeY; LLMLight) were not
consulted for this document, and no paper numbers are quoted here. If they are added later, they
must be copied from the PDF with the table number, and the different metric definitions and
the FixedTime bug above must be taken into account before comparing.

## Reproducing

```bash
scripts/fetch_collmlight_data.sh
git clone --depth 1 https://github.com/usail-hkust/CoLLMLight.git data/external/collmlight_repo
python3 -m venv data/external/collmlight_venv
data/external/collmlight_venv/bin/pip install numpy==1.26.4 pandas==2.2.2 tqdm==4.66.2
ln -s "$(.venv/bin/python -c 'import cityflow;print(cityflow.__file__)')" \
      data/external/collmlight_venv/lib/python3.10/site-packages/
data/external/collmlight_venv/bin/python scripts/validation/run_collmlight_baseline.py --model Fixedtime --dataset synthetic_4x4 --seed 0
python scripts/validation/run_matched.py --scenario synthetic_4x4 --profile replica_fixedtime --engine-seed 47
python scripts/validation/flow_demand.py --scenario synthetic_4x4
python scripts/validation/make_tables.py
```
