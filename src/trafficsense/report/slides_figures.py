"""The architecture diagram redrawn for the slide (docs/ppt/figures/architecture_slide.png).

Same boxes, wording and arrows as the report's Figure 1 (`figures.fig_architecture`), laid out
wide and with larger type so that it is legible on a projected 16:9 slide. A diagram: no data.
"""
from __future__ import annotations

from pathlib import Path

from trafficsense.report.figures import INK, INK2, MUTED, SLOT

OUT = Path("docs/ppt/figures/architecture_slide.png")
OUT_LOOP = Path("docs/ppt/figures/agent_loop_slide.png")
W, H = 9.45, 4.0          # inches: the picture area on the slide (8.64 M x 3.65 M EMU)
FS = 12.5


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
    lab = dict(fontsize=FS + 0.5, fontweight="bold", color=INK2)
    ax.text(0.05, 3.82, "Perception (offline)", **lab)
    ax.text(5.85, 3.82, "Extra inputs to the agent", **lab)
    _box(ax, 0.05, 2.85, 1.7, 0.8, "IDD images\n(dash camera,\nIndia)")
    _box(ax, 2.05, 2.85, 1.6, 0.8, "Detector\nYOLOv8n,\n640 px")
    _box(ax, 3.95, 2.85, 1.6, 0.8, "Error model\np_detect, labels,\nfalse detections")
    _box(ax, 5.85, 2.85, 1.7, 0.8, "Neighbours:\nphase, queues\ntowards us")
    _box(ax, 7.75, 2.85, 1.65, 0.8, "Ambulances\n≤ 150 m (GPS/\nV2X, exact)")
    _arrow(ax, (1.75, 3.25), (2.05, 3.25)); _arrow(ax, (3.65, 3.25), (3.95, 3.25))
    _box(ax, 0.05, 1.35, 1.7, 0.95, "CityFlow\nengine (exact\nstate; metrics)", fc="#e8f1fb", ec=SLOT["mp"])
    _box(ax, 2.05, 1.35, 1.6, 0.95, "Observation\nlayer: exact or\nnoised counts")
    _box(ax, 3.95, 1.35, 1.6, 0.95, "MaxPressure\nranking: offers\ntop 2 + keep")
    _box(ax, 5.85, 1.35, 3.55, 0.95, "LLM agent per intersection\nobserve → reason → act\n(Ollama, JSON schema)",
         fc="#e6f6ef", ec=SLOT["llm"], bold=True)
    for a, b in [(1.75, 2.05), (3.65, 3.95), (5.55, 5.85)]:
        _arrow(ax, (a, 1.82), (b, 1.82))
    _arrow(ax, (6.7, 2.85), (6.7, 2.30)); _arrow(ax, (8.57, 2.85), (8.57, 2.30))
    _arrow(ax, (4.75, 2.85), (3.0, 2.30))
    ax.text(4.95, 2.45, "noise parameters", fontsize=FS - 1, color=INK2, ha="left")
    _box(ax, 5.85, 0.1, 3.55, 0.85, "Guard + signal timing\npressure ≥ 0.8 × top; min/max\ngreen; 5 s transition")
    _arrow(ax, (7.62, 1.35), (7.62, 0.95))
    ax.plot([5.85, 4.8, 4.8, 0.9], [0.52, 0.52, 1.13, 1.13], color=INK2, lw=1.4)
    _arrow(ax, (0.9, 1.13), (0.9, 1.35))
    ax.text(2.85, 1.17, "applied phase", fontsize=FS - 1, color=INK2, ha="center", va="bottom")
    _box(ax, 0.05, 0.1, 1.7, 0.85, "outputs/\nsummary, metrics,\ndecisions")
    _box(ax, 2.05, 0.1, 1.6, 0.85, "Dashboard,\ndocs, report")
    _arrow(ax, (0.4, 1.35), (0.4, 0.95)); _arrow(ax, (1.75, 0.52), (2.05, 0.52))
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
        ax.text(x + bw / 2, 1.5, head, ha="center", va="center", fontsize=FS, fontweight="bold", color=INK)
        ax.text(x + bw / 2, 0.97, textwrap.fill(body, 17), ha="center", va="center", fontsize=FS - 2, color=INK,
                linespacing=1.15)
        if i < 4:
            _arrow(ax, (x + bw, 1.05), (x + bw + gap, 1.05))
    ax.text(w / 2, 1.82, "every 5 s per intersection, once its minimum green is met", ha="center", va="center",
            fontsize=FS - 1, color=INK2)
    ax.annotate("", xy=(1.0, 0.46), xytext=(w - 1.0, 0.46),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.4, connectionstyle="arc3,rad=-0.08"))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, facecolor="white", metadata={"Software": None})
    plt.close(fig)
