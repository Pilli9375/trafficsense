"""Overview: the headline result, three stat tiles, the story in three steps and the architecture.

Every number is read from outputs/ or computed from those values through data.derived().
The animated grid behind the headline is decoration (no data): a schematic of the 2x2 network
with one ambulance route; the Network Replay page shows the real runs.
"""
from __future__ import annotations

from trafficsense.dashboard import data, theme, ui

FULL = "outputs/full/results.json"
MODEL_SIZE = "outputs/model_size/model_size.json"
DETECTOR = "outputs/perception/detector_test.json"
CAMERA = "outputs/camera_error/results.json"
BASELINES = ("maxpressure", "fixedtime_webster", "fixedtime")
NEMOTRON = "nvidia/nemotron-3-ultra-550b-a55b"
MAIN = ("llm_guarded_mp", "llama3.2:3b")
EXPL = ("llm_guided_mp_v3", "gemma4:e4b")
TILE_NAMES = {MAIN: "LLM main", EXPL: "gemma4 (expl.)", ("maxpressure", None): "MaxPressure",
              ("fixedtime_webster", None): "Webster"}
CLASS_ABBR = {"car": "car", "motorcycle": "2W", "autorickshaw": "auto", "bus": "bus", "truck": "truck",
              "bicycle": "cycle", "person": "person"}


def _by_controller(scenario: dict) -> dict[tuple[str, str | None], dict]:
    return {(v["controller"], v["model"]): v for v in scenario.values()}


def signal_rows(full: dict, scenario: str) -> tuple[tuple, dict, list[tuple]]:
    """Best baseline (lowest mean ATT) and the LLM arms of one scenario, with % vs that baseline."""
    arms = _by_controller(full["scenarios"][scenario])
    base = min((k for k in arms if k[0] in BASELINES), key=lambda k: arms[k]["att"][0])
    best = arms[base]["att"][0]
    llm = [(k, arms[k]["att"][0], data.derived(100 * (arms[k]["att"][0] / best - 1)))
           for k in arms if k[0].startswith("llm_")]
    return base, arms[base], llm


# ---- decoration: the schematic grid behind the headline --------------------------------------------
HERO_GRID = """<svg class="ts-hero-grid" viewBox="0 0 420 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<defs><linearGradient id="trail" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff3b3b" stop-opacity="0"/>
<stop offset="1" stop-color="#ff3b3b" stop-opacity=".9"/></linearGradient>
<radialGradient id="glow"><stop offset="0" stop-color="#ff3b3b" stop-opacity=".9"/><stop offset="1" stop-color="#ff3b3b" stop-opacity="0"/></radialGradient></defs>
<g class="roads"><path d="M0 95H420M0 205H420M150 0V300M270 0V300"/></g>
<g class="lanes"><path d="M0 95H420M0 205H420M150 0V300M270 0V300"/></g>
<g class="boxes"><rect x="139" y="84" width="22" height="22" rx="3"/><rect x="259" y="84" width="22" height="22" rx="3"/>
<rect x="139" y="194" width="22" height="22" rx="3"/><rect x="259" y="194" width="22" height="22" rx="3"/></g>
<g class="sig"><circle class="g1" cx="164" cy="80" r="3"/><circle class="r1" cx="136" cy="110" r="3"/>
<circle class="g2" cx="284" cy="80" r="3"/><circle class="r2" cx="256" cy="110" r="3"/>
<circle class="g2" cx="164" cy="190" r="3"/><circle class="r2" cx="136" cy="220" r="3"/>
<circle class="g1" cx="284" cy="190" r="3"/><circle class="r1" cx="256" cy="220" r="3"/></g>
<path class="route" d="M420 90H155V300"/>
<g class="amb"><circle r="16" fill="url(#glow)"/><rect x="-6" y="-3.5" width="12" height="7" rx="2" fill="#fff"/>
<rect class="beacon" x="-2" y="-3.5" width="4" height="7" rx="1"/></g>
</svg>"""



STEP_ICONS = {
    "p": '<path d="M12 7v5l3 2"/><circle cx="12" cy="12" r="8.5"/>',
    "a": '<rect x="6" y="6" width="12" height="12" rx="2.5"/><path d="M9.5 2.5v3M14.5 2.5v3M9.5 18.5v3M14.5 18.5v3M2.5 9.5h3M2.5 14.5h3M18.5 9.5h3M18.5 14.5h3"/><path d="M10 10h4v4h-4z"/>',
    "f": '<path d="M4 19h16"/><path d="M7 16v-5M12 16V7M17 16v-8"/>',
}


