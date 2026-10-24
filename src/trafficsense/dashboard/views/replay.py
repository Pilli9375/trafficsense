"""Network Replay: two saved runs of the 2x2 grid side by side, second by second.

Reads the replays made by scripts/make_replays.py (pre-registered in docs/dashboard.md; each one
verified to reproduce its saved run exactly), the source runs' summary.json and decision logs,
and the roadnet. Nothing is simulated here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trafficsense.dashboard import data, theme, ui
from trafficsense.sim.roadnet import load_roadnet

MAX_FRAMES = 160
APPROACH_VEC = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
HINT = ("Make the replays with `python scripts/make_replays.py` (after creating the symlink "
        "`data/external/replays`, see configs/default.yaml).")


@dataclass
class Run:
    name: str
    src: str              # source run folder (repo-relative)
    rdir: str             # replay folder (repo-relative)
    meta: dict
    summary: dict
    z: dict
    decisions: list[dict]
    decisions_file: str
    label: str
    colour: str


def load_runs() -> list[Run]:
    cfg = data.config()
    rdir_root = data.config_path("replays")
    runs = []
    for src in cfg["dashboard"]["replays"]["runs"]:
        name = Path(src).name
        rdir = f"{rdir_root}/{name}"
        meta = data.read_json(f"{rdir}/meta.json", HINT)
        summary = data.read_json(f"{src}/summary.json", "Source run missing.")
        z = data.read_npz(f"{rdir}/replay.npz", HINT)
        dfile = f"{src}/decisions.jsonl" if meta["source_decisions_sha256"] else f"{rdir}/decisions_replay.jsonl"
        decisions = data.read_jsonl(dfile, HINT)
        label, colour = theme.entity(meta["controller"], meta["model"])
        runs.append(Run(name, src, rdir, meta, summary, z, decisions, dfile, label, colour))
    return runs


def signal_relevant(roadnet_raw: dict, route: list[str]) -> bool:
    """True if the route crosses a movement a signal controls (not a free right turn)."""
    links = {(rl["startRoad"], rl["endRoad"]): rl["type"] for it in roadnet_raw["intersections"]
             for rl in it.get("roadLinks", [])}
    return any(links.get((a, b)) not in (None, "turn_right") for a, b in zip(route, route[1:]))


def last_green(phase: np.ndarray, transition: list[int]) -> np.ndarray:
    """Phase index, with transition steps replaced by the green shown before them."""
    out = phase.astype(np.int16).copy()
    for i, tp in enumerate(transition):
        for t in range(len(out)):
            if out[t, i] == tp and t > 0:
                out[t, i] = out[t - 1, i]
    return out


def _panel_static(fig: go.Figure, raw: dict, col: int) -> None:
    for r in raw["roads"]:
        xs, ys = [p["x"] for p in r["points"]], [p["y"] for p in r["points"]]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#232328", width=14),
                                 hoverinfo="skip", showlegend=False), row=1, col=col)
    real = [i for i in raw["intersections"] if not i["virtual"]]
    fig.add_trace(go.Scatter(x=[i["point"]["x"] for i in real], y=[i["point"]["y"] for i in real], mode="markers",
                             marker=dict(symbol="square", size=26, color="#1c1c20", line=dict(color=theme.BORDER, width=1)),
                             hoverinfo="skip", showlegend=False), row=1, col=col)


def _dynamic(run: Run, net, t: int, green: np.ndarray, amb_type: int, focus: int) -> list[dict]:
    """Trace dicts (vehicles, ambulances, signals+queues, phase labels) for second t of one run."""
    z, meta = run.z, run.meta
    k = t - 1
    a, b = z["veh_offsets"][k], z["veh_offsets"][k + 1]
    x, y, typ, fid = z["veh_x"][a:b], z["veh_y"][a:b], z["veh_type"][a:b], z["veh_flow"][a:b]
    amb = typ == amb_type
    sx, sy, ssym, scol, stext, spos, shover = [], [], [], [], [], [], []
    px, py, ptext = [], [], []
    for i, iid in enumerate(meta["intersections"]):
        inter = net.intersections[iid]
        shown = int(z["phase"][k, i])
        in_tr = shown == meta["transition_phase"][iid]
        g = int(green[k, i])
        served = {inter.movements[m].approach for m in inter.phases[g].movements
                  if inter.movements[m].turn != "turn_right"}
        cx, cy = inter.point
        for j, app in enumerate(meta["approaches"]):
            ax, ay = APPROACH_VEC[app]
            dx, dy = -ax, -ay                      # travel direction of incoming traffic
            mx, my = cx + 44 * ax + 6 * dy, cy + 44 * ay - 6 * dx
            q = int(z["queue"][k, i, j])
            if app in served:
                state, colour, sym = ("yellow" if in_tr else "green"), (theme.YELLOW_SIGNAL if in_tr else theme.GREEN_SIGNAL), "circle"
            else:
                state, colour, sym = "red", "#71717a", "circle-open"
            sx.append(mx); sy.append(my); ssym.append(sym); scol.append(colour); stext.append(str(q))
            spos.append({"N": "top center", "S": "bottom center", "E": "middle right", "W": "middle left"}[app])
            shover.append(f"{iid} · from {app}: {state}, queue {q}")
        px.append(cx); py.append(cy)
        ptext.append("→" if in_tr else f"P{g}")
    big = fid[amb] == focus
    return [
        dict(type="scatter", x=x[~amb], y=y[~amb], mode="markers", marker=dict(size=4, color=theme.VEHICLE),
             hoverinfo="skip"),
        dict(type="scatter", x=x[amb], y=y[amb], mode="markers",
             marker=dict(symbol="diamond", size=np.where(big, 15, 10), color="#ededef",
                         line=dict(color="#0f0f11", width=2)),
             text=[f"ambulance flow_{f}_0" for f in fid[amb]], hovertemplate="%{text}<extra></extra>"),
        dict(type="scatter", x=sx, y=sy, mode="markers+text", text=stext, textposition=spos,
             textfont=dict(color=theme.TEXT, size=11), hovertext=shover, hovertemplate="%{hovertext}<extra></extra>",
             marker=dict(symbol=ssym, size=10, color=scol, line=dict(color=scol, width=2))),
        dict(type="scatter", x=px, y=py, mode="text", text=ptext, textfont=dict(color=theme.TEXT, size=12),
             hoverinfo="skip"),
    ]


def network_figure(runs: list[Run], raw: dict, net, t0: int, t1: int, focus: int) -> go.Figure:
    step = max(1, math.ceil((t1 - t0 + 1) / MAX_FRAMES))
    times = list(range(t0, t1 + 1, step))
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.02, subplot_titles=[r.label for r in runs])
    n_static = 0
    for c in (1, 2):
        before = len(fig.data)
        _panel_static(fig, raw, c)
        n_static = len(fig.data) - before
    amb_types = [r.meta["vehicle_types"].index(r.meta["emergency_type"]) for r in runs]
    greens = [last_green(r.z["phase"], [r.meta["transition_phase"][i] for i in r.meta["intersections"]]) for r in runs]
    dyn_idx = []
    for c, r in enumerate(runs, start=1):
        for tr in _dynamic(r, net, times[0], greens[c - 1], amb_types[c - 1], focus):
            fig.add_trace(go.Scatter(**{k: v for k, v in tr.items() if k != "type"}, showlegend=False), row=1, col=c)
            dyn_idx.append(len(fig.data) - 1)
    frames = []
    for t in times:
        trs = []
        for c, r in enumerate(runs):
            trs += [go.Scatter(**{k: v for k, v in tr.items() if k != "type"})
                    for tr in _dynamic(r, net, t, greens[c], amb_types[c], focus)]
        frames.append(go.Frame(data=trs, traces=dyn_idx, name=str(t)))
    fig.frames = frames
    xs = [p["x"] for r in raw["roads"] for p in r["points"]]
    ys = [p["y"] for r in raw["roads"] for p in r["points"]]
    pad = 15
    for c in (1, 2):
        fig.update_xaxes(range=[min(xs) - pad, max(xs) + pad], visible=False, row=1, col=c)
        fig.update_yaxes(range=[min(ys) - pad, max(ys) + pad], visible=False, row=1, col=c,
                         scaleanchor="x" if c == 1 else "x2", scaleratio=1)
    fig.update_annotations(font=dict(color=theme.TEXT, size=13))
    dur = 220
    fig.update_layout(
        height=560, margin=dict(l=0, r=0, t=36, b=0), showlegend=False,
        updatemenus=[dict(type="buttons", direction="left", showactive=False, x=0, y=-0.02, xanchor="left", yanchor="top",
                          bgcolor=theme.SURFACE_2, bordercolor=theme.BORDER, font=dict(color=theme.TEXT),
                          pad=dict(r=8, t=4),
                          buttons=[dict(label="▶ Play", method="animate",
                                        args=[None, dict(frame=dict(duration=dur, redraw=False), transition=dict(duration=0),
                                                         fromcurrent=True, mode="immediate")]),
                                   dict(label="❚❚ Pause", method="animate",
                                        args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=0.16, len=0.84, y=-0.02, yanchor="top", pad=dict(t=4),
                      currentvalue=dict(prefix="t = ", suffix=" s", font=dict(color=theme.TEXT, size=12)),
                      font=dict(color=theme.TEXT_3, size=10), bgcolor=theme.SURFACE_2, bordercolor=theme.BORDER,
                      tickcolor=theme.BORDER, activebgcolor=theme.TEXT_2,
                      steps=[dict(label=str(t), method="animate",
                                  args=[[str(t)], dict(frame=dict(duration=0, redraw=False), mode="immediate")])
                             for t in times])])
    return fig


def decision_rows(run: Run, net, lo: int, hi: int) -> pd.DataFrame:
    names = run.meta["phase_names"]
    rows = []
    for d in run.decisions:
        if not lo <= d["step"] <= hi:
            continue
        iid = d["intersection"]
        amb = d.get("ambulances") or []
        pr = d.get("mp_pressures", {})
        rows.append({
            "t (s)": d["step"], "Intersection": iid.replace("intersection_", ""),
            "Applied": f"P{d['phase']} {names[iid][str(d['phase'])]}",
            "Action": d.get("action", ""),
            "MP pick": f"P{d['mp_choice']}" if "mp_choice" in d else
            (f"P{max(pr, key=lambda p: pr[p])}" if pr else ""),
            "Ambulance in prompt": "; ".join(f"{a['movement']} {a['distance_m']:.0f} m" for a in amb),
            "Reason (LLM's own words)" if run.meta["model"] else "Pressures":
                (d.get("reason") or (f"failed: {d.get('failure_type')}" if not d.get("ok", True) else ""))
                if run.meta["model"] else ", ".join(f"P{p} {v}" for p, v in pr.items()),
        })
    df = pd.DataFrame(rows[::-1])
    if len(df) and not df["Ambulance in prompt"].any():
        df = df.drop(columns="Ambulance in prompt")
    return df


def render() -> None:
    ui.header("Network Replay", "Two controllers, same traffic, second by second",
              "Saved runs of the Indian 2x2 grid at peak with ambulances, replayed from their own logged decisions "
              "(no model is called). Each replay was checked to reproduce its run's metrics exactly.")
    try:
        runs = load_runs()
        roadnet_rel = runs[0].meta["roadnet"]
        raw = data.read_json(roadnet_rel, "")
    except data.MissingData as e:
        ui.missing(e)
        return
    net = load_roadnet(data.path(roadnet_rel))
    labels = [r.label for r in runs]
    by_label = {r.label: r for r in runs}

    c1, c2, c3 = st.columns([1, 1, 1.25], gap="small")
    a_lab = c1.selectbox("Left", labels, index=labels.index(theme.entity("maxpressure", None)[0]))
    b_default = theme.entity("llm_guided_mp_v3", "gemma4:e4b")[0]
    b_lab = c2.selectbox("Right", labels, index=labels.index(b_default))
    A, B = by_label[a_lab], by_label[b_lab]
    amb_a = {v["vehicle"]: v for v in A.summary["emergency"]["vehicles"]}
    amb_b = {v["vehicle"]: v for v in B.summary["emergency"]["vehicles"]}
    relevant = [v for v in amb_a.values() if signal_relevant(raw, v["route"])]

    def amb_fmt(v: str) -> str:
        a, b = amb_a[v], amb_b[v]
        return f"t {a['scheduled_start']} s · {v} · {a['travel_time_s']:.0f} vs {b['travel_time_s']:.0f} s"
    amb_id = c3.selectbox("Ambulance (signal-relevant, by start time)", [v["vehicle"] for v in relevant],
                          format_func=amb_fmt)
    va, vb = amb_a[amb_id], amb_b[amb_id]
    steps = int(A.meta["steps"])
    lo_def = max(1, int(va["scheduled_start"]) - 5)
    hi_def = min(steps, int(max(va["finished"], vb["finished"])) + 10)
    t0, t1 = st.slider("Window (s)", 1, steps, (lo_def, hi_def), key=f"win_{amb_id}")
    focus = int(amb_id.split("_")[1])

    # headline comparison for this pair: the selected ambulance next to the means over the whole seed
    ea, eb = A.summary["emergency"], B.summary["emergency"]
    if (ea["finished"], ea["scheduled_in_run"]) == (eb["finished"], eb["scheduled_in_run"]):
        all_title = f"All {ea['scheduled_in_run']} ambulances · mean travel"
        if ea["finished"] != ea["scheduled_in_run"]:
            all_title = f"{ea['finished']} of {ea['scheduled_in_run']} ambulances finished · mean travel"
    else:
        all_title = "All ambulances (finished only) · mean travel"

    def rel_mean(amb: dict) -> float:
        done = [amb[v["vehicle"]]["travel_time_s"] for v in relevant if amb[v["vehicle"]]["travel_time_s"] is not None]
        return data.derived(sum(done) / len(done))
    n_rel = data.derived(len(relevant))
    for col, (title, fa, fb, unit, d) in zip(st.columns(4, gap="small"), (
            ("This ambulance · travel time", va["travel_time_s"], vb["travel_time_s"], "s", 0),
            (all_title, ea["travel_time_mean_s"], eb["travel_time_mean_s"], "s", 1),
            (f"{n_rel} signal-relevant · mean travel", rel_mean(amb_a), rel_mean(amb_b), "s", 1),
            ("Run ATT · all vehicles", A.summary["metrics"]["att"], B.summary["metrics"]["att"], "s", 1))):
        col.markdown(ui.duo_card(title, unit, [(theme.short(A.meta["controller"], A.meta["model"]), A.colour, f"{fa:.{d}f}"),
                                               (theme.short(B.meta["controller"], B.meta["model"]), B.colour, f"{fb:.{d}f}")]),
                     unsafe_allow_html=True)
    ui.note(
        "<p><b>How the shown ambulance is picked.</b> By default, the first ambulance of the seed (by scheduled start) "
        "whose route crosses a signal: a fixed rule written into the page before it was first rendered, not a choice "
        "by result. Any other can be picked from the list. One ambulance can differ a lot by chance; the means over "
        "all ambulances of this seed (from each run's summary) and over the signal-relevant ones put it in context. "
        "The seed itself is the emergency seed with the most ambulances (pre-registered, docs/dashboard.md).</p>",
        tags=[("selection rule", "")])

    fig = network_figure([A, B], raw, net, t0, t1, focus)
    st.plotly_chart(fig, width="stretch", config={**ui.PLOT_CONFIG, "scrollZoom": False}, key="replay_map")
    st.caption("Grey dots: vehicles. White diamonds: ambulances (the selected one larger). Circles at each approach: "
               "filled = green (yellow while switching), hollow = red; the number is the queue (waiting vehicles). "
               "Pn = green phase shown; → = transition.")
    ui.caption_source(A.rdir + "/replay.npz", A.src + "/summary.json", B.rdir + "/replay.npz", B.src + "/summary.json",
                      roadnet_rel)

    # ---- inspect one second ----------------------------------------------------------------------
    st.subheader("Inspect a second", anchor=False)
    # default: the first decision of the right-hand run whose prompt lists the selected ambulance, if any
    seen = [d["step"] for d in B.decisions if t0 <= d["step"] <= t1
            and any(a["vehicle"] == amb_id for a in d.get("ambulances") or [])]
    t_def = seen[0] if seen else min(t1, int(va["scheduled_start"]) + 15)
    t = st.slider("Second", t0, t1, t_def, key=f"insp_{amb_id}_{t0}_{t1}",
                  help="Starts at the first decision whose prompt lists this ambulance (right-hand run), if any.")
    cols = st.columns(2, gap="medium")
    for col, r in zip(cols, (A, B)):
        with col:
            st.markdown(f"**{ui.esc(r.label)}**")
            k = t - 1
            rows = []
            for i, iid in enumerate(r.meta["intersections"]):
                ph = int(r.z["phase"][k, i])
                tr = ph == r.meta["transition_phase"][iid]
                rows.append({"Intersection": iid.replace("intersection_", ""),
                             "Phase": "transition (yellow)" if tr else f"P{ph} {r.meta['phase_names'][iid][str(ph)]}",
                             **{f"Q {a}": int(r.z["queue"][k, i, j]) for j, a in enumerate(r.meta["approaches"])}})
            ui.html_table(pd.DataFrame(rows), wide="Phase")
    st.markdown("##### Decisions in the 30 s up to this second, newest first")
    for r in (A, B):
        dec = decision_rows(r, net, t - 30, t)
        st.markdown(f"**{ui.esc(r.label)}**" + ("" if len(dec) else ": no decision in this interval"))
        if len(dec):
            ui.html_table(dec, max_height=260, wide="Reason (LLM's own words)" if r.meta["model"] else "Pressures")
        v = r.meta["verified"]
        st.caption(f"Replay check: reproduces the saved ATT and all {v['emergency_vehicles_identical']} ambulances "
                   f"exactly; driven by {r.meta['drive']}.")
        ui.caption_source(r.decisions_file, r.rdir + "/meta.json")

    # ---- whole run -------------------------------------------------------------------------------
    st.subheader("Network queue over the hour", anchor=False)
    fig = go.Figure()
    for r in (A, B):
        q = r.z["queue"].sum(axis=(1, 2))
        fig.add_trace(go.Scatter(x=r.z["time"], y=q, mode="lines", name=r.label, line=dict(color=r.colour, width=1.5),
                                 hovertemplate="t %{x} s: %{y} waiting<extra>" + r.label + "</extra>"))
    fig.add_vrect(x0=t0, x1=t1, fillcolor="#ededef", opacity=0.06, line_width=0)
    for r in (A, B):
        v = {x["vehicle"]: x for x in r.summary["emergency"]["vehicles"]}[amb_id]
        fig.add_vline(x=v["finished"], line=dict(color=r.colour, width=1, dash="dot"))
    fig.add_vline(x=va["scheduled_start"], line=dict(color=theme.TEXT_3, width=1, dash="dot"))
    fig.update_xaxes(title_text="simulation time (s) · shaded: window · dotted: selected ambulance starts / arrives")
    fig.update_yaxes(title_text="waiting vehicles, whole grid")
    ui.chart(fig, A.rdir + "/replay.npz", B.rdir + "/replay.npz", height=260, key="replay_queue")
