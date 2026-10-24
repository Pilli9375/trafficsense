"""Overview: the project in plain words, and the headline numbers (all read from outputs/)."""
from __future__ import annotations

import streamlit as st

from trafficsense.dashboard import data, theme, ui

FULL = "outputs/full/results.json"
MODEL_SIZE = "outputs/model_size/model_size.json"
DETECTOR = "outputs/perception/detector_test.json"
CAMERA = "outputs/camera_error/results.json"
BASELINES = ("maxpressure", "fixedtime_webster", "fixedtime")
NEMOTRON = "nvidia/nemotron-3-ultra-550b-a55b"


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


def render() -> None:
    ui.header("TrafficSense · B.Tech capstone",
              "Can a small local LLM run Indian traffic signals?",
              "A cooperative LLM signal controller (adapted from the ICLR paper CoLLMLight) running on a laptop GPU, "
              "tested in simulation against classical controllers, with a YOLOv8 detector trained on Indian road "
              "images to measure what real camera counts would do to it.")
    try:
        full = data.read_json(FULL, "Run scripts/make_results.py.")
        ms = data.read_json(MODEL_SIZE, "Run scripts/make_model_size.py.")
        det = data.read_json(DETECTOR, "Run scripts/eval_detector.py --stage test.")
        cam = data.read_json(CAMERA, "Run scripts/make_camera_error.py.")
        cfg = data.config()
    except data.MissingData as e:
        ui.missing(e)
        return

    seeds = {sc: len(next(iter(v.values()))["seeds"]) for sc, v in full["scenarios"].items()}
    em = full["emergency"]["controllers"]
    em_seeds = len(full["emergency"]["provenance"]["seeds"])
    n_amb = em["maxpressure"]["ambulances_relevant"]["n"]
    peak_base, peak_b, peak_llm = signal_rows(full, "indian_2x2_peak")
    off_base, off_b, off_llm = signal_rows(full, "indian_2x2_offpeak")
    main = ("llm_guarded_mp", "llama3.2:3b")
    expl = ("llm_guided_mp_v3", "gemma4:e4b")
    d_main = {sc: dict((k, d) for k, _, d in rows)[main] for sc, rows in (("peak", peak_llm), ("off", off_llm))}
    mp_cam = cam["main"]
    nem = ms["full"]["indian_2x2_peak_amb"]["models"][NEMOTRON]["ambulances"]

    mp_pcts = [mp_cam[sc]["maxpressure"][lvl]["att_vs_perfect"]["pct_mean"]
               for sc in ("indian_2x2_offpeak", "indian_2x2_peak") for lvl in ("junction", "crowded")]

    # ---- story ---------------------------------------------------------------------------
    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        ui.html_block(
            '<div class="ts-step"><div class="n">Problem</div><div class="t">Fixed plans do not adapt</div>'
            "<p>Indian junctions carry mixed traffic (two-wheelers, autos, cars, buses, trucks) whose demand "
            "changes through the day. Fixed signal plans cannot react, and adaptive controllers need vehicle "
            "counts that, in practice, come from cameras that make mistakes. Ambulances lose minutes in queues.</p></div>")
    with c2:
        ui.html_block(
            '<div class="ts-step"><div class="n">Approach</div><div class="t">Simulate, control, perceive</div><ul>'
            "<li>A CityFlow 2x2 grid of signalised junctions with an Indian vehicle mix and ambulances.</li>"
            "<li>LLM controllers on a local GPU via Ollama, against MaxPressure and fixed-time plans; "
            "designs and analyses pre-registered before the runs.</li>"
            "<li>YOLOv8n trained on the India Driving Dataset; its measured errors are fed back into "
            "the controllers' counts.</li></ul></div>")
    with c3:
        ui.html_block(
            '<div class="ts-step"><div class="n">Findings</div><div class="t">Safe, not better; useful for ambulances</div><ul>'
            f"<li>The pre-registered LLM arm's average travel time is {abs(d_main['peak']):.1f}% "
            f"{'slower' if d_main['peak'] > 0 else 'faster'} (peak) and {abs(d_main['off']):.1f}% "
            f"{'slower' if d_main['off'] > 0 else 'faster'} (off-peak) than MaxPressure's: safe, but no gain.</li>"
            f"<li>Told where ambulances are, LLM arms cut their travel time from "
            f"{em['maxpressure']['ambulances_relevant']['travel_time_mean_s']:.1f} s to "
            f"{em['llm_guided_mp_v3']['ambulances_relevant']['travel_time_mean_s']:.1f}–"
            f"{em['llm_guarded_mp']['ambulances_relevant']['travel_time_mean_s']:.1f} s, near rule-based preemption.</li>"
            f"<li>Realistic camera errors add {min(mp_pcts):.1f}–{max(mp_pcts):.1f}% to "
            "MaxPressure's travel time; a fixed plan is immune.</li>"
            "</ul></div>")

    st.write("")
    st.subheader("Headline numbers", anchor=False)

    # ---- KPI cards -------------------------------------------------------------------------
    k1, k2 = st.columns(2, gap="small")
    with k1:
        rows = ""
        for scen, base, b, llm in (("Peak", peak_base, peak_b, peak_llm), ("Off-peak", off_base, off_b, off_llm)):
            if scen == "Off-peak":
                lab, col = theme.entity(*base)
                rows += ui.row(f"{scen} · {lab} (best baseline)", f"{b['att'][0]:.1f} s", col, "")
            for k, att, d in llm:
                lab, col = theme.entity(*k)
                rows += ui.row(f"{scen} · {lab}", f"{att:.1f} s", col, ui.pct(d))
        lab, _ = theme.entity(*peak_base)
        ui.html_block(ui.kpi_card(
            "Average travel time · best baseline vs LLM arms", f"{peak_b['att'][0]:.1f}", "s",
            f"{lab}, the best baseline at peak (Indian 2x2, mean of {seeds['indian_2x2_peak']} seeds). "
            "Δ = vs the best baseline of the same scenario.", rows))
        ui.caption_source(FULL)
    with k2:
        arms = [(("maxpressure", None), em["maxpressure"]["ambulances_relevant"]["travel_time_mean_s"]),
                (("preemption_mp", None), em["preemption_mp"]["ambulances_relevant"]["travel_time_mean_s"]),
                (main, em["llm_guarded_mp"]["ambulances_relevant"]["travel_time_mean_s"]),
                (expl, em["llm_guided_mp_v3"]["ambulances_relevant"]["travel_time_mean_s"]),
                (("llm_guided_mp_v3", NEMOTRON), nem["travel_time_mean_s"])]
        top = max(v for _, v in arms)
        best_llm = min((a for a in arms if a[0][0].startswith("llm_")), key=lambda a: a[1])
        rows = "".join(ui.bar_row(theme.short(*k), f"{v:.1f} s", theme.entity(*k)[1], v / top) for k, v in arms)
        ui.html_block(ui.kpi_card(
            "Ambulance travel time", f"{best_llm[1]:.1f}", "s",
            f"{theme.entity(*best_llm[0])[0]}: fastest LLM arm. Mean over the {n_amb} ambulances whose route "
            f"crosses a signal, {em_seeds} seeds of peak traffic. The gemma4 and Nemotron hybrids are exploratory.", rows))
        ui.caption_source(FULL, MODEL_SIZE)

    k3, k4 = st.columns(2, gap="small")
    with k3:
        u = det["ultralytics"]
        pc = u["per_class"]
        rows = "".join(ui.bar_row(c, f"{pc[c]['mAP50']:.3f}", theme.CLASS_COLOURS[c], pc[c]["mAP50"])
                       for c in det["classes"])
        ui.html_block(ui.kpi_card(
            "Detector · mAP50 on the IDD test split", f"{u['mAP50']:.3f}", "",
            f"YOLOv8n, {det['errors']['images']:,} images never used in training; mAP50-95 {u['mAP50_95']:.3f}. "
            "Dashcam images, not a junction camera.", rows))
        ui.caption_source(DETECTOR)
    with k4:
        rows = ""
        for ctl in ("maxpressure", "llm_guarded_mp", "fixedtime_webster"):
            k = main if ctl == "llm_guarded_mp" else (ctl, None)
            lab, col = theme.entity(*k)
            for lvl in ("junction", "crowded"):
                vals = [mp_cam[sc][ctl][lvl]["att_vs_perfect"]["pct_mean"] for sc in ("indian_2x2_offpeak", "indian_2x2_peak")]
                rows += ui.row(f"{theme.short(*k)} · {theme.LEVEL_LABELS[lvl].lower()}",
                               f"{ui.pct(vals[0])} / {ui.pct(vals[1])}", col)
        big = mp_cam["indian_2x2_offpeak"]["maxpressure"]["junction"]["att_vs_perfect"]["pct_mean"]
        ui.html_block(ui.kpi_card(
            "Camera-error impact on travel time", ui.pct(big), "",
            "MaxPressure with the junction-camera errors measured from our detector, off-peak. "
            "Rows: off-peak / peak, paired by seed against exact counts.", rows))
        ui.caption_source(CAMERA)

    ui.note(
        "<p><b>How to read these numbers.</b> Simulation results are means over "
        f"{min(seeds.values())}–{em_seeds} seeds, reported as measured: no significance test was pre-registered, so "
        "small differences are leads, not proof. Arms marked <i>exploratory</i> were not chosen by the "
        "pre-registered selection rule. Ambulance positions are assumed to come from GPS/V2X, never from the camera. "
        "The detector was evaluated once on the test split after its threshold was frozen on validation data.</p>",
        tags=[("pre-registered", ""), ("no significance test", "warn")])