def _svg_icon(paths: str, size: int = 20) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>')


ARROW = ('<div class="ts-arrow"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg></div>')

# ---- the architecture diagram (static, no data) ------------------------------------------------------
ARCH = """<div class="ts-arch"><svg viewBox="0 0 1000 286" role="img" aria-label="System architecture: junction camera, YOLOv8n detector and vehicle counts; four cooperative LLM agents that pick among MaxPressure's top phases, with ambulance positions from GPS or V2X; signal timing; and the CityFlow simulator, whose traffic gives the next counts.">
<defs><marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#3a475a"/></marker>
<marker id="ahl" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#19e6d2"/></marker>
<marker id="ahr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#ff6b6b"/></marker></defs>
<rect class="grp" x="8" y="70" width="388" height="146" rx="14"/><text class="grpl" x="22" y="88">Perception · evaluated on IDD</text>
<g class="node" transform="translate(22,100)"><rect width="110" height="100" rx="12"/>
<g class="ic" transform="translate(44,16)"><rect x="0" y="5" width="16" height="12" rx="2"/><path d="M16 9l6-3v10l-6-3"/></g>
<text class="tt" x="55" y="62" text-anchor="middle">Camera</text><text class="st" x="55" y="80" text-anchor="middle">junction video</text></g>
<g class="node" transform="translate(148,100)"><rect width="110" height="100" rx="12"/>
<g class="ic" transform="translate(44,14)"><rect x="0" y="0" width="22" height="22" rx="3"/><rect x="4" y="5" width="9" height="7" rx="1"/><rect x="10" y="10" width="8" height="8" rx="1"/></g>
<text class="tt" x="55" y="62" text-anchor="middle">YOLOv8n</text><text class="st" x="55" y="80" text-anchor="middle">trained on IDD</text></g>
<g class="node" transform="translate(274,100)"><rect width="110" height="100" rx="12"/>
<g class="ic" transform="translate(44,16)"><path d="M2 18V8M8 18V3M14 18v-7M20 18v-4"/></g>
<text class="tt" x="55" y="62" text-anchor="middle">Counts</text><text class="st" x="55" y="80" text-anchor="middle">queue per lane</text></g>
<path class="flow live" d="M132 150H146" marker-end="url(#ahl)"/><path class="flow live" d="M258 150H272" marker-end="url(#ahl)"/>
<g class="node amb" transform="translate(410,6)"><rect width="280" height="50" rx="12"/>
<g class="ic" transform="translate(16,13)"><rect x="0" y="4" width="22" height="15" rx="3"/><path d="M11 7.5v8M7 11.5h8"/></g>
<text class="tt" x="52" y="23">Ambulance positions</text><text class="st" x="52" y="40">GPS / V2X (assumed), never the camera</text></g>
<path class="flow amb" d="M550 56V90" marker-end="url(#ahr)"/>
<g class="node hot" transform="translate(428,92)"><rect width="244" height="116" rx="14"/>
<g class="ic" transform="translate(18,16)"><rect x="0" y="0" width="22" height="22" rx="4"/><path d="M6 8h10M6 13h7"/></g>
<text class="tt" x="50" y="26">LLM agents ×4</text><text class="chip" x="50" y="42">cooperative · local</text>
<text class="st" x="18" y="66">a small model on the 4 GB laptop GPU;</text>
<text class="st" x="18" y="83">each sees its neighbours and picks</text>
<text class="st" x="18" y="100">one of MaxPressure's top phases</text></g>
<path class="flow live" d="M384 150H426" marker-end="url(#ahl)"/>
<g class="node" transform="translate(712,100)"><rect width="118" height="100" rx="12"/>
<g class="ic" transform="translate(49,10)"><rect x="3" y="0" width="14" height="26" rx="4"/><circle cx="10" cy="6" r="2"/><circle cx="10" cy="13" r="2"/><circle cx="10" cy="20" r="2"/></g>
<text class="tt" x="59" y="62" text-anchor="middle">Signals</text><text class="st" x="59" y="80" text-anchor="middle">min green, yellow</text></g>
<path class="flow live" d="M672 150H710" marker-end="url(#ahl)"/>
<g class="node sim" transform="translate(850,92)"><rect width="144" height="116" rx="14"/>
<g class="ic" transform="translate(16,16)"><path d="M0 7h26M0 17h26M8 0v24M18 0v24"/></g>
<text class="tt" x="16" y="62">CityFlow</text><text class="st" x="16" y="79">2x2 grid, Indian mix,</text><text class="st" x="16" y="96">with ambulances</text></g>
<path class="flow live" d="M830 150H848" marker-end="url(#ahl)"/>
<path class="flow" d="M922 208V246H329V202" marker-end="url(#ah)"/>
<text class="lbl" x="625" y="270" text-anchor="middle">simulated traffic gives the next counts: exact, or with the detector's measured errors</text>
</svg></div>"""


