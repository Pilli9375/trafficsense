"""Results: one tab per study, each with a takeaway line computed from the data, the charts and
the honesty notes. Everything comes from the results files the experiment scripts generate (the
same files the tables in docs/ are checked against) and, for the per-seed views, from the run
summaries those files list."""
from __future__ import annotations

import re

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trafficsense.dashboard import data, theme, ui

FULL = "outputs/full/results.json"
MODEL_SIZE = "outputs/model_size/model_size.json"
CAMERA = "outputs/camera_error/results.json"
DETECTOR = "outputs/perception/detector_test.json"
SCENARIO_CFG = "configs/scenarios/indian_2x2.yaml"
MP = ("maxpressure", None)
MAIN = ("llm_guarded_mp", "llama3.2:3b")
EXPL = ("llm_guided_mp_v3", "gemma4:e4b")
ORDER = [MP, ("fixedtime_webster", None), ("fixedtime", None), ("preemption_mp", None), MAIN, EXPL]


def _arms(full: dict, scen: str) -> tuple[dict, dict]:
    """(controller, model) -> entry, and -> the entry's name in results.json."""
    sc = full["scenarios"][scen]
    return ({(v["controller"], v["model"]): v for v in sc.values()},
            {(v["controller"], v["model"]): name for name, v in sc.items()})


def _seeds_phrase(lower: int, higher: int, n: int) -> str:
    """'faster on every seed' / 'slower on every seed' / 'faster on k of n seeds' (no threshold)."""
    if lower == n:
        return "faster on every seed"
    if higher == n:
        return "slower on every seed"
    return f"faster on {lower} of {n} seeds"


def _label(k: tuple) -> str:
    return theme.entity(*k)[0]


# ---- tab 1: signal control -----------------------------------------------------------------------
def forest(arms: dict, keys: list, x_title: str, metric: str = "att") -> go.Figure:
    """Mean ± std over seeds per controller; Fixed-time is noted at the edge when it is far off scale."""
    means = {k: arms[k][metric][0] for k in keys}
    others = [means[k] for k in keys if k[0] != "fixedtime"]
    span = max(others) - min(others)
    off = [k for k in keys if k[0] == "fixedtime" and means[k] > max(others) + 2 * max(span, 1.0)]
    on = [k for k in keys if k not in off]
    fig = go.Figure()
    fig.add_vline(x=means[MP], line=dict(color=theme.entity(*MP)[1], width=1, dash="dot"))
    for k in on:
        lab, col = theme.entity(*k)
        m, sd = arms[k][metric]
        fig.add_trace(go.Scatter(
            x=[m], y=[lab], mode="markers", marker=dict(color=col, size=12, line=dict(color=theme.SURFACE, width=2)),
            error_x=dict(type="data", array=[sd], color=col, thickness=1.6, width=6),
            hovertemplate=f"<b>%{{x:.1f}} s</b> ± {sd:.1f}<br>{ui.esc(lab)}<extra></extra>", showlegend=False))
    hi = max(means[k] + arms[k][metric][1] for k in on)
    lo = min(means[k] - arms[k][metric][1] for k in on)
    pad = 0.08 * (hi - lo) + 0.5
    for k in off:
        lab, col = theme.entity(*k)
        m, sd = arms[k][metric]
        fig.add_trace(go.Scatter(x=[hi + pad], y=[lab], mode="markers", marker=dict(color=col, size=11, symbol="triangle-right"),
                                 customdata=[[m, sd]], showlegend=False,
                                 hovertemplate="%{customdata[0]:.1f} ± %{customdata[1]:.1f} s (off this scale)<extra>"
                                               + ui.esc(lab) + "</extra>"))
        fig.add_annotation(x=hi + pad, y=lab, xanchor="right", xshift=-12, text=f"{m:.1f} ± {sd:.1f} s, off scale",
                           font=dict(color=theme.TEXT_2, size=11.5))
    order = [_label(k) for k in keys]
    fig.update_yaxes(categoryorder="array", categoryarray=order[::-1], showgrid=False)
    fig.update_xaxes(title_text=x_title, range=[lo - pad, hi + pad * 1.6], nticks=6)
    fig.update_layout(height=max(330, 70 + 46 * len(keys)), margin=dict(l=8, r=16, t=8, b=8))
    return fig


def per_seed_att(arm: dict) -> dict[int, float]:
    """Seed -> ATT from the summary.json of each run the results file lists for this arm."""
    out = {}
    for run in arm["runs"]:
        s = data.read_json(f"{run}/summary.json", "Run folder missing; results.json lists it.")
        out[int(s["provenance"]["seed"])] = s["metrics"]["att"]
    return out


