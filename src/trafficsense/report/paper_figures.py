"""Figures of the IEEE paper, drawn from outputs/ into docs/paper/figures/ as vector PDFs.

Sized for one IEEE column (3.5 in) and print size (text 6.5-7.5 pt). The plotted values are
the report's: each paper figure takes its data from the report figure of the same content
(trafficsense.report.figures), so the two can never disagree, and stores them in
`<name>.data.json`. `make_all(check=True)` recomputes the values and reports any figure whose
data file differs, without redrawing.
"""
from __future__ import annotations

import json
from pathlib import Path

from trafficsense.report import figures as rf

FIG_DIR = Path("docs/paper/figures")
W = 3.5                                     # IEEE column width, inches

INK, INK2, MUTED, SLOT, SEQ = rf.INK, rf.INK2, rf.MUTED, rf.SLOT, rf.SEQ
SHORT = {"mp": "MaxPressure", "web": "Webster plan", "pre": "MP + preemption",
         "llm": "LLM guarded\n(llama3.2:3b, pre-reg.)", "gem": "LLM hybrid\n(gemma4:e4b, explor.)"}


def _plt():
    plt = rf._plt()
    plt.rcParams.update({"font.size": 7, "axes.titlesize": 7.2, "axes.labelsize": 7, "xtick.labelsize": 6.6,
                         "ytick.labelsize": 6.6, "legend.fontsize": 6.6, "pdf.fonttype": 42,
                         "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                         "grid.linewidth": 0.5})
    return plt


def _save(fig, path: Path):
    fig.savefig(path, facecolor="white",
                metadata={"Creator": None, "Producer": None, "CreationDate": None})
    import matplotlib.pyplot as plt
    plt.close(fig)


# --- system overview ---------------------------------------------------------------------------

def fig_overview(root, fs):
    margin = round(fs["cfg.guard.margin"].value)
    data = {"kind": "diagram", "labels": rf.ARCH_LABELS, "guard_margin_pct": margin}

    def draw(path):
        plt = _plt()
        fig = plt.figure(figsize=(W, 2.45))
        ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        b, a = rf._box, rf._arrow
        s = 6.0
        ax.text(0.0, 0.975, "Offline perception", fontsize=6.8, fontweight="bold", color=INK2)
        b(ax, 0.00, 0.78, 0.27, 0.16, "IDD images\n(dash camera)", size=s)
        b(ax, 0.36, 0.78, 0.27, 0.16, "YOLOv8n\ndetector", size=s)
        b(ax, 0.72, 0.78, 0.28, 0.16, "Error model:\nmisses, labels,\nphantoms", size=s)
        a(ax, (0.27, 0.86), (0.36, 0.86)); a(ax, (0.63, 0.86), (0.72, 0.86))
        ax.text(0.0, 0.70, "Control loop (every 5 s, per intersection)", fontsize=6.8, fontweight="bold", color=INK2)
        b(ax, 0.00, 0.40, 0.27, 0.25, "CityFlow\n(exact state;\nall metrics\nmeasured here)", fc="#e8f1fb",
          ec=SLOT["mp"], size=s)
        b(ax, 0.36, 0.48, 0.27, 0.17, "Observation:\nexact or\nnoised counts", size=s)
        b(ax, 0.72, 0.48, 0.28, 0.17, "MaxPressure\nranking: top 2\n+ keep current", size=s)
        b(ax, 0.36, 0.22, 0.27, 0.19, f"Guard: pressure\nwithin {margin}% of top;\nmin/max green", size=s)
        b(ax, 0.72, 0.22, 0.28, 0.19, "LLM agent\n(Ollama, JSON\nschema)", fc="#e6f6ef", ec=SLOT["llm"], size=s,
          bold=True)
        a(ax, (0.27, 0.565), (0.36, 0.565)); a(ax, (0.63, 0.565), (0.72, 0.565))
        a(ax, (0.86, 0.48), (0.86, 0.41)); a(ax, (0.72, 0.315), (0.63, 0.315))
        a(ax, (0.36, 0.315), (0.135, 0.40))
        a(ax, (0.86, 0.78), (0.50, 0.65))
        b(ax, 0.72, 0.01, 0.28, 0.14, "neighbours' state;\nambulances (exact)", size=s)
        a(ax, (0.86, 0.15), (0.86, 0.22))
        b(ax, 0.00, 0.01, 0.27, 0.14, "outputs/: tables,\ndashboard, paper", size=s)
        a(ax, (0.135, 0.40), (0.135, 0.15))
        _save(fig, path)
    return data, draw


# --- results -----------------------------------------------------------------------------------

def fig_paired(root, fs):
    data, _ = rf.fig_paired(root, fs)
    titles = {"indian_2x2_offpeak": "Indian off-peak", "indian_2x2_peak": "Indian peak", "jinan_3x4": "Jinan 3x4",
              "indian_2x2_peak_amb": "Peak + ambulances"}

    def draw(path):
        plt = _plt()
        fig, axes = plt.subplots(4, 1, figsize=(W, 2.75), sharex=True, layout="constrained")
        for ax, (sc, p) in zip(axes, data["panels"].items()):
            ax.axvline(0, color=INK2, lw=0.8)
            for i, (arm, _) in enumerate(rf.PAIRED):
                if arm in p:
                    ax.scatter(p[arm], [i] * len(p[arm]), s=16, color=SLOT[arm], edgecolor="white", lw=0.5, zorder=3)
                else:
                    ax.text(-6.4, i, "not run", fontsize=6, color=MUTED, va="center")
            ax.set_yticks([0, 1], ["guarded (pre-reg.)", "gemma4 (explor.)"])
            ax.set_ylim(-0.7, 1.7); ax.grid(axis="y", visible=False)
            ax.set_title(titles[sc], loc="left", pad=1.5)
        axes[-1].set_xlabel("ATT minus MaxPressure's ATT on the same seed (s)")
        _save(fig, path)
    return data, draw


def fig_ambulance(root, fs):
    data, _ = rf.fig_ambulance(root, fs)

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(W, 1.6), layout="constrained")
        for i, k in enumerate(rf.AMB_ORDER):
            t, s = data["bars"][k]["travel"], data["bars"][k]["stopped"]
            ax.barh(i, s, color=SLOT[k], height=0.6, edgecolor="white", linewidth=1)
            ax.barh(i, t - s, left=s, color=SLOT[k], alpha=0.35, height=0.6, edgecolor="white", linewidth=1)
            ax.text(t + 2, i, f"{t:.1f} s ({s:.1f} stopped)", va="center", fontsize=6.4, color=INK)
        ax.set_yticks(range(len(rf.AMB_ORDER)), [SHORT[k] for k in rf.AMB_ORDER])
        ax.invert_yaxis(); ax.grid(axis="y", visible=False)
        ax.set_xlim(0, max(v["travel"] for v in data["bars"].values()) * 1.85)
        ax.set_xlabel("mean ambulance travel time (s)")
        _save(fig, path)
    return data, draw


def fig_camera(root, fs):
    cam, _ = rf.fig_camera(root, fs)
    dec, _ = rf.fig_decomposition(root, fs)
    data = {"source": cam["source"], "sweep": cam["sweep"],
            "mp_levels": {sc: cam["main"][sc]["mp"] for sc in cam["main"]}, "decomposition": dec["parts"]}
    parts = [("misses", "misses only"), ("false", "false det. only"), ("confusion", "confusion only"),
             ("all", "all (junction)")]

    def draw(path):
        plt = _plt()
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 1.9), gridspec_kw={"width_ratios": [1.15, 1]},
                                     layout="constrained")
        h = 0.36
        for j, (sc, col, lab) in enumerate((("indian_2x2_offpeak", SEQ[1], "off-peak"),
                                            ("indian_2x2_peak", SEQ[3], "peak"))):
            for i, (k, _) in enumerate(parts):
                v = data["decomposition"][k][sc][0]
                a1.barh(i + (j - 0.5) * h, v, height=h, color=col, edgecolor="white", linewidth=0.6,
                        label=lab if i == 0 else None)
        a1.axvline(0, color=INK2, lw=0.7)
        a1.set_yticks(range(len(parts)), [p[1] for p in parts]); a1.invert_yaxis()
        a1.grid(axis="y", visible=False)
        a1.set_xlabel("MaxPressure ATT vs\nperfect counts (%)")
        a1.set_title("(a) one error at a time", loc="left")
        a1.legend(loc="upper right", handlelength=1, borderaxespad=0.2)
        for sc, col, lab in (("indian_2x2_offpeak", SEQ[1], "off-peak"), ("indian_2x2_peak", SEQ[3], "peak")):
            s = data["sweep"][sc]
            ks = sorted(s, key=lambda k: -float(k.split("_p")[1]))
            a2.plot([float(k.split("_p")[1]) for k in ks], [s[k] for k in ks], marker="o", ms=2.5, lw=1.3, color=col)
            peff = cam["sweep"][sc + "_peff"]["junction"]
            a2.scatter(peff, data["mp_levels"][sc]["junction"][0], marker="*", s=40, color=col, edgecolor=INK, lw=0.4,
                       zorder=4)
        a2.set_xlim(1.03, 0.45); a2.set_xlabel("detection probability,\nno false detections")
        a2.set_title("(b) misses only", loc="left")
        a2.set_ylabel("ATT vs perfect (%)")
        _save(fig, path)
    return data, draw


