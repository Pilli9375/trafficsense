# The Dashboard Walk-Through

The dashboard is a web page that runs on our laptop, built with **Streamlit** (a Python tool for
making data web pages). It has four pages in the left sidebar: **Overview**, **Live Detection**,
**Network Replay** and **Results**.

Three rules make it trustworthy. Say them during the demo:

1. **It only reads files.** It shows the result files in `outputs/`; it holds no numbers of its own
   and does not call the LLM.
2. **Every number has a source chip.** The small **"ⓘ source"** button next to each chart, tile and
   table opens the list of files it read and the git commit that last changed each one.
3. **It is tested.** A test fails if any number shown on a page is not in the files that page read.

The sidebar also shows "Reads files only", the date of the results and the code commit.

## Page 1: Overview

**What it shows.**

- **The headline** (the big "hero" box): the question "Can a small, local LLM run Indian traffic
  signals?" and the answer "Ambulances 32<!--=e.llm.amb_cut_vs_mp-->% faster", with the
  pre-registered LLM controller, for the 29<!--=e.mp.amb_n--> ambulances whose route crosses a
  signal, over five seeds of peak traffic. Four cells: MaxPressure 130.1<!--=e.mp.amb--> s; LLM
  main, pre-registered 88.9<!--=e.llm.amb--> s; gemma4 hybrid (with an "exploratory" badge)
  82.2<!--=e.gem.amb--> s, 37<!--=e.gem.amb_cut_vs_mp-->% faster; rule-based preemption
  81.2<!--=e.pre.amb--> s. Badges: "pre-registered", "no significance test", "ambulances not
  noised".
- **Three tiles:** (1) "Travel time vs MaxPressure": +0.5<!--=f.peak.llm.vs_mp-->% for the
  pre-registered arm at peak, "safe, but no gain", with small bars for both LLM arms at peak and
  off-peak; (2) "Detector mAP50 · IDD test split": 0.563<!--=d.test.map50-->, with mAP50 per class; and
  (3) "Camera-error impact": +4.8<!--=c.off.mp.junction.pct-->% for MaxPressure off-peak with the
  junction camera, and the fixed-time plan shown as "unaffected".
- **The project in three steps:** Problem, Approach, Findings ("camera errors cost
  2.3<!--=c.peak.mp.junction.pct-->–8.2<!--=c.off.mp.crowded.pct-->%" for MaxPressure across both
  camera levels).
- **System architecture:** one decision cycle, every 5<!--=cfg.mp.interval--> s per junction.
- **"Why / How to read"** drawer at the bottom: how to read the numbers, the ambulance assumptions,
  the detector caveat, and a note that the animated grid behind the headline is decoration, not data.

**What to click.** Hover over the hero. Click one **source** chip to show where the number comes
from. Open the **Why / How to read** drawer.

**What to say.** "The headline is our pre-registered result: ambulances
32<!--=e.llm.amb_cut_vs_mp-->% faster than under MaxPressure. The exploratory gemma4 number is
smaller on the page and carries its badge; nothing exploratory is the biggest number on a page. For
normal traffic, the tile says it plainly: safe, but no gain."

**Do not get wrong.** The 32<!--=e.llm.amb_cut_vs_mp-->% on the dashboard and the 31.7<!--=e.llm.amb_cut_vs_mp-->% in the
report are the same number, rounded differently.

## Page 2: Live Detection

**What it shows.** Our trained YOLOv8n detector running frame by frame on a video, on this laptop,
right now. Badges: "dashcam proxy", "no tracking", "measured now". A **Model** card: the weights file
`best.pt`, a check that its fingerprint (sha256) matches the evaluated weights, test mAP50
0.563<!--=d.test.map50-->, default threshold 0.3<!--=d.conf-->, and the seven classes.

**What to click.**

1. **Video:** choose **Sample clip** (frames from the IDD test split) or **Upload** (your own video).
2. **Confidence threshold** slider: the default is the value chosen on our validation split.
3. **Max frames** and **Force CPU** (leave them as they are).
4. Press **Run detector**.

After the run: a video player with the boxes drawn (class colours; you can hide a class), the
number of boxes per class in the current frame and over all frames, and four measured figures:
detector speed (frames per second), latency per frame (with its 95th percentile), end-to-end speed,
and the device (GPU or CPU). These speed figures are measured live and are not stored anywhere.

**What to say.** "This is our detector trained on Indian street images. The sample clip comes from
images it never saw in training. It counts per frame, with no tracking, and the clip is a time-lapse
of IDD's sampled frames. It was filmed from a car, so it stands in for a junction camera."

**GPU note.** The page uses the GPU only if at least about 1 GB of its memory is free. If an LLM
is loaded in Ollama, the page may switch to the CPU and **says why** ("is an LLM loaded?"). That is
fine; it is just slower.

## Page 3: Network Replay

**What it shows.** Two controllers on the same traffic, side by side, second by second, replayed
from the runs' own logged decisions. Badges: "replayed, verified", "selection rule". The traffic is
the peak + ambulances scenario, seed 1 (chosen by a rule fixed in advance: the emergency seed with
the most ambulances).

- **Left** and **Right** drop-downs: which runs to compare. The default pair is **MaxPressure**
  (left) and the **pre-registered LLM arm** (right). Exploratory runs can be picked; they keep their
  badge.
- **Ambulance** drop-down: the signal-relevant ambulances, by start time, each with its travel time
  in both runs. The default is the first one (a fixed rule, not a choice by result).
