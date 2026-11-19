# Who Explains What

A suggested split, based on each member's role in the report's team table. Anyone may answer any
question, so everyone must also know the basics of the other parts (end of this part).

## The Split of the Slides and the Demo

| Slides | Topic | Speaker |
|:--|:----------------------------------|:--|
| 1–3 | Title, outline, project overview | Akul |
| 4 | Problem statement (mixed traffic, cameras as the sensor) | Bhargav |
| 5–6 | Objectives, related work | Abhishek |
| 7–8 | Improvements, system architecture | Akul |
| 9 | Key components and modules (ending with the dashboard) | Amit |
| 10 | Algorithms and tools | Bhargav |
| 11–12 | Data, scenarios and parameters | Abhishek |
| 13 | Main results (baselines and LLM controllers) | Akul |
| 14 | Ambulances (first table): Akul; camera errors (second table): Bhargav | Akul, Bhargav |
| 15 | Detector results: Bhargav; dashboard screenshots: Amit | Bhargav, Amit |
| 16 | Findings, limitations, future directions | Abhishek |
| 17 | Bibliography | Abhishek |
| 18 | Thank you, GitHub link, hand over to the demo | Amit |
| Demo | Amit drives; Akul explains a replay decision card; Bhargav runs Live Detection | Amit, Akul, Bhargav |

Hand-overs: end your part with one sentence that names the next speaker's topic, for example "Akul
will now show how the system is built."

## Bhargav: Perception and the Detector

**Must know deeply.**

- Why cameras: weak lane discipline makes loop detectors poor.
- YOLOv8n, trained from COCO weights at 640<!--=cfg.imgsz--> pixels, batch
  8<!--=cfg.det.batch-->, mixed precision off (GTX 16-series cards give invalid losses with it),
  up to 50<!--=cfg.det.epochs--> epochs; 13.3<!--=d.train_h--> hours; best epoch
  49<!--=d.best_epoch-->.
- IDD: seven classes; `rider` boxes dropped so a two-wheeler is not counted twice; split by drive;
  test split = official validation set; validation = 10<!--=cfg.det.val_pct-->% of the training
  drives.
- Threshold 0.3<!--=d.conf--> chosen on validation (best mean F1, 0.620<!--=d.f1-->), frozen, then
  one test evaluation: mAP50 0.563<!--=d.test.map50-->, mAP50-95 0.375<!--=d.test.map5095-->.
- Precision high, recall moderate, misses mostly small distant objects.
- The camera error model: per-class detection probability, confusion probabilities, phantom
  vehicles per road; junction and crowded / far levels; the dash-camera proxy caveat.
- Camera results: +4.8<!--=c.off.mp.junction.pct-->% / +2.3<!--=c.peak.mp.junction.pct-->% for
  MaxPressure (junction); Webster unaffected; false detections matter most (post-hoc decomposition).

## Akul: Architecture, the LLM Controller and Ambulances

**Must know deeply.**

- The architecture diagram (slide 8), every box and arrow.
- The decision loop: observe, reason, act, enforce, log; every 5<!--=cfg.mp.interval--> s once the
  minimum green of 15<!--=cfg.mp.min_green--> s has been served; maximum green
  60<!--=cfg.signal.max_green--> s.
- The six LLM designs (arms); the final round's three; why the guard was added (small models
  preferred low pressure); prompt v3 as a post-hoc fix.
- The guard rule (within 20<!--=cfg.guard.margin-->% of the top pressure), and how often it acts.
- Cooperation: what the prompt says about each neighbour.
- Ollama, JSON answer, temperature 0, fixed seed, timeout 60<!--=cfg.llm.timeout_s--> s.
- Ambulances: 150<!--=cfg.amb.range--> m range, the prompt sentence, the guard exemption, the
  preemption rule, GPS / V2X assumption; 130.1<!--=e.mp.amb--> s → 88.9<!--=e.llm.amb--> s, against
  81.2<!--=e.pre.amb--> s for preemption.
- Why the LLM matches but does not beat MaxPressure (three reasons, question 22).

## Amit: The Dashboard

**Must know deeply.**

- The four pages and every control (Part 6), the default choices on each page and why they are
  defaults (fixed rules, not chosen by result).
- "Reads files only", the source chip, the test that every number shown is in a file.
- The replay is verified: it re-drives the simulator with logged decisions and must reproduce the
  run's results exactly; no LLM is called.
- The fallbacks if something fails (end of Part 6), and how to start the dashboard by hand.
- Badges and their meaning: pre-registered, exploratory, no significance test, post-hoc, hosted,
  dashcam proxy.

## Abhishek: Data, Integration, Tests and Reproducibility

**Must know deeply.**

- Data: CoLLMLight's road networks and flows (Jinan 3x4), the Indian 2x2 network and how demand was
  calibrated (5500<!--=cal.r_star--> veh/h, peak 4750<!--=cal.peak-->, off-peak
  2375<!--=cal.offpeak-->); IDD converted to YOLO format with drive-level splits.
- Validation against the CoLLMLight code, and the fixed-time bug.
- Configuration: every setting is read from `configs/*.yaml`; nothing is typed into code.
- Provenance: every run records its controller, model, seed, scenario, run length, git commit and
  LLM statistics.
- Tests (pytest) and checks (`make_report.py --check`); fresh-clone reproduction:
  42<!--=r.det_runs_identical--> of 42<!--=r.det_runs--> deterministic runs identical.
- Seeds, paired comparison, no significance test; pre-registered versus exploratory; all
  limitations (Part 8).

## The Basics Everyone Must Know

Learn these even if they are not your part:

1. Simulation only; CityFlow; validated against CoLLMLight's code.
2. Indian 2x2 network with the Indian vehicle mix; off-peak and peak; Jinan 3x4.
3. MaxPressure: green to the highest pressure; tuned first; the main baseline.
4. The LLM agent: `llama3.2:3b`, local through Ollama on a 4 GB GPU; MaxPressure proposes, the LLM
   decides, the guard checks.
5. Main result: matches MaxPressure (+0.5<!--=f.peak.llm.vs_mp-->% to
   +0.9<!--=f.off.llm.vs_mp-->%), does not beat it.
6. Ambulances: 130.1<!--=e.mp.amb--> s → 88.9<!--=e.llm.amb--> s; preemption
   81.2<!--=e.pre.amb--> s.
7. Detector: YOLOv8n on IDD, mAP50 0.563<!--=d.test.map50-->; camera errors cost a few percent;
   dash-camera proxy.
8. Pre-registered versus exploratory (gemma4 arm, model-size study).
9. Three seeds, no significance test.
10. The dashboard reads only result files; every number has a source.
11. The AI coding assistant was used under the team's direction (question 39).
12. The GitHub link: <https://github.com/Pilli9375/trafficsense>.