def slopes(arms: dict, keys: list) -> go.Figure:
    """Paired by seed: MaxPressure's ATT -> the controller's, one line per seed; green = faster on that seed."""
    mp = per_seed_att(arms[MP])
    fig = make_subplots(rows=1, cols=len(keys), shared_yaxes=True, horizontal_spacing=0.05,
                        subplot_titles=[theme.short(*k) for k in keys])
    for j, k in enumerate(keys, start=1):
        att = per_seed_att(arms[k])
        col = theme.entity(*k)[1]
        for seed in sorted(att):
            a, b = mp[seed], att[seed]
            line = theme.GREEN if b < a else theme.RED if b > a else theme.TEXT_3
            fig.add_trace(go.Scatter(
                x=["MP", "arm"], y=[a, b], mode="lines+markers", showlegend=False,
                line=dict(color=line, width=2), marker=dict(size=9, color=[theme.entity(*MP)[1], col],
                                                            line=dict(color=theme.SURFACE, width=2)),
                customdata=["MaxPressure", theme.short(*k)],
                hovertemplate=f"seed {seed} · %{{customdata}}: <b>%{{y:.1f}} s</b><extra></extra>"), row=1, col=j)
            fig.add_annotation(x="arm", y=b, text=f"s{seed}", xshift=14, showarrow=False,
                               font=dict(size=10.5, color=theme.TEXT_3), row=1, col=j)
        fig.update_xaxes(showgrid=False, tickmode="array", tickvals=["MP", "arm"], ticktext=["MaxPressure", theme.short(*k)],
                         tickfont=dict(size=10.5), range=[-0.25, 1.35], row=1, col=j)
    fig.update_yaxes(title_text="ATT (s)", row=1, col=1)
    fig.update_annotations(selector=dict(xref="paper"), font=dict(color=theme.TEXT_2, size=12.5))
    fig.update_layout(height=330, margin=dict(l=8, r=20, t=30, b=8))
    return fig


def signal_control(full: dict) -> None:
    scen = st.segmented_control("Scenario", list(full["scenarios"]), default="indian_2x2_peak",
                                format_func=lambda s: theme.SCENARIO_LABELS[s], key="res_scen") or "indian_2x2_peak"
    arms, names = _arms(full, scen)
    keys = [k for k in ORDER if k in arms]
    n_seeds = sorted({data.derived(len(arms[k]["seeds"])) for k in keys})
    paired = full["paired"][scen]

    # takeaway: each LLM arm vs MaxPressure, with the paired seeds
    parts = []
    for k in (MAIN, EXPL):
        if k not in arms:
            continue
        d = data.derived(100 * (arms[k]["att"][0] / arms[MP]["att"][0] - 1))
        p = paired[names[k]]
        phrase = _seeds_phrase(p["seeds_lower_att"], p["seeds_higher_att"], data.derived(len(p["seeds"])))
        if k == MAIN:
            parts.append(f"Pre-registered LLM arm: <b>{ui.pct(d)}</b> average travel time vs MaxPressure, {phrase}")
        else:    # exploratory: in the sentence, never the emphasised number
            parts.append(f"Exploratory gemma4 hybrid: {ui.pct(d)}, {phrase}")
    ui.takeaway(". ".join(parts) + ".", ["pre-registered", "no significance test"], FULL)

    c1, c2 = st.columns([1, 1.25], gap="medium")
    with c1:
        ui.chart(forest(arms, keys, "ATT (s) · dotted line: MaxPressure"), FULL, key="res_att",
                 title="Average travel time", subtitle=f"Mean ± std over {'/'.join(str(n) for n in n_seeds)} seeds")
    with c2:
        pkeys = [k for k in keys if k not in (MP, ("fixedtime", None))]
        runs = [f"{r}/summary.json" for k in [MP] + pkeys for r in arms[k]["runs"]]
        ft = ""
        if ("fixedtime", None) in arms:
            d = paired[names[("fixedtime", None)]]["att_minus_mp"]
            ft = f" Fixed-time is left out: {min(d):+.1f} to {max(d):+.1f} s per seed."
        ui.chart(slopes(arms, pkeys), FULL, *runs, key="res_slope", title="Paired by seed",
                 subtitle="One line per seed (same flow file): green = faster than MaxPressure, red = slower." + ft)

    rows = [{"Controller": _label(k), "Seeds": len(arms[k]["seeds"]),
             "ATT (s)": ui.mean_std(arms[k]["att"]),
             "Queue / intersection (veh)": ui.mean_std(arms[k]["queue_mean_per_intersection"], 2),
             "Waiting / vehicle (s)": ui.mean_std(arms[k]["waiting_time_mean"]),
             "Finished trips": ui.mean_std(arms[k]["throughput"], 0)} for k in keys]
    colours = {_label(k): theme.entity(*k)[1] for k in keys}
    ui.html(ui.card(ui.card_header("All metrics", "Mean ± std over seeds", [FULL])
                    + ui.table(rows, num=["Seeds", "ATT (s)", "Queue / intersection (veh)", "Waiting / vehicle (s)", "Finished trips"],
                               colours=colours, first="Controller")))

    llm = [v for v in full["llm"].values() if v["scenario"] == scen]
    if llm:
        rows = []
        for v in llm:
            k = next(k for k in keys if k[0].startswith("llm_") and k[1] and k[1] in v["arm"])
            rows.append({"Arm": _label(k), "Calls": f"{v['calls']:,}",
                         "Failed": f"{v['failures']} ({ui.pct(100 * v['failure_rate'], 2, sign=False)})",
                         "Mean latency (s)": f"{v['latency_mean_s']:.2f}",
                         "p95 per run (s)": "–".join(f"{x:.2f}" for x in v["latency_p95_s_range"]),
                         "Answer ≠ MaxPressure": ui.pct(100 * v["mp_disagreement_rate"], sign=False),
                         "Guard override": ui.pct(100 * v["guard_override_rate"], sign=False)
                         if v.get("guard_override_rate") is not None else "no guard",
                         "Applied ≠ MaxPressure": ui.pct(100 * v["applied_differs_rate"], sign=False),
                         "Wall time (h)": f"{v['wall_time_h']:.1f}"})
        ui.html(ui.card(ui.card_header("LLM decisions", "Every call, all seeds", [FULL])
                        + ui.table(rows, num=[c for c in rows[0] if c != "Arm"],
                                   colours={_label(k): theme.entity(*k)[1] for k in keys}, first="Arm")))
    ui.why(
        "<p><b>Design.</b> Plan, arms and analysis were committed before any run (pre-registered). Every controller "
        "sees the same flow file per seed, so the paired view is the fairer comparison. No significance test was "
        "pre-registered.</p>"
        "<p><b>Arms.</b> <i>LLM main</i> is the pick of the pre-registered selection rule: MaxPressure with a guard "
        "that only applies the LLM's choice when its pressure is close to the best. The <i>gemma4:e4b</i> arm is "
        "<b>exploratory, not selected by the rule</b> (it failed the latency limit) and has no guard; on this GPU it "
        "is not real-time (the simulator waited for each call).</p>"
        "<p><b>Reproducibility.</b> Deterministic baselines repeat exactly (Jinan's flow file is fixed, hence zero "
        "spread). Ollama on the GPU is not bit-for-bit deterministic even at temperature 0, so LLM runs can be "
        "inspected and replayed from their decision logs but not re-run identically.</p>")


