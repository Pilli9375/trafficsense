# Key Ideas Explained Simply

Each idea has three parts: what it is, an everyday analogy, and a one-line answer to give if the
panel asks. Learn the "If asked, say" lines by heart.

## The Simulator (CityFlow)

**What it is.** CityFlow is a free computer program that simulates traffic. It moves every single
vehicle second by second along the roads, stops it at red lights and lets it go on green. All our
results are *measured* inside CityFlow: travel times, queues, waiting times. A **simulation** means
nothing happened on a real road.

We did one important check first, called **validation**. We drove our CityFlow setup exactly the
way the CoLLMLight authors' own code drives it, and compared the numbers. Throughput, queue length
and waiting time were identical on all three of their datasets, and travel time was identical or
differed only in the sixth significant digit. Along the way we found a bug in their fixed-time
baseline: it never gives north–south traffic a green.

One limit to remember: CityFlow is **lane-based**. Vehicles stay in their lanes. It cannot show
two-wheelers squeezing between cars. So our network has the Indian *vehicle mix*, but not Indian
*driving behaviour*.

**Analogy.** A flight simulator for traffic signals: pilots practise in a simulator before flying a
real plane. We tested our controller in the simulator; we never "flew the real plane".

> **If asked, say:** "CityFlow is the traffic simulator used by CoLLMLight and most research in this
> area. We validated our setup against the authors' own code before trusting any result."

## Fixed-Time Plans and Webster's Method

**What it is.** A **fixed-time plan** repeats the same timing forever, for example
30<!--=cfg.ft.green--> s of green for each of four phases. It is cheap and predictable, but it
cannot react to the traffic actually present.

**Webster's method** (from 1958) is the textbook way to compute a *good* fixed plan. It looks at how
busy each direction is (its flow compared with how many vehicles the road can pass) and computes a
cycle length and how to split the green between phases. We gave Webster an unfair advantage: its
plan was computed from the *exact* traffic of the simulated hour. A real plan would be built from
older counts.

**Analogy.** A school timetable. The periods do not change with how many students are in each
class. Webster's method is a timetable made by someone who counted the students carefully first.

> **If asked, say:** "Webster's plan is a well-timed fixed plan. We computed it from perfect counts,
> so it is a strong baseline. At peak it is effectively tied with MaxPressure."

## MaxPressure

**What it is.** MaxPressure is a classical rule that reacts to the traffic. For each phase it
computes a **pressure**: the number of vehicles waiting on the roads that phase would serve, minus
the vehicles queued on the roads they would drive into. The phase with the highest pressure gets
green. It needs no training and no forecast. It is the main baseline of our project, and our best
classical controller.

We **tuned** it before any AI run. The setting that mattered most was the *minimum green* (the
shortest time a green must last). With a pre-registered rule we chose 15<!--=mg.chosen--> s. With
10 s, too much time at peak is lost to transitions (32.4<!--=i.peak.maxpressure_5s.transition-->%
of each junction's time against 24.7<!--=i.peak.maxpressure.transition-->%).

**Analogy.** A shopkeeper with several queues opens the counter for the longest queue, but only if
those customers have somewhere to go after the counter (the road ahead is not jammed).

> **If asked, say:** "MaxPressure gives green to the phase with the most waiting vehicles, minus
> the ones already queued downstream. It is simple, needs no training, and it is very strong. We
> tuned it before comparing."

## The LLM Agent and the Local Model

**What it is.** An **LLM** (large language model) is an AI that reads text and writes text, like
the models behind chatbots. Our **agent** at each junction does five things every
5<!--=cfg.mp.interval--> seconds (once the minimum green has been served):

1. **Observe:** it gets a short text describing its junction and its neighbours: for each phase,
   the pressure and the queue (about 277<!--=docs/llm_benchmark.md | llm_benchmark | guarded_v3 & llama3.2:3b | Prompt tokens--> tokens; a token is a word or part of a word).
2. **Reason:** the text goes to the model.
3. **Act:** the model answers in a fixed format (JSON): a phase number and a short reason of at most
   15<!--=code.reason_words.guided_v3--> words. Our code checks the answer.
4. **Enforce:** our code adds the yellow/all-red transition and keeps the green within its limits.
5. **Log:** everything is written to a log file, so every decision can be checked and replayed.

The model runs **locally** through **Ollama**, a free program that runs AI models on your own
computer. No internet and no paid service are needed. Our laptop has an NVIDIA **GTX 1650**
graphics card (**GPU**) with only 4 GB of memory, so we used small models of 3 to 4 billion
**parameters** (the model's internal numbers; more parameters usually means a stronger but slower
model). The selected model is `llama3.2:3b`. We used the models as released: no
**fine-tuning** (extra training on our task).

How was the model chosen? A pre-registered benchmark: each candidate controlled
600<!--=b.steps--> s of peak traffic. A model was *eligible* only if fewer than
2<!--=b.rule.fail_pct-->% of its calls failed and 95% of its answers came within
3<!--=b.rule.p95_s--> s. Among eligible ones, the lowest mean queue won.

A hard lesson from the benchmark: the small models misread pressure. They often **preferred low
pressure** (choosing the phase that needs green *least*). We fixed two lines of the prompt (version
v3, a post-hoc fix, stated openly); it helped `gemma4:e4b` but not the 3B models.

**Analogy.** A new trainee traffic police officer who reads a written report from each junction
and says which road to release, with one line of explanation. The trainee is fast and cheap, but
sometimes misunderstands the report. So a senior officer checks the decision (that is the guard).

> **If asked, say:** "Each junction has its own small local LLM agent through Ollama on a 4 GB
> laptop GPU. It reads its and its neighbours' state as text and returns a phase and a short
> reason in JSON."

## The Guard

**What it is.** The guard is a safety check after the LLM. MaxPressure first ranks the phases. The
LLM chooses among MaxPressure's two best phases or keeping the current one (this is the **hybrid**
design: MaxPressure proposes, the LLM decides). Then the guard checks the choice: it is applied only
if its pressure is within 20<!--=cfg.guard.margin-->% of the top pressure. Otherwise MaxPressure's
choice is applied, and the override is counted.

