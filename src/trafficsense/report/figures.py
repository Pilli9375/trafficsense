"""Figures of the report, drawn from outputs/ into docs/report/figures/.

Each figure is a PNG plus `<name>.data.json` holding exactly the values plotted and the files
they came from. `make_all(check=True)` recomputes the values and reports any figure whose data
file differs, without redrawing (PNG bytes depend on the matplotlib version). Diagrams (no data)
record their fixed labels; screenshots record the sha256 of the source WebP.

Colours: the dataviz reference palette in fixed order, one slot per controller everywhere
(validated for the white page: adjacent CVD and normal-vision separation pass; three slots are
below 3:1 contrast, so every mark is also labelled in text and each figure has a table).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIG_DIR = Path("docs/report/figures")

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
SLOT = {"mp": "#2a78d6", "web": "#eb6834", "llm": "#1baf7a", "gem": "#eda100", "pre": "#e87ba4", "ft": "#008300"}
SEQ = ["#bcd6f3", "#6aa3e6", "#2a78d6", "#174f94"]          # one hue, light -> dark
NAMES = {"mp": "MaxPressure", "web": "Webster fixed time", "ft": "FixedTime 30 s",
         "llm": "LLM, pre-registered\n(guarded, llama3.2:3b)", "gem": "LLM, exploratory\n(gemma4:e4b hybrid)",
         "pre": "MaxPressure + preemption"}
FILES = {"full": "outputs/full/results.json", "camera": "outputs/camera_error/results.json",
         "ms": "outputs/model_size/model_size.json", "bench": "outputs/llm_benchmark/benchmark.json",
         "calib": "outputs/validation/indian_demand_calibration.json",
         "train": "outputs/perception/detector_train.json", "test": "outputs/perception/detector_test.json",
         "roadnet": "data/scenarios/indian_2x2/roadnet.json"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "savefig.dpi": 200,
        "legend.frameon": False, "svg.hashsalt": "ts"})
    return plt


def _save(fig, path: Path):
    fig.savefig(path, bbox_inches="tight", pad_inches=0.08, facecolor="white", metadata={"Software": None})
    import matplotlib.pyplot as plt
    plt.close(fig)


def _j(root, k):
    return json.loads((root / FILES[k]).read_text())


R = lambda x, n=4: round(float(x), n)


# --- diagrams --------------------------------------------------------------------------------

def _box(ax, x, y, w, h, text, fc="#f4f3f0", ec=MUTED, bold=False, size=8.2):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012",
                                fc=fc, ec=ec, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def _arrow(ax, a, b, text="", color=INK2, rad=0.0):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0,
                                                    shrinkA=2, shrinkB=2, connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.012, text, fontsize=7, color=INK2, ha="center")


ARCH_LABELS = ["CityFlow engine", "Observation layer", "MaxPressure ranking", "LLM agent", "Guard + timing",
               "IDD detector", "Error model", "outputs/", "Dashboard"]


def fig_architecture(root, fs):
    data = {"kind": "diagram", "labels": ARCH_LABELS}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7.2, 4.8))
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        fs_ = 7.4
        ax.text(0.02, 0.975, "Perception (offline)", fontsize=8.5, fontweight="bold", color=INK2)
        _box(ax, 0.02, 0.79, 0.17, 0.14, "IDD images\n(dash camera,\nIndia)", size=fs_)
        _box(ax, 0.23, 0.79, 0.17, 0.14, "Detector\nYOLOv8n,\n640 px", size=fs_)
        _box(ax, 0.44, 0.79, 0.19, 0.14, "Error model\np_detect, labels,\nfalse detections", size=fs_)
        _arrow(ax, (0.19, 0.86), (0.23, 0.86)); _arrow(ax, (0.40, 0.86), (0.44, 0.86))
        ax.text(0.69, 0.975, "Extra inputs to the agent", fontsize=8.5, fontweight="bold", color=INK2)
        _box(ax, 0.68, 0.79, 0.145, 0.14, "Neighbours:\nphase, queues\ntowards us", size=fs_)
        _box(ax, 0.845, 0.79, 0.145, 0.14, "Ambulances\n≤ 150 m (GPS/\nV2X, exact)", size=fs_)
        ax.text(0.02, 0.69, "Control loop (every decision step)", fontsize=8.5, fontweight="bold", color=INK2)
        _box(ax, 0.02, 0.41, 0.17, 0.22, "CityFlow\nengine\n(exact state;\nmetrics measured\nhere)",
             fc="#e8f1fb", ec=SLOT["mp"], size=fs_)
        _box(ax, 0.23, 0.44, 0.17, 0.16, "Observation\nlayer: exact or\nnoised counts", size=fs_)
        _box(ax, 0.44, 0.44, 0.19, 0.16, "MaxPressure\nranking: offers\ntop 2 + keep", size=fs_)
        _box(ax, 0.68, 0.41, 0.31, 0.22, "LLM agent per intersection\nobserve → reason → act\n(Ollama, JSON schema)",
             fc="#e6f6ef", ec=SLOT["llm"], bold=True, size=fs_ + 0.3)
        _box(ax, 0.68, 0.17, 0.31, 0.15, "Guard + signal timing\npressure ≥ 0.8 × top; min/max\ngreen; 5 s transition", size=fs_)
        _arrow(ax, (0.19, 0.52), (0.23, 0.52)); _arrow(ax, (0.40, 0.52), (0.44, 0.52))
        _arrow(ax, (0.63, 0.52), (0.68, 0.52))
        _arrow(ax, (0.7525, 0.79), (0.7525, 0.63)); _arrow(ax, (0.9175, 0.79), (0.9175, 0.63))
        _arrow(ax, (0.835, 0.41), (0.835, 0.32))
        _arrow(ax, (0.535, 0.79), (0.33, 0.60))
        ax.text(0.475, 0.70, "noise parameters", fontsize=7, color=INK2)
        ax.plot([0.68, 0.11], [0.245, 0.245], color=INK2, lw=1.0)
        _arrow(ax, (0.11, 0.245), (0.11, 0.41))
        ax.text(0.40, 0.255, "applied phase", fontsize=7, color=INK2, ha="center")
        _box(ax, 0.22, 0.02, 0.17, 0.13, "outputs/\nsummary, metrics,\ndecisions", size=fs_)
        _box(ax, 0.44, 0.02, 0.19, 0.13, "Dashboard,\ndocs, report", size=fs_)
        ax.plot([0.05, 0.05, 0.22], [0.41, 0.085, 0.085], color=INK2, lw=1.0)
        _arrow(ax, (0.20, 0.085), (0.22, 0.085)); _arrow(ax, (0.39, 0.085), (0.44, 0.085))
        _save(fig, path)
    return data, draw


LOOP_STEPS = ["Observe", "Reason", "Act", "Enforce", "Log"]


def fig_agent_loop(root, fs):
    data = {"kind": "diagram", "labels": LOOP_STEPS}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7.2, 2.5))
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        texts = ["1. Observe\nqueue and\npressure per\nphase; neigh-\nbours; ambulances",
                 "2. Reason\nLLM reads the\nprompt, answers\nJSON: phase +\nshort reason",
                 "3. Act\nvalidate; guard\nchecks pressure;\nfailure → Max-\nPressure's choice",
                 "4. Enforce\n5 s transition,\nmin green 15 s,\nmax green 60 s",
                 "5. Log\ndecisions.jsonl:\nstate, raw answer,\nlatency, applied\nphase"]
        colors = ["#f4f3f0", "#e6f6ef", "#f4f3f0", "#f4f3f0", "#f4f3f0"]
        for i, (t, c) in enumerate(zip(texts, colors)):
            _box(ax, 0.01 + i * 0.2, 0.12, 0.18, 0.76, t, fc=c, size=7.2)
            if i:
                _arrow(ax, (0.01 + i * 0.2 - 0.02, 0.5), (0.01 + i * 0.2, 0.5))
        ax.annotate("", xy=(0.10, 0.10), xytext=(0.90, 0.10),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9, connectionstyle="arc3,rad=-0.12"))
        ax.text(0.5, 0.93, "every 5 s per intersection, once its minimum green is met", ha="center",
                fontsize=7.5, color=INK2)
        _save(fig, path)
    return data, draw


# --- scenario --------------------------------------------------------------------------------

def fig_network(root, fs):
    rn = _j(root, "roadnet")
    inter = {i["id"]: (i["point"]["x"], i["point"]["y"], i["virtual"]) for i in rn["intersections"]}
    roads = [[(p["x"], p["y"]) for p in r["points"]] for r in rn["roads"]]
    data = {"source": FILES["roadnet"], "intersections": {k: list(v) for k, v in sorted(inter.items())},
            "roads": len(roads)}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(3.6, 3.6))
        for pts in roads:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color="#c9c8c3", lw=6, solid_capstyle="butt", zorder=1)
        for k, (x, y, virt) in inter.items():
            if not virt:
                ax.add_patch(plt.Rectangle((x - 12, y - 12), 24, 24, color=INK2, zorder=3))
                ax.text(x + 16, y + 16, k.replace("intersection_", "I"), fontsize=8, color=INK, zorder=4)
        ax.annotate("", xy=(0, -150), xytext=(200, -150), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.8))
        ax.text(100, -140, "200 m", ha="center", fontsize=8, color=INK2)
        ax.text(-190, 0, "W", fontsize=9, color=INK2, va="center"); ax.text(390, 0, "E", fontsize=9, color=INK2, va="center")
        ax.text(0, 390, "N", fontsize=9, color=INK2, ha="center"); ax.text(0, -195, "S", fontsize=9, color=INK2, ha="center")
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_xlim(-210, 410); ax.set_ylim(-210, 410)
        _save(fig, path)
    return data, draw


def fig_calibration(root, fs):
    c = _j(root, "calib")
    by = {}
    for x in c["sweep"]:
        by.setdefault(x["veh_per_hour"], []).append(x["maxpressure"])
    rates = sorted(by)
    att = [R(sum(m["att"] for m in by[r]) / len(by[r]), 2) for r in rates]
    backlog = [R(max(m["backlog_share"] for m in by[r]) * 100, 2) for r in rates]
    sel = c["selection"]
    data = {"source": FILES["calib"], "rates": rates, "att_mean": att, "backlog_worst_pct": backlog,
            "offpeak": sel["offpeak_veh_per_hour"], "peak": sel["peak_veh_per_hour"], "r_star": sel["R_star"]}

    def draw(path):
        plt = _plt()
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.7))
        for ax in (a1, a2):
            for v, lab in ((data["offpeak"], "off-peak"), (data["peak"], "peak"), (data["r_star"], "R*")):
                ax.axvline(v, color=MUTED, lw=0.8, ls="--")
            ax.set_xlabel("demand (veh/h, whole network)")
        a1.plot(rates, att, color=SLOT["mp"], lw=2, marker="o", ms=4)
        a1.set_title("MaxPressure ATT (mean of 3 seeds)", loc="left"); a1.set_ylabel("ATT (s)")
        a2.plot(rates, backlog, color=SLOT["mp"], lw=2, marker="o", ms=4)
        a2.axhline(2, color="#e34948", lw=0.8)
        a2.text(rates[-1], 2.6, "2% limit", ha="right", fontsize=7.5, color=INK2)
        a2.set_title("Backlog at 3600 s (worst seed)", loc="left"); a2.set_ylabel("% of generated vehicles")
        for (v, lab), yf in zip(((data["offpeak"], "off-peak"), (data["peak"], "peak"), (data["r_star"], "R*")),
                                (0.92, 0.80, 0.68)):
            a1.text(v + 150, yf, lab, fontsize=7, color=INK2, ha="left", transform=a1.get_xaxis_transform())
        _save(fig, path)
    return data, draw


# --- signal control results -------------------------------------------------------------------

FULL_ORDER = ["ft", "web", "mp", "llm", "gem"]
FULL_LABEL = {"mp": "MaxPressure", "web": "Webster fixed time", "ft": "FixedTime (4 phases, 30 s)",
              "llm": "LLM main: guarded hybrid, `llama3.2:3b`",
              "gem": "LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b`"}
SCN = [("indian_2x2_offpeak", "Indian 2x2, off-peak"), ("indian_2x2_peak", "Indian 2x2, peak"),
       ("jinan_3x4", "Jinan 3x4 (real flow)")]


def fig_att(root, fs):
    b = _j(root, "full")
    data = {"source": FILES["full"], "panels": {}}
    for sc, _ in SCN:
        arms = b["scenarios"][sc]
        data["panels"][sc] = {a: [R(arms[FULL_LABEL[a]]["att"][0], 2), R(arms[FULL_LABEL[a]]["att"][1], 2)]
                              for a in FULL_ORDER if FULL_LABEL[a] in arms}

    def draw(path):
        plt = _plt()
        fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.9), sharey=True)
        for ax, (sc, title) in zip(axes, SCN):
            p = data["panels"][sc]
            for i, a in enumerate(FULL_ORDER):
                if a not in p:
                    ax.text(0.02, i, "not run", transform=ax.get_yaxis_transform(), fontsize=7, color=MUTED, va="center")
                    continue
                m, s = p[a]
                ax.errorbar(m, i, xerr=s, fmt="o", color=SLOT[a], ms=6, elinewidth=1.4, capsize=3,
                            mec="white", mew=1)
                ax.text(m, i + 0.3, f"{m:.1f}", ha="center", fontsize=7, color=INK)
            ax.set_title(title, loc="left")
            ax.set_ylim(-0.6, len(FULL_ORDER) - 0.3)
            ax.grid(axis="y", visible=False)
        axes[0].set_yticks(range(len(FULL_ORDER)), [NAMES[a] for a in FULL_ORDER])
        fig.supxlabel("ATT (s), mean ± std over 3 seeds", fontsize=8, color=INK2)
        fig.tight_layout(w_pad=1.0)
        _save(fig, path)
    return data, draw


PAIRED = [("llm", "LLM main: guarded hybrid, `llama3.2:3b`"),
          ("gem", "LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b`")]


def fig_paired(root, fs):
    b = _j(root, "full")
    data = {"source": FILES["full"], "panels": {}}
    for sc in ("indian_2x2_offpeak", "indian_2x2_peak", "jinan_3x4", "indian_2x2_peak_amb"):
        data["panels"][sc] = {a: [R(x, 3) for x in b["paired"][sc][lab]["att_minus_mp"]]
                              for a, lab in PAIRED if lab in b["paired"][sc]}
    titles = {"indian_2x2_offpeak": "Off-peak", "indian_2x2_peak": "Peak", "jinan_3x4": "Jinan 3x4",
              "indian_2x2_peak_amb": "Peak + ambulances (5 seeds)"}

    def draw(path):
        plt = _plt()
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.1), sharey=True)
        for ax, (sc, p) in zip(axes, data["panels"].items()):
            ax.axvline(0, color=INK2, lw=0.9)
            for i, (a, _) in enumerate(PAIRED):
                if a in p:
                    xs = p[a]
                    ax.scatter(xs, [i] * len(xs), s=26, color=SLOT[a], edgecolor="white", lw=0.8, zorder=3)
                else:
                    ax.text(0.5, i, "not run", transform=ax.get_yaxis_transform(), fontsize=7, color=MUTED,
                            ha="center", va="center")
            ax.set_title(titles[sc], loc="left")
            ax.set_ylim(-0.6, 1.6); ax.grid(axis="y", visible=False)
        axes[0].set_yticks(range(len(PAIRED)), [NAMES[a] for a, _ in PAIRED])
        fig.supxlabel("ATT minus MaxPressure's on the same seed (s); left of 0 = faster", fontsize=8, color=INK2)
        fig.tight_layout(w_pad=0.8)
        _save(fig, path)
    return data, draw


BENCH_ARMS = ["v1", "v2", "hybrid", "v3", "hybrid_v3", "guarded_v3"]
BENCH_MODELS = ["qwen2.5:3b", "llama3.2:3b", "gemma4:e4b"]


def fig_bench(root, fs):
    b = _j(root, "bench")
    data = {"source": FILES["bench"],
            "queue": {arm: {m: R(b["arms"][arm]["models"][m]["queue_mean_per_intersection"], 3)
                            for m in BENCH_MODELS if m in b["arms"][arm]["models"]} for arm in BENCH_ARMS},
            "maxpressure": R(b["baselines"]["maxpressure"]["queue_mean_per_intersection"], 3),
            "webster": R(b["baselines"]["fixedtime_webster"]["queue_mean_per_intersection"], 3)}
    mcol = {"qwen2.5:3b": SLOT["web"], "llama3.2:3b": SLOT["llm"], "gemma4:e4b": SLOT["gem"]}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7.2, 2.9))
        for j, m in enumerate(BENCH_MODELS):
            xs = [i + (j - 1) * 0.22 for i, arm in enumerate(BENCH_ARMS) if m in data["queue"][arm]]
            ys = [data["queue"][arm][m] for arm in BENCH_ARMS if m in data["queue"][arm]]
            ax.bar(xs, ys, width=0.2, color=mcol[m], label=m, edgecolor="white", linewidth=1)
        ax.axhline(data["maxpressure"], color=SLOT["mp"], lw=1.6, label=f"MaxPressure ({data['maxpressure']:.2f})")
        ax.set_xticks(range(len(BENCH_ARMS)), ["v1\nplain", "v2\nplain", "hybrid\n(guided)", "v3\nplain",
                                               "hybrid_v3", "guarded_v3\n(pre-registered\npick: llama)"])
        ax.set_ylabel("queue per intersection (veh)")
        ax.set_title("LLM benchmark: Indian 2x2 peak, seed 0, first 600 s (lower is better)", loc="left")
        ax.legend(ncol=4, fontsize=7.5, loc="upper right")
        ax.set_ylim(0, max(max(v.values()) for v in data["queue"].values()) * 1.18)
        ax.grid(axis="x", visible=False)
        _save(fig, path)
    return data, draw


AMB_ORDER = ["mp", "web", "llm", "gem", "pre"]
AMB_CTL = {"mp": "maxpressure", "web": "fixedtime_webster", "llm": "llm_guarded_mp", "gem": "llm_guided_mp_v3",
           "pre": "preemption_mp"}


def fig_ambulance(root, fs):
    b = _j(root, "full")["emergency"]["controllers"]
    data = {"source": FILES["full"], "bars": {}}
    for a in AMB_ORDER:
        rel = b[AMB_CTL[a]]["ambulances_relevant"]
        data["bars"][a] = {"travel": R(rel["travel_time_mean_s"], 3), "stopped": R(rel["stopped_time_mean_s"], 3)}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7.2, 2.6))
        for i, a in enumerate(AMB_ORDER):
            t, s = data["bars"][a]["travel"], data["bars"][a]["stopped"]
            ax.barh(i, s, color=SLOT[a], height=0.55, edgecolor="white", linewidth=1.5)
            ax.barh(i, t - s, left=s, color=SLOT[a], alpha=0.35, height=0.55, edgecolor="white", linewidth=1.5)
            ax.text(t + 1.5, i, f"{t:.1f} s (stopped {s:.1f} s)", va="center", fontsize=7.5, color=INK)
        ax.set_yticks(range(len(AMB_ORDER)), [NAMES[a] for a in AMB_ORDER])
        ax.invert_yaxis(); ax.grid(axis="y", visible=False)
        ax.set_xlim(0, max(v["travel"] for v in data["bars"].values()) * 1.35)
        ax.set_xlabel("mean travel time of the signal-relevant ambulances (s); solid = stopped, light = moving")
        _save(fig, path)
    return data, draw


MS_ORDER = [("qwen", "qwen2.5:3b"), ("llama3b", "llama3.2:3b"), ("gem", "gemma4:e4b"), ("llama8b", "llama3.1:8b"),
            ("nemo", "nvidia/nemotron-3-ultra-550b-a55b")]


def fig_model_size(root, fs):
    b = _j(root, "ms")
    data = {"source": FILES["ms"], "models": {}}
    for k, m in MS_ORDER:
        p = b["full"]["indian_2x2_peak"]["models"][m]
        e = b["full"]["indian_2x2_peak_amb"]["models"][m]
        data["models"][m] = {"size_b": b["sizes"][m]["total_b"],
                             "att_vs_mp_pct": [R(100 * p["att_vs_mp"][x], 3) for x in ("mean", "min", "max")],
                             "amb_travel": R(e["ambulances"]["travel_time_mean_s"], 3),
                             "follows_pct": R(100 * p["follows_pressure_rate"], 2)}
    data["mp_amb"] = R(b["full"]["indian_2x2_peak_amb"]["baselines"]["maxpressure"]["ambulances"]["travel_time_mean_s"], 3)
    data["pre_amb"] = R(b["full"]["indian_2x2_peak_amb"]["baselines"]["preemption_mp"]["ambulances"]["travel_time_mean_s"], 3)

    def draw(path):
        plt = _plt()
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
        labels = [f"{m.split('/')[-1]}\n({data['models'][m]['size_b']:g} B)" for _, m in MS_ORDER]
        for i, (_, m) in enumerate(MS_ORDER):
            mean, lo, hi = data["models"][m]["att_vs_mp_pct"]
            a1.errorbar(mean, i, xerr=[[mean - lo], [hi - mean]], fmt="o", color=SLOT["gem"] if i >= 2 else MUTED,
                        ms=6, capsize=3, mec="white")
            a1.text(hi + 2, i, f"{mean:+.1f}%", va="center", fontsize=7.5, color=INK)
            a2.barh(i, data["models"][m]["amb_travel"], color=SLOT["gem"] if i >= 2 else MUTED, height=0.5,
                    edgecolor="white")
            a2.text(data["models"][m]["amb_travel"] + 2, i, f"{data['models'][m]['amb_travel']:.1f} s", va="center",
                    fontsize=7.5, color=INK)
        a1.axvline(0, color=SLOT["mp"], lw=1.4)
        a1.set_title("Peak: ATT vs MaxPressure", loc="left"); a1.set_xlabel("%\n(dot: mean; bar: range over 3 seeds)")
        a2.axvline(data["mp_amb"], color=SLOT["mp"], lw=1.4); a2.axvline(data["pre_amb"], color=SLOT["pre"], lw=1.4)
        a2.set_title("Ambulance travel time", loc="left")
        a2.set_xlabel("s\n(pink line: preemption; blue: MaxPressure)")
        a1.set_yticks(range(len(MS_ORDER)), labels); a1.invert_yaxis()
        for ax in (a1, a2):
            ax.grid(axis="y", visible=False)
        a2.set_xlim(0, max(v["amb_travel"] for v in data["models"].values()) * 1.25)
        fig.suptitle("EXPLORATORY: hybrid_v3 controller, only the model changes", fontsize=8, color=INK2, x=0.01,
                     ha="left", y=1.02)
        fig.tight_layout()
        _save(fig, path)
    return data, draw


def fig_camera(root, fs):
    b = _j(root, "camera")
    data = {"source": FILES["camera"], "main": {}, "sweep": {}}
    for sc in ("indian_2x2_offpeak", "indian_2x2_peak"):
        data["main"][sc] = {}
        for c, a in (("maxpressure", "mp"), ("llm_guarded_mp", "llm"), ("fixedtime_webster", "web")):
            data["main"][sc][a] = {lvl: [R(b["main"][sc][c][lvl]["att_vs_perfect"][k], 3)
                                         for k in ("pct_mean", "pct_min", "pct_max")]
                                   for lvl in ("junction", "crowded")}
        data["sweep"][sc] = {lvl: R(x["att_vs_perfect"]["pct_mean"], 3) if x.get("att_vs_perfect") else 0.0
                             for lvl, x in b["sweep"][sc].items()}
        data["sweep"][sc + "_peff"] = {k: R(v, 4) for k, v in b["effective_p_detect"][sc].items()}

    def draw(path):
        plt = _plt()
        fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [1, 1, 1.1]})
        for ax, sc, title in ((axes[0], "indian_2x2_offpeak", "Off-peak"), (axes[1], "indian_2x2_peak", "Peak")):
            ctl = ["mp", "llm", "web"]
            for j, lvl in enumerate(("junction", "crowded")):
                for i, a in enumerate(ctl):
                    m, lo, hi = data["main"][sc][a][lvl]
                    y = i + (j - 0.5) * 0.3
                    ax.errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="o" if j == 0 else "s", color=SLOT[a],
                                ms=5, capsize=2, mec="white", alpha=1 if j == 0 else 0.65)
            ax.axvline(0, color=INK2, lw=0.8)
            ax.set_yticks(range(3), ["MaxPressure", "LLM (guarded)", "Webster"]); ax.invert_yaxis()
            ax.set_title(title, loc="left"); ax.set_xlabel("ATT vs perfect counts (%)")
            ax.grid(axis="y", visible=False)
        fig.text(0.01, -0.03, "● junction camera   ■ crowded / far camera   (bar: range over 3 seeds)", fontsize=7, color=INK2)
        ax = axes[2]
        for sc, col, lab in (("indian_2x2_offpeak", SEQ[1], "off-peak"), ("indian_2x2_peak", SEQ[3], "peak")):
            s = data["sweep"][sc]
            ps = sorted(s, key=lambda k: -float(k.split("_p")[1]))
            ax.plot([float(k.split("_p")[1]) for k in ps], [s[k] for k in ps], marker="o", ms=4, lw=2, color=col)
            ax.plot([], [], color=col, lw=2, label=lab)
            for lvl, mk in (("junction", "o"), ("crowded", "s")):
                ax.scatter(data["sweep"][sc + "_peff"][lvl], data["main"][sc]["mp"][lvl][0], marker=mk, s=30,
                           color=col, edgecolor=INK, lw=0.6, zorder=4)
        ax.set_xlim(1.02, 0.45); ax.set_xlabel("p_detect (all classes)")
        ax.legend(fontsize=7, loc="upper left")
        ax.set_title("MaxPressure: misses only (line)\nvs camera levels (●■)", loc="left")
        ax.set_ylabel("ATT vs perfect (%)")
        fig.tight_layout(w_pad=0.6)
        _save(fig, path)
    return data, draw


def fig_decomposition(root, fs):
    b = _j(root, "camera")["decomposition"]
    parts = [("misses", "misses only"), ("false", "false detections only"), ("confusion", "class confusion only"),
             ("all", "all three (junction)")]
    data = {"source": FILES["camera"], "parts": {}}
    for k, _ in parts:
        data["parts"][k] = {sc: [R(b[k]["att_vs_perfect"][sc][x], 3) for x in ("pct_mean",)]
                            + [R(b[k]["att_vs_perfect"][sc]["min"], 3), R(b[k]["att_vs_perfect"][sc]["max"], 3)]
                            for sc in ("indian_2x2_offpeak", "indian_2x2_peak")}

    def draw(path):
        plt = _plt()
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.3), sharey=True)
        for ax, sc, title in ((axes[0], "indian_2x2_offpeak", "Off-peak"), (axes[1], "indian_2x2_peak", "Peak")):
            for i, (k, lab) in enumerate(parts):
                v = data["parts"][k][sc][0]
                ax.barh(i, v, color=SLOT["mp"] if k != "all" else INK2, height=0.55, edgecolor="white")
                ax.text(v + (0.15 if v >= 0 else -0.15), i, f"{v:+.1f}%", va="center",
                        ha="left" if v >= 0 else "right", fontsize=7.5, color=INK)
            ax.axvline(0, color=INK2, lw=0.8)
            ax.set_title(title, loc="left")
            ax.grid(axis="y", visible=False); ax.set_xlim(-1.5, 6.5)
        axes[0].set_yticks(range(len(parts)), [p[1] for p in parts]); axes[0].invert_yaxis()
        fig.supxlabel("MaxPressure ATT vs perfect counts, mean of 3 seeds (%)", fontsize=8, color=INK2)
        fig.tight_layout()
        _save(fig, path)
    return data, draw


# --- detector -------------------------------------------------------------------------------

def fig_det_training(root, fs):
    t = _j(root, "train")
    ep = [x for x in t["epochs"] if x.get("event") == "epoch"]
    data = {"source": FILES["train"], "epoch": [x["epoch"] for x in ep],
            "map50": [R(x["metrics"]["metrics/mAP50(B)"]) for x in ep],
            "map5095": [R(x["metrics"]["metrics/mAP50-95(B)"]) for x in ep]}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7.2, 2.5))
        ax.plot(data["epoch"], data["map50"], color=SEQ[1], lw=2)
        ax.plot(data["epoch"], data["map5095"], color=SEQ[3], lw=2)
        ax.text(data["epoch"][-1] + 0.5, data["map50"][-1], "mAP50", fontsize=7.5, color=INK, va="center")
        ax.text(data["epoch"][-1] + 0.5, data["map5095"][-1], "mAP50-95", fontsize=7.5, color=INK, va="center")
        ax.set_xlabel("epoch"); ax.set_ylabel("our validation split")
        ax.set_xlim(0, data["epoch"][-1] + 6)
        ax.set_title("YOLOv8n on IDD: validation accuracy per epoch", loc="left")
        _save(fig, path)
    return data, draw


DET_CLASSES = ["car", "motorcycle", "autorickshaw", "bus", "truck", "bicycle", "person"]


def fig_det_size(root, fs):
    e = _j(root, "test")["errors"]["miss_rate_by_size"]
    data = {"source": FILES["test"], "miss_pct": {c: {s: R(100 * e[c][s]["miss_rate"], 2) for s in ("small", "medium", "large")}
                                                  for c in DET_CLASSES}}

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(7.2, 2.6))
        for j, (s, col) in enumerate((("small", SEQ[0]), ("medium", SEQ[1]), ("large", SEQ[3]))):
            xs = [i + (j - 1) * 0.26 for i in range(len(DET_CLASSES))]
            ys = [data["miss_pct"][c][s] for c in DET_CLASSES]
            ax.bar(xs, ys, width=0.24, color=col, label=s, edgecolor="white", linewidth=1)
        ax.set_xticks(range(len(DET_CLASSES)), [c.replace("autorickshaw", "auto-\nrickshaw") for c in DET_CLASSES])
        ax.set_ylabel("miss rate (%)"); ax.legend(title="box size at 640 px (COCO buckets)", ncol=3, fontsize=7.5,
                                                   title_fontsize=7.5, loc="upper left")
        ax.set_ylim(0, 100); ax.grid(axis="x", visible=False)
        ax.set_title("Test split (official IDD val): misses by object size", loc="left")
        _save(fig, path)
    return data, draw


# --- screenshots ----------------------------------------------------------------------------

SHOTS = {"screen_overview": "docs/screenshots/overview_viewport.webp",
         "screen_replay": "docs/screenshots/network_replay_viewport.webp",
         "screen_detection": "docs/screenshots/live_detection_viewport.webp"}


def _shot(name):
    def fn(root, fs):
        src = root / SHOTS[name]
        data = {"source": SHOTS[name], "sha256": hashlib.sha256(src.read_bytes()).hexdigest()}

        def draw(path):
            from PIL import Image
            Image.open(src).convert("RGB").save(path, optimize=True)
        return data, draw
    return fn


FIGURES = {
    "architecture": fig_architecture, "agent_loop": fig_agent_loop, "network": fig_network,
    "calibration": fig_calibration, "att": fig_att, "paired": fig_paired, "bench": fig_bench,
    "ambulance": fig_ambulance, "model_size": fig_model_size, "camera": fig_camera,
    "decomposition": fig_decomposition, "det_training": fig_det_training, "det_size": fig_det_size,
    **{k: _shot(k) for k in SHOTS},
}


def make_all(root: Path, check: bool, only: list[str] | None = None) -> list[str]:
    from trafficsense.report.facts import facts
    fs = facts(root)
    errors = []
    out = root / FIG_DIR
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        if only and name not in only:
            continue
        data, draw = fn(root, fs)
        dj = out / f"{name}.data.json"
        text = json.dumps(data, indent=1, sort_keys=True) + "\n"
        if check:
            if not dj.is_file() or dj.read_text() != text:
                errors.append(f"{FIG_DIR}/{name}.png: data out of date (run scripts/make_report.py)")
            elif not (out / f"{name}.png").is_file():
                errors.append(f"{FIG_DIR}/{name}.png missing")
            continue
        if dj.is_file() and dj.read_text() == text and (out / f"{name}.png").is_file() and not only:
            continue
        dj.write_text(text)
        draw(out / f"{name}.png")
    return errors
