"""Generated tables of README.md and the report. Each function returns Markdown for one
`<!-- BEGIN:name -->` block. Values come from `facts()` (outputs/ and configs/) or are copied
from tables in docs whose own --check scripts verify them against outputs/; never from literals.

Pipe tables get separator dashes in proportion to their content, so pandoc gives LaTeX and Word
relative column widths and long cells wrap inside the page instead of running into the margin.
"""
from __future__ import annotations

import re
from pathlib import Path

from trafficsense.report.numbers import DocTables

SHORT = {
    "LLM main: guarded hybrid, `llama3.2:3b`": "LLM, pre-registered (guarded, `llama3.2:3b`)",
    "LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b`": "LLM, exploratory (hybrid_v3, `gemma4:e4b`)",
    "maxpressure": "MaxPressure", "fixedtime_webster": "Webster fixed time", "preemption_mp": "MaxPressure + preemption",
    "llm_guarded_mp": "LLM, pre-registered (guarded, `llama3.2:3b`)",
    "llm_guided_mp_v3": "LLM, exploratory (hybrid_v3, `gemma4:e4b`)",
    "indian_2x2_offpeak": "Indian 2x2 off-peak", "indian_2x2_peak": "Indian 2x2 peak",
    "jinan_3x4": "Jinan 3x4", "indian_2x2_peak_amb": "Peak + ambulances",
    "nvidia/nemotron-3-ultra-550b-a55b": "nemotron-3-ultra-550b",
}


def short(s: str) -> str:
    for k, v in SHORT.items():
        if s == k or s == f"`{k}`":
            return v
    return s


