"""Every file the dashboard shows comes through here.

* Paths are relative to the repo root (or come from configs/default.yaml), never absolute.
* Each read is recorded in READ, so tests can check that every number on a page can be traced
  to a file the page read (tests/test_dashboard.py). Numbers the pages compute from file
  values (e.g. a % difference of two means) go through `derived()`, which records them too.
* `source()` gives the caption shown under each chart: the file and the last git commit that
  changed it, or a plain statement that it is not in git / has uncommitted changes.
* A missing file raises MissingData with the command that makes it; pages show that as an
  error instead of a chart. Nothing falls back to a default value.
"""
from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from trafficsense.config import load_config, repo_root

ROOT: Path = repo_root()          # tests may point this at a copy of the data
GIT_ROOT: Path = repo_root()      # provenance always comes from the real repository
CONFIG = "configs/default.yaml"
READ: set[str] = set()            # files read since the last reset_registry() (relative paths)
DERIVED: list[float] = []         # values computed from file values by the pages


class MissingData(FileNotFoundError):
    def __init__(self, path: str, hint: str):
        super().__init__(f"{path} not found. {hint}")
        self.path, self.hint = path, hint


def reset_registry() -> None:
    READ.clear()
    DERIVED.clear()


def _rel(path: str | Path) -> str:
    p = Path(path)
    if p.is_absolute():
        raise ValueError(f"Dashboard paths must be relative to the repo root, got {p}")
    return p.as_posix()


def path(rel: str | Path) -> Path:
    return ROOT / _rel(rel)


def _check(rel: str, hint: str) -> Path:
    p = path(rel)
    if not p.is_file():
        raise MissingData(rel, hint)
    READ.add(rel)
    return p


@functools.lru_cache(maxsize=256)
def _json_cached(p: str, mtime: float) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def read_json(rel: str | Path, hint: str = "") -> Any:
    rel = _rel(rel)
    p = _check(rel, hint)
    return _json_cached(str(p), p.stat().st_mtime)


@functools.lru_cache(maxsize=64)
def _jsonl_cached(p: str, mtime: float) -> list[dict[str, Any]]:
    with Path(p).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_jsonl(rel: str | Path, hint: str = "") -> list[dict[str, Any]]:
    rel = _rel(rel)
    p = _check(rel, hint)
    return _jsonl_cached(str(p), p.stat().st_mtime)


@functools.lru_cache(maxsize=32)
def _npz_cached(p: str, mtime: float) -> dict[str, np.ndarray]:
    with np.load(p) as z:
        return {k: z[k] for k in z.files}


def read_npz(rel: str | Path, hint: str = "") -> dict[str, np.ndarray]:
    rel = _rel(rel)
    p = _check(rel, hint)
    return _npz_cached(str(p), p.stat().st_mtime)


def config() -> dict[str, Any]:
    _check(CONFIG, "")
    return load_config(path(CONFIG))


def config_path(key: str) -> str:
    """paths.<key> from the config, as a repo-relative path."""
    raw = config()["paths"][key]
    return _rel(raw)


def derived(value: float) -> float:
    """Register a number the page computed from file values (for the traceability test)."""
    DERIVED.append(float(value))
    return value


@functools.lru_cache(maxsize=512)
def _git_state(rel: str) -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=GIT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    try:
        tracked = git("ls-files", "--", rel)
        if not tracked:
            return "not in git"
        commit = git("log", "-1", "--format=%h", "--", rel)
        dirty = git("status", "--porcelain", "--", rel)
        return f"commit {commit}" + (" + uncommitted changes" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f"git unavailable ({type(e).__name__})"


def sources(*rels: str) -> list[tuple[str, str]]:
    """(file, git state) per file: 'commit abc1234', '... + uncommitted changes' or 'not in git'."""
    # files outside git (symlinks to D) are resolved for the state check only
    return [(_rel(rel), _git_state(_rel(rel))) for rel in rels]


def source(*rels: str) -> str:
    """One line of text: 'Source: <file> · commit abc1234; <file> · ...'."""
    return "Source: " + "; ".join(f"{rel} · {state}" for rel, state in sources(*rels))


def code_version() -> dict[str, str]:
    """The dashboard's own code version and the date the result files last changed, both from git:
    {'commit': short hash of HEAD (+ '-dirty' with uncommitted changes to what the app runs: src/,
    configs/, .streamlit/, pyproject.toml), 'data_date': YYYY-MM-DD of the last commit that touched
    outputs/}. Values are 'unknown' without git."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=GIT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    try:
        commit = git("rev-parse", "--short", "HEAD")
        dirty = git("status", "--porcelain", "--untracked-files=no", "--", "src", "configs", ".streamlit", "pyproject.toml")
        date = git("log", "-1", "--format=%cs", "--", "outputs")
        return {"commit": commit + ("-dirty" if dirty else ""), "data_date": date or "unknown"}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "unknown", "data_date": "unknown"}


@functools.lru_cache(maxsize=32)
def _yaml_cached(p: str, mtime: float) -> Any:
    import yaml
    with Path(p).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_yaml(rel: str | Path, hint: str = "") -> Any:
    rel = _rel(rel)
    p = _check(rel, hint)
    return _yaml_cached(str(p), p.stat().st_mtime)