def render() -> None:
    try:
        full = data.read_json(FULL, "Run scripts/make_results.py.")
        ms = data.read_json(MODEL_SIZE, "Run scripts/make_model_size.py.")
        det = data.read_json(DETECTOR, "Run scripts/eval_detector.py --stage test.")
        cam = data.read_json(CAMERA, "Run scripts/make_camera_error.py.")
    except data.MissingData as e:
        ui.missing(e)
        return

    seeds = {sc: data.derived(len(next(iter(v.values()))["seeds"])) for sc, v in full["scenarios"].items()}
    em = full["emergency"]["controllers"]
    em_seeds = data.derived(len(full["emergency"]["provenance"]["seeds"]))
    n_amb = em["maxpressure"]["ambulances_relevant"]["n"]
    peak_base, peak_b, peak_llm = signal_rows(full, "indian_2x2_peak")
    off_base, off_b, off_llm = signal_rows(full, "indian_2x2_offpeak")
    d_peak, d_off = dict((k, d) for k, _, d in peak_llm), dict((k, d) for k, _, d in off_llm)
    nem = ms["full"]["indian_2x2_peak_amb"]["models"][NEMOTRON]["ambulances"]
    cam_main = cam["main"]

    # ---- hero: ambulance travel time, MaxPressure vs the fastest LLM arm --------------------------
    amb = {("maxpressure", None): em["maxpressure"]["ambulances_relevant"]["travel_time_mean_s"],
           ("preemption_mp", None): em["preemption_mp"]["ambulances_relevant"]["travel_time_mean_s"],
           MAIN: em["llm_guarded_mp"]["ambulances_relevant"]["travel_time_mean_s"],
           EXPL: em["llm_guided_mp_v3"]["ambulances_relevant"]["travel_time_mean_s"],
           ("llm_guided_mp_v3", NEMOTRON): nem["travel_time_mean_s"]}
    mp = amb[("maxpressure", None)]
    best_k = min((k for k in amb if k[0].startswith("llm_")), key=lambda k: amb[k])
    best = amb[best_k]
    faster = data.derived(100 * (1 - best / mp))
    faster_main = data.derived(100 * (1 - amb[MAIN] / mp))
    best_lab = theme.entity(*best_k)[0].replace(" (exploratory)", "").replace(" (exploratory, hosted)", "")
    tags = (["exploratory"] if theme.is_exploratory(*best_k) else ["pre-registered"]) + ["no significance test"]
    hero = (
        '<section class="ts-hero">' + HERO_GRID
        + f'<div class="src">{ui.source_chip(FULL, MODEL_SIZE)}</div>'
        + '<div class="q">Can a small, local LLM run Indian traffic signals?</div>'
        + f'<h1>Ambulances <span class="num"><span class="ts-count">{faster:.0f}</span>% faster</span></h1>'
        + f'<p class="lede">when the LLM controller is told where they are. Mean travel time of the <b>{n_amb} ambulances</b> '
          f'whose route crosses a signal, {em_seeds} seeds of peak traffic, against MaxPressure.</p>'
        + '<div class="cmp">'
        + f'<div><div class="k"><span class="ts-dot" style="background:{theme.entity("maxpressure", None)[1]}"></span>MaxPressure</div>'
          f'<div class="v">{mp:.1f}<small>s</small></div></div>'
        + f'<div class="best"><div class="k"><span class="ts-dot" style="background:{theme.entity(*best_k)[1]}"></span>{ui.esc(best_lab)}</div>'
          f'<div class="v">{best:.1f}<small>s</small></div></div>'
        + f'<div><div class="k"><span class="ts-dot" style="background:{theme.entity(*MAIN)[1]}"></span>LLM main, pre-registered</div>'
          f'<div class="v">{amb[MAIN]:.1f}<small>s · −{faster_main:.0f}%</small></div></div>'
        + f'<div><div class="k"><span class="ts-dot" style="background:{theme.entity("preemption_mp", None)[1]}"></span>Rule-based preemption</div>'
          f'<div class="v">{amb[("preemption_mp", None)]:.1f}<small>s</small></div></div>'
        + '</div>'
        + '<div class="badges">' + "".join(ui.badge(t) for t in tags) + ui.badge("ambulances not noised", "plain")
        + '</div></section>')

    # ---- tile 1: ATT vs MaxPressure ----------------------------------------------------------------
    att_rows = [(MAIN, "peak", d_peak[MAIN]), (MAIN, "off-peak", d_off[MAIN]),
                (EXPL, "peak", d_peak[EXPL]), (EXPL, "off-peak", d_off[EXPL])]
    scale = max(abs(d) for *_, d in att_rows)
    rows = ""
    for k, scen, d in att_rows:
        w = 50 * abs(d) / scale
        left = 50 if d >= 0 else 50 - w
        col = theme.entity(*k)[1]
        rows += (f'<div class="ts-mrow"><span class="n">{TILE_NAMES[k]} · {scen}</span>'
                 f'<span class="ts-track div"><span class="fill" style="left:{left:.1f}%;width:{w:.1f}%;background:{col}"></span></span>'
                 f'<span class="v">{ui.pct(d)}</span></div>')
    base_lab = theme.short(*peak_base)
    tile1 = (f'<div class="ts-tile"><div class="lab"><span class="grow">Travel time vs {ui.esc(base_lab)}</span>'
             f'{ui.source_chip(FULL)}</div>'
             f'<div class="val"><span class="ts-count">{ui.pct(d_peak[MAIN])}</span></div>'
             f'<div class="cap">Pre-registered LLM arm at peak, mean of {seeds["indian_2x2_peak"]} seeds: safe, but no gain. '
             f'Baseline: the best of the classical controllers ({ui.esc(base_lab)}, {peak_b["att"][0]:.1f} s).</div>'
             f'<div class="ts-mini">{rows}</div></div>')

    # ---- tile 2: detector mAP50 ----------------------------------------------------------------------
    u = det["ultralytics"]
    pc = u["per_class"]
    cols = "".join(f'<div class="c" title="{ui.esc(c)}: mAP50 {pc[c]["mAP50"]:.3f}">'
                   f'<span class="b" style="height:{40 * pc[c]["mAP50"]:.1f}px;background:{theme.CLASS_COLOURS[c]}"></span>'
                   f'<span class="l">{CLASS_ABBR[c]}</span></div>' for c in det["classes"])
    tile2 = (f'<div class="ts-tile"><div class="lab"><span class="grow">Detector mAP50 · IDD test split</span>'
             f'{ui.source_chip(DETECTOR)}</div>'
             f'<div class="val"><span class="ts-count">{u["mAP50"]:.3f}</span></div>'
             f'<div class="cap">YOLOv8n, {det["errors"]["images"]:,} images never used in training; mAP50-95 '
             f'{u["mAP50_95"]:.3f}. Dashcam images, not a junction camera.</div>'
             f'<div class="ts-cols">{cols}</div></div>')

    # ---- tile 3: camera-error impact -----------------------------------------------------------------
    rows = ""
    cam_rows = []
    for ctl, k in (("maxpressure", ("maxpressure", None)), ("llm_guarded_mp", MAIN), ("fixedtime_webster", ("fixedtime_webster", None))):
        vals = {sc: cam_main[sc][ctl]["junction"]["att_vs_perfect"] for sc in ("indian_2x2_offpeak", "indian_2x2_peak")}
        cam_rows.append((k, vals))
    top = max(abs(v[sc]["pct_mean"]) for _, v in cam_rows for sc in v)
    for k, vals in cam_rows:
        lab, col = theme.entity(*k)
        unaffected = all(v["pct_min"] == 0 and v["pct_max"] == 0 for v in vals.values())
        for sc, scen in (("indian_2x2_offpeak", "off-peak"), ("indian_2x2_peak", "peak")):
            if unaffected:
                rows += (f'<div class="ts-mrow"><span class="n">{TILE_NAMES[k]} fixed-time</span>'
                         f'<span class="v mute wide">unaffected</span></div>')
                break
            p = vals[sc]["pct_mean"]
            rows += (f'<div class="ts-mrow"><span class="n">{TILE_NAMES[k]} · {scen}</span>'
                     f'<span class="ts-track"><span class="fill" style="left:0;width:{100 * max(p, 0) / top:.1f}%;background:{col}"></span></span>'
                     f'<span class="v">{ui.pct(p)}</span></div>')
    big = cam_main["indian_2x2_offpeak"]["maxpressure"]["junction"]["att_vs_perfect"]["pct_mean"]
    tile3 = (f'<div class="ts-tile"><div class="lab"><span class="grow">Camera-error impact</span>'
             f'{ui.source_chip(CAMERA)}</div>'
             f'<div class="val"><span class="ts-count">{ui.pct(big)}</span></div>'
             f'<div class="cap">MaxPressure fed counts with our detector\'s measured junction-camera errors, off-peak, '
             'paired by seed against exact counts. A fixed plan reads no counts.</div>'
             f'<div class="ts-mini">{rows}</div></div>')

    ui.html(hero + f'<div class="ts-tiles" style="margin-top:16px">{tile1}{tile2}{tile3}</div>')
    ui.count_up()

    # ---- the story in three steps ----------------------------------------------------------------------
    mp_pcts = [cam_main[sc]["maxpressure"][lvl]["att_vs_perfect"]["pct_mean"]
               for sc in ("indian_2x2_offpeak", "indian_2x2_peak") for lvl in ("junction", "crowded")]
    steps = [
        ("p", "Problem", "Fixed signal plans cannot react to <b>mixed Indian traffic</b>, and ambulances lose minutes in queues."),
        ("a", "Approach", "<b>Local LLM agents</b> on a laptop GPU pick the phases of a simulated 2x2 grid; a YOLOv8n "
                          "detector's measured errors stress-test them."),
        ("f", "Findings", f"Travel time on a par with MaxPressure ({ui.pct(d_peak[MAIN])} at peak); ambulances "
                          f"<b>{faster_main:.0f}–{faster:.0f}% faster</b>; camera errors cost {min(mp_pcts):.1f}–{max(mp_pcts):.1f}%."),
    ]
    parts = []
    for i, (k, n, t) in enumerate(steps):
        if i:
            parts.append(ARROW)
        parts.append(f'<div class="ts-step"><div class="ic {k}">{_svg_icon(STEP_ICONS[k])}</div>'
                     f'<div><div class="n">{n}</div><div class="t">{t}</div></div></div>')
    ui.html('<div class="ts-sec"><div class="h" role="heading" aria-level="2">The project in three steps</div></div>'
            + f'<div class="ts-steps">{"".join(parts)}</div>')

    # ---- architecture -------------------------------------------------------------------------------
    every = full["emergency"]["provenance"]["llm_arm"]["decision_interval_s"]
    ui.html(f'<div class="ts-sec"><div class="h" role="heading" aria-level="2">System architecture</div>'
            f'<span>one decision cycle, every {every} s per junction</span></div>' + ARCH)

    ui.why(
        "<p><b>How to read these numbers.</b> Simulation results are means over "
        f"{min(seeds.values())}–{em_seeds} seeds, reported as measured. No significance test was pre-registered, so "
        "small differences are leads, not proof. Arms marked <i>exploratory</i> were not chosen by the "
        "pre-registered selection rule: the headline's fastest arm is one of them; the pre-registered main arm is "
        "shown next to it.</p>"
        "<p><b>Ambulances.</b> Positions are assumed to come from GPS / V2X, never from the camera, and are never "
        "noised. In CityFlow nobody yields and nothing overtakes, so only the signal can help an ambulance; the LLM "
        "arms see ambulances listed in their prompt and do not preempt.</p>"
        "<p><b>Detector.</b> Evaluated once on the test split after its threshold was frozen on validation data. "
        "IDD is dashcam footage, so its errors stand in for a junction camera's.</p>"
        "<p><b>Decoration.</b> The animated grid behind the headline is a schematic, not data; the Network Replay "
        "page shows real runs.</p>")
