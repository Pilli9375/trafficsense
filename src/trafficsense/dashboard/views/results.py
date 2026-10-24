"""Results: interactive charts straight from the results files, with their honesty notes."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trafficsense.dashboard import data, theme, ui

FULL = "outputs/full/results.json"
MODEL_SIZE = "outputs/model_size/model_size.json"
CAMERA = "outputs/camera_error/results.json"
DETECTOR = "outputs/perception/detector_test.json"
SCENARIO_CFG = "configs/scenarios/indian_2x2.yaml"
ORDER = [("maxpressure", None), ("fixedtime_webster", None), ("fixedtime", None), ("preemption_mp", None),
         ("llm_guarded_mp", "llama3.2:3b"), ("llm_guided_mp_v3", "gemma4:e4b")]


def _hbar(names, values, errors, colours, x_title, text_fmt="{:.1f}") -> go.Figure:
    fig = go.Figure(go.Bar(
        y=names, x=values, orientation="h", marker=dict(color=colours, cornerradius=4),
        error_x=dict(type="data", array=errors, color=theme.TEXT_3, thickness=1.2, width=4) if errors else None,
        text=[text_fmt.format(v) for v in values], textposition="outside", cliponaxis=False,
        textfont=dict(color=theme.TEXT), hovertemplate="%{y}<br>%{x:.2f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(title_text=x_title, rangemode="tozero")
    fig.update_layout(showlegend=False, height=60 + 44 * len(names), margin=dict(l=8, r=48, t=12, b=8))
    return fig


# ---- tab 1: signal control -----------------------------------------------------------------
def signal_control(full: dict) -> None:
    scen = st.segmented_control("Scenario", list(full["scenarios"]), default="indian_2x2_peak",
                                format_func=lambda s: theme.SCENARIO_LABELS[s], key="res_scen")
    scen = scen or "indian_2x2_peak"
    arms = {(v["controller"], v["model"]): v for v in full["scenarios"][scen].values()}
    keys = [k for k in ORDER if k in arms]
    n_seeds = sorted({len(arms[k]["seeds"]) for k in keys})
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        st.markdown("##### Average travel time (s), mean ± std over seeds")
        fig = _hbar([theme.entity(*k)[0] for k in keys], [arms[k]["att"][0] for k in keys],
                    [arms[k]["att"][1] for k in keys], [theme.entity(*k)[1] for k in keys], "ATT (s)")
        ui.chart(fig, FULL, key="res_att")
    with c2:
        st.markdown("##### Paired by seed: ATT minus MaxPressure (s)")
        paired = full["paired"][scen]
        fig = go.Figure()
        by_ctl = {(v["controller"], v["model"]): name for name, v in full["scenarios"][scen].items()}
        # Fixed-time is far off the scale of the others (see the table); it would hide them.
        pkeys = [k for k in keys if k not in (("maxpressure", None), ("fixedtime", None))]
        for k in pkeys:
            p = paired[by_ctl[k]]
            lab, col = theme.entity(*k)
            fig.add_trace(go.Scatter(
                x=p["att_minus_mp"], y=[lab] * len(p["att_minus_mp"]), mode="markers", name=lab,
                marker=dict(color=col, size=10, line=dict(color=theme.SURFACE, width=2)),
                customdata=p["seeds"], hovertemplate="seed %{customdata}: %{x:+.2f} s<extra>" + lab + "</extra>"))
        fig.add_vline(x=0, line=dict(color=theme.TEXT_3, width=1, dash="dot"))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(title_text="s vs MaxPressure, same seed (− = faster)")
        fig.update_layout(showlegend=False, height=60 + 44 * len(pkeys), margin=dict(l=8, r=16, t=12, b=8))
        ui.chart(fig, FULL, key="res_paired")
        if ("fixedtime", None) in keys:
            ft = paired[by_ctl[("fixedtime", None)]]["att_minus_mp"]
            st.caption(f"Fixed-time is left out of this chart: {min(ft):+.1f} to {max(ft):+.1f} s per seed.")
    tbl = pd.DataFrame([{
        "Controller": theme.entity(*k)[0], "Seeds": len(arms[k]["seeds"]),
        "ATT (s)": ui.mean_std(arms[k]["att"]),
        "Queue / int. (veh)": ui.mean_std(arms[k]["queue_mean_per_intersection"], 2),
        "Waiting / veh (s)": ui.mean_std(arms[k]["waiting_time_mean"]),
        "Finished trips": ui.mean_std(arms[k]["throughput"], 0)} for k in keys])
    st.dataframe(tbl, hide_index=True, width="stretch")
    ui.caption_source(FULL)

    llm = [v for v in full["llm"].values() if v["scenario"] == scen]
    if llm:
        st.markdown("##### LLM decisions")
        rows = []
        for v in llm:
            k = next(k for k in keys if k[0].startswith("llm_") and k[1] and k[1] in v["arm"])
            rows.append({"Arm": theme.entity(*k)[0], "Calls": v["calls"],
                         "Failed": f"{v['failures']} ({ui.pct(100 * v['failure_rate'], 2, sign=False)})",
                         "Latency (s)": f"{v['latency_mean_s']:.2f}",
                         "p95/run (s)": "–".join(f"{x:.2f}" for x in v["latency_p95_s_range"]),
                         "Answer ≠ MP": ui.pct(100 * v["mp_disagreement_rate"], sign=False),
                         "Guard override": ui.pct(100 * v["guard_override_rate"], sign=False)
                         if v.get("guard_override_rate") is not None else "no guard",
                         "Applied ≠ MP": ui.pct(100 * v["applied_differs_rate"], sign=False),
                         "Wall (h)": f"{v['wall_time_h']:.1f}"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        ui.caption_source(FULL)
    ui.note(
        f"<p><b>Design.</b> Plan, arms and analysis were committed before any run (pre-registered). "
        f"{'/'.join(str(n) for n in n_seeds)} seeds per controller here; every controller sees the same flow file per "
        "seed, so the paired view is the fairer comparison. No significance test was pre-registered.</p>"
        "<p><b>Arms.</b> <i>LLM main</i> is the pick of the pre-registered selection rule: MaxPressure with a guard "
        "that only applies the LLM's choice when its pressure is close to the best. The <i>gemma4:e4b</i> arm is "
        "<b>exploratory, not selected by the rule</b> (it failed the latency limit) and has no guard; on this GPU it "
        "is not real-time (the simulator waited for each call).</p>"
        "<p><b>Reproducibility.</b> Deterministic baselines repeat exactly (Jinan's flow file is fixed, hence zero "
        "spread). Ollama on the GPU is not bit-for-bit deterministic even at temperature 0, so LLM runs can be "
        "inspected and replayed from their decision logs but not re-run identically.</p>",
        tags=[("pre-registered", ""), ("no significance test", "warn")])


# ---- tab 2: emergency ------------------------------------------------------------------------
def emergency(full: dict, ms: dict) -> None:
    em = full["emergency"]
    scfg = data.read_yaml(SCENARIO_CFG, "")
    ctl = em["controllers"]
    models = ms["full"]["indian_2x2_peak_amb"]["models"]
    rows = [((c, m), ctl[c]["ambulances_relevant"]) for c, m in ORDER if c in ctl]
    rows += [(("llm_guided_mp_v3", m), v["ambulances"]) for m, v in models.items() if m != "gemma4:e4b"]
    names = [theme.entity(*k)[0] for k, _ in rows]
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        st.markdown("##### Ambulance travel time (s)")
        fig = _hbar(names, [a["travel_time_mean_s"] for _, a in rows], None, [theme.entity(*k)[1] for k, _ in rows],
                    "mean travel time (s)")
        ui.chart(fig, FULL, MODEL_SIZE, key="res_amb")
    with c2:
        st.markdown("##### Ambulance stopped time (s)")
        fig = _hbar(names, [a["stopped_time_mean_s"] for _, a in rows], None, [theme.entity(*k)[1] for k, _ in rows],
                    "mean stopped time (s)")
        ui.chart(fig, FULL, MODEL_SIZE, key="res_amb_stop")
    tbl = []
    for c, m in ORDER:
        if c not in ctl:
            continue
        v = ctl[c]
        vp = v["vs_preemption_relevant"]
        tbl.append({"Controller": theme.entity(c, m)[0], "ATT, all traffic (s)": ui.mean_std(v["att_s"]),
                    "Queue / int. (veh)": ui.mean_std(v["queue_mean_per_intersection"], 2),
                    "Ambulances finished": f"{v['ambulances_relevant']['finished']} / {v['ambulances_relevant']['n']}",
                    "Median travel (s)": f"{v['ambulances_relevant']['travel_time_median_s']:.1f}",
                    "vs preemption": "–" if c == "preemption_mp" else
                    f"{vp['mean_diff_s']:+.1f} s ({vp['faster']} faster, {vp['slower']} slower)"})
    st.dataframe(pd.DataFrame(tbl), hide_index=True, width="stretch")
    ui.caption_source(FULL)
    amb = ctl["maxpressure"]
    ui.note(
        f"<p><b>Design.</b> Pre-registered: peak traffic plus ambulances at {scfg['emergency']['veh_per_hour']} per "
        f"hour (an assumption), seeds {', '.join(str(s) for s in em['provenance']['seeds'])}. The primary metric is "
        f"the mean travel time of the {amb['ambulances_relevant']['n']} ambulances (of {amb['ambulances_all']['n']}) "
        "whose route crosses a signal, pooled over seeds; the same ambulances run under every controller.</p>"
        "<p><b>Limits.</b> In CityFlow nobody yields and nothing overtakes, so only the signal can help an "
        "ambulance. LLM arms see ambulances listed in their prompt and do not preempt. Model-size rows "
        "(Nemotron, llama3.1:8b, qwen2.5:3b, llama3.2:3b hybrid) are <b>exploratory</b>, added after the main "
        "results. No significance test.</p>",
        tags=[("pre-registered", ""), ("exploratory rows labelled", "warn")])
    ui.caption_source(SCENARIO_CFG)


# ---- tab 3: model size -----------------------------------------------------------------------
def model_size(ms: dict) -> None:
    ui.note(
        f"<p><b>{ms['provenance']['label'].capitalize()}.</b> Its plan was committed "
        "before its runs; it changes none of the pre-registered results. Controller held fixed (the gemma4 "
        "hybrid's setup); only the model changes. Local models are 4-bit quantized on the laptop GPU; "
        "Nemotron 3 Ultra is <b>hosted</b> (NVIDIA NIM): its prompts leave the machine, the served model can change, "
        "and throttled calls fall back to MaxPressure's choice (counted below).</p>",
        tags=[("exploratory", "warn"), ("hosted arm not local", "warn")])
    scen = st.segmented_control("Scenario", list(ms["full"]), default="indian_2x2_peak",
                                format_func=lambda s: theme.SCENARIO_LABELS[s], key="ms_scen") or "indian_2x2_peak"
    blk = ms["full"][scen]
    order = sorted(blk["models"], key=lambda m: ms["sizes"][m]["total_b"])
    labels = [f"{theme.model_short(m)}<br>{ms['sizes'][m]['total_b']:g} B" for m in order]
    cols = [theme.entity("llm_guided_mp_v3", m)[1] for m in order]
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(f"##### ATT vs MaxPressure, % (mean; range over {len(blk['seeds'])} seeds)")
        mean = [100 * blk["models"][m]["att_vs_mp"]["mean"] for m in order]
        lo = [100 * (blk["models"][m]["att_vs_mp"]["mean"] - blk["models"][m]["att_vs_mp"]["min"]) for m in order]
        hi = [100 * (blk["models"][m]["att_vs_mp"]["max"] - blk["models"][m]["att_vs_mp"]["mean"]) for m in order]
        fig = go.Figure(go.Scatter(
            x=labels, y=mean, mode="markers", marker=dict(color=cols, size=12, line=dict(color=theme.SURFACE, width=2)),
            error_y=dict(type="data", symmetric=False, array=hi, arrayminus=lo, color=theme.TEXT_3, thickness=1.2, width=5),
            hovertemplate="%{x}<br>%{y:+.1f}% (mean over seeds)<extra></extra>"))
        fig.update_xaxes(tickangle=0)
        fig.add_hline(y=0, line=dict(color=theme.TEXT_3, width=1, dash="dot"))
        fig.update_yaxes(title_text="% (positive = slower than MaxPressure)")
        ui.chart(fig, MODEL_SIZE, height=330, key="ms_att")
    with c2:
        st.markdown("##### Share of answers that pick the highest-pressure phase")
        fp = [100 * blk["models"][m]["follows_pressure_rate"] for m in order]
        fig = go.Figure(go.Bar(x=labels, y=fp, marker=dict(color=cols, cornerradius=4),
                               text=[f"{v:.0f}%" for v in fp], textposition="outside", cliponaxis=False,
                               textfont=dict(color=theme.TEXT), hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>"))
        fig.update_yaxes(title_text="% of successful calls", range=[0, 110])
        fig.update_xaxes(tickangle=0)
        fig.update_layout(showlegend=False)
        ui.chart(fig, MODEL_SIZE, height=330, key="ms_fp")
    rows = []
    for m in order:
        v = blk["models"][m]
        a = v["att_vs_mp"]
        rows.append({"Model": theme.model_short(m), "Params total / active (B)": f"{ms['sizes'][m]['total_b']:g} / {ms['sizes'][m]['active']}",
                     "ATT (s)": ui.mean_std(v["att_s"]),
                     "vs MP, mean (range)": f"{ui.pct(100 * a['mean'])} ({100 * a['min']:+.1f} to {100 * a['max']:+.1f})",
                     "Seeds worse": f"{a['seeds_worse']} of {len(v['runs'])}",
                     "Failed → MP": f"{v['failures']} of {v['calls']}",
                     "Retries": "–" if v["retries"] is None else f"{v['retries']}",
                     "Min / run": f"{v['wall_time_s_mean'] / 60:.0f}",
                     "Served model id": ", ".join(v["served_models"])})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ui.caption_source(MODEL_SIZE)


# ---- tab 4: camera errors ---------------------------------------------------------------------
def camera(cam: dict) -> None:
    ui.note(
        "<p><b>Pre-registered.</b> The simulator stays exact; only what the controllers <i>observe</i> is noised with "
        "the error rates measured from our detector on the IDD test split. Ambulance positions are assumed to come "
        "from GPS / V2X and are <b>never noised</b>. IDD is dashcam footage, so its errors are a proxy for a junction "
        "camera. One pre-registered check (realised detection rates within a fixed tolerance of their targets) failed "
        "narrowly for a rare class; docs/camera_error.md explains it. The decomposition table is <b>post-hoc</b>.</p>",
        tags=[("pre-registered", ""), ("decomposition post-hoc", "warn"), ("ambulances not noised", "warn")])
    main = cam["main"]
    scens = list(main)
    st.markdown("##### Paired change in ATT vs exact counts, % (mean; range over seeds)")
    fig = make_subplots(rows=1, cols=len(scens), shared_yaxes=True, horizontal_spacing=0.06,
                        subplot_titles=[theme.SCENARIO_LABELS[s] for s in scens])
    ctl_keys = {"maxpressure": ("maxpressure", None), "fixedtime_webster": ("fixedtime_webster", None),
                "llm_guarded_mp": ("llm_guarded_mp", "llama3.2:3b")}
    levels = ["junction", "crowded"]
    for j, sc in enumerate(scens, start=1):
        for c, k in ctl_keys.items():
            lab, col = theme.entity(*k)
            a = [main[sc][c][lvl]["att_vs_perfect"] for lvl in levels]
            fig.add_trace(go.Scatter(
                x=[theme.LEVEL_LABELS[l] for l in levels], y=[v["pct_mean"] for v in a], mode="markers", name=lab,
                legendgroup=lab, showlegend=j == 1, offsetgroup=lab,
                marker=dict(color=col, size=11, line=dict(color=theme.SURFACE, width=2)),
                error_y=dict(type="data", symmetric=False, array=[v["pct_max"] - v["pct_mean"] for v in a],
                             arrayminus=[v["pct_mean"] - v["pct_min"] for v in a], color=col, thickness=1.4, width=4),
                hovertemplate="%{x}: %{y:+.1f}%<extra>" + lab + "</extra>"), row=1, col=j)
    fig.add_hline(y=0, line=dict(color=theme.TEXT_3, width=1, dash="dot"))
    fig.update_layout(scattermode="group", scattergap=0.5, height=380, margin=dict(l=8, r=8, t=40, b=8),
                      legend=dict(y=-0.12, yanchor="top"))
    fig.update_yaxes(title_text="% ATT change (positive = slower)", row=1, col=1)
    fig.update_annotations(font=dict(color=theme.TEXT_2, size=12))
    ui.chart(fig, CAMERA, key="cam_main")

    st.markdown("##### MaxPressure vs detection rate (sweep: same p for every class, no false detections)")
    sweep = cam["sweep"]
    fig = make_subplots(rows=1, cols=len(scens), horizontal_spacing=0.08,
                        subplot_titles=[theme.SCENARIO_LABELS[s] for s in scens])
    mp_lab, mp_col = theme.entity("maxpressure", None)
    for j, sc in enumerate(scens, start=1):
        lv = sorted(sweep[sc], key=lambda k: float(k.split("_p")[1]))
        p = [float(k.split("_p")[1]) for k in lv]
        fig.add_trace(go.Scatter(
            x=p, y=[sweep[sc][k]["att"][0] for k in lv], mode="lines+markers", name="sweep",
            line=dict(color=mp_col, width=2), marker=dict(size=8), showlegend=False,
            error_y=dict(type="data", array=[sweep[sc][k]["att"][1] for k in lv], color=theme.TEXT_3, thickness=1, width=3),
            hovertemplate="p_detect %{x:.2f}: %{y:.1f} s<extra>uniform sweep</extra>"), row=1, col=j)
        for lvl, sym in (("junction", "diamond"), ("crowded", "square")):
            fig.add_trace(go.Scatter(
                x=[cam["effective_p_detect"][sc][lvl]], y=[main[sc]["maxpressure"][lvl]["att"][0]],
                mode="markers+text", text=[theme.LEVEL_LABELS[lvl]], textposition="top center",
                textfont=dict(color=theme.TEXT_2, size=11), showlegend=False,
                marker=dict(symbol=sym, size=11, color=theme.SURFACE, line=dict(color=mp_col, width=2)),
                hovertemplate="effective p_detect %{x:.3f}: %{y:.1f} s<extra>" + theme.LEVEL_LABELS[lvl] + "</extra>"),
                row=1, col=j)
        fig.update_xaxes(title_text="p_detect", autorange="reversed", row=1, col=j)
    fig.update_yaxes(title_text="MaxPressure ATT (s)", row=1, col=1)
    fig.update_layout(height=340, margin=dict(l=8, r=8, t=48, b=8))
    fig.update_annotations(font=dict(color=theme.TEXT_2, size=12))
    ui.chart(fig, CAMERA, key="cam_sweep")

    st.markdown("##### Post-hoc decomposition of the junction-camera errors (MaxPressure)")
    dec = cam["decomposition"]
    names = {"misses": "Misses only", "false": "False detections only", "confusion": "Class confusion only",
             "all": "All three (main batch)"}
    rows = []
    for k, lab in names.items():
        r = {"Errors switched on": lab}
        for sc in scens:
            a = dec[k]["att_vs_perfect"][sc]
            r[theme.SCENARIO_LABELS[sc]] = f"{a['mean']:+.1f} s ({a['min']:+.1f} to {a['max']:+.1f}); {ui.pct(a['pct_mean'])}"
        r["Phantoms / road / snapshot"] = f"{dec[k]['realised']['phantoms_per_road_snapshot']:.3f}"
        rows.append(r)
    r = {"Errors switched on": "Sum of the three single components"}
    for sc in scens:
        r[theme.SCENARIO_LABELS[sc]] = f"{dec['sum_abc'][sc]['mean']:+.1f} s; {ui.pct(dec['sum_abc'][sc]['pct_mean'])}"
    r["Phantoms / road / snapshot"] = ""
    rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ui.caption_source(CAMERA)


# ---- tab 5: detector ---------------------------------------------------------------------------
def detector(det: dict) -> None:
    ui.note(
        f"<p><b>Evaluated once</b> on our test split ({det['split']}): the confidence threshold "
        f"{det['conf_threshold']} was chosen on our validation split and committed before the test split was touched. "
        "<b>Caveat:</b> IDD is filmed from a moving vehicle, not a pole-mounted junction camera; viewpoint, distance "
        "and occlusion differ.</p>", tags=[("frozen before test", ""), ("dashcam proxy", "warn")])
    classes = det["classes"]
    pc = det["ultralytics"]["per_class"]
    err = det["errors"]
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(f"##### mAP50 per class (all classes {det['ultralytics']['mAP50']:.3f})")
        fig = _hbar(classes, [pc[c]["mAP50"] for c in classes], None, [theme.CLASS_COLOURS[c] for c in classes],
                    "mAP50", "{:.3f}")
        fig.update_traces(customdata=[[pc[c]["mAP50_95"], err["precision"][c]["value"], err["recall"][c]["value"]]
                                      for c in classes],
                          hovertemplate="%{y}<br>mAP50 %{x:.3f} · mAP50-95 %{customdata[0]:.3f}<br>"
                                        "precision %{customdata[1]:.3f} · recall %{customdata[2]:.3f} at the operating point<extra></extra>")
        fig.update_xaxes(range=[0, 1])
        ui.chart(fig, DETECTOR, key="det_map")
    with c2:
        st.markdown("##### Miss rate by object size (box area at 640 px)")
        sizes = ["small", "medium", "large"]
        z = [[100 * err["miss_rate_by_size"][c][s]["miss_rate"] for s in sizes] for c in classes]
        fig = go.Figure(go.Heatmap(
            z=z, x=sizes, y=classes, colorscale=[[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]], zmin=0, zmax=100,
            text=[[f"{v:.0f}%" for v in r] for r in z], texttemplate="%{text}", textfont=dict(size=12),
            customdata=[[err["miss_rate_by_size"][c][s]["gt"] for s in sizes] for c in classes],
            hovertemplate="%{y}, %{x}: %{z:.1f}% missed (of %{customdata} boxes)<extra></extra>",
            colorbar=dict(title=dict(text="% missed", font=dict(color=theme.TEXT_2)), tickfont=dict(color=theme.TEXT_2),
                          thickness=10, outlinewidth=0), xgap=2, ygap=2))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(showgrid=False, side="top")
        ui.chart(fig, DETECTOR, height=60 + 44 * len(classes), key="det_size")


def render() -> None:
    ui.header("Results", "What the experiments measured",
              "Every chart reads the summary files the experiment scripts generate (the same files that the "
              "tables in docs/ are checked against). Hover for exact values; each chart names its source.")
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
