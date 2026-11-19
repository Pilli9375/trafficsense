```{=latex}
\begin{center}
{\LARGE\bfseries\color{headblue} My Part: Speaking Guide\par}
\vspace{4pt}
{\large Achalla Akul Lakhan (23BCE8015)\par}
{\normalsize System architect and multi-agent lead\par}
\end{center}
\vspace{4pt}
```

# The Project in 30 Seconds

TrafficSense controls traffic signals with a small AI language model running on a laptop. There is
one AI "agent" at each junction. It reads how many vehicles are waiting at its own junction and at
its neighbours', and chooses which direction gets green next. We tested it in a traffic simulator
on a small Indian-style road network of four junctions, with an Indian mix of two-wheelers, autos,
cars, buses and trucks. Result: the AI matches MaxPressure but does not beat it. Its clear benefit
is for ambulances: told where an ambulance is, it cut the ambulance's travel time by about a third.
Everything is a simulation; no real signal was controlled.

# My Part in Plain Words

**What I did.** I designed how the whole system fits together and built its "brain". From the
report's team table:

- The overall architecture: simulator, observation layer, controllers and result files (the
  diagram on slide 8).
- The cooperative LLM controller and its **guard**, the prompts and the structured (JSON) answer
  (`control/`, `llm/`).
- CityFlow integration, the Indian 2x2 network and its traffic flows, and ambulance priority
  (`sim/`, `control/preemption.py`).

**Why it was needed.** A traffic signal keeps deciding which direction gets green next. We wanted to
know if a small local AI agent can make that decision as well as the best classical rule,
MaxPressure, and whether it can use extra information, such as an approaching ambulance.

**How it connects to the others.**

