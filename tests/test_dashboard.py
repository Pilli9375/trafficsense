"""Every number on the dashboard comes from a data file.

1. Traceability: each page is rendered with Streamlit's AppTest; every number a reader can see
   (text, KPI cards, table cells, widget options and values, chart text and hover values) must
   equal, at its displayed precision, a value in one of the files the page read (dashboard/data.py
   records them), or a value the page computed from them through data.derived().
2. Perturbation: Overview and Results are rendered again from a copy of their data files in which
   every float is scaled by a factor (1.25-1.45) that depends on its position in the file. A decimal
   number shown unchanged at the same place on the page cannot come from the data (hardcoded).
3. Sources: every "ⓘ source" chip names only files the page read, with their git state, and every
   results file (outputs/...) the page read is named by some chip.

HTML blocks (st.markdown / st.html) count as visible text without their CSS, scripts and source
chips; the custom components' JSON payloads are checked field by field (see the replay tests).

Pages that need the files kept on D (replays, sample clip, detector weights) are skipped with a
reason when those are absent.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import shutil
import zlib
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from trafficsense.config import load_config, repo_root  # noqa: E402
from trafficsense.dashboard import data, theme  # noqa: E402

PAGES = Path("src/trafficsense/dashboard/screens")
NUM = re.compile(r"(?<![\w.\-/:])[-+−]?\d[\d,]*(?:\.\d+)?(?![\w:/])")
NPZ_TEXT_ARRAYS = ("time", "phase", "queue")   # integer arrays whose values are shown as text


# ---- what the reader sees ---------------------------------------------------------------------
SRC_CHIP = re.compile(r'<details class="ts-src[^"]*" data-ts-src="([^"]*)">(.*?)</details>', re.S)
NON_TEXT = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.S | re.I)


def _strip_html(s: str) -> str:
    """Visible text of an HTML block: without CSS, scripts and source chips (test_source_chips checks
    those), then without the tags."""
    s = SRC_CHIP.sub(" ", NON_TEXT.sub(" ", s))
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def html_blocks(at: AppTest) -> list[str]:
    """Raw HTML of every st.markdown and st.html element."""
    return [e.value for e in at.markdown] + [e.proto.body for e in at.get("html")]


def source_chips(at: AppTest) -> list[tuple[list[str], str]]:
    """(files, panel text) of every source chip on the page."""
    return [([html.unescape(f) for f in m.group(1).split("|") if f], html.unescape(re.sub(r"<[^>]+>", " ", m.group(2))))
            for b in html_blocks(at) for m in SRC_CHIP.finditer(b)]


def _decode(v):
    if isinstance(v, dict) and "bdata" in v and "dtype" in v:
        return np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v["dtype"])).tolist()
    return v


def _flat(v) -> list:
    v = _decode(v)
    if isinstance(v, list):
        return [y for x in v for y in _flat(x)]
    return [v]


def _trace_texts(tr: dict) -> list[str]:
    out = []
    for k in ("text", "hovertext"):
        out += [str(x) for x in _flat(tr.get(k, [])) if x is not None]
    ht = str(tr.get("hovertemplate", ""))
    if tr.get("hoverinfo") == "skip":
        return out
    for axis in ("x", "y", "z"):
        if f"%{{{axis}" in ht:
            out += [repr(x) if isinstance(x, float) else str(x) for x in _flat(tr.get(axis, []))]
    if "%{customdata" in ht:
        out += [repr(x) if isinstance(x, float) else str(x) for x in _flat(tr.get("customdata", []))]
    for axis in ("x", "y"):      # category labels on the axes
        out += [x for x in _flat(tr.get(axis, [])) if isinstance(x, str)]
    return out


def visible_text(at: AppTest) -> list[str]:
    out = []
    for kind in ("title", "header", "subheader", "markdown", "text", "info", "warning", "error", "success"):
        out += [_strip_html(e.value) for e in getattr(at, kind)]
    out += [_strip_html(e.proto.body) for e in at.get("html")]
    for ex in at.expander:
        out.append(ex.label)
    for tab in at.tabs:
        out.append(tab.label)
    out += [e.value for e in at.caption if not e.value.startswith("Source:")]
    for m in at.metric:
        out += [m.label, str(m.value), str(m.delta or "")]
    for df in at.dataframe:
        out += [str(c) for c in df.value.columns]
        out += [repr(x) if isinstance(x, float) else str(x) for x in df.value.to_numpy().ravel().tolist()]
    for sb in at.selectbox:
        out += [str(o) for o in sb.options]
    for sl in at.slider:
        out += [str(x) for x in np.atleast_1d(sl.value)]
    for _, payload in components(at):
        _payload_texts(payload, out)
    for pc in at.get("plotly_chart"):
        spec = json.loads(pc.proto.spec)
        traces = list(spec.get("data", []))
        for fr in spec.get("frames", []):
            traces += fr.get("data", [])
        for tr in traces:
            out += _trace_texts(tr)
        lay = spec.get("layout", {})
        out += [str(a.get("text", "")) for a in lay.get("annotations", [])]
        for s in lay.get("sliders", []):
            out += [str(st.get("label", "")) for st in s.get("steps", [])]
    return out


# style values; the binary positions; flow indices, i.e. vehicle ids ("flow_4797_0") as numbers. The last two are
# checked against replay.npz by test_replay_payload_is_the_logged_replay.
# View settings (screen-axis signs, default view) are checked by test_replay_views_keep_north_up.
PAYLOAD_SKIP = {"colour", "colours", "veh", "flow", "views", "view"}


def _payload_texts(o, out: list) -> None:
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in PAYLOAD_SKIP:
                _payload_texts(v, out)
    elif isinstance(o, list):
        for v in o:
            _payload_texts(v, out)
    elif isinstance(o, bool) or o is None:
        return
    elif isinstance(o, float):
        out.append(repr(o))
    else:
        out.append(str(o))


def components(at: AppTest) -> list[tuple[str, object]]:
    """(name, payload) of every custom (v2) component on the page."""
    return [(e.proto.component_name, json.loads(e.proto.json)) for e in at.get("bidi_component")]


def numbers(texts: list[str]) -> list[str]:
    return [m.group(0) for t in texts for m in NUM.finditer(t)]


def _norm(tok: str) -> str:
    return tok.replace("−", "-").lstrip("+-").replace(",", "")


# ---- what the files hold ----------------------------------------------------------------------
def _walk(o, out: list):
    if isinstance(o, bool) or o is None:
        return
    if isinstance(o, (int, float)):
        out.append(float(o))
    elif isinstance(o, str):
        out += [float(_norm(m.group(0))) for m in NUM.finditer(o) if _norm(m.group(0))]
    elif isinstance(o, dict):
        for k, v in o.items():
            _walk(k, out)
            _walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out)


def _walk_strings(o, out: list):
    """Numbers written inside strings or keys, including ones glued to letters ("uniform_p0.60")."""
    if isinstance(o, str):
        out += [float(m) for m in re.findall(r"\d+(?:\.\d+)?", o)]
    elif isinstance(o, dict):
        for k, v in o.items():
            _walk_strings(k, out)
            _walk_strings(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk_strings(v, out)


def file_values(rel: str) -> np.ndarray:
    p = data.path(rel)
    vals: list[float] = []
    if p.suffix == ".npz":
        with np.load(p) as z:
            arrs = [np.unique(z[k]).astype(float) for k in NPZ_TEXT_ARRAYS if k in z.files]
        return np.concatenate(arrs)
    if p.suffix == ".jsonl":
        for line in p.read_text(encoding="utf-8").splitlines():
            _walk(json.loads(line), vals)
    elif p.suffix in (".yaml", ".yml"):
        import yaml
        _walk(yaml.safe_load(p.read_text(encoding="utf-8")), vals)
    else:
        _walk(json.loads(p.read_text(encoding="utf-8")), vals)
    return np.array(vals, dtype=float)


def traceable(values: np.ndarray) -> set[str]:
    vals = np.unique(np.abs(np.concatenate([values, 100 * values])))
    vals = vals[np.isfinite(vals)]
    return {f"{v:.{d}f}" for v in vals.tolist() for d in range(4)} | {repr(v) for v in vals.tolist()}


def render(page: str, root: Path | None = None) -> AppTest:
    data.reset_registry()
    old = data.ROOT
    if root is not None:
        data.ROOT = root
    try:
        at = AppTest.from_file(str(repo_root() / PAGES / f"{page}.py"), default_timeout=180).run()
    finally:
        data.ROOT = old
    assert not at.exception, [e.value for e in at.exception]
    return at


def untraceable(at: AppTest) -> tuple[list[str], set[str]]:
    vals = [file_values(rel) for rel in sorted(data.READ)]
    ok = traceable(np.concatenate(vals + [np.array(data.DERIVED, dtype=float)]))
    bad = []
    for tok in numbers(visible_text(at)):
        n = _norm(tok)
        if n in ok:
            continue
        try:
            if repr(abs(float(n))) in ok:
                continue
        except ValueError:
            pass
        bad.append(tok)
    return bad, set(data.READ)


def _need(*rels: str) -> None:
    cfg = load_config("configs/default.yaml")
    for rel in rels:
        p = repo_root() / rel.format(**cfg["paths"])
        if not p.exists():
            pytest.skip(f"{p} not present (kept on D, see configs/default.yaml)")


# ---- tests --------------------------------------------------------------------------------------
@pytest.mark.parametrize("page", ["overview", "results"])
def test_every_number_traceable(page):
    at = render(page)
    bad, read = untraceable(at)
    assert read, "page read no data files"
    assert not bad, f"{page}: numbers not found in {sorted(read)}: {bad}"


def test_overview_headline_is_the_pre_registered_arm():
    """The biggest number on the Overview is a pre-registered result: MaxPressure vs the main LLM arm."""
    at = render("overview")
    hero = next(b for b in html_blocks(at) if 'class="ts-hero"' in b)
    h1 = re.search(r"<h1>(.*?)</h1>", hero, re.S).group(1)
    shown = int(re.search(r'class="ts-count">(\d+)<', h1).group(1))
    em = json.loads((repo_root() / "outputs/full/results.json").read_text())["emergency"]["controllers"]
    mp = em["maxpressure"]["ambulances_relevant"]["travel_time_mean_s"]
    main = em["llm_guarded_mp"]["ambulances_relevant"]["travel_time_mean_s"]
    assert shown == round(100 * (1 - main / mp))


def test_replay_numbers_traceable():
    _need("{replays}")
    at = render("network_replay")
    assert [n for n, _ in components(at)] == ["trafficsense_network_replay"]
    bad, read = untraceable(at)
    assert any(r.endswith("replay.npz") for r in read) and any(r.endswith("summary.json") for r in read)
    assert not bad, f"network_replay: numbers not found in {sorted(read)}: {bad}"


def _unb64(s: str, dtype: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.dtype(dtype).newbyteorder("<"))


def test_replay_payload_is_the_logged_replay():
    """No invented frames: the canvas gets, for every second of the window, exactly the vehicles, positions
    (to 1/20 m), headings, phases and queues logged in replay.npz, and the ambulance's times from summary.json."""
    _need("{replays}")
    at = render("network_replay")
    (name, pay), = components(at)
    t0, t1 = pay["t0"], pay["t1"]
    assert 1 <= t0 < t1 and t1 - t0 <= 600
    replays = [r for r in sorted(data.READ) if r.endswith("replay.npz")]
    summaries = [r for r in sorted(data.READ) if r.endswith("/summary.json")]
    assert len(pay["runs"]) == 2
    for run in pay["runs"]:
        rdir = next(r for r in replays if _matches(run, r))
        assert run["amb"]["flow"] == int(pay["focus"].split("_")[1]) and run["amb"]["vehicle"] == pay["focus"]
        with np.load(data.path(rdir)) as z:
            k0, k1 = t0 - 1, t1
            assert z["time"][k0:k1].tolist() == list(range(t0, t1 + 1))
            assert run["phase"] == z["phase"][k0:k1].tolist()
            assert run["queue"] == z["queue"][k0:k1].tolist()
            a, b = int(z["veh_offsets"][k0]), int(z["veh_offsets"][k1])
            v = run["veh"]
            assert v["n"] == np.diff(z["veh_offsets"][k0:k1 + 1]).tolist()
            idx = _unb64(v["idx"], "u2")
            assert np.array_equal(np.array(v["flow"])[idx], z["veh_flow"][a:b])
            assert np.array_equal(np.array(v["type"])[idx], z["veh_type"][a:b])
            assert np.abs(_unb64(v["x"], "i2") / 20 - z["veh_x"][a:b]).max() <= 0.025 + 1e-4   # half a 1/20 m step, float32
            assert np.abs(_unb64(v["y"], "i2") / 20 - z["veh_y"][a:b]).max() <= 0.025 + 1e-4
            assert np.abs(_unb64(v["ang"], "i2") / 1000 - z["veh_angle"][a:b].astype(float)).max() <= 0.0006
        summary = next(json.loads(data.path(s).read_text()) for s in summaries if _summary_of(run, s))
        amb = {x["vehicle"]: x for x in summary["emergency"]["vehicles"]}[pay["focus"]]
        assert (run["amb"]["start"], run["amb"]["finished"], run["amb"]["travel"]) == \
            (amb["scheduled_start"], amb["finished"], amb["travel_time_s"])


