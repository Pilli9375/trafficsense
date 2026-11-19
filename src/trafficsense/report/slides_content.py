"""What is on each slide of the capstone final-review deck, and what is said about it.

Every sentence here is condensed from the report (docs/report/*.md, extended/). A number is
written the way the report writes it, with its tag, `88.1<!--=f.off.mp.att-->`: the build checks
the tag against outputs/ (trafficsense.report.numbers) and removes it from the slide, and a number
without a tag fails the build. Numbers inside a table come from a generated table of the report
(`Table(...)` below), never from this file. `**x**` is bold, `` `x` `` is code.

Keys are the slide numbers of the university template (1-16). Slide 13 is split into the three
outcome slides "13a", "13b", "13c" (same title and layout).
"""
from __future__ import annotations

from dataclasses import dataclass, field

FIG = "docs/report/figures/"


@dataclass
class Table:
    """Rows picked from a generated table of the report (`block` in `doc`): `rows` are texts that
    select one row each (in the order given), `cols` are header texts that select the columns.
    `labels` replace the first column's text (short names for the slide)."""
    doc: str
    block: str
    rows: list[str]
    cols: list[str]
    labels: list[str] | None = None
    headers: list[str] | None = None


@dataclass
class Literal:
    """A small table typed here (text and tagged numbers only)."""
    header: list[str]
    rows: list[list[str]]


@dataclass
class Slide:
    bullets: list[str] = field(default_factory=list)
    notes: str = ""
    image: str | None = None
    alt: str = ""
    tables: list = field(default_factory=list)     # Table | Literal, each with a label above it
    table_labels: list[str] = field(default_factory=list)
    columns: list[tuple[str, list[str]]] = field(default_factory=list)   # (heading, bullets)
    layout: str = "text"
    images: list[tuple[str, str, str]] = field(default_factory=list)     # (path, alt, caption)
    heading_suffix: str = ""


CH2, CH4 = "docs/report/20_ch2_system.md", "docs/report/40_ch4_results.md"

