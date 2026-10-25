"""Figures of the report, drawn from outputs/ into docs/report/figures/.

Each figure is a PNG plus `<name>.data.json` holding exactly the values plotted (and the files
they came from). `make_all(check=True)` recomputes the values and reports any figure whose
data file differs, without redrawing (PNG bytes depend on the matplotlib version)."""
from __future__ import annotations

import json
from pathlib import Path

FIG_DIR = Path("docs/report/figures")
FIGURES: dict = {}   # name -> function(root, facts) -> (data dict, draw callable)


def make_all(root: Path, check: bool) -> list[str]:
    from trafficsense.report.facts import facts
    fs = facts(root)
    errors = []
    out = root / FIG_DIR
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        data, draw = fn(root, fs)
        dj = out / f"{name}.data.json"
        text = json.dumps(data, indent=1, sort_keys=True) + "\n"
        if check:
            if not dj.is_file() or dj.read_text() != text:
                errors.append(f"{FIG_DIR}/{name}.png: data out of date (run scripts/make_report.py)")
            elif not (out / f"{name}.png").is_file():
                errors.append(f"{FIG_DIR}/{name}.png missing")
            continue
        dj.write_text(text)
        draw(out / f"{name}.png")
    return errors