def test_replay_default_pair_is_pre_registered():
    """The replay opens on MaxPressure vs the pre-registered LLM arm: nothing exploratory leads the page."""
    _need("{replays}")
    at = render("network_replay")
    (_, pay), = components(at)
    assert [r["label"] for r in pay["runs"]] == [theme.entity("maxpressure", None)[0],
                                                theme.entity("llm_guarded_mp", "llama3.2:3b")[0]]
    assert not any(r["exploratory"] for r in pay["runs"])


def test_replay_views_keep_north_up():
    """North is up in every view (the screen y axis points south); the default view is the layout as simulated,
    whose road names match the compass; keep left is a left-right mirror."""
    _need("{replays}")
    at = render("network_replay")
    (_, pay), = components(at)
    assert all(v["y"] == -1 for v in pay["views"].values())
    assert pay["views"]["sim"] == {"x": 1, "y": -1} and pay["views"]["left"] == {"x": -1, "y": -1}
    assert pay["view"]["side"] == "sim"


def _matches(run: dict, replay_rel: str) -> bool:
    """The payload run is the replay whose controller and model carry this label."""
    meta = json.loads(data.path(replay_rel.replace("replay.npz", "meta.json")).read_text())
    return theme.entity(meta["controller"], meta["model"])[0] == run["label"]


