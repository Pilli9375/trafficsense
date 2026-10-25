"""Keep every number in README.md and the report (docs/report/*.md) equal to the data.

    python scripts/make_report.py            # regenerate tables, figures and tagged numbers
    python scripts/make_report.py --check    # exit 1 if anything differs from outputs/
    python scripts/make_report.py --sources  # list each fact used and the file it came from

How numbers are tied to the data (details in src/trafficsense/report/numbers.py):

* Generated tables sit between `<!-- BEGIN:name -->` / `<!-- END:name -->` markers; this script
  writes them from outputs/ (TABLES below).
* Every other number from the data is tagged in the text, `88.1<!--=f.off.mp.att-->`. The key
  names a fact read from outputs/ or configs/ (src/trafficsense/report/facts.py), or a cell of a
  table in another doc that its own --check script verifies against outputs/. --check fails if
  the shown number is not the data rounded to the decimals shown.
* A lint pass fails on any untagged number in the prose that is not a year, a section / figure
  / table reference, a small count (0-12) or a product name or version.
* Figures (docs/report/figures/*.png) are drawn from outputs/ by trafficsense.report.figures;
  each has a `.data.json` with the exact values plotted, which --check compares.

The other docs' --check scripts must pass too (the table references rely on them).
"""
import argparse
import sys
from pathlib import Path

from trafficsense.config import repo_root
from trafficsense.report import numbers
from trafficsense.report.facts import facts
from trafficsense.report import tables as report_tables

ROOT = repo_root()
REPORT = Path("docs/report")


def documents() -> list[Path]:
    chapters = sorted((ROOT / REPORT).glob("[0-9][0-9]_*.md"))
    return [Path("README.md")] + [c.relative_to(ROOT) for c in chapters]


def process(path: Path, fs, dt, blocks: dict, write: bool) -> list[str]:
    text = (ROOT / path).read_text()
    new = numbers.render_blocks(text, {k: v for k, v in blocks.items() if f"<!-- BEGIN:{k} -->" in text}, str(path))
    probs, n = numbers.check_tags(new, fs, dt)
    errors = [f"{path}: {p}" for p in probs]
    if write and not errors:
        new = numbers.refresh_tags(new, fs, dt)
    errors += [f"{path}: {p}" for p in numbers.lint(new)]
    if write:
        if new != text:
            (ROOT / path).write_text(new)
            print(f"updated {path} ({n} tagged numbers)")
    elif new != text:
        errors.append(f"{path}: generated tables out of date (run scripts/make_report.py)")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sources", action="store_true")
    args = ap.parse_args()
    fs = facts(ROOT)
    dt = numbers.DocTables(ROOT)
    if args.sources:
        used = set()
        for p in documents():
            used |= {m["key"].strip() for m in numbers.TAG.finditer((ROOT / p).read_text())}
        for k in sorted(used):
            print(f"{k:40s} {fs[k].source if k in fs else k.split('|')[0].strip()}")
        return
    blocks = report_tables.blocks(ROOT, fs, dt)
    errors = []
    if not args.check:
        from trafficsense.report import figures
        figures.make_all(ROOT, check=False)
    else:
        from trafficsense.report import figures
        errors += figures.make_all(ROOT, check=True)
    for p in documents():
        errors += process(p, fs, dt, blocks, write=not args.check)
    if errors:
        print("\n".join(errors))
        print(f"{len(errors)} problem(s)")
        sys.exit(1)
    print("README.md and docs/report match outputs/" if args.check else "done")


if __name__ == "__main__":
    main()