def fig_model_size(root, fs):
    data, _ = rf.fig_model_size(root, fs)

    def draw(path):
        plt = _plt()
        fig, ax = plt.subplots(figsize=(W, 1.75), layout="constrained")
        order = [m for _, m in rf.MS_ORDER]
        for i, m in enumerate(order):
            mean, lo, hi = data["models"][m]["att_vs_mp_pct"]
            col = SLOT["gem"] if i >= 2 else MUTED
            ax.errorbar(mean, i, xerr=[[mean - lo], [hi - mean]], fmt="o", color=col, ms=4, capsize=2, mec="white",
                        mew=0.5, lw=0.9)
            ax.text(hi + 2, i, f"{mean:+.1f}%", va="center", fontsize=6.4, color=INK)
        ax.axvline(0, color=SLOT["mp"], lw=1.0)
        ax.text(1.5, -0.75, "MaxPressure", fontsize=6.2, color=SLOT["mp"], va="center")
        ax.set_yticks(range(len(order)),
                      [f"{m.split('/')[-1].replace('-a55b', '')} ({data['models'][m]['size_b']:g} B)" for m in order])
        ax.set_ylim(len(order) - 0.5, -1.1)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(min(v["att_vs_mp_pct"][1] for v in data["models"].values()) - 6,
                    max(v["att_vs_mp_pct"][2] for v in data["models"].values()) + 16)
        ax.set_xlabel("peak ATT vs MaxPressure (%)\n(dot: mean; bar: range over seeds)")
        fig.suptitle("EXPLORATORY: unguarded hybrid, only the model changes", x=0.01, ha="left", fontsize=7,
                     fontweight="bold", color=INK2)
        _save(fig, path)
    return data, draw


