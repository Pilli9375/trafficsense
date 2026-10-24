"""Network Replay: two saved runs of the 2x2 grid side by side, drawn on a canvas.

Reads the replays made by scripts/make_replays.py (pre-registered in docs/dashboard.md; each one
verified to reproduce its saved run exactly), the source runs' summary.json and decision logs, the
roadnet and the vehicle dimensions. Nothing is simulated here, and no frame is invented: the
canvas (assets/replay.js) draws the positions CityFlow logged at the end of each second and, between
two logged seconds, a straight-line interpolation of the same vehicle's two logged positions. Phases
and queues change only at logged seconds.

The payload carries vehicle positions as little-endian typed arrays in base64: x and y in 1/20 m
(int16), heading in 1/1000 rad (int16), and an index into the window's vehicle table (uint16).
tests/test_dashboard.py decodes them and checks them against replay.npz.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from trafficsense.dashboard import data, theme, ui
from trafficsense.llm.prompt import phase_label
from trafficsense.sim.roadnet import load_roadnet

MAX_WINDOW_S = 600          # longest window sent to the browser (positions of every vehicle, every second)
CONTEXT_S = 30              # decisions shown from this long before the window starts
POS_SCALE = 20              # positions in 1/20 m
ANG_SCALE = 1000            # headings in 1/1000 rad
HINT = ("Make the replays with `python scripts/make_replays.py` (after creating the symlink "
        "`data/external/replays`, see configs/default.yaml).")
SCENARIO_CFG = "configs/scenarios/indian_2x2.yaml"


@dataclass
class Run:
    name: str
    src: str              # source run folder (repo-relative)
    rdir: str             # replay folder (repo-relative)
    meta: dict
    label: str
    colour: str

    @property
    def key(self) -> tuple:
        return self.meta["controller"], self.meta["model"]


def run_index() -> list[Run]:
    """Every configured replay, from its meta.json only (the selectors need no more)."""
    cfg = data.config()
    root = data.config_path("replays")
    runs = []
    for src in cfg["dashboard"]["replays"]["runs"]:
        name = Path(src).name
        rdir = f"{root}/{name}"
        meta = data.read_json(f"{rdir}/meta.json", HINT)
        label, colour = theme.entity(meta["controller"], meta["model"])
        runs.append(Run(name, src, rdir, meta, label, colour))
    return runs


def decisions_file(r: Run) -> str:
    return f"{r.src}/decisions.jsonl" if r.meta["source_decisions_sha256"] else f"{r.rdir}/decisions_replay.jsonl"


def signal_relevant(roadnet_raw: dict, route: list[str]) -> bool:
    """True if the route crosses a movement a signal controls (not a free right turn)."""
    links = {(rl["startRoad"], rl["endRoad"]): rl["type"] for it in roadnet_raw["intersections"]
             for rl in it.get("roadLinks", [])}
    return any(links.get((a, b)) not in (None, "turn_right") for a, b in zip(route, route[1:]))


def last_green(phase: np.ndarray, transition: list[int]) -> np.ndarray:
    """Phase index, with transition steps replaced by the green shown before them."""
    out = phase.astype(np.int16).copy()
    for i, tp in enumerate(transition):
        for t in range(1, len(out)):
            if out[t, i] == tp:
                out[t, i] = out[t - 1, i]
    return out


def _b64(a: np.ndarray, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=np.dtype(dtype).newbyteorder("<")).tobytes()).decode("ascii")


def geometry(raw: dict, net) -> dict:
    """What the canvas draws of the network, straight from the roadnet file."""
    width = {i["id"]: i.get("width", 0) for i in raw["intersections"]}
    roads = [{"id": r["id"], "a": [r["points"][0]["x"], r["points"][0]["y"]], "b": [r["points"][-1]["x"], r["points"][-1]["y"]],
              "lanes": len(r["lanes"]), "lw": r["lanes"][0]["width"], "wa": width[r["startIntersection"]],
              "wb": width[r["endIntersection"]]} for r in raw["roads"]]
    junctions = []
    for it in raw["intersections"]:
        if it["virtual"]:
            continue
        inter = net.intersections[it["id"]]
        moves = []
        for m, rl in zip(inter.movements, it["roadLinks"]):
            mid = rl["laneLinks"][len(rl["laneLinks"]) // 2]
            moves.append({"approach": m.approach, "turn": {"go_straight": "straight", "turn_left": "cross", "turn_right": "free"}[m.turn],
                          "road": m.in_road, "lane": mid["startLaneIndex"], "pts": [[p["x"], p["y"]] for p in mid["points"]]})
        junctions.append({"id": it["id"], "label": it["id"].replace("intersection_", ""), "x": it["point"]["x"],
                          "y": it["point"]["y"], "w": it["width"], "moves": moves,
                          "phases": {str(p.index): list(p.movements) for p in inter.phases},
                          "labels": {str(p.index): phase_label(inter, p) for p in inter.green_phases},
                          "transition": inter.transition_phase.index})
    return {"roads": roads, "junctions": junctions}


def vehicle_dims(scfg: dict) -> dict[str, list[float]]:
    types = {**scfg["vehicle_types"], **scfg.get("emergency_vehicle_types", {})}
    return {k: [v["length"], v["width"]] for k, v in types.items()}


def run_payload(r: Run, summary: dict, z: dict, decisions: list[dict], t0: int, t1: int, focus: str, labels: dict) -> dict:
    k0, k1 = t0 - 1, t1                       # replay.npz row k holds second k + 1
    a, b = int(z["veh_offsets"][k0]), int(z["veh_offsets"][k1])
    flow = z["veh_flow"][a:b]
    uniq, idx = np.unique(flow, return_inverse=True)
    vtype = np.zeros(len(uniq), dtype=np.int8)
    vtype[idx] = z["veh_type"][a:b]
    trans = [r.meta["transition_phase"][i] for i in r.meta["intersections"]]
    green = last_green(z["phase"], trans)[k0:k1]
    em = {v["vehicle"]: v for v in summary["emergency"]["vehicles"]}
    dec = []
    for d in decisions:
        if not t0 - CONTEXT_S <= d["step"] <= t1:
            continue
        iid = d["intersection"]
        pr = d.get("mp_pressures") or {}
        dec.append({"t": d["step"], "j": iid.replace("intersection_", ""), "action": d.get("action", ""),
                    "phase": d["phase"], "from": d["current_phase"], "in_phase": d["time_in_phase"],
                    "label": labels[iid][str(d["phase"])], "reason": d.get("reason"), "ok": d.get("ok", True),
                    "failure": d.get("failure_type"), "llm_phase": d.get("llm_phase"), "allowed": d.get("allowed"),
                    "mp": d.get("mp_choice"), "pressures": pr, "latency_s": d.get("latency_s"),
                    "amb": [{"vehicle": x["vehicle"], "movement": x["movement"], "distance_m": x["distance_m"]}
                            for x in d.get("ambulances") or []]})
    v = em[focus]
    return {
        "label": r.label, "short": theme.short(*r.key), "colour": r.colour, "exploratory": theme.is_exploratory(*r.key),
        "llm": bool(r.meta["model"]), "drive": r.meta["drive"],
        "intersections": r.meta["intersections"], "approaches": r.meta["approaches"],
        "phase": z["phase"][k0:k1].tolist(), "green": green.tolist(), "queue": z["queue"][k0:k1].tolist(),
        "veh": {"n": np.diff(z["veh_offsets"][k0:k1 + 1]).tolist(), "idx": _b64(idx, "u2"),
                "x": _b64(np.round(z["veh_x"][a:b] * POS_SCALE), "i2"), "y": _b64(np.round(z["veh_y"][a:b] * POS_SCALE), "i2"),
                "ang": _b64(np.round(z["veh_angle"][a:b].astype(np.float32) * ANG_SCALE), "i2"),
                "flow": uniq.tolist(), "type": vtype.tolist()},
        "amb": {"vehicle": focus, "flow": int(focus.split("_")[1]), "start": v["scheduled_start"], "entered": v["entered"],
                "finished": v["finished"], "travel": v["travel_time_s"], "route": v["route"]},
        "decisions": dec,
    }


def queue_figure(runs: list[Run], zs: list[dict], t0: int, t1: int, va: dict, vb: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_vrect(x0=t0, x1=t1, fillcolor=theme.rgba(theme.ACCENT, .06), line_width=0)
    for r, z in zip(runs, zs):
        q = z["queue"].sum(axis=(1, 2))
        fig.add_trace(go.Scatter(x=z["time"], y=q, mode="lines", name=r.label, line=dict(color=r.colour, width=1.6),
                                 hovertemplate="t %{x} s: <b>%{y}</b> waiting<extra>" + ui.esc(r.label) + "</extra>"))
    fig.add_vline(x=va["scheduled_start"], line=dict(color=theme.AMBULANCE, width=1, dash="dot"))
    for r, v in zip(runs, (va, vb)):
        fig.add_vline(x=v["finished"], line=dict(color=r.colour, width=1.2, dash="dot"))
    fig.update_xaxes(title_text="simulation time (s) · shaded: the replayed window · dotted: ambulance start and arrivals")
    fig.update_yaxes(title_text="waiting vehicles")
    fig.update_layout(hovermode="x unified", margin=dict(l=8, r=12, t=28, b=8), legend=dict(y=1.0, yanchor="bottom"))
    return fig


def render() -> None:
    ui.page_header("Simulation", "Network Replay",
                   "Two controllers, the same traffic, second by second, replayed from the runs' own logged decisions.",
                   ["replayed, verified", "selection rule"])
    try:
        index = run_index()
        roadnet_rel = index[0].meta["roadnet"]
        raw = data.read_json(roadnet_rel, "")
        scfg = data.read_yaml(SCENARIO_CFG, "")
    except data.MissingData as e:
        ui.missing(e)
        return
    net = load_roadnet(data.path(roadnet_rel))
    labels = [r.label for r in index]
    by_label = {r.label: r for r in index}

    c1, c2, c3 = st.columns([1, 1, 1.3], gap="small")
    a_lab = c1.selectbox("Left", labels, index=labels.index(theme.entity("maxpressure", None)[0]))
    b_lab = c2.selectbox("Right", labels, index=labels.index(theme.entity("llm_guided_mp_v3", "gemma4:e4b")[0]))
    A, B = by_label[a_lab], by_label[b_lab]
    try:
        sa = data.read_json(f"{A.src}/summary.json", "Source run missing.")
        sb = data.read_json(f"{B.src}/summary.json", "Source run missing.")
        za = data.read_npz(f"{A.rdir}/replay.npz", HINT)
        zb = data.read_npz(f"{B.rdir}/replay.npz", HINT)
        da = data.read_jsonl(decisions_file(A), HINT)
        db = data.read_jsonl(decisions_file(B), HINT)
    except data.MissingData as e:
        ui.missing(e)
        return
    amb_a = {v["vehicle"]: v for v in sa["emergency"]["vehicles"]}
    amb_b = {v["vehicle"]: v for v in sb["emergency"]["vehicles"]}
    relevant = [v for v in amb_a.values() if signal_relevant(raw, v["route"])]

    def amb_fmt(v: str) -> str:
        a, b = amb_a[v], amb_b[v]
        return f"t {a['scheduled_start']} s · {v} · {a['travel_time_s']:.0f} vs {b['travel_time_s']:.0f} s"
    amb_id = c3.selectbox("Ambulance (signal-relevant, by start time)", [v["vehicle"] for v in relevant], format_func=amb_fmt)
    va, vb = amb_a[amb_id], amb_b[amb_id]
    steps = int(A.meta["steps"])
    lo_def = max(1, int(va["scheduled_start"]) - 5)
    hi_def = min(steps, int(max(va["finished"], vb["finished"])) + 10, lo_def + MAX_WINDOW_S)
    t0, t1 = st.slider("Window (s)", 1, steps, (lo_def, hi_def), key=f"win_{amb_id}",
                       help=f"At most {MAX_WINDOW_S} s are sent to the browser; a longer selection is cut at its start + {MAX_WINDOW_S} s.")
    t1 = min(t1, t0 + MAX_WINDOW_S)

    # the selected ambulance next to the seed's means, so one trip is seen in context
    ea, eb = sa["emergency"], sb["emergency"]
    if (ea["finished"], ea["scheduled_in_run"]) == (eb["finished"], eb["scheduled_in_run"]):
        all_title = f"All {ea['scheduled_in_run']} ambulances"
        if ea["finished"] != ea["scheduled_in_run"]:
            all_title = f"{ea['finished']} of {ea['scheduled_in_run']} ambulances (finished)"
    else:
        all_title = "All ambulances (finished only)"

    def rel_mean(amb: dict) -> float:
        done = [amb[v["vehicle"]]["travel_time_s"] for v in relevant if amb[v["vehicle"]]["travel_time_s"] is not None]
        return data.derived(sum(done) / len(done))
    n_rel = data.derived(len(relevant))
    duo = []
    for title, fa, fb, d in (("This ambulance", va["travel_time_s"], vb["travel_time_s"], 0),
                             (all_title, ea["travel_time_mean_s"], eb["travel_time_mean_s"], 1),
                             (f"{n_rel} signal-relevant ambulances", rel_mean(amb_a), rel_mean(amb_b), 1),
                             ("All vehicles (ATT)", sa["metrics"]["att"], sb["metrics"]["att"], 1)):
        win = "a" if fa < fb else "b" if fb < fa else ""
        duo.append(f'<div class="ts-duo"><div class="h">{ui.esc(title)}</div><div class="vs">'
                   f'<div class="{"win" if win == "a" else ""}"><span class="ts-dot" style="background:{A.colour}"></span>'
                   f'<span class="who">{ui.esc(theme.short(*A.key))}</span><span class="n"><b>{fa:.{d}f}</b><small>s</small></span></div>'
                   f'<div class="{"win" if win == "b" else ""}"><span class="ts-dot" style="background:{B.colour}"></span>'
                   f'<span class="who">{ui.esc(theme.short(*B.key))}</span><span class="n"><b>{fb:.{d}f}</b><small>s</small></span></div></div></div>')
    ui.html('<div class="ts-duo-head"><span>Mean travel time, this seed</span>'
            f'{ui.source_chip(A.src + "/summary.json", B.src + "/summary.json")}</div>'
            f'<div class="ts-duos">{"".join(duo)}</div>')

    labels_by_iid = {iid: {str(p.index): phase_label(inter, p) for p in inter.green_phases} for iid, inter in net.intersections.items()}
    payload = {
        "t0": t0, "t1": t1, "focus": amb_id, "types": A.meta["vehicle_types"], "emergency": A.meta["emergency_type"],
        "dims": vehicle_dims(scfg), "colours": theme.VEHICLE_COLOURS, "geom": geometry(raw, net),
        "runs": [run_payload(A, sa, za, da, t0, t1, amb_id, labels_by_iid),
                 run_payload(B, sb, zb, db, t0, t1, amb_id, labels_by_iid)],
    }
    with st.container(key="replay-stage"):
        replay = ui.component("trafficsense_network_replay", "rp-host", "replay.css", "replay.js")
        replay(data=payload, key="replay", height="content")
        ui.html('<div class="ts-replay-src">' + ui.source_chip(
            A.rdir + "/replay.npz", B.rdir + "/replay.npz", A.rdir + "/meta.json", B.rdir + "/meta.json",
            decisions_file(A), decisions_file(B), roadnet_rel, SCENARIO_CFG) + "</div>")

    ui.chart(queue_figure([A, B], [za, zb], t0, t1, va, vb), A.rdir + "/replay.npz", B.rdir + "/replay.npz",
             key="replay_queue", height=260, title="Network queue over the hour",
             subtitle="Waiting vehicles on the whole grid, both runs; the replayed window is shaded")

    v = A.meta["verified"]
    ui.why(
        "<p><b>What is drawn.</b> CityFlow logged every vehicle's position and heading at the end of each second while "
        "the run was replayed. Between two logged seconds the canvas moves each vehicle in a straight line between its "
        "two logged positions; no vehicle, position or second is invented. Signals and queues change only at logged "
        "seconds. Vehicles are drawn to their length and width (with a minimum size on screen).</p>"
        "<p><b>Left-hand traffic.</b> CityFlow simulates right-hand traffic; India's left-hand network is its mirror "
        "image (docs/indian_scenario.md), so <i>Keep left</i> draws the mirror image and <i>As simulated</i> draws "
        "CityFlow's own layout. Road names (N, E, S, W) are the simulator's in both, as in the decision log and the "
        "LLM's prompts, so the compass in the mirrored view has north at the bottom.</p>"
        f"<p><b>Verified.</b> Each replay reproduces its saved run's ATT, throughput, queue, waiting time and all "
        f"{v['emergency_vehicles_identical']} ambulances exactly. LLM runs are driven by their decisions.jsonl (no model "
        "is called); deterministic controllers are run again.</p>"
        "<p><b>Which ambulance.</b> By default the first ambulance of the seed (by scheduled start) whose route crosses "
        "a signal: a fixed rule written into the page before it was first rendered, not a choice by result. One "
        "ambulance can differ a lot by chance; the means above put it in context. The seed is the emergency seed with "
        "the most ambulances (pre-registered, docs/dashboard.md).</p>")
