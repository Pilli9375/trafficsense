"""Build the project report, in the college capstone thesis format, into docs/report/report.docx
(the master) and docs/report/report.pdf (LibreOffice's conversion of that same .docx).

    python scripts/build_report.py                 # check numbers, build, fill lists, check
    python scripts/build_report.py --pages 1-8,40  # also render those PDF pages to PNG
    python scripts/build_report.py --skip-check    # build even if make_report.py --check fails

Inputs: docs/report/NN_*.md in file-name order; the format is docs/report/format_spec.md. The
college's example thesis (configs/default.yaml `paths.thesis_format`, kept on D, not in git)
supplies the base styles and the logo; Times New Roman and Consolas for the PDF are read from
`paths.report_fonts` (the Windows font folder, linked, not copied).

Tools: pandoc >= 3.8 (PATH or ~/.local/bin) with the Lua filter docs/report/template/thesis.lua and
citeproc (references.bib, IEEE CSL); LibreOffice (PATH, $SOFFICE, or the AppImage extracted in
~/.local/opt/libreoffice; in WSL it needs the NSS libraries in $SOFFICE_LIBS, default
~/.cache/pw-libs/root/usr/lib/x86_64-linux-gnu); pypdfium2 to read the PDF.

Steps
1. make_report.py --check (every number equals outputs/), unless --skip-check.
2. Reference .docx = a cleaned copy of the college styles with the spec's values; the logo is
   taken from the college file's title page.
3. pandoc -> docx; the appendix code listings are generated from the files at HEAD.
4. Post-process: footers, roman front matter / Arabic body, table text, update-fields flag.
5. Fill the contents and lists (Word fields) with the page numbers LibreOffice's PDF shows, and
   convert again until the page numbers no longer change; the last PDF is the published one.
6. scripts/check_report_format.py checks the result against format_spec.md.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from trafficsense.config import load_config, repo_root, resolve_path
from trafficsense.report import thesis

ROOT = repo_root()
REP = ROOT / "docs/report"
TPL = REP / "template"
TITLE = "TrafficSense: An AI-Based Smart Traffic Management System"
AUTHORS = ["C Bhargav Kumar", "Achalla Akul Lakhan", "Darsi Amit", "Mylapalli Abhishek Raj"]
MAX_PASSES = 4


def tool(name: str) -> str:
    p = shutil.which(name) or str(Path.home() / ".local/bin" / name)
    if not Path(p).is_file():
        raise SystemExit(f"{name} not found on PATH or in ~/.local/bin (see the docstring)")
    return p


def chapters() -> list[Path]:
    files = sorted(REP.glob("[0-9][0-9]_*.md"))
    if not files:
        raise SystemExit("no chapters docs/report/NN_*.md")
    return files


def combined(tmp: Path) -> Path:
    text = "\n\n".join(p.read_text() for p in chapters())
    marker = "::: code-listings\n:::"
    if text.count(marker) != 1:
        raise SystemExit("expected one '::: code-listings' block in the appendix")
    text = text.replace(marker, thesis.code_listings(ROOT))
    # generated-block markers would separate tables from their captions
    import re
    text = re.sub(r"^<!-- (?:BEGIN|END):[\w.\-]+ -->\n", "", text, flags=re.M)
    out = tmp / "report.md"
    out.write_text(text)
    return out


def pandoc(src: Path, ref: Path, logo: Path, out: Path, numbers_json: Path):
    args = [tool("pandoc"), str(src), "--from", "markdown+raw_html+raw_attribute+fenced_divs+bracketed_spans",
            "--to", "docx", "--reference-doc", str(ref), "--resource-path", f"{REP}:{ROOT}",
            "--lua-filter", str(TPL / "thesis.lua"), "--citeproc", "--bibliography", str(REP / "references.bib"),
            "--csl", str(TPL / "ieee.csl"), "--syntax-highlighting=none", "-M", f"logo={logo}",
            "-M", "lang=en-GB", "-M", "link-citations=false", "-o", str(out)]
    r = subprocess.run(args, env={**os.environ, "REPORT_NUMBERS_JSON": str(numbers_json)},
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"pandoc failed:\n{r.stderr}")
    bad = [ln for ln in r.stderr.splitlines() if "[WARNING]" in ln]
    if bad:
        raise SystemExit("pandoc warnings:\n" + "\n".join(bad))


def render_pages(pdf: Path, spec: str, out_dir: Path):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    pages = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        pages |= set(range(int(a), int(b or a) + 1))
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(pages):
        if 1 <= p <= len(doc):
            doc[p - 1].render(scale=1.4).to_pil().save(out_dir / f"page_{p:03d}.png")
    print(f"rendered {len(pages)} page(s) to {out_dir}")


def record_tools():
    """Write the pandoc and LibreOffice versions to docs/report/build_tools.json (the software
    table of Section 2.4.1 reads them). If they changed, the table must be regenerated first."""
    pv = subprocess.run([tool("pandoc"), "--version"], capture_output=True, text=True, check=True).stdout.split()[1]
    exe, env = thesis.soffice()
    lo = subprocess.run([exe, "--version"], capture_output=True, text=True, env=env, timeout=120).stdout.split()
    if len(lo) < 2 or lo[0] != "LibreOffice":
        raise SystemExit(f"cannot read the LibreOffice version: {' '.join(lo)!r}")
    now = {"pandoc": pv, "libreoffice": lo[1]}
    path = REP / "build_tools.json"
    old = json.loads(path.read_text()) if path.is_file() else None
    if old != now:
        path.write_text(json.dumps(now) + "\n")
        raise SystemExit(f"report tools changed ({old} -> {now}): run scripts/make_report.py, then build again")


def build(work: Path) -> tuple[Path, Path]:
    record_tools()
    cfg = load_config("configs/default.yaml")
    college = resolve_path(cfg, "thesis_format")
    fonts = resolve_path(cfg, "report_fonts")
    ref = work / "reference.docx"
    thesis.reference_docx(college, tool("pandoc"), ref)
    logo = thesis.extract_logo(college, work)
    raw = work / "raw.docx"
    numbers_json = work / "numbers.json"
    pandoc(combined(work), ref, logo, raw, numbers_json)
    thesis.postprocess(raw, AUTHORS, TITLE)

    docx, pdf_dir = REP / "report.docx", work / "pdf"
    pdf_dir.mkdir()
    pages, last = None, None
    for n in range(1, MAX_PASSES + 1):
        shutil.copyfile(raw, docx)
        es = thesis.fill_lists(docx, pages)
        now = [e.page for e in es]
        if now == last:
            break
        last = now
        pdf = thesis.render_pdf(docx, pdf_dir, fonts, work)
        pages = thesis.pdf_pages(pdf)
        print(f"pass {n}: {len(pages)} pages")
    else:
        raise SystemExit(f"page numbers still changing after {MAX_PASSES} passes")
    # the .docx written in the last loop iteration is the one the last PDF was made from
    shutil.copyfile(pdf, REP / "report.pdf")
    fonts_used = thesis.pdf_fonts(REP / "report.pdf")
    if not any(f.startswith("TimesNewRoman") for f in fonts_used):
        raise SystemExit(f"the PDF does not embed Times New Roman: {sorted(fonts_used)}")
    print(f"wrote {docx.relative_to(ROOT)} and report.pdf ({len(pages)} pages); fonts: {', '.join(sorted(fonts_used))}")
    return docx, REP / "report.pdf"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-check", action="store_true", help="build even if make_report.py --check fails")
    ap.add_argument("--pages", default="", help="render these PDF pages to PNG, e.g. 1-8,40")
    ap.add_argument("--png-dir", default=str(REP / "build/pages"))
    ap.add_argument("--keep", help="keep the intermediate files in this folder")
    args = ap.parse_args()
    if not args.skip_check:
        r = subprocess.run([sys.executable, str(ROOT / "scripts/make_report.py"), "--check"], cwd=ROOT)
        if r.returncode:
            raise SystemExit("make_report.py --check failed: the report's numbers do not match outputs/")
    (REP / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REP / "build") as t:
        work = Path(t)
        docx, pdf = build(work)
        if args.keep:
            shutil.copytree(work, args.keep, dirs_exist_ok=True, ignore=shutil.ignore_patterns("lo-profile"))
    if args.pages:
        render_pages(pdf, args.pages, Path(args.png_dir))
    r = subprocess.run([sys.executable, str(ROOT / "scripts/check_report_format.py")], cwd=ROOT)
    if r.returncode:
        sys.exit(1)


if __name__ == "__main__":
    main()