def _summary_of(run: dict, summary_rel: str) -> bool:
    pv = json.loads(data.path(summary_rel).read_text())["provenance"]
    return theme.entity(pv["controller"], pv["model"])[0] == run["label"]


def test_detection_page_numbers_traceable_before_a_run():
    _need("{dashboard_media}", "{detector_runs}")
    at = render("live_detection")
    bad, read = untraceable(at)
    assert "outputs/perception/detector_val.json" in read
    assert not bad, f"live_detection: numbers not found in {sorted(read)}: {bad}"


def _detection_root(tmp_path: Path, sample_json: bool = False) -> Path:
    """A copy of just what Live Detection reads, with a dummy weights file (test fake: only hashed,
    never loaded, since no detection is run) and no sample clip."""
    cfg = load_config("configs/default.yaml")
    (tmp_path / "configs").mkdir()
    shutil.copy(repo_root() / "configs/default.yaml", tmp_path / "configs/default.yaml")
    wdir = tmp_path / data.config_path("detector_runs") / "detector" / cfg["perception"]["train"]["run_name"] / "weights"
    wdir.mkdir(parents=True)
    weights = wdir / "best.pt"
    weights.write_bytes(b"not a model")
    (tmp_path / "outputs/perception").mkdir(parents=True)
    test = json.loads((repo_root() / "outputs/perception/detector_test.json").read_text())
    test["weights"]["sha256"] = hashlib.sha256(weights.read_bytes()).hexdigest()
    (tmp_path / "outputs/perception/detector_test.json").write_text(json.dumps(test))
    shutil.copy(repo_root() / "outputs/perception/detector_val.json", tmp_path / "outputs/perception/detector_val.json")
    if sample_json:
        media = tmp_path / data.config_path("dashboard_media")
        media.mkdir(parents=True)
        (media / "idd_test_sample.json").write_text(json.dumps({"frames": [], "fps": 4, "frame_step_in_recording": 1}))
    return tmp_path


