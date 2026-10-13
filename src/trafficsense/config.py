"""Config loading. All paths come from YAML and resolve relative to the repo root."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_MARKER = "pyproject.toml"


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / _MARKER).is_file():
            return parent
    raise RuntimeError(f"Cannot locate repo root: no {_MARKER} above {__file__}")


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = repo_root() / p
    if not p.is_file():
        raise FileNotFoundError(f"Config file not found: {p}")
    with p.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config {p} must contain a YAML mapping at top level")
    return cfg


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    """Resolve cfg['paths'][key] relative to the repo root; absolute paths are rejected."""
    try:
        raw = cfg["paths"][key]
    except KeyError as e:
        raise KeyError(f"Config is missing paths.{key}") from e
    p = Path(raw)
    if p.is_absolute():
        raise ValueError(f"paths.{key}={raw!r} must be relative to the repo root")
    return repo_root() / p