The guard does most of the work. The model's own answer differs from MaxPressure in
87<!--=l.amb.llm.differs-->–93<!--=l.peak.llm.differs-->% of calls, but the guard replaces most of
them, so the phase actually applied differs from MaxPressure's in only
10<!--=l.peak.llm.applied-->–11<!--=l.jinan.llm.applied-->% of calls. The report says it plainly:
*the guard made the LLM safe to deploy, not useful.*

**Analogy.** A driving-school car with a second brake pedal for the instructor. The learner drives,
but if the learner does something clearly wrong, the instructor's pedal wins.

> **If asked, say:** "The guard accepts the LLM's choice only if it is within 20<!--=cfg.guard.margin-->% of the best
> pressure. It makes the controller safe; it is also why the result is so close to MaxPressure."

## Cooperation Between Neighbouring Junctions

**What it is.** This idea comes from CoLLMLight. Each agent is told about its neighbours: for each
neighbour, its current phase, how many vehicles are stopped on its approaches towards this
junction and how many of those have green, and how many are stopped on this junction's road into
the neighbour. So an agent can avoid sending cars into a jammed neighbour. That is why it is
called **multi-agent** and **cooperative**.

**Analogy.** Neighbours on a street sharing the news: "a big crowd is coming your way" or "my side
is full, don't send more".

> **If asked, say:** "Cooperation means each agent's prompt includes its neighbours' state, as in
> CoLLMLight. All four agents share one GPU, so their calls run one after another."

## Pre-Registration

**What it is.** **Pre-registration** means writing down the plan of an experiment *and the rule that
decides its outcome* before running it, and saving it in git (version control) so the order can be
checked. Then nobody can quietly change the plan after seeing the results. We pre-registered every
major step: demand calibration, MaxPressure tuning, the model-selection rule, the final design
round, the full experiments, the ambulance experiment, the detector's settings and the camera-error
experiment. The rule even said: the selected controller goes to the full experiments *even if it is
worse than MaxPressure*.

**Analogy.** Writing down your prediction for a cricket match before it starts, and giving the
sealed envelope to a friend. You cannot change it after the result.

> **If asked, say:** "We fixed the plan and the decision rule in git before each experiment, so
> the confirmatory results could not be tuned after we saw them."

## Pre-Registered Versus Exploratory

**What it is.** A **pre-registered** (confirmatory) result followed the plan fixed in advance. An
**exploratory** result was added later, after the plan was fixed or after results were seen. It is
useful as a lead, but it is not proof. Our exploratory parts, each labelled in the deck, report and
dashboard:

1. **Prompt v3** was a post-hoc fix (the final design round that used it was itself pre-registered).
2. **The `gemma4:e4b` hybrid arm** failed the selection rule only on latency (speed), and was added
   to the full experiments at the user's request after the plan was fixed.
3. **The model-size study** (including the hosted 550<!--=m.size.nemo--> B Nemotron model) was
   planned after the main results.
