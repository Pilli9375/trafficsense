"""Named numbers for the README and the report, each read from a file in outputs/ (or a config).

`facts()` returns {key: Fact}. A key names one number in display units: percentages are
already multiplied by 100, times are in seconds unless the key says otherwise. Every Fact
records the file it came from, so `scripts/make_report.py --sources` can list them.

Key scheme (scenario: off = Indian 2x2 off-peak, peak, jinan = Jinan 3x4, amb = Indian 2x2
peak with ambulances; arm: mp = MaxPressure, web = Webster plan, ft = 30 s FixedTime,
pre = rule-based preemption, llm = the pre-registered main LLM arm (guarded, llama3.2:3b),
gem = the exploratory gemma4:e4b hybrid):

    f.<sc>.<arm>.att | att_sd | queue | queue_sd | wait | trips | vs_mp     full experiments
    p.<sc>.<arm>.s<seed> | lower | higher                                  ATT minus MaxPressure per seed
    l.<sc>.<arm>.calls | fail | lat | p95lo | p95hi | differs | guard | applied | wall_h
    e.<arm>.att | att_sd | queue | trips | amb | amb_med | amb_stop | amb_all | amb_n
             | amb_fin | vs_pre | vs_pre_faster | vs_pre_slower | amb_cut_vs_mp
    c.<sc>.<arm>.<level>.att | att_sd | d | dmin | dmax | pct | pctmin | pctmax | queue
    c.amb.<arm>.<level>.att | d | dmin | dmax | pct | amb | amb_d | amb_slower | amb_faster
    c.sweep.<sc>.p<100p>.att | pct ;  c.peff.<sc>.<level> ;  c.dec.<part>.<sc>.d | pct | dmin | dmax
    m.<sc>.<model>.att | att_sd | vs_mp | vs_mp_min | vs_mp_max | worse | queue | follows | differs
             | fail | calls | amb | amb_stop | amb_vs_mp | amb_vs_pre | amb_serve | amb_calls
    d.<split>.map50 | map5095 ;  d.test.<class>.map50 | precision | recall | miss | fdet
    d.size.<class>.<small|medium|large> ;  d.conf | f1 | train_h | epochs | best_epoch
    cfg.<...>                                                             configs/*.yaml
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from trafficsense.config import load_config, repo_root


@dataclass(frozen=True)
class Fact:
    value: float
    source: str


SC = {"off": "indian_2x2_offpeak", "peak": "indian_2x2_peak", "jinan": "jinan_3x4", "amb": "indian_2x2_peak_amb"}
FULL_LABELS = {"mp": "MaxPressure", "web": "Webster fixed time", "ft": "FixedTime (4 phases, 30 s)",
               "pre": "Preemption (rule-based)", "llm": "LLM main: guarded hybrid, `llama3.2:3b`",
               "gem": "LLM exploratory, NOT selected by the rule: hybrid_v3, `gemma4:e4b`"}
CONTROLLERS = {"mp": "maxpressure", "web": "fixedtime_webster", "pre": "preemption_mp",
               "llm": "llm_guarded_mp", "gem": "llm_guided_mp_v3"}
MODELS = {"qwen": "qwen2.5:3b", "llama3b": "llama3.2:3b", "gem": "gemma4:e4b", "llama8b": "llama3.1:8b",
          "nemo": "nvidia/nemotron-3-ultra-550b-a55b"}
CLASSES = ["car", "motorcycle", "autorickshaw", "bus", "truck", "bicycle", "person"]

FILES = {
    "full": "outputs/full/results.json",
    "camera": "outputs/camera_error/results.json",
    "model_size": "outputs/model_size/model_size.json",
    "det_test": "outputs/perception/detector_test.json",
    "det_val": "outputs/perception/detector_val.json",
    "det_train": "outputs/perception/detector_train.json",
    "idd": "outputs/perception/idd_conversion.json",
    "bench": "outputs/llm_benchmark/benchmark.json",
    "indian": "outputs/indian_2x2/results.json",
    "calib": "outputs/validation/indian_demand_calibration.json",
    "mg_sweep": "outputs/baselines/maxpressure_min_green_sweep.json",
}


def _load(root: Path, name: str) -> dict:
    p = root / FILES[name]
    if not p.is_file():
        raise FileNotFoundError(f"{FILES[name]} is missing; the report's numbers are read from it")
    return json.loads(p.read_text())


class _Reg(dict):
    def put(self, key: str, value, source: str):
        if key in self:
            raise KeyError(f"duplicate fact {key}")
        if value is None:
            return
        self[key] = Fact(float(value), source)


@lru_cache(maxsize=4)
def facts(root: Path | None = None) -> dict[str, Fact]:
    root = root or repo_root()
    r = _Reg()
    _full(r, _load(root, "full"))
    _camera(r, _load(root, "camera"))
    _model_size(r, _load(root, "model_size"))
    _detector(r, _load(root, "det_test"), _load(root, "det_val"), _load(root, "det_train"), _load(root, "idd"))
    _bench(r, _load(root, "bench"))
    _indian(r, _load(root, "indian"), _load(root, "calib"), _load(root, "mg_sweep"))
    _config(r, root)
    return dict(r)


def _full(r: _Reg, b: dict):
    src = FILES["full"]
    for sc in ("off", "peak", "jinan"):
        arms = b["scenarios"][SC[sc]]
        mp = arms["MaxPressure"]["att"][0]
        for a, label in FULL_LABELS.items():
            if label not in arms:
                continue
            x = arms[label]
            k = f"f.{sc}.{a}"
            r.put(f"{k}.att", x["att"][0], src)
            r.put(f"{k}.att_sd", x["att"][1], src)
            r.put(f"{k}.queue", x["queue_mean_per_intersection"][0], src)
            r.put(f"{k}.queue_sd", x["queue_mean_per_intersection"][1], src)
            r.put(f"{k}.wait", x["waiting_time_mean"][0], src)
            r.put(f"{k}.trips", x["throughput"][0], src)
            r.put(f"{k}.vs_mp", 100 * (x["att"][0] - mp) / mp, src)
    for scname, arms in b["paired"].items():
        sc = {v: k for k, v in SC.items()}[scname]
        for label, x in arms.items():
            a = {v: k for k, v in FULL_LABELS.items()}[label]
            for s, d in zip(x["seeds"], x["att_minus_mp"]):
                r.put(f"p.{sc}.{a}.s{s}", d, src)
            r.put(f"p.{sc}.{a}.lower", x["seeds_lower_att"], src)
            r.put(f"p.{sc}.{a}.higher", x["seeds_higher_att"], src)
    for x in b["llm"].values():
        sc = {v: k for k, v in SC.items()}[x["scenario"]]
        a = {v: k for k, v in FULL_LABELS.items()}[x["arm"]]
        k = f"l.{sc}.{a}"
        r.put(f"{k}.calls", x["calls"], src)
        r.put(f"{k}.fail", 100 * x["failure_rate"], src)
        r.put(f"{k}.lat", x["latency_mean_s"], src)
        r.put(f"{k}.p95lo", x["latency_p95_s_range"][0], src)
        r.put(f"{k}.p95hi", x["latency_p95_s_range"][1], src)
        r.put(f"{k}.differs", 100 * x["mp_disagreement_rate"], src)
        if x["guard_overrides"] is not None:
            r.put(f"{k}.guard", 100 * x["guard_override_rate"], src)
        r.put(f"{k}.applied", 100 * x["applied_differs_rate"], src)
        r.put(f"{k}.wall_h", x["wall_time_h"], src)
    r.put("f.reproduced", sum(x["identical_metrics"] for x in b["reproduction"]), src)
    r.put("f.reproduced_of", len(b["reproduction"]), src)
    r.put("f.runs", b["provenance"]["runs"], src)
    ctl = b["emergency"]["controllers"]
    for a, c in CONTROLLERS.items():
        x = ctl[c]
        k = f"e.{a}"
        r.put(f"{k}.att", x["att_s"][0], src)
        r.put(f"{k}.att_sd", x["att_s"][1], src)
        r.put(f"{k}.queue", x["queue_mean_per_intersection"][0], src)
        r.put(f"{k}.trips", x["throughput"][0], src)
        rel = x["ambulances_relevant"]
        r.put(f"{k}.amb", rel["travel_time_mean_s"], src)
        r.put(f"{k}.amb_med", rel["travel_time_median_s"], src)
        r.put(f"{k}.amb_stop", rel["stopped_time_mean_s"], src)
        r.put(f"{k}.amb_n", rel["n"], src)
        r.put(f"{k}.amb_fin", rel["finished"], src)
        r.put(f"{k}.amb_all", x["ambulances_all"]["travel_time_mean_s"], src)
        r.put(f"{k}.amb_all_n", x["ambulances_all"]["n"], src)
        vp = x.get("vs_preemption_relevant")
        if vp:
            r.put(f"{k}.vs_pre", vp["mean_diff_s"], src)
            r.put(f"{k}.vs_pre_faster", vp["faster"], src)
            r.put(f"{k}.vs_pre_slower", vp["slower"], src)
    mp_amb = ctl["maxpressure"]["ambulances_relevant"]["travel_time_mean_s"]
    for a, c in CONTROLLERS.items():
        x = ctl[c]["ambulances_relevant"]["travel_time_mean_s"]
        r.put(f"e.{a}.amb_cut_vs_mp", 100 * (1 - x / mp_amb), src)
        r.put(f"e.{a}.att_vs_mp", 100 * (ctl[c]["att_s"][0] - ctl["maxpressure"]["att_s"][0])
              / ctl["maxpressure"]["att_s"][0], src)


def _camera(r: _Reg, b: dict):
    src = FILES["camera"]
    names = {"maxpressure": "mp", "fixedtime_webster": "web", "llm_guarded_mp": "llm", "preemption_mp": "pre"}
    for scname, ctls in b["main"].items():
        sc = {v: k for k, v in SC.items()}[scname]
        for c, levels in ctls.items():
            for lvl, x in levels.items():
                k = f"c.{sc}.{names[c]}.{lvl}"
                r.put(f"{k}.att", x["att"][0], src)
                r.put(f"{k}.att_sd", x["att"][1], src)
                r.put(f"{k}.queue", x["queue_mean_per_intersection"][0], src)
                d = x.get("att_vs_perfect")
                if d:
                    for kk, jj in (("d", "mean"), ("dmin", "min"), ("dmax", "max"), ("pct", "pct_mean"),
                                   ("pctmin", "pct_min"), ("pctmax", "pct_max")):
                        r.put(f"{k}.{kk}", d[jj], src)
                if "llm" in x:
                    r.put(f"{k}.guard", 100 * x["llm"]["guard_override_rate"], src)
                    r.put(f"{k}.differs", 100 * x["llm"]["mp_disagreement_rate"], src)
                    r.put(f"{k}.fail", x["llm"]["failures"], src)
    for c, levels in b["emergency"].items():
        for lvl, x in levels.items():
            k = f"c.amb.{names[c]}.{lvl}"
            r.put(f"{k}.att", x["att"][0], src)
            r.put(f"{k}.amb", x["ambulances_relevant"]["travel_time_mean_s"], src)
            d = x.get("att_vs_perfect")
            if d:
                for kk, jj in (("d", "mean"), ("dmin", "min"), ("dmax", "max"), ("pct", "pct_mean")):
                    r.put(f"{k}.{kk}", d[jj], src)
            ad = x.get("ambulances_vs_perfect")
            if ad:
                r.put(f"{k}.amb_d", ad["mean_diff_s"], src)
                r.put(f"{k}.amb_slower", ad["slower"], src)
                r.put(f"{k}.amb_faster", ad["faster"], src)
    for scname, levels in b["sweep"].items():
        sc = {v: k for k, v in SC.items()}[scname]
        for lvl, x in levels.items():
            p = round(100 * float(lvl.split("_p")[1]))
            r.put(f"c.sweep.{sc}.p{p}.att", x["att"][0], src)
            d = x.get("att_vs_perfect")
            if d:
                r.put(f"c.sweep.{sc}.p{p}.pct", d["pct_mean"], src)
    for scname, levels in b["effective_p_detect"].items():
        sc = {v: k for k, v in SC.items()}[scname]
        for lvl, v in levels.items():
            r.put(f"c.peff.{sc}.{lvl}", v, src)
    for part, x in b["decomposition"].items():
        if part == "sum_abc":
            for scname, y in x.items():
                sc = {v: k for k, v in SC.items()}[scname]
                r.put(f"c.dec.sum.{sc}.d", y["mean"], src)
                r.put(f"c.dec.sum.{sc}.pct", y["pct_mean"], src)
            continue
        r.put(f"c.dec.{part}.phantoms", x["realised"]["phantoms_per_road_snapshot"], src)
        r.put(f"c.dec.{part}.lost", 100 * x["realised"]["lost_to_non_vehicle_label"], src)
        for scname, y in x["att_vs_perfect"].items():
            sc = {v: k for k, v in SC.items()}[scname]
            for kk, jj in (("d", "mean"), ("dmin", "min"), ("dmax", "max"), ("pct", "pct_mean")):
                if jj in y:
                    r.put(f"c.dec.{part}.{sc}.{kk}", y[jj], src)
    for cls, v in b["params"]["junction"]["p_detect"].items():
        r.put(f"c.param.junction.{cls}", v, src)
    for cls, v in b["params"]["crowded"]["p_detect"].items():
        r.put(f"c.param.crowded.{cls}", v, src)
    r.put("c.phantoms_per_road", sum(b["params"]["junction"]["false_det_per_road_snapshot"].values()), src)
    r.put("c.runs", b["provenance"]["runs"], src)
    r.put("c.check.reproduced", b["checks"]["perfect_vs_full_experiments"]["compared"]
          - len(b["checks"]["perfect_vs_full_experiments"]["mismatches"]), src)


def _model_size(r: _Reg, b: dict):
    src = FILES["model_size"]
    for m, name in MODELS.items():
        r.put(f"m.size.{m}", b["sizes"][name]["total_b"], src)
    for scname, block in b["full"].items():
        sc = {v: k for k, v in SC.items()}[scname]
        for m, name in MODELS.items():
            x = block["models"].get(name)
            if not x:
                continue
            k = f"m.{sc}.{m}"
            r.put(f"{k}.att", x["att_s"][0], src)
            r.put(f"{k}.att_sd", x["att_s"][1], src)
            r.put(f"{k}.vs_mp", 100 * x["att_vs_mp"]["mean"], src)
            r.put(f"{k}.vs_mp_min", 100 * x["att_vs_mp"]["min"], src)
            r.put(f"{k}.vs_mp_max", 100 * x["att_vs_mp"]["max"], src)
            r.put(f"{k}.worse", x["att_vs_mp"]["seeds_worse"], src)
            r.put(f"{k}.queue", x["queue_mean_per_intersection"][0], src)
            r.put(f"{k}.follows", 100 * x["follows_pressure_rate"], src)
            r.put(f"{k}.differs", 100 * x["mp_disagreement_rate"], src)
            r.put(f"{k}.calls", x["calls"], src)
            r.put(f"{k}.fail", 100 * x["fallback_to_mp_rate"], src)
            r.put(f"{k}.wall_min", x["wall_time_s_mean"] / 60, src)
            amb = x.get("ambulances")
            if amb:
                r.put(f"{k}.amb", amb["travel_time_mean_s"], src)
                r.put(f"{k}.amb_stop", amb["stopped_time_mean_s"], src)
                r.put(f"{k}.amb_vs_mp", amb["vs_maxpressure"]["mean_diff_s"], src)
                r.put(f"{k}.amb_vs_pre", amb["vs_preemption_mp"]["mean_diff_s"], src)
            ad = x.get("ambulance_decisions")
            if ad:
                r.put(f"{k}.amb_calls", ad["calls"], src)
                r.put(f"{k}.amb_serve", 100 * ad["serving_nearest"] / ad["calls"], src)
    r.put("m.hosted_runs", len(b["hosted_runs"]), src)


def _detector(r: _Reg, t: dict, v: dict, tr: dict, idd: dict):
    for split, b, src in (("test", t, FILES["det_test"]), ("val", v, FILES["det_val"])):
        r.put(f"d.{split}.map50", b["ultralytics"]["mAP50"], src)
        r.put(f"d.{split}.map5095", b["ultralytics"]["mAP50_95"], src)
        r.put(f"d.{split}.images", b["ultralytics"]["images"], src)
    src = FILES["det_test"]
    e = t["errors"]
    r.put("d.test.sequences", e["sequences"], src)
    r.put("d.test.gt", sum(e["gt"].values()), src)
    for c in CLASSES:
        pc = t["ultralytics"]["per_class"][c]
        r.put(f"d.test.{c}.map50", pc["mAP50"], src)
        r.put(f"d.test.{c}.map5095", pc["mAP50_95"], src)
        r.put(f"d.test.{c}.precision", 100 * e["precision"][c]["value"], src)
        r.put(f"d.test.{c}.recall", 100 * e["recall"][c]["value"], src)
        r.put(f"d.test.{c}.miss", 100 * e["miss_rate"][c]["value"], src)
        r.put(f"d.test.{c}.fdet", e["false_det_per_image"][c]["value"], src)
        r.put(f"d.test.{c}.gt", e["gt"][c], src)
        for size, x in e["miss_rate_by_size"][c].items():
            r.put(f"d.size.{c}.{size}", 100 * x["miss_rate"], src)
    r.put("d.conf", t["conf_threshold"], src)
    r.put("d.f1", v["threshold"]["mean_f1"], FILES["det_val"])
    src = FILES["det_train"]
    r.put("d.train_h", tr["train_hours"], src)
    r.put("d.epochs", tr["epochs_run"], src)
    r.put("d.best_epoch", tr["best_epoch"], src)
    src = FILES["idd"]
    for split, x in idd["splits"].items():
        r.put(f"idd.{split}.images", x["images"], src)
        r.put(f"idd.{split}.boxes", x["boxes_total"], src)
        r.put(f"idd.{split}.sequences", x["sequences"], src)


def _bench(r: _Reg, b: dict):
    src = FILES["bench"]
    for arm, x in b["arms"].items():
        for model, y in x["models"].items():
            k = f"b.{arm}.{model}"
            for kk, jj in (("queue", "queue_mean_per_intersection"), ("att", "att_s"),
                           ("p95", "latency_p95_s"), ("lat", "latency_mean_s"), ("calls", "calls")):
                if jj in y:
                    r.put(f"{k}.{kk}", y[jj], src)
            if "failure_rate" in y:
                r.put(f"{k}.fail", 100 * y["failure_rate"], src)
    for c, y in b["baselines"].items():
        r.put(f"b.base.{c}.queue", y["queue_mean_per_intersection"], src)
        r.put(f"b.base.{c}.att", y["att_s"], src)
    r.put("b.final.round_p95x4", b["final"]["round_p95_s"], src)


def _indian(r: _Reg, b: dict, cal: dict, mg: dict):
    src = FILES["indian"]
    for lvl, ctls in b.items():
        sc = {"offpeak": "off", "peak": "peak"}[lvl]
        for c, x in ctls.items():
            k = f"i.{sc}.{c}"
            r.put(f"{k}.att", x["att"]["mean"], src)
            r.put(f"{k}.att_sd", x["att"]["std"], src)
            r.put(f"{k}.transition", 100 * x["transition_share"]["mean"], src)
            r.put(f"{k}.backlog", x["vehicles_waiting_to_enter_at_end"]["mean"], src)
            for s, v in zip(x["seeds"], x["att"]["values"]):
                r.put(f"{k}.s{s}", v, src)
    src = FILES["calib"]
    sel = cal["selection"]
    r.put("cal.r_star", sel["R_star"], src)
    r.put("cal.peak", sel["peak_veh_per_hour"], src)
    r.put("cal.offpeak", sel["offpeak_veh_per_hour"], src)
    sat = cal["capacity"]["saturation_flow"]
    for turn, x in sat.items():
        r.put(f"cal.sat.{turn}", x["fit_saturation_flow_veh_per_hour"], src)
    r.put("cal.entry_admission", cal["capacity"]["entry_admission"]["measured_veh_per_hour"], src)
    r.put("cal.lost_time", cal["capacity"]["startup_lost_time_s"], src)
    w = cal["selection"]["webster_reference_ANALYTIC"]
    r.put("cal.y_cap", w["Y_cap"], src)
    src = FILES["mg_sweep"]
    r.put("mg.chosen", mg["selection"]["chosen_min_green"], src)


def _config(r: _Reg, root: Path):
    cfg = load_config(root / "configs/default.yaml")
    src = "configs/default.yaml"
    r.put("cfg.steps", cfg["sim"]["steps"], src)
    r.put("cfg.signal.min_green", cfg["signal"]["min_green"], src)
    r.put("cfg.signal.max_green", cfg["signal"]["max_green"], src)
    mp = cfg["controllers"]["maxpressure"]
    r.put("cfg.mp.interval", mp["decision_interval"], src)
    r.put("cfg.mp.min_green", mp["min_green"], src)
    r.put("cfg.guard.margin", 100 * (1 - cfg["controllers"]["llm_guarded_mp"]["guard_ratio"]), src)
    r.put("cfg.ft.green", cfg["controllers"]["fixedtime"]["green_time"], src)
    r.put("cfg.web.cycle_min", cfg["controllers"]["fixedtime_webster"]["cycle_min"], src)
    r.put("cfg.web.cycle_max", cfg["controllers"]["fixedtime_webster"]["cycle_max"], src)
    r.put("cfg.amb.range", cfg["emergency"]["detection_range_m"], src)
    r.put("cfg.imgsz", cfg["perception"]["imgsz"], src)
    tr = cfg["perception"]["train"]
    r.put("cfg.det.epochs", tr["epochs"], src)
    r.put("cfg.det.batch", tr["batch"], src)
    r.put("cfg.det.patience", tr["patience"], src)
    llm = cfg.get("llm", {})
    for k in ("temperature", "num_ctx", "timeout_s"):
        if k in llm:
            r.put(f"cfg.llm.{k}", llm[k], src)
    sc = load_config(root / "configs/scenarios/indian_2x2.yaml")
    src = "configs/scenarios/indian_2x2.yaml"
    for k, v in _flatten_numbers(sc).items():
        r.put(f"scn.{k}", v, src)


def _flatten_numbers(d, pre=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten_numbers(v, f"{pre}{k}."))
    elif isinstance(d, (int, float)) and not isinstance(d, bool):
        out[pre.rstrip(".")] = d
    return out
