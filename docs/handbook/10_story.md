# The Project in 60 Seconds

## The 60-Second Version

TrafficSense controls traffic signals with a small AI language model running on a laptop. There is
one AI "agent" at each junction. It reads how many vehicles are waiting at its own junction and at
its neighbours', and chooses which direction gets green next. We tested it in a traffic simulator
on a small Indian-style road network of four junctions, with an Indian mix of two-wheelers, autos,
cars, buses and trucks.

We compared it fairly with the best classical method, MaxPressure, using a plan we fixed in
advance. Result: the AI matches MaxPressure but does not beat it. Its clear benefit is for
ambulances: told where an ambulance is, it cut the ambulance's travel time by about a third. We
also trained a camera detector on Indian street images and showed that its errors make every
count-based controller a few percent slower. Everything is a simulation; no real signal was
controlled.

## The 3-Minute Version (to Say Out Loud)

Read this aloud two or three times tonight. It follows the deck.

"Good morning. Our project is TrafficSense, an AI-based smart traffic management system.

At every junction, a traffic signal keeps deciding which direction gets green next. Indian
junctions are hard: the traffic is a mix of two-wheelers, auto-rickshaws, cars, buses and trucks,
lane discipline is weak, and many signals still run fixed timings. Ambulances get no priority.

Recent research, especially a paper called CoLLMLight from ICLR 2026, put a large language
model, an LLM, at each junction as a decision-maker. We asked a practical question: can a *small*
LLM, running on an ordinary laptop graphics card with only 4 GB of memory, control signals as
well as the best classical method? And how does it cope when the vehicle counts come from a real
camera detector, with its mistakes?

We built the system in the CityFlow traffic simulator. First we checked that our simulator setup
gives the same numbers as the CoLLMLight authors' own code. We built an Indian-style network of
four junctions and tuned the classical baselines before any AI run. Then we fixed our full
experiment plan in advance: this is called pre-registration.

The AI agent sees MaxPressure's ranking of the options, chooses a phase and gives a short reason.
A safety check, which we call the guard, accepts the AI's choice only if it is close to the best
option.

The results. The pre-registered AI controller is within 0.5<!--=f.peak.llm.vs_mp-->% to
0.9<!--=f.off.llm.vs_mp-->% of MaxPressure's average travel time. It matches MaxPressure; it does
not beat it. Its clear benefit is for ambulances: when ambulances are listed in its prompt, their
mean travel time falls from 130.1<!--=e.mp.amb--> seconds to 88.9<!--=e.llm.amb--> seconds, close
to a hand-written priority rule, with no measurable cost to other traffic.

We also trained a YOLOv8n vehicle detector on the India Driving Dataset. It reaches an mAP50 of
0.563<!--=d.test.map50--> on images it never saw in training. When we put its measured errors into
the counts, MaxPressure became 2.3<!--=c.peak.mp.junction.pct-->% to
4.8<!--=c.off.mp.junction.pct-->% slower, mostly because of false detections; a fixed-time plan was
not affected.

This is a simulation study, with three random seeds and dash-camera images as a stand-in for a
junction camera. Our conclusion: a small local LLM is best used as a safe layer on top of
MaxPressure that adds information MaxPressure cannot use, such as ambulances, not as its
replacement. The dashboard shows all of this from the result files, and the code is on GitHub."

# The Story in Plain Words

## What Does a Traffic Signal Decide?

Think of a junction as a door that several queues want to pass through, but only some can go at a
time. A **phase** is one set of movements that get green together, for example "east and west go
straight". The signal keeps answering one question: *which phase should be green next, and for
how long?*

Every change costs time. Between two greens there is a short yellow and all-red period, so that
the junction can clear. We call it the **transition**. Change too often and you lose time to
transitions; change too slowly and queues grow on the red roads. Over a city, these small
decisions add up to the delay that millions of people feel every day.

## Why Indian Roads Are Hard

- **Mixed traffic.** In the traffic data we used, two-wheelers are
  45.1<!--=docs/report/20_ch2_system.md | tab_mix | motorcycle | Share-->% of vehicles and
  auto-rickshaws 17.6<!--=docs/report/20_ch2_system.md | tab_mix | auto_rickshaw | Share-->%. They
  differ a lot in size and speed.
- **Weak lane discipline.** Vehicles do not stay in lanes, so road sensors buried under one lane
  (loop detectors) work poorly. Cameras are the natural sensor.
- **Fixed plans.** Many junctions still repeat the same timing all day, whatever the traffic.
- **Ambulances get no priority.** They wait at red lights like everyone else.

## What We Built

1. **A simulated city.** We used CityFlow, a traffic simulator used by most research in this area.
   We first checked that our setup reproduces the CoLLMLight authors' own baseline numbers.
2. **An Indian test network.** Four junctions in a 2x2 grid, with the Indian vehicle mix, and a
   documented source for every setting.
3. **Strong classical baselines.** A fixed-time plan, a fixed-time plan computed by Webster's
   method, and MaxPressure. We tuned them *before* any AI run, so the comparison is fair.
4. **The AI controller.** One small LLM agent at each junction, running locally through a program
   called Ollama on a 4 GB laptop graphics card. It reads its own and its neighbours' queues and
   picks the next phase. A **guard** keeps its choice close to MaxPressure's best option.
5. **A camera detector.** A YOLOv8n model trained on Indian street images. We measured its
   mistakes and fed them into the controllers' counts to see how much they hurt.
6. **A dashboard.** A web page (built with Streamlit) that shows every result, read only from the
   result files.

## What We Found

- **Normal traffic:** the pre-registered AI controller is as good as MaxPressure, but not better
  (+0.9<!--=f.off.llm.vs_mp-->% off-peak, +0.5<!--=f.peak.llm.vs_mp-->% at peak,
  +0.8<!--=f.jinan.llm.vs_mp-->% on the Jinan network). A "+" means slightly slower.
- **Why so close:** the small model's own answer often disagrees with MaxPressure, but the guard
  replaces most of those answers. So in practice it mostly does what MaxPressure would do.
- **Ambulances:** its clear benefit. Ambulance travel time fell from 130.1<!--=e.mp.amb--> s to
  88.9<!--=e.llm.amb--> s, a cut of 31.7<!--=e.llm.amb_cut_vs_mp-->%. Rule-based preemption:
  81.2<!--=e.pre.amb--> s.
- **Camera errors:** count-based controllers get a few percent slower; a fixed-time plan does not
  read counts, so it is unaffected. False detections (vehicles that are not there) hurt more than
  missed vehicles.
- **Exploratory leads:** a bigger local model, `gemma4:e4b`, was faster than MaxPressure at peak
  (−1.5<!--=f.peak.gem.vs_mp-->%) but slower off-peak (+2.7<!--=f.off.gem.vs_mp-->%), and too slow
  on our laptop for real-time control. It was added after the plan was fixed, so it is a lead, not
  a result.

> **The one-sentence conclusion (from the report):** a small local LLM does not yet beat a
> well-tuned classical controller on routine traffic, but as a guarded layer on top of one it is
> safe, and it adds value where the situation is described in words rather than in queue counts.
