```{=latex}
\begin{titlepage}
\centering
\vspace*{3cm}
{\Huge\bfseries TrafficSense\par}
\vspace{0.6cm}
{\LARGE Study Handbook for the Final Review\par}
\vspace{0.4cm}
{\large Everything the team needs to learn the project in one night\par}
\vspace{2cm}
{\large Capstone Final Review, SCOPE, VIT-AP University\par}
\vspace{0.3cm}
{\large SDP Id: 3328F4C8\par}
\vspace{0.3cm}
{\large Supervised by Dr. Mohd Irfan\par}
\vspace{1.5cm}
\begin{tabular}{ll}
C Bhargav Kumar & 23BCE8195\\
Achalla Akul Lakhan & 23BCE8015\\
Darsi Amit & 23BCE8288\\
Mylapalli Abhishek Raj & 23BCE9470\\
\end{tabular}
\vfill
{\normalsize Every number in this handbook is checked against the project's result files\\
by \texttt{scripts/check\_handbook.py}. It follows the deck and the dashboard exactly.\par}
\end{titlepage}
\setcounter{tocdepth}{1}
\tableofcontents
\clearpage
```

# How to Use This Handbook

This handbook is for the four of us. Tomorrow morning we present TrafficSense to the panel.
The handbook follows the **slide deck** (`docs/ppt/TrafficSense_Capstone_Final_Review.pptx`) and
the **dashboard** exactly, so what we say and what we show will match. Every result number in it
comes from the same checked result files as the report. Nothing here is new: if it is not in the
report, the deck or the dashboard, it is not in this handbook.

You do not need a technical background to follow it. Every new word is explained the first time
it appears, and again in the glossary (Part 11).

## A Reading Plan for One Night

Read in this order. The times are a guide for one evening of about four hours.

| Order | Part | Why | Time |
|:--|:-------------------------------|:-------------------------------------------|:--|
| 1 | Part 1 and Part 2 (this part, the 60-second story) | The whole project in one page | 15 minutes |
| 2 | Part 3 (the story in plain words) | Why the project exists and what we found | 20 minutes |
| 3 | Part 7 (results cheat sheet) | The numbers you will be asked about | 15 minutes |
| 4 | Part 4 (key ideas) | The ideas behind every slide | 45 minutes |
| 5 | Part 5 (slide by slide) | What to say on each slide | 45 minutes |
| 6 | Part 6 (dashboard) | What to click in the demo | 20 minutes |
| 7 | Part 8 (limitations) and Part 9 (questions) | How to answer calmly and honestly | 45 minutes |
| 8 | Part 10 (who explains what) | Your own slides, in depth | 20 minutes |
| 9 | Part 12 (checklist and quiz) | Tomorrow morning | 15 minutes |

If you only have one hour: read Part 2, Part 7, the "5 things" box below, your own slides in
Part 5, and the quiz in Part 12.

## Five Things Everyone Must Remember

> **1. It is a simulation study.** No real traffic signal was controlled. All traffic was simulated
> in a program called CityFlow. Say it first, before anyone asks.
>
> **2. The LLM controller matches MaxPressure but does NOT beat it.** The pre-registered LLM
> controller's average travel time is within 0.5<!--=f.peak.llm.vs_mp-->% to
> 0.9<!--=f.off.llm.vs_mp-->% of MaxPressure (slightly slower). Never say "our AI is better than
> the classical method".
>
> **3. The clear benefit is ambulances.** Told where ambulances are, the LLM controller cut
> their mean travel time from 130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s. A simple
> hand-written priority rule (preemption) did a little better: 81.2<!--=e.pre.amb--> s.
>
> **4. Camera errors cost a few percent.** Real detector errors made MaxPressure
> 2.3<!--=c.peak.mp.junction.pct-->% to 4.8<!--=c.off.mp.junction.pct-->% slower (junction
> camera level). But our camera errors come from dash-camera images, so they are a *proxy*
> (a stand-in), not a measurement at a real junction.
>
> **5. Pre-registered versus exploratory.** "Pre-registered" means we wrote the plan and the
> decision rule down *before* running the experiment. The gemma4 arm and the model-size study
> were added later: they are *exploratory*, a lead, not a proven result. If you do not know
> something, say "we did not test that".

## How the Numbers Are Kept Honest

Our project has a strict rule: no number is typed from memory. In the report, every number is
tied to a result file in the `outputs/` folder, and a script (`make_report.py --check`) fails if
any number differs from the data. This handbook uses the same system, and its own check
(`scripts/check_handbook.py`) does the same. So if the handbook says 88.1<!--=f.off.mp.att--> s,
that is what the simulator measured.

Many results are written as "mean ± spread", for example 88.1<!--=f.off.mp.att--> ±
1.0<!--=f.off.mp.att_sd--> s. The first number is the average over the random seeds (three
repeats with different traffic). The second shows how much the result moved from one repeat to
the next (the *standard deviation*). A small spread means the result is steady.