# ---- tab 2: ambulances ------------------------------------------------------------------------------
def emergency(full: dict, ms: dict) -> None:
    em = full["emergency"]
    scfg = data.read_yaml(SCENARIO_CFG, "")
    ctl = em["controllers"]
    models = ms["full"]["indian_2x2_peak_amb"]["models"]
    rows = [((c, m), ctl[c]["ambulances_relevant"]) for c, m in ORDER if c in ctl]
    rows += [(("llm_guided_mp_v3", m), v["ambulances"]) for m, v in models.items() if m != "gemma4:e4b"]
    mp = ctl["maxpressure"]["ambulances_relevant"]["travel_time_mean_s"]
    main_t = ctl["llm_guarded_mp"]["ambulances_relevant"]["travel_time_mean_s"]
    expl_t = ctl["llm_guided_mp_v3"]["ambulances_relevant"]["travel_time_mean_s"]
    pre = ctl["preemption_mp"]["ambulances_relevant"]["travel_time_mean_s"]
    ui.takeaway(f"Told where ambulances are, the pre-registered LLM arm cuts their mean travel time from "
                f"<b>{mp:.1f} s</b> (MaxPressure) to <b>{main_t:.1f} s</b>; rule-based preemption: {pre:.1f} s; "
                f"the exploratory gemma4 hybrid: {expl_t:.1f} s.",
                ["pre-registered", "no significance test"], FULL)

    # where the time goes: stopped vs the rest of the trip
    labels = [_label(k) for k, _ in rows]
    stopped = [a["stopped_time_mean_s"] for _, a in rows]
    travel = [a["travel_time_mean_s"] for _, a in rows]
    rest = [data.derived(t - s) for t, s in zip(travel, stopped)]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=stopped, orientation="h", name="stopped", marker=dict(color=theme.rgba(theme.RED, .85)),
                         customdata=travel, hovertemplate="stopped <b>%{x:.1f} s</b> of %{customdata:.1f} s<extra>%{y}</extra>"))
    fig.add_trace(go.Bar(y=labels, x=rest, orientation="h", name="rest of the trip",
                         marker=dict(color=[theme.entity(*k)[1] for k, _ in rows]),
                         customdata=travel, text=[f"{t:.1f} s" for t in travel], textposition="outside", cliponaxis=False,
                         textfont=dict(color=theme.TEXT, size=12),
                         hovertemplate="moving or entering <b>%{x:.1f} s</b><br>travel time %{customdata:.1f} s<extra>%{y}</extra>"))
    fig.add_vline(x=pre, line=dict(color=theme.entity("preemption_mp", None)[1], width=1, dash="dot"))
    fig.update_layout(barmode="stack", bargap=0.38, height=70 + 40 * len(rows), margin=dict(l=8, r=56, t=28, b=8),
                      legend=dict(y=1.0, yanchor="bottom", x=0, traceorder="normal"))
    fig.update_yaxes(categoryorder="array", categoryarray=labels[::-1], showgrid=False)
    fig.update_xaxes(title_text="mean travel time of the signal-relevant ambulances (s) · dotted: preemption", rangemode="tozero")
    ui.chart(fig, FULL, MODEL_SIZE, key="res_amb", grow="h", title="Where the ambulances' time goes",
             subtitle=f"Mean over the {ctl['maxpressure']['ambulances_relevant']['n']} ambulances whose route crosses a "
                      "signal, all seeds pooled. Red: stopped in the network; colour: the rest of the trip.",
             tags=["exploratory"])

    tbl = []
    for c, m in ORDER:
        if c not in ctl:
            continue
        v = ctl[c]
        vp = v["vs_preemption_relevant"]
        tbl.append({"Controller": _label((c, m)), "ATT, all traffic (s)": ui.mean_std(v["att_s"]),
                    "Queue / intersection (veh)": ui.mean_std(v["queue_mean_per_intersection"], 2),
                    "Ambulances finished": f"{v['ambulances_relevant']['finished']} / {v['ambulances_relevant']['n']}",
                    "Median travel (s)": f"{v['ambulances_relevant']['travel_time_median_s']:.1f}",
                    "vs preemption, paired": "reference" if c == "preemption_mp" else
                    f"{vp['mean_diff_s']:+.1f} s · {vp['faster']} faster, {vp['slower']} slower"})
    ui.html(ui.card(ui.card_header("Per controller", "Pre-registered arms; the model-size rows are in the next tab", [FULL])
                    + ui.table(tbl, num=["ATT, all traffic (s)", "Queue / intersection (veh)", "Ambulances finished",
                                         "Median travel (s)"],
                               colours={_label(k): theme.entity(*k)[1] for k in ORDER}, first="Controller",
                               wide="vs preemption, paired")))
    amb = ctl["maxpressure"]
    ui.why(
        f"<p><b>Design.</b> Pre-registered: peak traffic plus ambulances at {scfg['emergency']['veh_per_hour']} per "
        f"hour (an assumption), seeds {', '.join(str(s) for s in em['provenance']['seeds'])}. The primary metric is "
        f"the mean travel time of the {amb['ambulances_relevant']['n']} ambulances (of {amb['ambulances_all']['n']}) "
        "whose route crosses a signal, pooled over seeds; the same ambulances run under every controller. Travel "
        "time runs from the scheduled start (so it includes any wait to enter); stopped time counts seconds below "
        "0.1 m/s inside the network.</p>"
        "<p><b>Limits.</b> In CityFlow nobody yields and nothing overtakes, so only the signal can help an "
        "ambulance. LLM arms see ambulances listed in their prompt and do not preempt. Model-size rows "
        "(Nemotron, llama3.1:8b, qwen2.5:3b, the llama3.2:3b hybrid) are <b>exploratory</b>, added after the main "
        "results.</p>" + f'<p>{ui.source_chip(SCENARIO_CFG, align="left")}</p>')


