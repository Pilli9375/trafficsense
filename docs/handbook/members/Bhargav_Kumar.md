```{=latex}
\begin{center}
{\LARGE\bfseries\color{headblue} My Part: Speaking Guide\par}
\vspace{4pt}
{\large C Bhargav Kumar (23BCE8195)\par}
{\normalsize Computer vision and machine learning lead\par}
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

**What I did.** I worked on the "eyes" of the system: a camera **detector**, an AI that finds
vehicles in a picture and draws a box around each one. From the report's team table:

- I chose the detector, **YOLOv8n** (a small, fast detector), and set up its training on our
  4 GB laptop graphics card (`scripts/train_detector.py`).
- I mapped the labels of the **India Driving Dataset (IDD)** to our seven classes: car,
  motorcycle, autorickshaw, bus, truck, bicycle, person (`perception/idd.py`). IDD's `rider` boxes
  are dropped, so a two-wheeler is not counted twice.
- I built the pipeline that runs the detector on images and video (`perception/detector.py`).
- I ran the detector evaluation (`scripts/eval_detector.py`). Its measured mistakes became the
  **camera error model** (`outputs/perception/error_model.json`).

**Why it was needed.** On Indian roads, lane discipline is weak, so sensors cut into the road work
poorly; cameras are the natural sensor. But a camera makes mistakes. My part measures those
mistakes, so the team could test how much they hurt each signal controller.

**How it connects to the others.**

> IDD images (Abhishek prepared the data) → **my detector, trained and evaluated** → measured
> misses, false detections and confusions → the camera error model → the controllers' vehicle
> counts in the simulator (Akul's system) → results shown on the dashboard (Amit).

The detector does not control signals directly. Its error *rates* are applied to the simulator's
counts.

# What to Say

**30-second version.** "I was the computer vision lead. I trained a YOLOv8n detector on the India
Driving Dataset. On images it never saw in training, it reaches mAP50 of
0.563<!--=d.test.map50-->. It is precise but misses many small, distant vehicles. I measured its
mistakes and turned them into a camera error model. When the team fed those errors into the
controllers' counts, MaxPressure became 2.3<!--=c.peak.mp.junction.pct-->% to
4.8<!--=c.off.mp.junction.pct-->% slower, mostly because of false detections."

**2-minute version.** "My part takes camera images and gives the simulator realistic counting
errors. First I mapped the India Driving Dataset's labels to seven classes, dropping the `rider`
boxes so a two-wheeler is not counted twice. The data was split by whole drives, so that
near-identical frames cannot be in both training and testing. I trained YOLOv8n at
640<!--=cfg.imgsz--> pixels with batch 8<!--=cfg.det.batch--> on our GTX 1650. Mixed precision was
switched off, because GTX 16-series cards give invalid losses with it. Training took
13.3<!--=d.train_h--> hours and the best epoch was 49<!--=d.best_epoch-->.

I chose the confidence threshold, 0.3<!--=d.conf-->, on the validation split, froze it, and only
then evaluated the test split, once. The result is mAP50 0.563<!--=d.test.map50--> and mAP50-95
0.375<!--=d.test.map5095--> on 10,225<!--=d.test.images--> test images. Precision is high and
recall is moderate, so the detector undercounts. Most misses are small, distant objects.

Then I turned the measured misses, false detections and class confusions into an error model with
two levels: junction and crowded or far. With the junction level, MaxPressure was
4.8<!--=c.off.mp.junction.pct-->% slower off-peak and 2.3<!--=c.peak.mp.junction.pct-->% at peak.
Missed vehicles alone cost little; phantom vehicles cost more. One honest caveat: IDD was filmed
from a moving car, so these errors are a proxy for a junction camera, not a measurement at one."

# My Slides and Dashboard Pages

| Slide or page | What to point at |
|:--|:----------------------------------------|
| Slide 4: Problem Statement & Motivations | The line "weak lane discipline: cameras are the natural sensor" |
| Slide 10: Algorithms and tools | The rows "YOLOv8n vehicle detection" and "Camera error model", and "Ultralytics YOLOv8, India Driving Dataset" |
| Slide 14: second table (camera errors) | The MaxPressure row, then the Webster row: +0.0<!--=c.off.web.junction.pct-->% because it never reads counts |
| Slide 15: detector results | mAP50 0.563<!--=d.test.map50-->; "high precision, moderate recall" |
| Dashboard: Live Detection (I run it in the demo) | Sample clip, then Run detector; the boxes, the counts per class, and the badges "dashcam proxy", "no tracking" |
| Dashboard: Results, Detector and Camera errors tabs | mAP50 per class; miss rate by object size; the change per camera level |

# My Key Numbers

| Number | Plain meaning |
|:--|:--------------------------------------------|
| mAP50 0.563<!--=d.test.map50--> | Detection score on held-out test images, from 0 (useless) to 1 (perfect) |
| mAP50-95 0.375<!--=d.test.map5095--> | The same score with stricter box overlap |
| Validation mAP50 0.602<!--=d.val.map50--> | Slightly higher on the validation split, as expected |
| 10,225<!--=d.test.images--> images, 88,753<!--=d.test.gt--> boxes | The size of the test split, never used in training |
| Threshold 0.3<!--=d.conf--> (mean F1 0.620<!--=d.f1-->) | Chosen on validation and frozen before the test |
| 13.3<!--=d.train_h--> h, best epoch 49<!--=d.best_epoch--> of up to 50<!--=cfg.det.epochs--> | Training time on the GTX 1650; it was still improving slowly |
| Small boxes missed: 59<!--=d.size.motorcycle.small-->–76<!--=d.size.person.small-->% | Most misses are small, distant objects |
| +4.8<!--=c.off.mp.junction.pct-->% / +2.3<!--=c.peak.mp.junction.pct-->% | MaxPressure slower with junction-camera errors (off-peak / peak) |
| +3.8<!--=c.dec.false.off.pct-->% of +4.8<!--=c.dec.all.off.pct-->% | Off-peak, false detections alone explain most of it (post-hoc) |

# Likely Questions About My Part

1. **Why YOLOv8n and not a bigger model?** It is small and fast, and it fits training on our 4 GB
   GPU at 640<!--=cfg.imgsz--> pixels.
2. **What is mAP50 in simple words?** A box counts as correct if it overlaps the true box by at least
   half (IoU 0.5); the score averages how precise and complete the boxes are over all classes.
3. **Is 0.563<!--=d.test.map50--> good?** Reasonable for a small model on crowded scenes, but it
   misses many small, distant objects. What matters here is its count errors, which we measured.
4. **Why is the test split IDD's validation set?** IDD's official test labels are not public.
5. **How did you avoid cheating on the test?** The threshold was frozen on validation first, and the
   test split was evaluated only once. Splits are by drive, not by frame.
6. **Why drop `rider` boxes?** So that a motorcycle and its rider are not counted as two vehicles.
7. **Why do false detections hurt more than misses?** Missing vehicles evenly shrinks every phase's
   pressure, so the ranking hardly changes. A phantom vehicle adds pressure where there is none.
8. **Is this a real junction camera?** No. IDD is dash-camera footage, so our error model is a proxy.
9. **Which classes are hardest?** Bicycle and person (mAP50 0.339<!--=d.test.bicycle.map50--> and
   0.444<!--=d.test.person.map50-->): small and, for bicycles, rare.
10. **Does the detector track vehicles?** No. It counts each frame on its own.

**Three questions about the other parts I should still answer.**

- *Does the LLM beat MaxPressure?* No. It matches it, within 0.5<!--=f.peak.llm.vs_mp-->% to
  0.9<!--=f.off.llm.vs_mp-->%.
- *What is the ambulance result?* 130.1<!--=e.mp.amb--> s under MaxPressure to
  88.9<!--=e.llm.amb--> s with the LLM; a preemption rule gives 81.2<!--=e.pre.amb--> s.
- *Where do the dashboard's numbers come from?* Only from the result files; every number has a
  source chip.

# Do Not Claim

- **Not a real junction.** Everything is a simulation, and the detector was tested on recorded
  dash-camera images. Say: "Our camera errors are a measured proxy."
- **No tracking, no live junction video.** The Live Detection page counts per frame on IDD's
  sampled frames.
- **Ambulances are not detected by the camera.** Their positions are assumed to come from GPS or
  V2X.
- **The camera decomposition is post-hoc** (added after the camera results were read).
- **Not my role:** the LLM controller, the guard and the dashboard code. Point to Akul or Amit.
- **The AI coding assistant.** Say the report's words: "The project was developed with the help of
  an AI coding assistant (Claude Code), working under the team's direction: the team decided what
  to build and how to evaluate it, reviewed the code and the text, ran the experiments and checked
  the results, and is responsible for all of the work presented in this report."
- If you do not know: **"We did not test that."**

# Five Terms I Must Explain Simply

- **Detector:** an AI that finds objects in a picture and draws a labelled box around each.
- **IoU:** how much two boxes overlap: the shared area divided by the combined area.
- **Precision / recall:** of the boxes drawn, how many were real / of the real vehicles, how many
  were found.
- **False detection:** a box where there is no vehicle (a "phantom" vehicle).
- **Proxy:** a stand-in measurement used when the real one is not available.