SLIDES: dict[str, Slide] = {
    "3": Slide(
        layout="text_image",
        bullets=[
            "**TrafficSense:** one local LLM agent at every signalised junction, adapted from CoLLMLight (ICLR 2026)",
            "The agents read their own and their neighbours' queues and choose the next phase",
            "Runs on a laptop GPU (GTX 1650, 4 GB) through Ollama",
            "Tested in the CityFlow simulator on an Indian-style 2x2 network",
            "A **simulation study**: no real signal was controlled",
        ],
        image=FIG + "network.png",
        alt="The 2x2 test network: four junctions 200 m apart with entry and exit roads",
        notes=(
            "TrafficSense places one local language-model agent at each signalised junction. "
            "Each agent sees its own and its neighbours' state and chooses the next signal phase; the idea is adapted from "
            "the CoLLMLight paper to run on a 4 GB laptop GPU. "
            "Everything is tested in the CityFlow simulator on an Indian-style 2x2 grid. "
            "This is a simulation study: no signal in the field was controlled."),
    ),
    "4": Slide(
        layout="text_table",
        bullets=[
            "Indian junctions carry a **mixed stream**: two-wheelers, auto-rickshaws, cars, buses, trucks",
            "Many still run **fixed plans**, and ambulances get no priority",
            "Weak lane discipline: loop detectors work poorly, cameras are the natural sensor",
            "**Question:** can a small local LLM agent match the best classical controller, and cope with camera errors?",
        ],
        tables=[Table(CH2, "tab_mix", ["motorcycle", "auto_rickshaw", "car", "bus", "truck"], ["Type", "Share"],
                      labels=["Motorcycle", "Auto-rickshaw", "Car", "Bus", "Truck"],
                      headers=["Vehicle type", "Share"])],
        table_labels=["Vehicle mix of the simulated traffic"],
        notes=(
            "Indian urban traffic is a mix of two-wheelers, auto-rickshaws, cars, buses and trucks, as the table shows. "
            "Many junctions still run fixed signal plans, and emergency vehicles have no priority. "
            "Lane discipline is weak, so loop detectors work poorly and cameras are the natural sensor. "
            "We therefore ask whether a small local language model can control signals as well as the best classical method, "
            "and how it copes with vehicle counts from a real camera detector."),
    ),
    "5": Slide(
        layout="columns",
        columns=[
            ("Objectives", [
                "Build a local multi-agent LLM signal controller for a 4 GB GPU, on a simulator validated against CoLLMLight's code",
                "Compare it with tuned MaxPressure and Webster plans under a plan fixed in advance, with and without ambulances",
                "Measure a YOLOv8n detector on Indian images and test how its errors hurt each controller",
            ]),
            ("Expected impact", [
                "Honest evidence of where a small LLM agent helps and where it does not",
                "Results that can be reproduced: every number is checked against the result files, shown in a dashboard",
            ]),
        ],
        notes=(
            "The objectives are to build and validate the pipeline, to compare the LLM agents with tuned baselines under a plan fixed in advance, "
            "and to train a detector on Indian street images and inject its measured errors into the controllers. "
            "The expected impact is honest evidence about when a small local LLM agent helps and when it does not. "
            "Every run records where it came from, and every number in the report is generated from, or checked against, the result files."),
    ),
    "6": Slide(
        layout="table",
        tables=[Literal(
            ["Approach", "Limitation"],
            [["Fixed time (Webster [1])", "Cannot react to the traffic present"],
             ["Actuated / adaptive (SCATS, SCOOT [2], [3])", "Need dense, well-kept detectors and lane-based models"],
             ["MaxPressure [4]", "Local rule: no explanation, cannot use extra context"],
             ["Reinforcement learning [16]–[19]", "Long training per network; decisions hard to explain"],
             ["LLM agents (LLMLight, LA-Light, CoLLMLight [6]–[8])",
              "Usually large hosted or fine-tuned models, untuned baselines, exact counts"]])],
        table_labels=[""],
        notes=(
            "Fixed-time plans are cheap but cannot react to the traffic present. "
            "Adaptive systems such as SCATS and SCOOT depend on dense, well-maintained detectors and on lane-based traffic models, which are hard to meet on Indian roads. "
            "MaxPressure needs no training but is a local rule that cannot use extra context, and reinforcement learning needs long training per network and is hard to explain. "
            "Published LLM controllers are usually evaluated with large hosted or fine-tuned models, against baselines not tuned for the test network, and with exact simulator counts."),
    ),
    "7": Slide(
        layout="text",
        bullets=[
            "**Tuned baselines first:** MaxPressure and a Webster plan were tuned before any LLM run",
            "**Local, off-the-shelf models** of 3–4 B parameters: no fine-tuning, no hosted API",
            "**A guard** keeps the LLM's choice close to MaxPressure's ranking",
            "**Context MaxPressure cannot use:** approaching ambulances are listed in the prompt",
            "**Real camera errors** from a detector trained on Indian images, not only exact counts",
        ],
        notes=(
            "Our comparison differs from earlier work in five ways. "
            "The classical baselines were tuned on the test network before any LLM run, and the comparison plan was fixed in advance. "
            "The agents use small off-the-shelf models through Ollama, with no fine-tuning, and a guard keeps their choice close to MaxPressure's ranking. "
            "The agent is also told about approaching ambulances, which MaxPressure cannot use. "
            "Finally, the controllers' counts can carry the measured errors of a real detector."),
    ),
    "8": Slide(
        layout="image",
        image="docs/ppt/figures/architecture_slide.png",
        alt="System architecture: perception offline, observation layer, MaxPressure ranking, LLM agent, guard and signal timing, CityFlow engine, outputs and dashboard",
        notes=(
            "The CityFlow engine simulates every vehicle and is the only place where metrics are measured. "
            "Controllers read lane counts through an observation layer, which returns exact counts or counts degraded by the detector's measured errors. "
            "The LLM controllers build on MaxPressure's ranking, ask an LLM agent for each intersection, and pass its answer through a guard and the signal timing rules. "
            "Ambulance positions reach the agent through a separate channel and are never noised. "
            "Each run writes its results to the outputs folder, from which the dashboard and the report are generated."),
    ),
    "9": Slide(
        layout="text_image_bottom",
        bullets=[
            "**Simulator and wrapper:** CityFlow; transition phase, min / max green, all metrics",
            "**Controllers:** FixedTime, Webster, MaxPressure, rule-based preemption, LLM arms",
            "**LLM agent and guard:** JSON answer via Ollama; guard keeps it near MaxPressure",
            "**Perception:** YOLOv8n on IDD; its measured errors become a camera-noise layer",
            "**Dashboard:** Streamlit, reads only `outputs/`, a source chip on every number",
        ],
        image="docs/ppt/figures/agent_loop_slide.png",
        alt="The decision loop: observe, reason, act, enforce, log",
        notes=(
            "The system has five main parts: the simulator and its environment wrapper, the controllers, the LLM agent with its guard, the perception and camera-noise layer, and the dashboard. "
            "At each decision the agent observes its state and its neighbours', reasons with the local model, and acts by returning a phase and a short reason. "
            "The wrapper then enforces the transition and the green limits, and every decision is logged. "
            "The dashboard reads only files in the outputs folder, and every number it shows carries a source chip naming its file."),
    ),
    "10": Slide(
        layout="table",
        tables=[Literal(
            ["Algorithms and methods", "Technologies and tools"],
            [["MaxPressure and a Webster fixed-time plan", "CityFlow simulator, Python"],
             ["Guarded hybrid LLM controller (MaxPressure proposes, LLM decides)", "Ollama, local `llama3.2:3b`"],
             ["YOLOv8n vehicle detection", "Ultralytics YOLOv8, India Driving Dataset"],
             ["Camera error model: misses, false detections, confusions", "Streamlit dashboard"],
             ["Pre-registered, seed-paired comparison", "pytest, git and GitHub"]])],
        table_labels=[""],
        notes=(
            "The algorithms are MaxPressure and a Webster fixed-time plan as baselines, and a hybrid LLM controller in which MaxPressure proposes and the LLM decides, followed by a guard. "
            "Vehicle detection uses YOLOv8n, and its measured misses, false detections and class confusions form the camera error model. "
            "The tools are the CityFlow simulator, Ollama with a local model, Ultralytics YOLOv8 trained on the India Driving Dataset, and a Streamlit dashboard. "
            "Comparisons are pre-registered and paired by seed."),
    ),
    "11": Slide(
        layout="text_table",
        bullets=[
            "**Traffic:** Indian 2x2 (one flow file per seed) and Jinan 3x4 from CoLLMLight",
            "**Camera data:** India Driving Dataset, 7 classes; test split = official validation set",
            "**Agent input:** pressure and queue per phase, neighbours' state, listed ambulances",
            "**Output:** a phase and a short reason; every run writes its summary and decisions",
        ],
        tables=[Literal(
            ["Scenario", "Demand (veh/h)"],
            [["Indian off-peak", "2375<!--=cal.offpeak-->"],
             ["Indian peak", "4750<!--=cal.peak-->"],
             ["Peak + ambulances", "4750<!--=cal.peak--> + 6<!--=scn.emergency.veh_per_hour--> amb./h"],
             ["Jinan 3x4", "fixed real-world flow"]])],
        table_labels=["Scenarios (seeds 0–2; ambulances 0–4)"],
        notes=(
            "Traffic comes from two sources: our Indian 2x2 network, with a different flow file for each seed, and the Jinan 3x4 network with CoLLMLight's real-world flow. "
            "Off-peak demand is 2375<!--=cal.offpeak--> vehicles per hour and peak demand is 4750<!--=cal.peak-->, set by a rule fixed before it was run; the emergency scenario adds ambulances to the peak flow. "
            "The detector uses the India Driving Dataset with seven classes; its test split is the official validation set. "
            "An agent receives a text description of its state and returns a phase number and a short reason, and every run writes its summary and decisions to the outputs folder."),
    ),
    "12": Slide(
        layout="two_tables",
        tables=[
            Literal(["Simulation and control", "Value"],
                    [["Run length", "3600<!--=cfg.steps--> s"],
                     ["Decision interval", "5<!--=cfg.mp.interval--> s"],
                     ["Minimum green", "15<!--=cfg.mp.min_green--> s"],
                     ["Maximum green", "60<!--=cfg.signal.max_green--> s"],
                     ["Guard margin", "20<!--=cfg.guard.margin-->% of top"]]),
            Literal(["LLM and detector", "Value"],
                    [["Temperature", "0, fixed seed"],
                     ["Context / answer", "2048<!--=cfg.llm.num_ctx--> / 128<!--=cfg.llm.num_predict--> tokens"],
                     ["Call timeout", "60<!--=cfg.llm.timeout_s--> s"],
                     ["Ambulance range", "150<!--=cfg.amb.range--> m"],
                     ["Detector input", "640<!--=cfg.imgsz--> px, batch 8<!--=cfg.det.batch-->"]]),
        ],
        table_labels=["", ""],
        notes=(
            "Every run simulates 3600<!--=cfg.steps--> seconds, and the controllers decide every 5 seconds once the minimum green of 15<!--=cfg.mp.min_green--> seconds has been served, with a maximum green of 60<!--=cfg.signal.max_green--> seconds. "
            "The guard applies the LLM's choice only if its pressure is within 20<!--=cfg.guard.margin--> percent of the top pressure; otherwise MaxPressure's choice is applied. "
            "The model is called with temperature 0 and a fixed seed, a context of 2048<!--=cfg.llm.num_ctx--> tokens, at most 128<!--=cfg.llm.num_predict--> answer tokens and a 60<!--=cfg.llm.timeout_s--> second timeout. "
            "Ambulances are detected within 150<!--=cfg.amb.range--> metres of the stop line, and the detector is trained on 640<!--=cfg.imgsz--> pixel images with batch size 8."),
    ),
    "13a": Slide(
        layout="table_bullets",
        heading_suffix="  (a) Baselines and the LLM controllers",
        tables=[Table(CH4, "tab_full_summary",
                      ["MaxPressure", "Webster", "FixedTime", "pre-registered", "exploratory"],
                      ["Controller", "Off-peak", "Peak", "Jinan"],
                      labels=["MaxPressure", "Webster plan", "FixedTime 30 s",
                              "LLM pre-registered", "LLM exploratory"],
                      headers=["ATT (s)", "Off-peak", "Peak", "Jinan 3x4"])],
        table_labels=[""],
        bullets=[
            "**Pre-registered LLM** (guarded `llama3.2:3b`): within +0.5<!--=f.peak.llm.vs_mp--> to +0.9<!--=f.off.llm.vs_mp-->% of MaxPressure, **does not beat it**",
            "**Exploratory** `gemma4:e4b`: −1.5<!--=f.peak.gem.vs_mp-->% at peak, +2.7<!--=f.off.gem.vs_mp-->% off-peak: a lead, not a result",
        ],
        notes=(
            "This table gives the average travel time of every controller in the three scenarios, mean and standard deviation over three seeds. "
            "The pre-registered LLM controller, llama3.2:3b guided and guarded by MaxPressure, is within 0.5<!--=f.peak.llm.vs_mp--> to 0.9<!--=f.off.llm.vs_mp--> percent of MaxPressure but does not improve on it, because the guard replaces most of the model's answers. "
            "At peak, MaxPressure and the Webster plan are effectively tied, so being as good as MaxPressure there also means being as good as a well-timed fixed plan. "
            "The gemma4:e4b arm is exploratory: it was added after the plan was fixed, it is faster than MaxPressure only at peak, and with three seeds and no significance test that is a lead, not a demonstrated improvement."),
    ),
    "13b": Slide(
        layout="two_tables_stacked",
        heading_suffix="  (b) Ambulances and camera errors",
        tables=[
            Table(CH4, "tab_ambulances",
                  ["MaxPressure |", "preemption", "pre-registered", "exploratory"],
                  ["Controller", "Travel time", "Stopped"],
                  labels=["MaxPressure", "MaxPressure + preemption rule", "LLM guarded (pre-registered)",
                          "LLM gemma4:e4b (exploratory)"],
                  headers=["Controller", "Travel time (s)", "Stopped (s)"]),
            Literal(["Controller", "Junction camera", "Crowded / far camera"],
                    [["MaxPressure", "+4.8<!--=c.off.mp.junction.pct-->% / +2.3<!--=c.peak.mp.junction.pct-->%",
                      "+8.2<!--=c.off.mp.crowded.pct-->% / +4.4<!--=c.peak.mp.crowded.pct-->%"],
                     ["LLM guarded", "+5.1<!--=c.off.llm.junction.pct-->% / +1.6<!--=c.peak.llm.junction.pct-->%",
                      "+7.2<!--=c.off.llm.crowded.pct-->% / +4.9<!--=c.peak.llm.crowded.pct-->%"],
                     ["Webster plan", "+0.0<!--=c.off.web.junction.pct-->% / +0.0<!--=c.peak.web.junction.pct-->%",
                      "+0.0<!--=c.off.web.crowded.pct-->% / +0.0<!--=c.peak.web.crowded.pct-->%"]]),
        ],
        table_labels=["Ambulance travel time, peak (29<!--=e.mp.amb_n--> signal-relevant)", "Camera errors (dash-camera proxy): ATT change vs perfect counts, off-peak / peak"],
        notes=(
            "With ambulances listed in its prompt, the pre-registered LLM controller cut their mean travel time from 130.1<!--=e.mp.amb--> seconds under MaxPressure to 88.9<!--=e.llm.amb--> seconds, close to rule-based preemption at 81.2<!--=e.pre.amb--> seconds, mostly by removing time stopped at a red. "
            "Normal traffic does not pay for the priority, since network travel time stays within the seed-to-seed spread. "
            "When the detector's measured errors are put into the counts, every count-based controller gets slower, while the Webster plan, which never reads counts, is unaffected. "
            "The errors are those of our detector on dash-camera images, so the junction-camera level is a proxy, not a measurement at a real junction."),
    ),
    "13c": Slide(
        layout="text_two_images",
        heading_suffix="  (c) Detector results and dashboard",
        bullets=[
            "YOLOv8n on held-out IDD drives: **mAP50 0.563<!--=d.test.map50-->**, mAP50-95 0.375<!--=d.test.map5095-->",
            "High precision, moderate recall: it **undercounts**, mostly small distant objects",
            "Dashboard (Streamlit) reads only the result files",
        ],
        images=[(FIG + "screen_detection.png", "Dashboard, Live Detection page: the trained detector on IDD test frames", "Live Detection page"),
                (FIG + "screen_overview.png", "Dashboard, Overview page: the pre-registered arm's ambulance result", "Overview page")],
        notes=(
            "The detector was trained on the India Driving Dataset and reaches mAP50 of 0.563<!--=d.test.map50--> on held-out drives, with a confidence threshold frozen on the validation split before the single test evaluation. "
            "Precision is high and recall is moderate, so the detector undercounts, and most misses are small, distant objects at 640<!--=cfg.imgsz--> pixels. "
            "The dashboard has four pages; the Live Detection page shows the detector on a clip of IDD test frames, and the Overview page shows the headline result with exploratory numbers labelled as such. "
            "The dashboard reads only the committed result files."),
    ),
    "14": Slide(
        layout="summary",
        columns=[
            ("Key Findings", [
                "The pre-registered LLM controller **matches MaxPressure** (+0.5<!--=f.peak.llm.vs_mp--> to +0.9<!--=f.off.llm.vs_mp-->% ATT) but **does not beat it**",
                "Ambulances: **130.1<!--=e.mp.amb--> s to 88.9<!--=e.llm.amb--> s** (preemption rule 81.2<!--=e.pre.amb--> s); camera errors add 2.3<!--=c.peak.mp.junction.pct-->–4.8<!--=c.off.mp.junction.pct-->% to MaxPressure",
            ]),
            ("Limitations", [
                "**Simulation only**; junction-camera errors are a dash-camera proxy; 3 seeds, no significance test; lane-based simulator",
                "**Exploratory, not confirmatory:** the model-size study (incl. the hosted 550<!--=m.size.nemo--> B model) and the gemma4 arm",
            ]),
            ("Future Directions", [
                "Memory and tool-using agents, fine-tuning small models, real junction-camera footage, field testing in shadow mode",
            ]),
        ],
        notes=(
            "The selected LLM controller matches MaxPressure within a small margin but does not beat it, and its clearest benefit is for ambulances, where it approaches a hand-written preemption rule. "
            "Camera errors cost count-based controllers a few percent of travel time, mostly through false detections. "
            "This is a simulation study; the camera errors are a dash-camera proxy for a junction camera, three seeds are few, and the model-size study with the hosted model is exploratory. "
            "Future work is memory and tool-using agents, fine-tuning small models, real junction camera footage, larger networks and field testing in shadow mode."),
    ),
    "15": Slide(
        layout="bibliography",
        notes=(
            "These are the main references, numbered as in the report. "
            "Webster and Varaiya give the classical baselines, and LLMLight, LA-Light and CoLLMLight are the language-model controllers our work builds on. "
            "CityFlow is the simulator, YOLOv8 the detector and the India Driving Dataset its training data. "
            "The full reference list is in the report."),
    ),
    "16": Slide(
        layout="closing",
        notes=(
            "Thank you for your time. "
            "The complete source code, the report and every result file are available in the project repository. "
            "The link is on the slide, and we are happy to take questions."),
    ),
    "1": Slide(
        layout="title",
        notes=(
            "This is our capstone final review of TrafficSense, an AI-based smart traffic management system. "
            "It was developed by four students under the supervision of Dr. Mohd Irfan at VIT-AP University. "
            "TrafficSense uses local language-model agents to control traffic signals, tested in simulation on an Indian-style network. "
            "We will present the problem, the method, the results and the limitations."),
    ),
    "2": Slide(
        layout="outline",
        notes=(
            "The presentation follows six parts. "
            "We start with the introduction and the related work, then the proposed solution. "
            "Implementation and results come next, with the results shown on three slides, followed by the summary and the bibliography. "
            "The slide numbers are shown beside each part."),
    ),
}

# Bibliography: report reference numbers, in the order shown (Webster, MaxPressure, LLMLight,
# LA-Light, CoLLMLight, CityFlow, YOLOv8, IDD).
BIBLIOGRAPHY = [1, 4, 6, 7, 8, 13, 23, 24]

TITLE = "TrafficSense: An AI-Based Smart Traffic Management System"
SUPERVISOR = "Dr. Mohd Irfan"
SDP_ID = "3328F4C8"
STUDENTS = [("C Bhargav Kumar", "23BCE8195"), ("Achalla Akul Lakhan", "23BCE8015"),
            ("Darsi Amit", "23BCE8288"), ("Mylapalli Abhishek Raj", "23BCE9470")]
GITHUB = "https://github.com/Pilli9375/trafficsense"