4. **The camera-error decomposition** (one error type at a time) was added after reading the camera
   results.

**Analogy.** In a court case, evidence collected by the proper procedure versus an interesting
clue found later: the clue tells you where to look next, but it does not decide the case.

> **If asked, say:** "Pre-registered means fixed in advance; exploratory means added later. We
> label every exploratory number, and we never use an exploratory number as our headline."

## Why Several Random Seeds

**What it is.** A **seed** is a number that fixes the random choices in a run. On our Indian
network, each seed gives a different traffic file (different arrival times of vehicles). We ran
seeds 0, 1 and 2 (five seeds, 0 to 4, for the ambulance experiment). Every controller sees the same
traffic on the same seed, so comparisons are **paired by seed**: like for like.

With only three seeds, a statistical **significance test** (a formal test of whether a difference
could be luck) has little power, and none was pre-registered. So our rule is: a difference counts as
a result only if it has the same sign on every seed and is large compared with the seed-to-seed
spread. Smaller differences are called "within seed noise".

The Jinan network has one fixed traffic file, so the deterministic baselines give identical
results on every seed there (that is why their spread shows ± 0.0<!--=f.jinan.mp.att_sd-->).

**Analogy.** Testing a new cricket bat in three different matches, not one. One good match can be
luck.

> **If asked, say:** "Each seed is a different traffic file. We compare controllers on the same
> seed. Three seeds are few, so we only call a difference a result when it is consistent on every
> seed, and we did not run a significance test."

## The Measures

All are measured from the simulator. A run lasts 3600<!--=cfg.steps--> s (one simulated hour).

- **Average travel time (ATT)**, the main measure: the average time from when a vehicle was
  scheduled to start until it finished its trip, *including time spent waiting to enter the
  network*. So a controller cannot hide delay by blocking an entry. **Lower is better.**
- **Queue length:** the number of waiting vehicles (speed below 0.1<!--=code.stop_speed--> m/s) on
  a junction's incoming lanes, averaged over time and junctions. Lower is better.
- **Waiting time:** the seconds each vehicle spends nearly stopped. Lower is better.
- **Throughput:** the number of vehicles that finished their trip. Higher is better.
- **Ambulance travel time:** finish time minus scheduled start, for each *signal-relevant*
  ambulance (one whose route crosses at least one signal-controlled movement).

**Analogy.** ATT is the average time from leaving home to reaching the office, including the time
you waited at your own gate before you could even get onto the road.

> **If asked, say:** "Our main measure is average travel time, CityFlow's own definition, which also
> counts the time vehicles wait to enter the network."

## The Camera Detector (YOLOv8n, IDD, mAP)

**What it is.** A **detector** is an AI that finds objects in an image and draws a box around each,
with a class label (car, bus...). **YOLOv8n** ("You Only Look Once", version 8, nano size) is a
small, fast detector. We trained it on the **India Driving Dataset (IDD)**, photos of Indian roads
that include auto-rickshaws, which Western datasets lack. We kept seven classes: car, motorcycle,
autorickshaw, bus, truck, bicycle and person.

Fair testing: we split the data **by drive** (whole recordings), so near-identical neighbouring
frames cannot appear in both training and testing. The **test split** is IDD's official validation
set (its official test labels are not public). We chose the confidence threshold
(0.3<!--=d.conf-->) on our validation split, froze it, and then evaluated the test split **once**.
Training took 13.3<!--=d.train_h--> hours on the GTX 1650, at 640<!--=cfg.imgsz--> pixels.

**mAP in plain words.** For each detected box, we check whether it overlaps a true box enough. The
overlap score is called **IoU** (intersection over union: the shared area divided by the combined
area). **mAP50** counts a detection as correct if IoU is at least 0.5, then averages how precise
and complete the detections are across all classes, from 0 (useless) to 1 (perfect).
**mAP50-95** is stricter: it averages over overlap thresholds from 0.5 to 0.95. Our detector:
mAP50 0.563<!--=d.test.map50-->, mAP50-95 0.375<!--=d.test.map5095--> on
10,225<!--=d.test.images--> test images it never saw in training.

Two more words: **precision** = of the boxes it drew, how many were real (high for us); **recall**
= of the real vehicles, how many it found (moderate for us). So our detector **undercounts**, and
most misses are small, distant objects.

**Analogy.** A ticket checker counting passengers: precision is "when he says someone is there,
someone is there"; recall is "how many of the passengers he actually noticed".