# ---- tab 3: model size ------------------------------------------------------------------------------
def active_b(ms: dict, model: str) -> str:
    """Active (or effective) parameters in billions as written in model_size.json, e.g. '4' for 'E4B: effective 4'."""
    m = re.search(r"(\d+(?:\.\d+)?)(?=\s*(?:\(|$))", ms["sizes"][model]["active"])
    if not m:
        raise ValueError(f"model_size.json: cannot read the active parameters of {model}: {ms['sizes'][model]['active']!r}")
    return m.group(1)


def model_size(ms: dict) -> None:
    scen = st.segmented_control("Scenario", list(ms["full"]), default="indian_2x2_peak",
                                format_func=lambda s: theme.SCENARIO_LABELS[s], key="ms_scen") or "indian_2x2_peak"
    blk = ms["full"][scen]
    order = sorted(blk["models"], key=lambda m: ms["sizes"][m]["total_b"])
    n_runs = {m: data.derived(len(blk["models"][m]["runs"])) for m in order}
    worse_all = [m for m in order if blk["models"][m]["att_vs_mp"]["seeds_worse"] == n_runs[m]]
    # the boundary: first model (by size) from which no model is worse than MaxPressure on every seed
    after = [i for i in range(len(order)) if not any(m in worse_all for m in order[i:])]
    boundary = order[after[0]] if after else None
    if boundary is not None:
        bad = ", ".join(f"{theme.model_short(m)} {ui.pct(100 * blk['models'][m]['att_vs_mp']['mean'], 0)}" for m in worse_all)
        text = ((f"The smaller models make the hybrid slower than MaxPressure on every seed ({bad}). " if worse_all else "")
                + f"From <b>{theme.model_short(boundary)}</b> (~{active_b(ms, boundary)}B active) up, travel time is "
                  "MaxPressure's within seed-to-seed noise.")
    else:
        text = "Every model makes the hybrid slower than MaxPressure on every seed."
    ui.takeaway(text, ["exploratory", "hosted, not local", "no significance test"], MODEL_SIZE)

    labels = [f"{theme.model_short(m)}<br><span style='font-size:11px'>{ms['sizes'][m]['total_b']:g}B total</span>"
              for m in order]
    cols = [theme.entity("llm_guided_mp_v3", m)[1] for m in order]
    c1, c2 = st.columns([1.35, 1], gap="medium")
    with c1:
        a = [blk["models"][m]["att_vs_mp"] for m in order]
        mean = [100 * v["mean"] for v in a]
        fig = go.Figure()
        if boundary is not None:
            i0 = order.index(boundary)
            fig.add_vrect(x0=i0 - 0.45, x1=len(order) - 0.55, fillcolor=theme.rgba(theme.GREEN, .07), line_width=0)
            fig.add_annotation(x=(i0 + len(order) - 1) / 2, y=1.0, yref="paper", yanchor="bottom",
                               text=f"≈ MaxPressure from ~{active_b(ms, boundary)}B up",
                               font=dict(color="#4ade80", size=12.5))
        if worse_all:
            idx = [order.index(m) for m in worse_all]
            fig.add_vrect(x0=min(idx) - 0.45, x1=max(idx) + 0.45, fillcolor=theme.rgba(theme.RED, .07), line_width=0)
            fig.add_annotation(x=(min(idx) + max(idx)) / 2, y=1.0, yref="paper", yanchor="bottom",
                               text="slower on every seed", font=dict(color="#fb7185", size=12.5))
        fig.add_hline(y=0, line=dict(color=theme.entity(*MP)[1], width=1, dash="dot"))
        fig.add_trace(go.Scatter(
            x=list(range(len(order))), y=mean, mode="markers", marker=dict(color=cols, size=13, line=dict(color=theme.SURFACE, width=2)),
            error_y=dict(type="data", symmetric=False, array=[100 * (v["max"] - v["mean"]) for v in a],
                         arrayminus=[100 * (v["mean"] - v["min"]) for v in a], color=theme.TEXT_3, thickness=1.4, width=6),
            customdata=[[100 * v["min"], 100 * v["max"]] for v in a], text=[theme.model_short(m) for m in order],
            hovertemplate="<b>%{y:+.1f}%</b> vs MaxPressure<br>seed range %{customdata[0]:+.1f} to %{customdata[1]:+.1f}%"
                          "<extra>%{text}</extra>", showlegend=False))
        fig.update_xaxes(tickmode="array", tickvals=list(range(len(order))), ticktext=labels, showgrid=False,
                         zeroline=False, range=[-0.6, len(order) - 0.4])
        fig.update_yaxes(title_text="ATT vs MaxPressure (+ = slower)", ticksuffix="%")
        fig.update_layout(margin=dict(l=8, r=12, t=34, b=8))
        ui.chart(fig, MODEL_SIZE, key="ms_att", height=360, title="Average travel time vs MaxPressure, by model size",
                 subtitle=f"Mean and range over {len(blk['seeds'])} seeds; models ordered by total parameters (not to scale)",
                 tags=["exploratory"])
    with c2:
        fp = [100 * blk["models"][m]["follows_pressure_rate"] for m in order]
        fig = go.Figure(go.Bar(x=[theme.model_short(m) for m in order], y=fp, marker=dict(color=cols),
                               text=[f"{v:.0f}%" for v in fp], textposition="outside", cliponaxis=False,
                               textfont=dict(color=theme.TEXT, size=12), hovertemplate="%{x}<br><b>%{y:.1f}%</b><extra></extra>"))
        fig.update_yaxes(title_text="% of successful calls", range=[0, 112], ticksuffix="%")
        fig.update_xaxes(showgrid=False, tickfont=dict(size=11), tickangle=0, tickmode="array",
                         tickvals=[theme.model_short(m) for m in order],
                         ticktext=[theme.model_short(m).replace(" 3 Ultra", "<br>3 Ultra").replace(":", "<br>") for m in order])
        fig.update_layout(margin=dict(l=8, r=12, t=34, b=8))
        ui.chart(fig, MODEL_SIZE, key="ms_fp", height=360, grow="v", title="Answers that pick the highest-pressure phase",
                 subtitle="Share of successful calls")

    rows = []
    for m in order:
        v = blk["models"][m]
        a = v["att_vs_mp"]
        rows.append({"Model": theme.model_short(m),
                     "Params total / active (B)": f"{ms['sizes'][m]['total_b']:g} / {ms['sizes'][m]['active']}",
                     "ATT (s)": ui.mean_std(v["att_s"]),
                     "vs MaxPressure, mean (range)": f"{ui.pct(100 * a['mean'])} ({100 * a['min']:+.1f} to {100 * a['max']:+.1f})",
                     "Seeds worse": f"{a['seeds_worse']} of {len(v['runs'])}",
                     "Failed → MaxPressure": f"{v['failures']} of {v['calls']:,}"
                                             + ("" if v["retries"] is None else f" · {v['retries']:,} retries"),
                     "Minutes / run": f"{v['wall_time_s_mean'] / 60:.0f}",
                     "Served model": ", ".join(v["served_models"])})
    ui.html(ui.card(ui.card_header("Per model", None, [MODEL_SIZE])
                    + ui.table(rows, num=["ATT (s)", "vs MaxPressure, mean (range)", "Seeds worse", "Failed → MaxPressure",
                                          "Minutes / run"],
                               colours={theme.model_short(m): theme.entity("llm_guided_mp_v3", m)[1] for m in order}, first="Model",
                               wide="Served model")))
    ui.why(
        f"<p><b>{ms['provenance']['label'].capitalize()}.</b> Its plan was committed before its runs; it changes "
        "none of the pre-registered results. The controller is held fixed (the gemma4 hybrid's setup); only the model "
        "changes. Local models are 4-bit quantized on the laptop GPU.</p>"
        "<p><b>Hosted arm.</b> Nemotron 3 Ultra runs on NVIDIA NIM: its prompts leave the machine, the served model "
        "can change, and throttled calls fall back to MaxPressure's choice (counted in the table).</p>"
        "<p><b>The boundary.</b> The shaded split is computed from the data: the first model, in size order, from "
        "which no model is slower than MaxPressure on every seed. \"Within noise\" means the seed ranges cross zero or "
        "lie close to it; with 3–5 seeds that is not evidence of a real gain over MaxPressure.</p>")


