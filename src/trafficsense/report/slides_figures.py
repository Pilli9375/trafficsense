"""The architecture diagram redrawn for the slide (docs/ppt/figures/architecture_slide.png).

Same boxes, wording and arrows as the report's Figure 1 (`figures.fig_architecture`), laid out
wide and with larger type so that it is legible on a projected 16:9 slide. A diagram: no data.
"""
from __future__ import annotations

from pathlib import Path

from trafficsense.report.figures import INK, INK2, MUTED, SLOT

OUT = Path("docs/ppt/figures/architecture_slide.png")
OUT_LOOP = Path("docs/ppt/figures/agent_loop_slide.png")
W, H = 9.78, 4.05         # inches: the picture area on the slide (8.94 M x 3.70 M EMU), drawn at 1:1
FS = 15


def _box(ax, x, y, w, h, text, fc="#f4f3f0", ec=MUTED, bold=False):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.06", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=FS, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.2)


def _arrow(ax, a, b):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.4, shrinkA=1, shrinkB=1))


def draw(path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    lab = dict(fontsize=FS - 0.5, fontweight="bold", color=INK2)
    ax.text(0.04, 3.86, "Perception (offline)", **lab)
    ax.text(5.99, 3.86, "Extra inputs to the agent", **lab)
    bw = 1.75
    xs = [0.04, 1.99, 3.94, 5.99, 7.94]
    texts = ["IDD images\n(dash camera,\nIndia)", "Detector\nYOLOv8n,\n640 px", "Error model\nmisses, false\ndetections",
             "Neighbours:\nphase, queues\nto us", "Ambulances\n≤ 150 m\n(GPS/V2X)"]
    for x, t in zip(xs, texts):
        _box(ax, x, 2.8, bw, 0.95, t)
    _arrow(ax, (xs[0] + bw, 3.27), (xs[1], 3.27)); _arrow(ax, (xs[1] + bw, 3.27), (xs[2], 3.27))
    _box(ax, 0.04, 1.4, bw, 1.0, "CityFlow\nengine\n(exact state)", fc="#e8f1fb", ec=SLOT["mp"])
    _box(ax, 1.99, 1.4, bw, 1.0, "Observation\nlayer: exact\nor noised", )
    _box(ax, 3.94, 1.4, bw, 1.0, "MaxPressure\nranking: top 2\n+ keep")
    _box(ax, 5.99, 1.4, 3.7, 1.0, "LLM agent per intersection\nobserve → reason → act\n(Ollama, JSON schema)",
         fc="#e6f6ef", ec=SLOT["llm"], bold=True)
    for a, b in [(0.04 + bw, 1.99), (1.99 + bw, 3.94), (3.94 + bw, 5.99)]:
        _arrow(ax, (a, 1.9), (b, 1.9))
    _arrow(ax, (6.865, 2.8), (6.865, 2.4)); _arrow(ax, (8.815, 2.8), (8.815, 2.4))
    _arrow(ax, (4.3, 2.8), (2.9, 2.4))
    ax.text(4.45, 2.52, "noise parameters", fontsize=FS - 2, color=INK2, ha="left", va="center")
    _box(ax, 5.99, 0.08, 3.7, 1.0, "Guard + signal timing\npressure ≥ 0.8 × top;\nmin/max green; 5 s transition")
    _arrow(ax, (7.84, 1.4), (7.84, 1.08))
    ax.plot([5.99, 5.15, 5.15, 0.91], [0.58, 0.58, 1.2, 1.2], color=INK2, lw=1.6)
    _arrow(ax, (0.91, 1.2), (0.91, 1.4))
    ax.text(3.2, 1.225, "applied phase", fontsize=FS - 2, color=INK2, ha="center", va="bottom")
    _box(ax, 0.04, 0.08, 2.05, 1.0, "outputs/\nsummary, metrics,\ndecisions")
    _box(ax, 2.5, 0.08, 1.75, 1.0, "Dashboard,\ndocs, report")
    _arrow(ax, (0.5, 1.4), (0.5, 1.08)); _arrow(ax, (2.09, 0.58), (2.5, 0.58))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, facecolor="white", metadata={"Software": None})
    plt.close(fig)


LOOP = [("1. Observe", "queue and pressure per phase; neighbours; ambulances"),
        ("2. Reason", "LLM reads the prompt, answers JSON: phase + short reason"),
        ("3. Act", "validate; guard checks pressure; failure → MaxPressure's choice"),
        ("4. Enforce", "5 s transition, min green 15 s, max green 60 s"),
        ("5. Log", "decisions.jsonl: state, raw answer, latency, applied phase")]


def draw_loop(path: Path):
    """The report's decision-loop diagram (`figures.fig_agent_loop`), wide and with larger type."""
    import textwrap
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    plt.rcParams["font.family"] = "DejaVu Sans"
    w, h = 9.45, 1.95
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    bw, gap = 1.74, 0.17
    for i, (head, body) in enumerate(LOOP):
        x = 0.04 + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, 0.5), bw, 1.15, boxstyle="round,pad=0.01,rounding_size=0.06",
                                    fc="#e6f6ef" if i == 1 else "#f4f3f0", ec=SLOT["llm"] if i == 1 else MUTED, lw=1.2))
        ax.text(x + bw / 2, 1.5, head, ha="center", va="center", fontsize=13, fontweight="bold", color=INK)
        ax.text(x + bw / 2, 0.97, textwrap.fill(body, 17), ha="center", va="center", fontsize=11.5, color=INK,
                linespacing=1.15)
        if i < 4:
            _arrow(ax, (x + bw, 1.05), (x + bw + gap, 1.05))
    ax.text(w / 2, 1.82, "every 5 s per intersection, once its minimum green is met", ha="center", va="center",
            fontsize=12, color=INK2)
    ax.annotate("", xy=(1.0, 0.46), xytext=(w - 1.0, 0.46),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.4, connectionstyle="arc3,rad=-0.08"))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, facecolor="white", metadata={"Software": None})
    plt.close(fig)