SCREEN = "docs/screenshots/network_replay_viewport.webp"
SCREEN_CROP = (296, 76, 1366, 768)          # main area of the 1366 x 768 viewport, sidebar dropped


def fig_dashboard(root, fs):
    import hashlib
    src = root / SCREEN
    data = {"kind": "screenshot", "source": SCREEN, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
            "crop": list(SCREEN_CROP)}

    def draw(path):
        from PIL import Image
        im = Image.open(src).convert("RGB").crop(SCREEN_CROP)
        im.save(path, "PDF", resolution=im.width / W, quality=92)
    return data, draw


FIGURES = {"overview": fig_overview, "paired": fig_paired, "ambulance": fig_ambulance, "camera": fig_camera,
           "model_size": fig_model_size, "dashboard": fig_dashboard}


def make_all(root: Path, check: bool) -> list[str]:
    from trafficsense.report.facts import facts
    fs = facts(root)
    errors = []
    out = root / FIG_DIR
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        data, draw = fn(root, fs)
        dj = out / f"{name}.data.json"
        text = json.dumps(data, indent=1, sort_keys=True) + "\n"
        if check:
            if not dj.is_file() or dj.read_text() != text:
                errors.append(f"{FIG_DIR}/{name}.pdf: data out of date (run scripts/make_paper.py)")
            elif not (out / f"{name}.pdf").is_file():
                errors.append(f"{FIG_DIR}/{name}.pdf missing")
            continue
        if dj.is_file() and dj.read_text() == text and (out / f"{name}.pdf").is_file():
            continue
        dj.write_text(text)
        draw(out / f"{name}.pdf")
    return errors