# ---- tab 4: camera errors ----------------------------------------------------------------------------
def camera(cam: dict) -> None:
    main = cam["main"]
    scens = list(main)
    lv = ("junction", "crowded")
    ctl_keys = {"maxpressure": MP, "llm_guarded_mp": MAIN, "fixedtime_webster": ("fixedtime_webster", None)}
    unaffected = [c for c in ctl_keys if all(main[sc][c][l]["att_vs_perfect"]["pct_min"] == 0 == main[sc][c][l]["att_vs_perfect"]["pct_max"]
                                             for sc in scens for l in lv)]
    affected = [c for c in ctl_keys if c not in unaffected]
    mp = [main[sc]["maxpressure"][l]["att_vs_perfect"]["pct_mean"] for sc in scens for l in lv]
    llm = [main[sc]["llm_guarded_mp"][l]["att_vs_perfect"]["pct_mean"] for sc in scens for l in lv]
    tail = (f"; {' and '.join(theme.short(*ctl_keys[c]) for c in unaffected)} reads no counts and is unaffected"
            if unaffected else "")
    ui.takeaway(f"Our detector's measured errors add <b>{min(mp):.1f}–{max(mp):.1f}%</b> to MaxPressure's travel time "
                f"and {min(llm):.1f}–{max(llm):.1f}% to the LLM arm's{tail}.",
                ["pre-registered", ("decomposition post-hoc", "post"), "ambulances not noised"], CAMERA)

    # paired change per scenario and camera level
    rows = [(sc, l) for sc in scens for l in lv]
    ylab = [f"{theme.SCENARIO_LABELS[sc].split(' · ')[1]} · {theme.LEVEL_LABELS[l].lower()}" for sc, l in rows]
    fig = go.Figure()
    for c in affected:
        lab, col = theme.entity(*ctl_keys[c])
        a = [main[sc][c][l]["att_vs_perfect"] for sc, l in rows]
        fig.add_trace(go.Scatter(
            x=[v["pct_mean"] for v in a], y=ylab, mode="markers", name=lab, offsetgroup=lab,
            marker=dict(color=col, size=12, line=dict(color=theme.SURFACE, width=2)),
            error_x=dict(type="data", symmetric=False, array=[v["pct_max"] - v["pct_mean"] for v in a],
                         arrayminus=[v["pct_mean"] - v["pct_min"] for v in a], color=col, thickness=1.5, width=5),
            customdata=[[v["pct_min"], v["pct_max"]] for v in a],
            hovertemplate="<b>%{x:+.1f}%</b> (seeds %{customdata[0]:+.1f} to %{customdata[1]:+.1f}%)<extra>" + ui.esc(lab) + "</extra>"))
    fig.add_vline(x=0, line=dict(color=theme.TEXT_3, width=1, dash="dot"))
    fig.update_layout(scattermode="group", scattergap=0.45, height=330, margin=dict(l=8, r=16, t=30, b=8),
                      legend=dict(y=1.0, yanchor="bottom"))
    fig.update_yaxes(categoryorder="array", categoryarray=ylab[::-1], showgrid=False)
    fig.update_xaxes(title_text="ATT change vs exact counts (+ = slower)", ticksuffix="%")
    note = (f"{', '.join(theme.short(*ctl_keys[c]) for c in unaffected)}: unaffected (identical runs at every level)."
            if unaffected else None)
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        ui.chart(fig, CAMERA, key="cam_main", title="What camera errors cost",
                 subtitle="Paired by seed; mean and seed range. " + (note or ""))
    with c2:
        sweep = cam["sweep"]
        fig = make_subplots(rows=1, cols=len(scens), horizontal_spacing=0.1,
                            subplot_titles=[theme.SCENARIO_LABELS[s].split(" · ")[1] for s in scens])
        mp_lab, mp_col = theme.entity(*MP)
        for j, sc in enumerate(scens, start=1):
            keys = sorted(sweep[sc], key=lambda k: float(k.split("_p")[1]))
            p = [float(k.split("_p")[1]) for k in keys]
            fig.add_trace(go.Scatter(
                x=p, y=[sweep[sc][k]["att"][0] for k in keys], mode="lines+markers", showlegend=False,
                line=dict(color=mp_col, width=2), marker=dict(size=8, color=mp_col),
                error_y=dict(type="data", array=[sweep[sc][k]["att"][1] for k in keys], color=theme.TEXT_3, thickness=1, width=3),
                hovertemplate="detection rate %{x:.2f}: <b>%{y:.1f} s</b><extra>uniform sweep</extra>"), row=1, col=j)
            for lvl, sym in (("junction", "diamond"), ("crowded", "square")):
                fig.add_trace(go.Scatter(
                    x=[cam["effective_p_detect"][sc][lvl]], y=[main[sc]["maxpressure"][lvl]["att"][0]],
                    mode="markers+text", text=[theme.LEVEL_LABELS[lvl].split(" ")[0]], textposition="top center",
                    textfont=dict(color=theme.TEXT_2, size=11), showlegend=False,
                    marker=dict(symbol=sym, size=11, color=theme.SURFACE, line=dict(color=mp_col, width=2)),
                    hovertemplate="effective detection rate %{x:.3f}: <b>%{y:.1f} s</b><extra>" + theme.LEVEL_LABELS[lvl] + "</extra>"),
                    row=1, col=j)
            fig.update_xaxes(title_text="detection rate", autorange="reversed", row=1, col=j)
        fig.update_yaxes(title_text="MaxPressure ATT (s)", row=1, col=1)
        fig.update_annotations(selector=dict(xref="paper"), font=dict(color=theme.TEXT_2, size=12.5))
        fig.update_layout(height=330, margin=dict(l=8, r=8, t=30, b=8))
        ui.chart(fig, CAMERA, key="cam_sweep", title="MaxPressure vs detection rate",
                 subtitle="Uniform sweep: the same rate for every class, no false detections. Hollow: the two camera levels.")

    # post-hoc decomposition as a waterfall per scenario
    dec = cam["decomposition"]
    comp = [("misses", "Misses"), ("false", "False detections"), ("confusion", "Class confusion")]
    fig = make_subplots(rows=1, cols=len(scens), shared_yaxes=True, horizontal_spacing=0.06,
                        subplot_titles=[theme.SCENARIO_LABELS[s].split(" · ")[1] for s in scens])
    for j, sc in enumerate(scens, start=1):
        vals = [dec[k]["att_vs_perfect"][sc] for k, _ in comp]
        tot, allv = dec["sum_abc"][sc], dec["all"]["att_vs_perfect"][sc]
        xs = [lab.replace(" ", "<br>") for _, lab in comp] + ["Sum of<br>the three", "All three,<br>measured"]
        ys = [v["mean"] for v in vals] + [tot["mean"], allv["mean"]]
        pcts = [v["pct_mean"] for v in vals] + [tot["pct_mean"], allv["pct_mean"]]
        pos = list(range(len(xs)))
        fig.add_trace(go.Waterfall(
            x=pos, y=ys, measure=["relative"] * 3 + ["total", "absolute"], customdata=pcts, width=0.62,
            text=[f"{v:+.2f} s" for v in ys], textposition="outside", textfont=dict(color=theme.TEXT, size=11.5),
            increasing=dict(marker=dict(color=theme.rgba(theme.RED, .85))), decreasing=dict(marker=dict(color=theme.rgba(theme.GREEN, .85))),
            totals=dict(marker=dict(color=theme.entity(*MP)[1])), connector=dict(line=dict(color=theme.BORDER_2, width=1, dash="dot")),
            hovertemplate="<b>%{y:+.2f} s</b> (%{customdata:+.1f}%)<extra></extra>", showlegend=False), row=1, col=j)
        # each component's seed range, drawn at the step it adds
        base = 0.0
        for k, v in enumerate(vals):
            lo, hi = base + v["min"], base + v["max"]
            fig.add_trace(go.Scatter(x=[pos[k] + 0.4] * 2, y=[lo, hi], mode="lines+markers", line=dict(color=theme.TEXT_2, width=1.4),
                                     marker=dict(symbol="line-ew", size=7, line=dict(color=theme.TEXT_2, width=1.4)),
                                     customdata=[v["min"], v["max"]], showlegend=False,
                                     hovertemplate="seed range %{customdata:+.2f} s<extra></extra>"), row=1, col=j)
            base = data.derived(base + v["mean"])
        a = allv
        fig.add_trace(go.Scatter(x=[pos[-1] + 0.4] * 2, y=[a["min"], a["max"]], mode="lines+markers", line=dict(color=theme.TEXT_2, width=1.4),
                                 marker=dict(symbol="line-ew", size=7, line=dict(color=theme.TEXT_2, width=1.4)),
                                 customdata=[a["min"], a["max"]], showlegend=False,
                                 hovertemplate="seed range %{customdata:+.2f} s<extra></extra>"), row=1, col=j)
        fig.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(size=11), tickangle=0, tickmode="array", tickvals=pos,
                         ticktext=xs, range=[-0.6, len(xs) - 0.2], row=1, col=j)
    fig.add_hline(y=0, line=dict(color=theme.BORDER_2, width=1))
    fig.update_yaxes(title_text="ATT change vs exact counts (s)", row=1, col=1)
    fig.update_annotations(selector=dict(xref="paper"), font=dict(color=theme.TEXT_2, size=12.5))
    fig.update_layout(height=360, margin=dict(l=8, r=8, t=30, b=8))
    ui.chart(fig, CAMERA, key="cam_dec", title="Which junction-camera error costs what (MaxPressure)",
             subtitle="Each error type switched on alone, then summed, next to all three together. Red adds time, green "
                      "saves it; whiskers: seed range of each step.",
             tags=[("post-hoc", "post")])
    ui.why(
        "<p><b>Pre-registered.</b> The simulator stays exact; only what the controllers <i>observe</i> is noised with "
        "the error rates measured from our detector on the IDD test split. Ambulance positions are assumed to come "
        "from GPS / V2X and are <b>never noised</b>. IDD is dashcam footage, so its errors are a proxy for a junction "
        "camera. One pre-registered check (realised detection rates within a fixed tolerance of their targets) failed "
        "narrowly for a rare class; docs/camera_error.md explains it.</p>"
        "<p><b>Post-hoc.</b> The decomposition was planned after the main batch: misses, false detections and class "
        "confusion each switched on alone. Where the sum differs from all three together, the errors interact.</p>")