@pytest.mark.parametrize("sample_json", [False, True], ids=["no sample files", "sample json but no mp4"])
def test_detection_page_without_the_sample_clip_still_offers_upload(tmp_path, sample_json):
    pytest.importorskip("cv2")
    at = render("live_detection", root=_detection_root(tmp_path, sample_json))
    assert not at.error, [e.value for e in at.error]          # the page is not stopped by an error box
    assert any("Sample clip not available" in i.value and "make_sample_clip.py" in i.value for i in at.info)
    assert len(at.get("file_uploader")) == 1                  # upload mode renders
    assert at.button[0].label == "Run detector" and at.button[0].disabled   # until a file is uploaded


def test_detection_page_keeps_the_weights_hash_check(tmp_path):
    root = _detection_root(tmp_path)
    test = json.loads((root / "outputs/perception/detector_test.json").read_text())
    test["weights"]["sha256"] = "0" * 64
    (root / "outputs/perception/detector_test.json").write_text(json.dumps(test))
    at = render("live_detection", root=root)
    assert any("not the evaluated model" in e.value for e in at.error)
    assert not at.get("file_uploader")


def _perturb(o, path=""):
    if isinstance(o, bool) or o is None:
        return o
    if isinstance(o, float) and o != 0:
        # factor and offset both depend on the position: values, their differences and their ratios all change,
        # and even small values shown with one decimal move visibly
        h = zlib.crc32(path.encode()) % 1000 / 1000
        return o * (1.25 + 0.2 * h) + (0.3 + 0.2 * h) * (1 if o > 0 else -1)
    if isinstance(o, dict):
        return {k: _perturb(v, f"{path}/{k}") for k, v in o.items()}
    if isinstance(o, list):
        return [_perturb(v, f"{path}/{i}") for i, v in enumerate(o)]
    return o


