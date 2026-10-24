"""Every number on the dashboard comes from a data file.

1. Traceability: each page is rendered with Streamlit's AppTest; every number a reader can see
   (text, KPI cards, table cells, widget options and values, chart text and hover values) must
   equal, at its displayed precision, a value in one of the files the page read (dashboard/data.py
   records them), or a value the page computed from them through data.derived().
2. Perturbation: Overview and Results are rendered again from a copy of their data files in which
   every float is scaled by a factor (1.25-1.45) that depends on its position in the file. A decimal
   number shown unchanged at the same place on the page cannot come from the data (hardcoded).

Pages that need the files kept on D (replays, sample clip, detector weights) are skipped with a
reason when those are absent.
"""
from __future__ import annotations

import base64
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
from trafficsense.dashboard import data  # noqa: E402

PAGES = Path("src/trafficsense/dashboard/pages")
NUM = re.compile(r"(?<![\w.\-/:])[-+−]?\d[\d,]*(?:\.\d+)?(?![\w:/])")
NPZ_TEXT_ARRAYS = ("time", "phase", "queue")   # integer arrays whose values are shown as text


# ---- what the reader sees ---------------------------------------------------------------------
def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


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


def test_replay_numbers_traceable():
    _need("{replays}")
    at = render("network_replay")
    bad, read = untraceable(at)
    assert any(r.endswith("replay.npz") for r in read) and any(r.endswith("summary.json") for r in read)
    assert not bad, f"network_replay: numbers not found in {sorted(read)}: {bad}"


def test_detection_page_numbers_traceable_before_a_run():
    _need("{dashboard_media}", "{detector_runs}")
    at = render("live_detection")
    bad, read = untraceable(at)
    assert "outputs/perception/detector_val.json" in read
    assert not bad, f"live_detection: numbers not found in {sorted(read)}: {bad}"


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