# ---- tab 5: detector -------------------------------------------------------------------------------
def detector(det: dict) -> None:
    classes = det["classes"]
    pc = det["ultralytics"]["per_class"]
    err = det["errors"]
    sizes = ["small", "medium", "large"]
    worst = sorted(classes, key=lambda c: pc[c]["mAP50"])[:2]
    pooled = {s: data.derived(100 * sum(err["miss_rate_by_size"][c][s]["miss_rate"] * err["miss_rate_by_size"][c][s]["gt"]
                                        for c in classes) / sum(err["miss_rate_by_size"][c][s]["gt"] for c in classes))
              for s in sizes}
    ui.takeaway(f"mAP50 <b>{det['ultralytics']['mAP50']:.3f}</b> on {err['images']:,} IDD images never used in training. "
                f"Weakest: {worst[0]} ({pc[worst[0]]['mAP50']:.3f}) and {worst[1]} ({pc[worst[1]]['mAP50']:.3f}); "
                f"{pooled['small']:.0f}% of small boxes are missed, {pooled['large']:.0f}% of large ones.",
                [("frozen before test", "pre"), "dashcam proxy"], DETECTOR)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        fig = go.Figure(go.Bar(
            y=classes, x=[pc[c]["mAP50"] for c in classes], orientation="h",
            marker=dict(color=[theme.CLASS_COLOURS[c] for c in classes]), text=[f"{pc[c]['mAP50']:.3f}" for c in classes],
            textposition="outside", cliponaxis=False, textfont=dict(color=theme.TEXT, size=12),
            customdata=[[pc[c]["mAP50_95"], err["precision"][c]["value"], err["recall"][c]["value"]] for c in classes],
            hovertemplate="%{y}<br>mAP50 <b>%{x:.3f}</b> · mAP50-95 %{customdata[0]:.3f}<br>"
                          "precision %{customdata[1]:.3f} · recall %{customdata[2]:.3f} at the operating point<extra></extra>"))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(range=[0, 1], title_text="mAP50")
        fig.update_layout(margin=dict(l=8, r=48, t=8, b=8))
        ui.chart(fig, DETECTOR, key="det_map", height=60 + 40 * len(classes), grow="h", title="mAP50 per class",
                 subtitle=f"All classes {det['ultralytics']['mAP50']:.3f}; hover for precision and recall at the operating point")
    with c2:
        z = [[100 * err["miss_rate_by_size"][c][s]["miss_rate"] for s in sizes] for c in classes]
        fig = go.Figure(go.Heatmap(
            z=z, x=sizes, y=classes, zmin=0, zmax=100,
            colorscale=[[0, "#141b25"], [0.35, "#5c1f2e"], [0.7, "#c2334f"], [1, "#ff6b81"]],
            text=[[f"{v:.0f}%" for v in r] for r in z], texttemplate="%{text}", textfont=dict(size=12, color=theme.TEXT),
            customdata=[[err["miss_rate_by_size"][c][s]["gt"] for s in sizes] for c in classes],
            hovertemplate="%{y}, %{x}: <b>%{z:.1f}%</b> missed (of %{customdata} boxes)<extra></extra>",
            colorbar=dict(title=dict(text="% missed", font=dict(color=theme.TEXT_2, size=11.5)), tickfont=dict(color=theme.TEXT_3),
                          thickness=8, outlinewidth=0, ticksuffix="%"), xgap=3, ygap=3))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(showgrid=False, side="top")
        ui.chart(fig, DETECTOR, key="det_size", height=60 + 40 * len(classes), title="Miss rate by object size",
                 subtitle="COCO size buckets on the box area at 640 px")
    ui.why(
        f"<p><b>Evaluated once</b> on our test split ({det['split']}): the confidence threshold "
        f"{det['conf_threshold']} was chosen on our validation split and committed before the test split was touched.</p>"
        "<p><b>Caveat.</b> IDD is filmed from a moving vehicle, not a pole-mounted junction camera; viewpoint, distance "
        "and occlusion differ.</p>")


def render() -> None:
    ui.page_header("Results", "What the experiments measured",
                   "Every chart reads the results files the experiment scripts generate. Hover for exact values.",
                   ["pre-registered", "no significance test"])
    try:
        full = data.read_json(FULL, "Run scripts/make_results.py.")
        ms = data.read_json(MODEL_SIZE, "Run scripts/make_model_size.py.")
        cam = data.read_json(CAMERA, "Run scripts/make_camera_error.py.")
        det = data.read_json(DETECTOR, "Run scripts/eval_detector.py --stage test.")
    except data.MissingData as e:
        ui.missing(e)
        return
    t1, t2, t3, t4, t5 = st.tabs(["Signal control", "Ambulances", "Model size · exploratory", "Camera errors", "Detector"])
    with t1:
        signal_control(full)
    with t2:
        emergency(full, ms)
    with t3:
        model_size(ms)
    with t4:
        camera(cam)
    with t5:
        detector(det)
