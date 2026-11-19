```{=latex}
\begin{center}
{\LARGE\bfseries\color{headblue} My Part: Speaking Guide\par}
\vspace{4pt}
{\large Darsi Amit (23BCE8288)\par}
{\normalsize Frontend and dashboard lead\par}
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

**What I did.** I built the **dashboard**: the web page, made with Streamlit, that shows all our
results. From the report's team table:

- The Streamlit dashboard and its four pages: Overview, Live Detection, Network Replay and Results
  (`dashboard/app.py`, `dashboard/screens/`, `dashboard/views/`).
- The Live Detection and Network Replay views.
- It reads only from `outputs/`, with a **source chip** on every number (`dashboard/data.py`).

**Why it was needed.** The panel needs to *see* the results, and trust them. So the dashboard holds
no numbers of its own: it reads the result files, and every number has a button that names its file.
A test (`tests/test_dashboard.py`) fails if any number shown is not in the files the page read.

**How it connects to the others.**

> Result files in `outputs/` (from Akul's experiments, Bhargav's detector evaluation, Abhishek's
> checked pipeline) → **my dashboard reads them, never changes them** → the four pages → what the
> panel sees in the demo.

# What to Say

**30-second version.** "I built the dashboard. It has four pages: Overview, Live Detection, Network
Replay and Results. It only reads the result files, and every number has a source chip that names
its file and the git commit that last changed it. The headline is our pre-registered result:
ambulances 32<!--=e.llm.amb_cut_vs_mp-->% faster than under MaxPressure. Exploratory numbers carry
a badge and are never the biggest number on a page."

**2-minute version.** "My part takes the result files and gives a page the panel can explore. The
**Overview** shows the headline: ambulances 32<!--=e.llm.amb_cut_vs_mp-->% faster with the
pre-registered LLM controller, 130.1<!--=e.mp.amb--> seconds against 88.9<!--=e.llm.amb--> seconds,
with rule-based preemption at 81.2<!--=e.pre.amb--> seconds beside it. A tile says it honestly:
travel time +0.5<!--=f.peak.llm.vs_mp-->% at peak, safe, but no gain.

**Live Detection** runs Bhargav's detector on a video, on this laptop, frame by frame, and shows the
boxes and the counts per class. **Network Replay** shows two controllers on the same traffic, side by
side, second by second. It is not an animation we made up: each replay re-drives the simulator with
the run's logged decisions and is kept only if it reproduces the run's results exactly. The default
pair is MaxPressure and the pre-registered LLM arm. **Results** has five tabs: signal control,
ambulances, model size (exploratory), camera errors and the detector. Each starts with a one-line
takeaway computed from the data.

Two rules guided the design: the dashboard only reads files, and every number can be traced to its
file. Honesty labels, such as pre-registered, exploratory and no significance test, sit next to what
they describe."

# My Slides and Dashboard Pages

| Slide or page | What to point at |
|:--|:----------------------------------------|
| Slide 9: key components | The last line: "Dashboard: Streamlit, reads only `outputs/`, a source chip on every number" |
| Slide 15: dashboard screenshots | The Live Detection and Overview screenshots |
| Slide 18: thank you | The GitHub link, then hand over to the demo |
| Dashboard demo (I drive it) | Overview, then Network Replay, then Results; Live Detection last (Bhargav explains it) |
| Overview | The headline 32<!--=e.llm.amb_cut_vs_mp-->%; open one source chip; the "Why / How to read" drawer |
| Results | The takeaway line at the top of each tab; hover over a chart for exact values |

**If something fails:** start it by hand (`streamlit run src/trafficsense/dashboard/app.py`), or
show the screenshots on slide 15 and in the report. If Live Detection says it uses the CPU, that is
fine: an LLM may be holding the GPU, and the page says so.

# My Key Numbers

These are the numbers the dashboard shows; they all come from the result files.

| Number | Plain meaning |
|:--|:--------------------------------------------|
| 32<!--=e.llm.amb_cut_vs_mp-->% faster | Overview headline: ambulances with the pre-registered LLM, against MaxPressure |
| 130.1<!--=e.mp.amb--> / 88.9<!--=e.llm.amb--> / 81.2<!--=e.pre.amb--> s | Ambulance travel time: MaxPressure / LLM / preemption |
| 82.2<!--=e.gem.amb--> s | The exploratory gemma4 hybrid, shown with its badge |
| +0.5<!--=f.peak.llm.vs_mp-->% | Tile 1: the pre-registered LLM's travel time against MaxPressure at peak |
| 0.563<!--=d.test.map50--> | Tile 2: the detector's mAP50 on the IDD test split |
| +4.8<!--=c.off.mp.junction.pct-->% | Tile 3: MaxPressure with junction-camera errors, off-peak |
| 2.3<!--=c.peak.mp.junction.pct-->–8.2<!--=c.off.mp.crowded.pct-->% | "Camera errors cost" range in the three-step story |

The report says 31.7<!--=e.llm.amb_cut_vs_mp-->%; the dashboard rounds the same number to
32<!--=e.llm.amb_cut_vs_mp-->%.

# Likely Questions About My Part

1. **Where do the numbers come from?** Only from the result files in `outputs/`. Click any source
   chip to see the file and its git commit.
2. **How do you know no number is typed in?** A test renders each page and fails if any number shown
   is not in the files that page read.
3. **Is the replay a real run?** Yes. It re-drives the simulator with the run's logged decisions and
   is kept only if it reproduces the run's results exactly. No LLM is called.
4. **Why this ambulance and this seed?** Fixed rules written before the page was first rendered: the
   seed with the most ambulances, and the first signal-relevant ambulance. Not chosen by result.
5. **Why is the gemma4 number smaller than the headline?** It is exploratory. Nothing exploratory is
   the biggest number on a page.
6. **Is Live Detection running now?** Yes, on this laptop. Its speed figures are measured live and not
   stored.
7. **What is "Keep left" in the replay?** The mirror image of the map, which is how the project models
   India's left-hand traffic.
8. **Does the dashboard need Ollama or the internet?** No. It never calls the LLM, and its fonts are
   bundled.
9. **What is Streamlit?** A free, open-source Python tool for building data web pages.

**Three questions about the other parts I should still answer.**

- *Does the LLM beat MaxPressure?* No. It matches it, within 0.5<!--=f.peak.llm.vs_mp-->% to
  0.9<!--=f.off.llm.vs_mp-->%.
- *What is the guard?* A check that applies the LLM's phase only if it is within
  20<!--=cfg.guard.margin-->% of the top pressure.
- *What is the camera caveat?* The detector's errors come from dash-camera images, a proxy for a
  junction camera.

# Do Not Claim

- **The dashboard shows results; it does not control signals** and does not call the LLM.
- **The replay is a simulation replay,** not video from a real junction. The animated grid behind
  the Overview headline is decoration, not data.
- **The Live Detection clip is IDD dash-camera frames,** played as a time-lapse, with no tracking.
- **Exploratory pages and badges** (model size, gemma4) are leads, not results.
- **Not my role:** the controllers, the detector training. Point to Akul or Bhargav.
- **The AI coding assistant.** Say the report's words: "The project was developed with the help of
  an AI coding assistant (Claude Code), working under the team's direction: the team decided what
  to build and how to evaluate it, reviewed the code and the text, ran the experiments and checked
  the results, and is responsible for all of the work presented in this report."
- If you do not know: **"We did not test that."**

# Five Terms I Must Explain Simply

- **Dashboard:** a web page that shows the results in charts and tables.
- **Streamlit:** a free Python tool for building data web pages.
- **Source chip:** the "source" button next to a number that names the file it came from.
- **Replay:** re-driving the simulator with a run's logged decisions, to show it second by second.
- **Badge:** a small label such as "pre-registered" or "exploratory" next to a number.