> **If asked, say:** "YOLOv8n trained on the India Driving Dataset reaches mAP50 0.563<!--=d.test.map50--> on held-out
> drives. It is precise but misses many small, distant vehicles."

## Camera Errors and How We Injected Them

**What it is.** We measured three kinds of detector mistakes: **misses** (a vehicle not detected),
**false detections** (a box where there is no vehicle) and **confusions** (a car labelled as a
bus). From these we built a **camera error model** (stored in a result file, never typed into the
code). In the camera experiment, the controller's counts are replaced by noisy counts: each vehicle
is detected with a class-dependent probability, may be given a wrong class, and each road gains a
random number of phantom stopped vehicles. The simulator itself stays exact, so the measures are
still true.

Two levels: **junction** (detection rates of medium and large objects, since queued vehicles near a
stop line are close to a pole camera) and **crowded / far** (rates over all objects, dominated by
distant ones). They bracket a range rather than predict one value.

Findings: MaxPressure's ATT rises by 4.8<!--=c.off.mp.junction.pct-->% off-peak and
2.3<!--=c.peak.mp.junction.pct-->% at peak with the junction camera. Webster's plan never reads
counts, so it is unaffected. Missed vehicles alone cost little, because missing vehicles evenly
shrinks every phase's pressure by the same factor, so the ranking stays the same on average. The
phantom vehicles hurt more: about 0.7<!--=c.phantoms_per_road--> per road at each look, all counted
as stopped. Off-peak, false detections alone cost +3.8<!--=c.dec.false.off.pct-->% of the
+4.8<!--=c.dec.all.off.pct-->% (post-hoc decomposition).

**The caveat.** IDD was filmed from a moving car (a dash camera), not from a pole at a junction. So
our camera errors are a measured **proxy** for a junction camera, not a measurement at a real
junction.

**Analogy.** Testing a recipe with a slightly wrong kitchen scale. Losing a little of every
ingredient equally barely changes the dish; a scale that sometimes adds weight that is not there
spoils it more.

> **If asked, say:** "We injected our detector's measured misses, false detections and confusions
> into the counts. Count-based controllers lost a few percent, mainly through false detections.
> These are dash-camera errors, so they are a proxy."

## Ambulance Handling and Preemption

**What it is.** In the emergency scenario we add ambulances to peak traffic at
6<!--=scn.emergency.veh_per_hour--> per hour over the network. An ambulance on an incoming lane
within 150<!--=cfg.amb.range--> m of the stop line is detected. For the LLM, its prompt lists each
ambulance with its movement, its distance and the phases that serve it, plus one instruction:
ambulances, if listed, must get through quickly. A phase serving the ambulance is always offered,
and it is exempt from the guard.

**Preemption** is the classical alternative: a hand-written rule that gives green to the
highest-pressure phase that serves the detected ambulance. Ambulance positions are assumed to come
from a separate channel (**GPS** or **V2X**, vehicle-to-everything radio), never from the camera,
and they are never noised.

In CityFlow nobody pulls over and the ambulance cannot overtake, so only the signal can help it.
Over seeds 0–4 there are 37<!--=e.mp.amb_all_n--> ambulances, of which 29<!--=e.mp.amb_n--> are
signal-relevant.

Result: 130.1<!--=e.mp.amb--> s under MaxPressure, 88.9<!--=e.llm.amb--> s under the pre-registered
LLM, 81.2<!--=e.pre.amb--> s under preemption. The gain comes almost entirely from less time stopped
at red: 62.3<!--=e.mp.amb_stop--> s under MaxPressure against 21.2<!--=e.llm.amb_stop--> s under the
LLM. Normal traffic does not pay: network ATT 116.4<!--=e.llm.att--> s against MaxPressure's
115.7<!--=e.mp.att--> s, well inside the seed-to-seed spread (±2.3<!--=e.mp.att_sd--> s).

**What it really means.** This is the one case where the agent has information MaxPressure lacks.
A one-sentence instruction was enough. But a hand-written rule did slightly better, so for one
well-defined rule a rule is simpler, faster and easier to verify. The case for an LLM is
*flexibility*: the same mechanism could carry other rules described in words (a road closure, a
school zone), but **we tested only the ambulance case**.

**Analogy.** Telling a traffic officer "an ambulance is coming from the east" works well. A siren
switch that always turns that road green works slightly better, but it can only do that one thing.

> **If asked, say:** "Told about ambulances, the LLM cut their travel time by about a third, close
> to a preemption rule, without slowing other traffic. The rule is still a bit better; the LLM's
> advantage is flexibility, which we did not test beyond ambulances."