def md(header, rows, align=None):
    ncol = len(header)
    rows = [[str(c).replace(" ± ", "\u00a0±\u00a0") for c in r] for r in rows]
    if align is None:
        num = re.compile(r"^[+\-−–]?\d")
        def numeric(c):   # short cells that start with a number: counts, means, percentages
            c = str(c).strip()
            return bool(num.match(c)) and len(c) <= 18
        align = ["l"] + ["r" if sum(numeric(r[i]) for r in rows) > len(rows) / 2 else "l" for i in range(1, ncol)]
    def width(w):   # monospace (code) characters are about 1.5 times as wide as body text
        return 1.5 * len(w.strip("`")) if w.startswith("`") else len(w.replace("*", ""))

    def words(i):
        cells = [str(header[i])] + [str(r[i]) for r in rows]
        return [w for c in cells for w in re.split(r"[ /]+", c) if w]
    need = [max(width(w) for w in words(i)) + 3 for i in range(ncol)]          # longest unbreakable word
    want = [min(max(len(str(header[i])) // 2, max(len(str(r[i])) for r in rows) if rows else 0, need[i]), 48)
            for i in range(ncol)]
    want = [max(w, n) for w, n in zip(want, need)]
    total = sum(want)
    dashes = [max(3, round(100 * w / total)) for w in want]
    sep = []
    for a, d in zip(align, dashes):
        s = "-" * d
        sep.append(s[:-1] + ":" if a == "r" else (":" + s[1:-1] + ":" if a == "c" else s))
    out = ["| " + " | ".join(str(h) for h in header) + " |", "|" + "|".join(sep) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def doc(dt: DocTables, path: str, block: str, cols=None, rows=None, rename=None, drop_bold=True):
    """Columns `cols` (header substrings, in order) of a checked doc table; rows filtered by `rows`
    (a function of the row dict); headers renamed by `rename`."""
    header, body = dt.table(path, block)
    idx = list(range(len(header))) if cols is None else [_col(header, c) for c in cols]
    out = []
    for r in body:
        d = dict(zip(header, r))
        if rows and not rows(d):
            continue
        cells = [short(r[i]) for i in idx]
        if drop_bold:
            cells = [re.sub(r"\*\*(.*?)\*\*", r"\1", c) for c in cells]
        out.append(cells)
    hdr = [(rename or {}).get(header[i], header[i]) for i in idx]
    return hdr, out


def _col(header, sub):
    hit = ([i for i, h in enumerate(header) if h == sub] or [i for i, h in enumerate(header) if h.startswith(sub)]
           or [i for i, h in enumerate(header) if sub in h])
    if len(hit) != 1:
        raise KeyError(f"column {sub!r} matches {len(hit)} of {header}")
    return hit[0]


def from_doc(dt, path, block, **kw):
    h, r = doc(dt, path, block, **kw)
    return md(h, r)


def pm(fs, k, nd=1):
    return f"{fs[k + '.att'].value:.{nd}f} ± {fs[k + '.att_sd'].value:.{nd}f}"


def pct(v, nd=1):
    return f"{v:+.{nd}f}%".replace("-", "−")


# --- README -------------------------------------------------------------------------------

def readme_headline(fs, dt) -> str:
    rows = []
    for sc, name in (("off", "Indian 2x2, off-peak (3 seeds)"), ("peak", "Indian 2x2, peak (3 seeds)"),
                     ("jinan", "Jinan 3x4, real flow (3 seeds)")):
        row = [f"ATT (s), {name}", pm(fs, f"f.{sc}.mp"), pm(fs, f"f.{sc}.web"),
               f"{pm(fs, f'f.{sc}.llm')} ({pct(fs[f'f.{sc}.llm.vs_mp'].value)})"]
        row.append(f"{pm(fs, f'f.{sc}.gem')} ({pct(fs[f'f.{sc}.gem.vs_mp'].value)})" if f"f.{sc}.gem.att" in fs else "not run")
        rows.append(row)
    e = lambda a: f"{fs[f'e.{a}.amb'].value:.1f}"
    rows.append([f"Ambulance travel time (s), mean of {fs['e.mp.amb_n'].value:.0f} signal-relevant trips, 5 seeds",
                 e("mp"), e("web"), f"{e('llm')} (preemption rule: {e('pre')})", e("gem")])
    rows.append(["ATT change with junction-camera counts (off-peak / peak)",
                 f"{pct(fs['c.off.mp.junction.pct'].value)} / {pct(fs['c.peak.mp.junction.pct'].value)}",
                 "unaffected (reads no counts)",
                 f"{pct(fs['c.off.llm.junction.pct'].value)} / {pct(fs['c.peak.llm.junction.pct'].value)}", "not run"])
    return "\n".join(["|  | MaxPressure | Webster fixed time | **LLM, pre-registered** (guarded, `llama3.2:3b`) "
                      "| LLM, exploratory (`gemma4:e4b`) |", "|---|--:|--:|--:|--:|"]
                     + ["| " + " | ".join(r) + " |" for r in rows])


# --- chapter 4: simulation and scenario -------------------------------------------------------

V, I, B, R, E, P, C, M, L, EM = ("docs/validation.md", "docs/indian_scenario.md", "docs/baselines.md",
                                 "docs/results.md", "docs/emergency.md", "docs/perception.md", "docs/camera_error.md",
                                 "docs/model_size.md", "docs/llm_benchmark.md", "docs/emergency.md")


def tab_validation(fs, dt):
    return from_doc(dt, V, "exactness", rename={"Controller": "Controller"})


def tab_fixedtime_bug(fs, dt):
    rows = []
    for block, name in (("all_synthetic", "Synthetic 4x4"), ("all_jinan", "Jinan 3x4"), ("all_hangzhou", "Hangzhou 4x4")):
        h, body = dt.table(V, block)
        for r in body:
            if r[0] in ("CoLLMLight code: FixedTime", "Ours: FixedTime, 4 phases, 30 s grid (matched, correct cycle)",
                        "CoLLMLight code: MaxPressure"):
                label = {"CoLLMLight code: FixedTime": "CoLLMLight's FixedTime (bug: E-W only)",
                         "CoLLMLight code: MaxPressure": "CoLLMLight's MaxPressure"}.get(r[0], "Correct 4-phase FixedTime, same 30 s grid")
                rows.append([name, label, r[_col(h, "ATT (CityFlow)")], r[_col(h, "ATT (CoLLMLight def.)")],
                             r[_col(h, "Throughput (CoLLMLight def.)")]])
    return md(["Dataset", "Controller", "CityFlow ATT (s)", "ATT, CoLLMLight's definition (s)",
               "Throughput, CoLLMLight's definition"], rows)


def tab_network(fs, dt):
    g = lambda k: fs[f"scn.roadnet.{k}"].value
    rows = [["Grid", f"{g('rows'):.0f} × {g('cols'):.0f} signalised intersections", "project specification"],
            ["Spacing between intersections", f"{g('spacing_m'):.0f} m", "project specification"],
            ["Entry and exit roads", f"{g('boundary_road_m'):.0f} m", "assumption (same as spacing)"],
            ["Lanes per direction", f"{g('lanes.left') + g('lanes.straight') + g('lanes.right'):.0f} (one per turn)",
             "CityFlow generator layout"],
            ["Lane width", f"{g('lane_width_m'):.1f} m", "project specification"],
            ["Speed limit", f"{g('lane_max_speed_mps'):.1f} m/s ({g('lane_max_speed_mps') * 3.6:.0f} km/h)",
             "assumption within the 11–13 m/s range"],
            ["Centre to stop line", f"{g('intersection_width_m'):.0f} m", "assumption (three lanes plus margin)"],
            ["Phases", "0 = 5 s transition (free turns only); 1–8 green", "CityFlow generator"],
            ["Minimum / maximum green", f"{fs['cfg.signal.min_green'].value:.0f} s / {fs['cfg.signal.max_green'].value:.0f} s"
             f" (MaxPressure and LLM arms: minimum {fs['cfg.mp.min_green'].value:.0f} s)", "configs/default.yaml"]]
    return md(["Parameter", "Value", "Source"], rows)


def tab_mix(fs, dt):
    return from_doc(dt, I, "mix", cols=["Type", "Share (config", "Length", "Width", "minGap", "headwayTime", "maxSpeed"],
                    rename={"Share (config, normalised)": "Share"})


def tab_capacity(fs, dt):
    return from_doc(dt, I, "capacity", cols=["Quantity", "Value"])


def tab_demand_selection(fs, dt):
    return from_doc(dt, I, "selection")


def tab_mg_selection(fs, dt):
    h, rows = doc(dt, B, "mg_selection")
    h = [c for c in h if c] + ["Chosen"]
    rows = [r[:-1] + [r[-1] or ""] for r in rows]
    h = ["Min green", "Jinan", "Hangzhou", "Off-peak", "Peak", "Mean rank", "Mean ATT / best", "Chosen"]
    return md(h, rows)


def tab_baselines_indian(fs, dt):
    out = []
    for lvl in ("offpeak", "peak"):
        h, rows = doc(dt, I, f"results_{lvl}", cols=["Controller", "ATT", "Queue", "Throughput", "Still waiting",
                                                      "Time in transition"])
        out += [[lvl.replace("offpeak", "off-peak")] + r for r in rows]
    return md(["Level", "Controller", "ATT (s)", "Queue / int. (veh)", "Finished trips", "Waiting to enter at end",
               "Share of time in transition"], out)


# --- chapter 5: perception --------------------------------------------------------------------

def tab_idd(fs, dt):
    rows = []
    for split, src, role in (("train", "official train minus held-out drives", "training"),
                             ("val", "held-out official-train drives", "early stopping, threshold"),
                             ("test", "official val", "final numbers, used once")):
        rows.append([split, src, role, f"{fs[f'idd.{split}.images'].value:,.0f}", f"{fs[f'idd.{split}.sequences'].value:.0f}",
                     f"{fs[f'idd.{split}.boxes'].value:,.0f}"])
    return md(["Our split", "From", "Used for", "Images", "Drives", "Boxes"], rows)


def tab_det_classes(fs, dt):
    rows = []
    for c in ("car", "motorcycle", "autorickshaw", "bus", "truck", "bicycle", "person"):
        k = f"d.test.{c}"
        rows.append([c, f"{fs[k + '.gt'].value:,.0f}", f"{fs[k + '.map50'].value:.3f}", f"{fs[k + '.map5095'].value:.3f}",
                     f"{fs[k + '.precision'].value:.1f}%", f"{fs[k + '.recall'].value:.1f}%", f"{fs[k + '.miss'].value:.1f}%",
                     f"{fs[k + '.fdet'].value:.3f}"])
    rows.append(["all", f"{fs['d.test.gt'].value:,.0f}", f"{fs['d.test.map50'].value:.3f}", f"{fs['d.test.map5095'].value:.3f}",
                 "", "", "", ""])
    return md(["Class", "Boxes", "mAP50", "mAP50-95", "Precision", "Recall", "Miss rate", "False det. / image"], rows)


def tab_det_sizes(fs, dt):
    return from_doc(dt, P, "detector_test_sizes", rename={"small miss rate (GT)": "Small: miss rate (boxes)",
                                                          "medium miss rate (GT)": "Medium", "large miss rate (GT)": "Large"})


def tab_camera_params(fs, dt):
    return from_doc(dt, C, "camera_params")


# --- chapter 7: results -----------------------------------------------------------------------

def _full(sc):
    def f(fs, dt):
        return from_doc(dt, R, f"results_{sc}", cols=["Controller", "Seeds", "ATT (s)", "Queue", "Waiting", "Finished",
                                                       "vs MaxPressure"])
    return f


def tab_paired(fs, dt):
    return from_doc(dt, R, "results_paired", rows=lambda d: "Webster" not in d["Controller"] and "FixedTime" not in d["Controller"],
                    rename={"Seeds with lower / higher ATT than MaxPressure": "Seeds lower / higher than MaxPressure"})


def tab_llm_stats(fs, dt):
    return from_doc(dt, R, "results_llm", cols=["Scenario", "Arm", "Calls", "Failures", "Latency mean", "p95 per run",
                                                 "answer differs", "Guard", "Applied phase"],
                    rename={"LLM's answer differs from MaxPressure": "Answer differs from MaxPressure",
                            "Guard replaced the answer": "Guard replaced it",
                            "Applied phase differs from MaxPressure": "Applied phase differs"})


def tab_bench(fs, dt):
    return from_doc(dt, L, "llm_benchmark", cols=["Arm", "Model", "Failures", "Latency p95", "Queue", "ATT at 600",
                                                   "Eligible"],
                    rows=lambda d: d["Arm"] != "baseline")


def tab_bench_selection(fs, dt):
    return from_doc(dt, L, "llm_selection")


def tab_emergency(fs, dt):
    return from_doc(dt, R, "results_emergency")


def tab_ambulances(fs, dt):
    return from_doc(dt, R, "results_emergency_ambulances",
                    cols=["Controller", "Relevant", "Travel time mean", "Median", "Stopped mean", "Per ambulance"],
                    rename={"Relevant ambulances finished / total": "Finished", "Per ambulance vs preemption_mp (s)":
                            "Per ambulance vs preemption (s)", "Stopped mean (s)": "Stopped (s)",
                            "Travel time mean (s)": "Travel time (s)"})


def tab_model_size(fs, dt):
    return from_doc(dt, M, "model_size_full", cols=["Model", "Total params", "ATT (s)", "ATT vs MaxPressure", "Seeds worse",
                                                     "Follows pressure", "Answer differs", "Failed calls"],
                    rename={"Failed calls → MaxPressure's choice applied": "Failed calls"})


def tab_model_size_amb(fs, dt):
    return from_doc(dt, M, "model_size_ambulances")


def _camera(sc):
    def f(fs, dt):
        return from_doc(dt, C, f"camera_main_{sc}")
    return f


def tab_camera_sweep(fs, dt):
    return from_doc(dt, C, "camera_sweep")


def tab_camera_emergency(fs, dt):
    return from_doc(dt, C, "camera_emergency")


def tab_decomposition(fs, dt):
    return from_doc(dt, C, "camera_decomposition", cols=["junction-camera errors", "Off-peak", "Peak", "realised detection",
                                                          "phantoms"])


# --- appendix ---------------------------------------------------------------------------------

def tab_app_per_seed(fs, dt):
    return from_doc(dt, I, "per_seed", cols=["Level", "Controller", "Seed", "ATT (s)", "Queue", "Waiting (s)", "Throughput",
                                             "Waiting to enter"])


def tab_app_mp_selection(fs, dt):
    return from_doc(dt, B, "mp_selection", cols=["Interval", "jinan", "hangzhou", "offpeak", "_peak", "Mean rank", "Mean ATT"])


def tab_app_hosted(fs, dt):
    return from_doc(dt, M, "model_size_hosted", cols=["Started", "Run", "Calls", "Calls that needed", "Failed calls",
                                                      "Wall time (min)"])


def tab_app_camera_llm(fs, dt):
    return from_doc(dt, C, "camera_llm")


def tab_app_crosscheck(fs, dt):
    out = []
    for block, name in (("crosscheck_synthetic", "Synthetic 4x4"), ("crosscheck_jinan", "Jinan 3x4"),
                        ("crosscheck_hangzhou", "Hangzhou 4x4")):
        h, rows = doc(dt, V, block)
        out += [[name] + r for r in rows]
    h = ["Dataset", "Run", "ATT (their def.)", "Throughput (their def.)", "Queue (their def.)", "Waiting (their def.)",
         "CityFlow ATT", "Engine seed"]
    return md(h, out)


def tab_app_bench_full(fs, dt):
    return from_doc(dt, L, "llm_decisions")


# --- appendix code blocks ---------------------------------------------------------------------

def _yaml_section(text: str, key: str, indent: int = 0) -> str:
    """The lines of `key:` at the given indentation up to the next key at that indentation."""
    lines = text.splitlines()
    pre = " " * indent
    start = next((i for i, ln in enumerate(lines) if ln.startswith(f"{pre}{key}:")), None)
    if start is None:
        raise KeyError(f"{key} not found in YAML text")
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and not ln.startswith(pre + " ") and not ln.lstrip().startswith("#"):
            break
        if ln.strip() and len(ln) - len(ln.lstrip()) <= indent and ln.lstrip().startswith("#"):
            break
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def _fence(text: str, lang: str = "text") -> str:
    return f"```{lang}\n{text}\n```"


ROOT_CACHE: dict = {}


def code_config(fs, dt):
    text = (ROOT_CACHE["root"] / "configs/default.yaml").read_text()
    parts = [_yaml_section(text, k) for k in ("sim", "signal", "emergency")]
    parts.append("controllers:  # excerpt")
    parts += [_yaml_section(text, k, 2) for k in ("fixedtime", "fixedtime_webster", "maxpressure", "preemption_mp",
                                                  "llm_guided_mp_v3", "llm_guarded_mp")]
    parts.append(_yaml_section(text, "llm"))
    return _fence("\n".join(parts), "yaml")


def code_scenario(fs, dt):
    text = (ROOT_CACHE["root"] / "configs/scenarios/indian_2x2.yaml").read_text()
    return _fence("\n".join(_yaml_section(text, k) for k in ("roadnet", "turn_probabilities", "entry_weights",
                                                              "demand_levels", "emergency")), "yaml")


def _prompts():
    from trafficsense.report import prompts
    if "prompts" not in ROOT_CACHE:
        ROOT_CACHE["prompts"] = prompts.system_prompts(ROOT_CACHE["root"])
        ROOT_CACHE["user"] = prompts.example_user_message(ROOT_CACHE["root"])
        ROOT_CACHE["obs"] = prompts.example_observation(ROOT_CACHE["root"])
    return ROOT_CACHE


def _code_prompt(version):
    def f(fs, dt):
        return _fence(_prompts()["prompts"][version])
    return f


def code_prompt_user(fs, dt):
    return _fence(_prompts()["user"])


def code_example_time(fs, dt):
    o = _prompts()["obs"]
    from trafficsense.report.prompts import EXAMPLE
    amb = o["ambulances"][0]
    top = o["ranking"][0]
    label = {p["id"]: p["label"] for p in o["phases"]}
    return (f"Indian 2x2 peak with ambulances, seed {EXAMPLE['seed']}, `{EXAMPLE['iid']}` at "
            f"t = {o['example_time_s']} s, under MaxPressure control up to that moment. MaxPressure ranks phase "
            f"{top} ({label[top]}) first, but an ambulance {amb['distance_m']:.0f} m from the stop line is served by "
            f"phases {', '.join(map(str, amb['phases']))}, so a phase that serves it is among the options.")


DECISION_RUN = "outputs/emergency/runs/20261015-090843_indian_2x2_peak_amb_llm_guarded_mp_s0"


def code_decision(fs, dt):
    import json
    path = ROOT_CACHE["root"] / DECISION_RUN / "decisions.jsonl"
    for ln in path.read_text().splitlines():
        d = json.loads(ln)
        if d.get("serves_nearest_ambulance") and d.get("disagrees_with_mp") and d.get("guard_ambulance_exempt"):
            keep = ["step", "intersection", "current_phase", "time_in_phase", "allowed", "mp_ranking", "mp_choice",
                    "ambulances", "latency_s", "prompt_tokens", "server_model", "raw", "llm_phase",
                    "guard_threshold", "guard_llm_pressure", "guard_override", "guard_ambulance_exempt", "phase"]
            d = {k: (round(d[k], 2) if isinstance(d[k], float) else d[k]) for k in keep}
            body = ",\n".join(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in d.items())
            return _fence("{\n" + body + "\n}", "json")
    raise ValueError("no decision of the required kind in " + DECISION_RUN)


TABLES = {
    "readme_headline": readme_headline,
    "tab_validation": tab_validation, "tab_fixedtime_bug": tab_fixedtime_bug, "tab_network": tab_network,
    "tab_mix": tab_mix, "tab_capacity": tab_capacity, "tab_demand_selection": tab_demand_selection,
    "tab_mg_selection": tab_mg_selection, "tab_baselines_indian": tab_baselines_indian,
    "tab_idd": tab_idd, "tab_det_classes": tab_det_classes, "tab_det_sizes": tab_det_sizes,
    "tab_camera_params": tab_camera_params,
    "tab_full_off": _full("indian_2x2_offpeak"), "tab_full_peak": _full("indian_2x2_peak"),
    "tab_full_jinan": _full("jinan_3x4"), "tab_paired": tab_paired, "tab_llm_stats": tab_llm_stats,
    "tab_bench": tab_bench, "tab_bench_selection": tab_bench_selection, "tab_emergency": tab_emergency,
    "tab_ambulances": tab_ambulances, "tab_model_size": tab_model_size, "tab_model_size_amb": tab_model_size_amb,
    "tab_camera_off": _camera("indian_2x2_offpeak"), "tab_camera_peak": _camera("indian_2x2_peak"),
    "tab_camera_sweep": tab_camera_sweep, "tab_camera_emergency": tab_camera_emergency,
    "tab_decomposition": tab_decomposition,
    "tab_app_per_seed": tab_app_per_seed, "tab_app_mp_selection": tab_app_mp_selection,
    "tab_app_hosted": tab_app_hosted, "tab_app_camera_llm": tab_app_camera_llm,
    "tab_app_crosscheck": tab_app_crosscheck, "tab_app_bench_full": tab_app_bench_full,
    "code_config": code_config, "code_scenario": code_scenario, "code_prompt_v1": _code_prompt("v1"),
    "code_prompt_v2": _code_prompt("v2"), "code_prompt_v3": _code_prompt("v3"),
    "code_prompt_guided": _code_prompt("guided"), "code_prompt_guided_v3": _code_prompt("guided_v3"),
    "code_prompt_guided_v3_amb": _code_prompt("guided_v3, emergency scenario"),
    "code_prompt_user": code_prompt_user, "code_example_time": code_example_time, "code_decision": code_decision,
}


def blocks(root: Path, fs, dt: DocTables, used: set[str] | None = None) -> dict[str, str]:
    """The blocks named in `used` (all if None)."""
    ROOT_CACHE["root"] = root
    return {name: f(fs, dt) for name, f in TABLES.items() if used is None or name in used}