- **Window (s)** slider: which part of the hour to replay.
- Above the map: **mean travel time, this seed**: this ambulance, all ambulances, the
  signal-relevant ones, and all vehicles (ATT), for both runs; the faster one is highlighted.
- **The map:** vehicles drawn to their real length and width, signal colours on each stop line, a
  queue bar per approach, the ambulance enlarged and flashing, with a trail and a timer. Views: the
  whole grid, or a camera that **follows the ambulance**. **As simulated** (default) or **Keep left**
  (the mirror image, how we model India's left-hand traffic; east and west swap sides).
- Under the map: each run's **decisions** as cards: the LLM's own reason, a guard override, or
  MaxPressure's pressures. "Show raw decision data" shows every logged field.
- At the bottom: **Network queue over the hour** for both runs.

**What to click.** Press play. Switch to the follow-the-ambulance view. Point at an LLM decision
card and read its reason aloud.

**What to say.** "This is not an animation we made up. Each replay re-drives the simulator with the
run's logged decisions and is kept only if it reproduces the run's results exactly. Here MaxPressure
does not know the ambulance is there; the LLM is told, and gives it green sooner."

**Do not get wrong.** One ambulance can differ a lot by chance. Always point to the **means**
above the map for context. The replays do not call the LLM again.

## Page 4: Results

**What it shows.** "What the experiments measured": five tabs, each opening with a one-line
**takeaway** computed from the data, then charts and tables with their honesty notes. Hover over a
chart for exact values.

1. **Signal control:** pick the **Scenario** (default: Indian peak). ATT of each controller (mean ±
   spread), a **paired-by-seed** slope chart, all metrics, and LLM decision statistics. The takeaway
   gives the pre-registered arm's change against MaxPressure and how many seeds were higher or lower.
2. **Ambulances:** where each controller's ambulance time goes: stopped versus the rest of the trip.
   Takeaway: 130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s; preemption
   81.2<!--=e.pre.amb--> s; exploratory gemma4 82.2<!--=e.gem.amb--> s.
3. **Model size · exploratory:** the same hybrid controller with five models, from 3B up to the
   hosted Nemotron model. Labelled "exploratory", "hosted, not local", "no significance test". The
   small models make the hybrid slower than MaxPressure on every seed; from gemma4 up, travel time is
   MaxPressure's within seed noise.
4. **Camera errors:** the paired change per camera level, the detection-rate sweep (misses only),
   and the post-hoc decomposition as a waterfall. Takeaway: the detector's errors add
   2.3<!--=c.peak.mp.junction.pct-->–8.2<!--=c.off.mp.crowded.pct-->% to MaxPressure's travel time;
   the Webster plan reads no counts and is unaffected.
5. **Detector:** mAP50 per class and miss rate by object size. Takeaway: mAP50
   0.563<!--=d.test.map50--> on 10,225<!--=d.test.images--> IDD images never used in training,
   the two weakest classes, and the share of small and large boxes missed.

**What to say.** Pick one tab per question. For the main result: "Signal control, peak: the
pre-registered arm is +0.5<!--=f.peak.llm.vs_mp-->%, and the slope chart shows each seed."

## Suggested Demo Order (5 to 7 Minutes)

| Time | Page | Action | Line to say |
|:--|:--|:------------------------|:--------------------------------|
| 0:00–1:00 | Overview | Show the headline, open one source chip | "Every number comes from a result file." |
| 1:00–2:30 | Network Replay | Play the default ambulance, follow view, one decision card | "MaxPressure does not know the ambulance is there; the LLM is told." |
| 2:30–4:00 | Results | Signal control (peak), then Ambulances, then Camera errors | "Matches MaxPressure, does not beat it; ambulances; camera errors." |
| 4:00–5:30 | Live Detection | Sample clip, Run detector | "Dashcam proxy, no tracking, measured now." |
| 5:30–6:30 | Results | Model size · exploratory (only if time) | "Exploratory: a lead, not a result." |

Run Live Detection **last** or near the end: it takes the longest, and if the GPU is busy it runs on
the CPU.

## If Something Fails

Stay calm and say what is happening. The panel cares about honesty more than a perfect demo.

**The dashboard does not start.**

1. If the team's `TrafficSense.bat` launcher is on the laptop, double-click it and wait for the
   browser to open. If it does not open, start it by hand (below).
2. By hand: open the Ubuntu (WSL) terminal and run:

```bash
cd ~/trafficsense
source .venv/bin/activate
streamlit run src/trafficsense/dashboard/app.py
```

3. Open the address it prints (normally `http://localhost:8501`) in the browser.
4. Still failing? Use the **slide screenshots** (slide 15 shows the Live Detection and Overview
   pages) and the report's screenshots of all four pages, and say: "The dashboard reads the same
   result files; here are its pages."

**Ollama is not running.** The dashboard does **not** need Ollama: it never calls the LLM.
Ollama is needed only to run a new LLM experiment, which we do not do in the demo. To check it
anyway: `ollama list` (lists the installed models) or `ollama ps` (shows a model loaded on the GPU).
To start it: `ollama serve`.

**The GPU is busy** (Live Detection says it uses the CPU, "is an LLM loaded?").

- Close other GPU-heavy apps (games, video editors, other browsers playing video).
- Unload a model held by Ollama: `ollama stop llama3.2:3b` (check with `ollama ps`).
- Or simply let it run on the CPU and say so: it is slower, the result is the same.

**Network Replay says a file is missing.** The replays live on the D: drive, not in git. Say: "The
replay files are kept outside the repository; the page names the command that rebuilds them", and
move to the Results page.
