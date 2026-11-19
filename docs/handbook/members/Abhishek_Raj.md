```{=latex}
\begin{center}
{\LARGE\bfseries\color{headblue} My Part: Speaking Guide\par}
\vspace{4pt}
{\large Mylapalli Abhishek Raj (23BCE9470)\par}
{\normalsize Data engineering and integration lead\par}
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

**What I did.** I made sure the project had the right data, that its parts work together, and that
anyone can check and repeat the results. From the report's team table:

- Dataset acquisition: CoLLMLight's road networks and traffic flows (fetched by the script
  `fetch_collmlight_data.sh`), and the India Driving Dataset (IDD), converted to the YOLO format with
  splits by whole drive (`scripts/prepare_idd.py`).
- Integration and configuration across the modules (`configs/`, `experiment.py`): every setting is
  read from configuration files, nothing is typed into the code.
- The pytest test suite, the README, git and GitHub, the environment and the requirements
  (`requirements-lock.txt`).

**Why it was needed.** Our results will be examined, so every number must be reproducible and honest.
Good data, one place for every setting, automatic tests and a clean repository make that possible.

**How it connects to the others.**

> Datasets and configuration (**my part**) → Akul's simulator and controllers, Bhargav's detector →
> result files in `outputs/`, each recording where it came from → checks and tests (**my part**) →
> Amit's dashboard and the report.

# What to Say

**30-second version.** "I was the data and integration lead. I brought in the datasets: CoLLMLight's
road networks and flows, and the India Driving Dataset, converted to YOLO format with splits by
drive. I kept every setting in configuration files, maintained the tests, the README and GitHub,
and the environment. Every result records where it came from, and a fresh copy of the repository
reproduced all 42<!--=r.det_runs_identical--> deterministic runs exactly."

**2-minute version.** "My part takes raw data and settings and gives the team a pipeline it can
trust. First the data. CoLLMLight's road networks and flows give the Jinan 3x4 network with a
real-world flow, and they let us validate our simulator setup against the authors' own code:
throughput, queue and waiting time were identical on all three of their datasets. For the detector,
I converted the India Driving Dataset to the YOLO format and split it by whole drives, with
10<!--=cfg.det.val_pct-->% of the training drives kept for validation. Splitting by drive stops
near-identical frames from leaking into the test.

Then integration. Every setting, such as the run length of 3600<!--=cfg.steps--> seconds or the
demand of 2375<!--=cal.offpeak--> and 4750<!--=cal.peak--> vehicles per hour, is read from the
configuration files. Every run writes a summary that records its controller, model, seed, scenario,
run length and git commit.

Finally, checking. The pytest suite tests the parts, and `make_report.py --check` fails if any number
in the report differs from the result files. We cloned the repository into an empty folder and set
it up from the README alone: all 42<!--=r.det_runs_identical--> of 42<!--=r.det_runs--> deterministic
runs came out identical, and a short LLM run repeated all 121<!--=r.llm_identical_answers--> answers."

# My Slides and Dashboard Pages

| Slide or page | What to point at |
|:--|:----------------------------------------|
| Slide 5: objectives and expected impact | "Results that can be reproduced: every number is checked against the result files" |
| Slide 6: related work | One line per row of the table; end with the three open questions |
| Slide 11: datasets, input and output | The scenario table: off-peak 2375<!--=cal.offpeak-->, peak 4750<!--=cal.peak-->, Jinan 3x4 |
| Slide 12: parameters | Run length, decision interval, minimum and maximum green |
| Slide 16: findings, limitations, future | Read the limitations calmly and fully |
| Slide 17: bibliography | CoLLMLight [8] is the base paper |
| Dashboard (not in my demo slot) | If asked: the sidebar's "Reads files only" and code commit; Results, Signal control, the per-seed chart |

# My Key Numbers

| Number | Plain meaning |
|:--|:--------------------------------------------|
| 3600<!--=cfg.steps--> s | Length of every run: one simulated hour |
| 2375<!--=cal.offpeak--> / 4750<!--=cal.peak--> veh/h | Off-peak and peak demand, set by a rule fixed in advance |
| 5500<!--=cal.r_star--> veh/h | The lowest demand at which the network no longer drains |
| 67<!--=f.runs--> and 130<!--=c.runs--> runs | Full experiments and camera-error experiment |
| 27<!--=f.reproduced--> of 27<!--=f.reproduced_of--> | Repeated baseline runs identical in every metric |
| 42<!--=r.det_runs_identical--> of 42<!--=r.det_runs--> | Deterministic runs identical from a fresh clone |
| 121<!--=r.llm_identical_answers--> answers | A short LLM run repeated exactly from a fresh clone |
| 10,225<!--=d.test.images--> images | The detector's test split (IDD's official validation set) |

# Likely Questions About My Part

1. **How do you know the simulator setup is right?** We validated it against the CoLLMLight
   authors' own code: identical throughput, queue and waiting time on all three datasets.
2. **Why split IDD by drive?** Neighbouring frames of one drive look almost the same; splitting by
   drive keeps them out of the test.
3. **Why is the test split IDD's validation set?** IDD's official test labels are not public.
4. **How can someone reproduce the results?** Clone the GitHub repository and follow the README:
   install the package with its locked requirements, run `pytest -q`, run the experiment scripts,
   and check every number with `python scripts/make_report.py --check`.
5. **Are the LLM runs repeatable?** Not bit-for-bit on a GPU, so every decision is logged and every
   run can be replayed exactly from its log.
6. **Why three seeds?** Each seed is a different traffic file; LLM runs are slow on our GPU. Three
   are few, so small differences are called "within seed noise".
7. **What does a result file record?** Controller, model, seed, scenario, run length, git commit and
   time, and for LLM runs the calls, failures and latency.
8. **What is not in the repository?** The IDD dataset, the detector weights and the hosted model's
   API key.
9. **How was demand chosen?** By a pre-registered rule: peak is the largest draining demand at or below
   0.9<!--=cal.rule.peak_fraction--> of 5500<!--=cal.r_star-->, and off-peak is half of peak.

**Three questions about the other parts I should still answer.**

- *Does the LLM beat MaxPressure?* No. It matches it, within 0.5<!--=f.peak.llm.vs_mp-->% to
  0.9<!--=f.off.llm.vs_mp-->%.
- *Ambulances?* 130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s; preemption
  81.2<!--=e.pre.amb--> s.
- *Detector?* mAP50 0.563<!--=d.test.map50--> on held-out drives; a dash-camera proxy.

# Do Not Claim

- **Simulation only;** the Indian demand is generated and calibrated, not counted on a real road.
- **Three seeds, no significance test.**
- **Exploratory parts** (the gemma4 arm, the model-size study) are leads, not results.
- **Not my role:** the controllers, the detector training, the dashboard code. Point to Akul,
  Bhargav or Amit.
- **The AI coding assistant.** Say the report's words: "The project was developed with the help of
  an AI coding assistant (Claude Code), working under the team's direction: the team decided what
  to build and how to evaluate it, reviewed the code and the text, ran the experiments and checked
  the results, and is responsible for all of the work presented in this report."
- If you do not know: **"We did not test that."**

# Five Terms I Must Explain Simply

- **Seed:** a number that fixes the random choices of a run; each seed is a different traffic file.
- **Configuration file:** a text file that holds every setting, so nothing is typed into the code.
- **Provenance:** the record of where a result came from (model, seed, commit and so on).
- **Fresh clone:** a new copy of the repository, set up from the README alone, to test that the
  results can be repeated.
- **pytest:** the tool that runs our automatic tests.