> Simulator counts (exact, or with Bhargav's camera errors) → **my agents: MaxPressure proposes, the
> LLM decides, the guard checks** → the signal changes in CityFlow → result files (Abhishek's
> configuration and checks) → the dashboard (Amit).

# What to Say

**30-second version.** "I was the system architect. I put one small LLM agent at each junction,
running locally through Ollama on a 4 GB laptop GPU. MaxPressure proposes its best phases, the LLM
decides, and a guard accepts the choice only if it is within 20<!--=cfg.guard.margin-->% of the top
pressure. The result: it matches MaxPressure, within 0.5<!--=f.peak.llm.vs_mp-->% to
0.9<!--=f.off.llm.vs_mp-->%, but does not beat it. Told about ambulances, it cut their travel time
from 130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s."

**2-minute version.** "My part takes the vehicle counts at each junction and gives the next signal
phase. Every 5<!--=cfg.mp.interval--> seconds, once the minimum green of
15<!--=cfg.mp.min_green--> seconds has been served, each agent gets a short text: for each phase,
its pressure and queue, and its neighbours' state. That is the cooperation idea from CoLLMLight.
The model, `llama3.2:3b`, answers in JSON with a phase and a reason of at most
15<!--=code.reason_words.guided_v3--> words. Our code checks the answer, inserts the yellow
transition and keeps the green within its limits. Everything is logged.

In the benchmark we found that small models misread pressure: they often chose the phase that
needs green least. So I added the guard. The model's own answer differs from MaxPressure in
87<!--=l.amb.llm.differs-->–93<!--=l.peak.llm.differs-->% of calls, but the guard replaces most of
them, so the applied phase differs in only 10<!--=l.peak.llm.applied-->–11<!--=l.jinan.llm.applied-->%.
That is why the result is so close to MaxPressure. In the report's words, the guard made the LLM
safe, not useful.

Ambulances are where the agent helps. An ambulance within 150<!--=cfg.amb.range--> m of the stop
line is listed in the prompt. Mean ambulance travel time fell from 130.1<!--=e.mp.amb--> s to
88.9<!--=e.llm.amb--> s, mostly by removing time stopped at red. A hand-written preemption rule
was still slightly better, at 81.2<!--=e.pre.amb--> s. Other traffic did not pay for it."

# My Slides and Dashboard Pages

| Slide or page | What to point at |
|:--|:----------------------------------------|
| Slides 1–3: title, outline, overview | "One local LLM agent at every junction"; "a simulation study" |
| Slide 7: improvements | Tuned baselines first; the guard; ambulances in the prompt |
| Slide 8: architecture | Follow the arrows: counts, MaxPressure ranking, LLM agent, guard, timing rules |
| Slide 13: main results | MaxPressure row, then "LLM pre-registered" row: +0.9<!--=f.off.llm.vs_mp-->% / +0.5<!--=f.peak.llm.vs_mp-->% / +0.8<!--=f.jinan.llm.vs_mp-->% |
| Slide 14: first table (ambulances) | 130.1<!--=e.mp.amb--> s → 88.9<!--=e.llm.amb--> s; preemption 81.2<!--=e.pre.amb--> s |
| Dashboard: Network Replay (in the demo) | Play the ambulance; read one LLM decision card's reason aloud; point at a guard override |
| Dashboard: Overview and Results, Ambulances tab | The headline and where each controller's ambulance time goes |

# My Key Numbers

| Number | Plain meaning |
|:--|:--------------------------------------------|
| +0.5<!--=f.peak.llm.vs_mp-->% to +0.9<!--=f.off.llm.vs_mp-->% | The LLM is slightly slower than MaxPressure: it matches, not beats |
| 87<!--=l.amb.llm.differs-->–93<!--=l.peak.llm.differs-->% / 10<!--=l.peak.llm.applied-->–11<!--=l.jinan.llm.applied-->% | Model disagrees with MaxPressure / applied phase disagrees after the guard |
| 1.02<!--=l.peak.llm.lat-->–1.10<!--=l.jinan.llm.lat--> s per call | Fast enough for real time with a 5 s decision interval |
| 130.1<!--=e.mp.amb--> → 88.9<!--=e.llm.amb--> s (31.7<!--=e.llm.amb_cut_vs_mp-->% less) | Ambulance travel time, MaxPressure against the LLM |
| 62.3<!--=e.mp.amb_stop--> → 21.2<!--=e.llm.amb_stop--> s | Ambulance time stopped at red |
| 116.4<!--=e.llm.att--> vs 115.7<!--=e.mp.att--> s | Other traffic: no measurable cost |
| 29<!--=e.mp.amb_n--> of 37<!--=e.mp.amb_all_n--> | Ambulances whose route crosses a signal (seeds 0–4) |
| 2375<!--=cal.offpeak--> / 4750<!--=cal.peak--> veh/h | Off-peak and peak demand on the Indian network |

# Likely Questions About My Part

1. **Why an LLM at all?** It can be told things in words (an ambulance, its neighbours) and it gives
   a reason. MaxPressure cannot use that extra context.
2. **What does the guard do?** It applies the LLM's phase only if it is within
   20<!--=cfg.guard.margin-->% of the top pressure; otherwise MaxPressure's choice is applied.
3. **Is the guard not cheating?** It is part of the pre-registered design, and we report how often it
   acts. We say openly that it made the LLM safe, not better.
4. **Why `llama3.2:3b`?** It won the pre-registered benchmark rule: few failures, fast enough, lowest
   queue.
5. **What is cooperation here?** Each prompt includes the neighbours' phases and queues, as in
   CoLLMLight.
6. **Why is the LLM worse than preemption for ambulances?** Preemption always gives the ambulance
   green; the LLM only usually does. Its advantage is flexibility, and we tested only ambulances.
7. **What if the model gives a bad answer?** It is checked; a failure is counted and MaxPressure's
   choice is applied and reported. The main arm never failed a call off-peak or at peak.
8. **Why is India's left-hand traffic correct in a right-hand simulator?** A square grid is
   mirror-symmetric, so CityFlow's free right turn plays India's free left turn.
9. **Is gemma4 better?** It was faster at peak but slower off-peak, and too slow on our GPU. It is
   exploratory, a lead, not a result.
10. **Why does the LLM not beat MaxPressure?** An LLM that reads pressure correctly becomes
    MaxPressure; small models misread it; and the guard turns them back into MaxPressure.

**Three questions about the other parts I should still answer.**

- *Detector score?* mAP50 0.563<!--=d.test.map50--> on held-out IDD drives.
- *What do camera errors do?* MaxPressure becomes 2.3<!--=c.peak.mp.junction.pct-->% to
  4.8<!--=c.off.mp.junction.pct-->% slower (junction level); a fixed plan is unaffected.
- *Can someone reproduce it?* Yes: the README and `make_report.py --check`; a fresh clone repeated
  42<!--=r.det_runs_identical--> of 42<!--=r.det_runs--> deterministic runs exactly.

# Do Not Claim

- **Never say the LLM beats MaxPressure.** It matches it.
- **Simulation only.** No real signal was controlled.
- **No fine-tuning.** The models were used as released, unlike CoLLMLight.
- **Exploratory, not proven:** the gemma4 arm and the model-size study (including the hosted model);
  prompt v3 was a post-hoc fix.
- **Only the ambulance case was tested** as "extra context". Road closures or school zones are ideas.
- **Not my role:** the detector and the dashboard code. Point to Bhargav or Amit.
- **The AI coding assistant.** Say the report's words: "The project was developed with the help of
  an AI coding assistant (Claude Code), working under the team's direction: the team decided what
  to build and how to evaluate it, reviewed the code and the text, ran the experiments and checked
  the results, and is responsible for all of the work presented in this report."
- If you do not know: **"We did not test that."**

# Five Terms I Must Explain Simply

- **Phase:** a set of movements that get green together.
- **Pressure:** vehicles waiting for a phase minus vehicles already queued on the roads they enter.
- **MaxPressure:** give green to the phase with the highest pressure.
- **Guard:** the safety check that keeps the LLM's choice close to MaxPressure's best.
- **Preemption:** a fixed rule that gives green to the phase serving an ambulance.
