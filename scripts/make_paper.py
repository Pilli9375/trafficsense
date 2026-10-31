"""Keep every number in the IEEE paper (docs/paper/paper.tex) equal to the data, and build it.

    python scripts/make_paper.py                # refresh tables, figures, numbers; build PDF + Overleaf zip
    python scripts/make_paper.py --check        # exit 1 if anything differs from outputs/ (no LaTeX needed)
    python scripts/make_paper.py --pages 1,3,5  # also render those PDF pages to docs/paper/build/pages/

The paper uses the report's tag system (scripts/make_report.py) in LaTeX form,
`\\V{f.off.mp.att}{88.1}`; details in src/trafficsense/report/paper.py. --check fails on:

* a tagged number that is not the data rounded to the decimals shown, or an unknown key;
* an untagged number in the body (identifiers such as registration numbers are explicit
  constants in paper.IDENTIFIERS, not an allowlist of other numbers);
* a generated table or a figure's data that is out of date;
* a citation missing from refs.bib, an unused entry, or an entry not among the report's
  verified references;
* an abstract outside 150-250 words;
* a PDF or Overleaf zip that is not built from the current sources, or a PDF over 6 pages.

The build runs tectonic (on PATH or in ~/.local/bin) and fails on overfull lines, undefined
references or citations.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from trafficsense.config import repo_root
from trafficsense.report import numbers, paper, paper_figures
from trafficsense.report.facts import facts

ROOT = repo_root()
BUILD = paper.PAPER_DIR / "build"


def tool(name: str) -> str:
    found = shutil.which(name) or (str(Path.home() / ".local/bin" / name)
                                   if (Path.home() / ".local/bin" / name).is_file() else None)
    if not found:
        raise SystemExit(f"{name} not found on PATH or in ~/.local/bin")
    return found


def text_errors(fs, dt, write: bool) -> list[str]:
    path = ROOT / paper.TEX
    text = path.read_text()
    new = paper.render_blocks(text, paper.blocks(fs))
    probs, n = paper.check_tags(new, fs, dt)
    errors = [f"{paper.TEX}: {p}" for p in probs]
    if write and not errors:
        new = paper.refresh_tags(new, fs, dt)
    errors += [f"{paper.TEX}: {p}" for p in paper.lint(new)]
    errors += [f"{paper.TEX}: {e}" for e in paper.check_identifiers(new)]
    words = paper.abstract_words(new)
    lo, hi = paper.ABSTRACT_WORDS
    if not lo <= words <= hi:
        errors.append(f"{paper.TEX}: abstract has {words} words, want {lo}-{hi}")
    errors += paper.check_citations(new, (ROOT / paper.BIB).read_text(), (ROOT / paper.REPORT_BIB).read_text())
    if write:
        if new != text:
            path.write_text(new)
            print(f"updated {paper.TEX}")
    elif new != text:
        errors.append(f"{paper.TEX}: generated tables out of date (run scripts/make_paper.py)")
    print(f"{n} tagged numbers, abstract {words} words")
    return errors


def build() -> list[str]:
    out = ROOT / BUILD
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([tool("tectonic"), "--keep-logs", "--outdir", str(out), "paper.tex"],
                       cwd=ROOT / paper.PAPER_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"tectonic failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    log = (out / "paper.log").read_text(errors="replace")
    errors = []
    for m in re.finditer(r"Overfull \\hbox \((\d+\.\d+)pt too wide\)[^\n]*\n", log):
        if float(m.group(1)) > 0.5:
            errors.append(f"overfull line, {m.group(1)} pt: {m.group(0).strip()}")
    for pat in (r"LaTeX Warning: (?:Reference|Citation) [^\n]*undefined", r"There were undefined references"):
        errors += [m.group(0) for m in re.finditer(pat, log)]
    pdf = ROOT / paper.PDF
    shutil.copyfile(out / "paper.pdf", pdf)
    pages = paper.pdf_pages(pdf)
    record = {"sources": {str(s): paper.sha256(ROOT / paper.PAPER_DIR / s) for s in paper.sources(ROOT)},
              "pdf_sha256": paper.sha256(pdf), "pages": pages}
    (ROOT / paper.BUILD_RECORD).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    paper.write_zip(ROOT)
    print(f"built {paper.PDF} ({pages} pages) and {paper.ZIP}")
    return errors


def render_pages(spec: str):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(ROOT / paper.PDF))
    out = ROOT / BUILD / "pages"
    out.mkdir(parents=True, exist_ok=True)
    for p in sorted({int(x) for x in spec.split(",")}):
        if 1 <= p <= len(doc):
            doc[p - 1].render(scale=2.2).to_pil().save(out / f"page_{p}.png")
    print(f"rendered pages {spec} to {out.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pages", help="comma-separated page numbers to render after the build")
    args = ap.parse_args()
    fs = facts(ROOT)
    dt = numbers.DocTables(ROOT)
    errors = paper_figures.make_all(ROOT, check=args.check)
    errors += text_errors(fs, dt, write=not args.check)
    if not args.check and not errors:
        errors += build()
    errors += paper.check_build(ROOT) + paper.check_zip(ROOT)
    if args.pages and (ROOT / paper.PDF).is_file():
        render_pages(args.pages)
    if errors:
        print("\n".join(errors))
        print(f"{len(errors)} problem(s)")
        sys.exit(1)
    print("docs/paper matches outputs/" if args.check else "done")


if __name__ == "__main__":
    main()