@pytest.mark.parametrize("page", ["overview", "results"])
def test_no_hardcoded_decimals(page, tmp_path):
    real = render(page)
    read = sorted(data.READ)
    for rel in read:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        src = repo_root() / rel
        if src.suffix == ".json":
            dst.write_text(json.dumps(_perturb(json.loads(src.read_text()))))
        else:
            shutil.copy(src, dst)
    mutated = render(page, root=tmp_path)
    assert sorted(data.READ) == read
    # numbers written inside strings or keys of the data (e.g. "3.1 (dense)", "uniform_p0.90") are not perturbed;
    # they are covered by the traceability test
    in_strings = []
    for rel in read:
        if rel.endswith(".json"):
            _walk_strings(json.loads((repo_root() / rel).read_text()), in_strings)
    exempt = traceable(np.array(in_strings, dtype=float))
    a, b = (numbers(visible_text(at)) for at in (real, mutated))
    assert len(a) == len(b), "perturbing the data changed the page's structure; compare by position impossible"
    same = [x for x, y in zip(a, b) if x == y and "." in x and float(_norm(x)) != 0 and _norm(x) not in exempt]
    assert not same, f"{page}: decimals unchanged when the data changed (hardcoded?): {same}"


def test_data_layer_rejects_absolute_paths_and_reports_missing(tmp_path):
    with pytest.raises(ValueError):
        data.read_json(str(tmp_path / "x.json"))
    with pytest.raises(data.MissingData, match="make it"):
        data.read_json("outputs/does_not_exist.json", "make it")


def test_source_caption_names_file_and_commit():
    s = data.source("outputs/full/results.json")
    assert s.startswith("Source: outputs/full/results.json · commit ")
    assert "not in git" in data.source("data/external/nothing_here.json")
    assert data.sources("outputs/full/results.json", "data/external/nothing_here.json")[1] == \
        ("data/external/nothing_here.json", "not in git")


def check_source_chips(at: AppTest, page: str) -> None:
    chips = source_chips(at)
    assert chips, f"{page}: no source chips"
    read = set(data.READ)
    for files, panel in chips:
        assert files, f"{page}: a source chip names no file"
        assert set(files) <= read, f"{page}: chip names files the page did not read: {sorted(set(files) - read)}"
        for f in files:
            assert f in panel and re.search(re.escape(f) + r"\s+(commit [0-9a-f]{7}|not in git)", panel), \
                f"{page}: chip panel lacks the git state of {f}"
    cited = {f for files, _ in chips for f in files}
    results = {r for r in read if r.startswith("outputs/")}
    assert results <= cited, f"{page}: results files read but not named by any chip: {sorted(results - cited)}"


@pytest.mark.parametrize("page", ["overview", "results"])
def test_source_chips(page):
    check_source_chips(render(page), page)


def test_replay_and_detection_source_chips():
    _need("{replays}", "{dashboard_media}", "{detector_runs}")
    for page in ("network_replay", "live_detection"):
        check_source_chips(render(page), page)


def test_run_summaries_match_the_paired_block():
    """The per-seed slope charts read the run summaries; results.json's paired differences come from them."""
    full = json.loads((repo_root() / "outputs/full/results.json").read_text())
    for sc, paired in full["paired"].items():
        if sc not in full["scenarios"]:
            continue
        arms = full["scenarios"][sc]

        def att(name):
            out = {}
            for r in arms[name]["runs"]:
                s = json.loads((repo_root() / r / "summary.json").read_text())
                out[s["provenance"]["seed"]] = s["metrics"]["att"]
            return out
        mp = att("MaxPressure")
        for name, p in paired.items():
            a = att(name)
            assert [a[s] - mp[s] for s in p["seeds"]] == pytest.approx(p["att_minus_mp"], abs=1e-9), (sc, name)


def test_seed_labels_never_overlap():
    """Slope chart: a seed's label moves up or down only where two seeds end close together, so no two labels
    of a panel overlap (two did, at every width, before)."""
    from trafficsense.dashboard.views import results

    assert results.spread([0.0, 40.0], 13) == [0.0, 40.0]            # apart already: unchanged
    for ys in ([0.0, 5.0, 30.0], [10.0, 10.0, 10.0], [50.0, 0.0, 49.0, 3.0]):
        out = results.spread(ys, 13)
        order = sorted(range(len(ys)), key=lambda i: ys[i])
        assert sorted(range(len(out)), key=lambda i: out[i]) == order    # order kept
        assert all(out[b] - out[a] >= 13 - 1e-9 for a, b in zip(order, order[1:]))
    full = json.loads((repo_root() / "outputs/full/results.json").read_text())
    for sc in full["scenarios"]:
        arms, _ = results._arms(full, sc)
        keys = [k for k in results.ORDER if k in arms and k not in (results.MP, ("fixedtime", None))]
        fig = results.slopes(arms, keys)
        rng = fig.layout.yaxis.range
        plot_h = results.SLOPES_H - 12 - 8 - 24
        for j in range(1, len(keys) + 1):
            xref = "x" if j == 1 else f"x{j}"
            px = sorted((a.y - rng[0]) / (rng[1] - rng[0]) * plot_h + a.yshift
                        for a in fig.layout.annotations if a.xref == xref)
            assert all(b - a >= 13 - 1e-9 for a, b in zip(px, px[1:])), (sc, keys[j - 1], px)
