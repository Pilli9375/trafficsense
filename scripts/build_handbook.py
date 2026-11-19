"""Build the team's study handbook PDF from docs/handbook/NN_*.md.

    python scripts/build_handbook.py              # check numbers, build the PDF
    python scripts/build_handbook.py --pages 1,9  # also render those pages to docs/handbook/build/ (git-ignored)
    python scripts/build_handbook.py --copy-to /mnt/d/trafficsense/final

pandoc (~/.local/bin) turns the Markdown into LaTeX and tectonic (~/.local/bin) typesets it, as
scripts/make_paper.py does. Fonts: Times New Roman and Consolas from the Windows font folder
(`paths.report_fonts` in configs/default.yaml), linked, not copied. The number tags
(`88.1<!--=f.off.mp.att-->`) are checked first (scripts/check_handbook.py does the full check)
and removed before typesetting.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root, resolve_path
from trafficsense.report import numbers
from trafficsense.report.facts import facts

ROOT = repo_root()
HB = ROOT / "docs/handbook"
OUT = HB / "TrafficSense_Study_Handbook.pdf"
BUILD = HB / "build"

HEADER = r"""
\usepackage{fontspec}
\setmainfont{times}[Path=@FONTS@/, Extension=.ttf, BoldFont=timesbd, ItalicFont=timesi, BoldItalicFont=timesbi]
\setmonofont{consola}[Path=@FONTS@/, Extension=.ttf, BoldFont=consolab, ItalicFont=consolai, BoldItalicFont=consolaz, Scale=0.9]
\usepackage{xcolor}
\definecolor{shadecolor}{RGB}{232,240,250}
\definecolor{headblue}{RGB}{20,60,120}
\usepackage{framed}
\renewenvironment{quote}{\begin{shaded}\setlength{\parskip}{4pt}}{\end{shaded}}
\usepackage{titlesec}
\setcounter{secnumdepth}{1}
\titleformat{\section}{\LARGE\bfseries\raggedright\color{headblue}}{Part \thesection.}{0.6em}{}
\titleformat{\subsection}{\Large\bfseries\raggedright\color{headblue}}{}{0em}{}
\titleformat{\subsubsection}{\large\bfseries}{}{0em}{}
\newcommand{\sectionbreak}{\needspace{0.45\textheight}\vspace{6pt}}
\usepackage{needspace}
\newcommand{\subsectionbreak}{\needspace{11\baselineskip}}
\newcommand{\subsubsectionbreak}{\needspace{5\baselineskip}}
\usepackage{titletoc}
\titlecontents{section}[0em]{\vspace{3pt}}{\makebox[4.6em][l]{Part \thecontentslabel.}}{}{\titlerule*[0.6pc]{.}\contentspage}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small TrafficSense Study Handbook}
\fancyhead[R]{\small Final Review}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0pt}}
\setlength{\emergencystretch}{3em}
\widowpenalty=10000
\clubpenalty=10000
\renewcommand{\arraystretch}{1.25}
"""


def tool(name: str) -> str:
    p = shutil.which(name) or str(Path.home() / ".local/bin" / name)
    if not Path(p).exists():
        sys.exit(f"{name} not found (on PATH or in ~/.local/bin)")
    return p


def fit_tables(md: str) -> str:
    """Give every pipe table column widths in proportion to its longest cell (capped), so that no
    short column is squeezed: pandoc reads the relative widths from the dashes of the separator."""
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("|") and i + 1 < len(lines) and re.match(r"^\|(\s*:?-+:?\s*\|)+\s*$", lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for k, ln in enumerate(lines[i:j]) if k != 1]
            n = len(rows[0])
            longest = [max(len(r[c]) if c < len(r) else 0 for r in rows) for c in range(n)]
            if sum(longest) + 3 * n > 72:                # pandoc wraps this table: set the shares
                width = [max(9, min(L, 48)) for L in longest]
                aligns = [c.strip() for c in lines[i + 1].strip().strip("|").split("|")]
                lines[i + 1] = "|" + "|".join((":" if a.startswith(":") else "") + "-" * w for a, w in zip(aligns, width)) + "|"
            i = j
        else:
            i += 1
    return "\n".join(lines)


def source() -> str:
    fs, dt = facts(ROOT), numbers.DocTables(ROOT)
    parts, errs = [], []
    for f in sorted(HB.glob("[0-9][0-9]_*.md")):
        text = f.read_text()
        errs += [f"{f.name}: {p}" for p in numbers.check_tags(text, fs, dt)[0]]
        parts.append(numbers.TAG.sub(lambda m: m["num"], text))
    if errs:
        sys.exit("\n".join(errs) + "\nnumbers differ from outputs/: run scripts/check_handbook.py")
    md = fit_tables("\n\n".join(parts))
    md = md.replace("ⓘ", "(i)")                    # no such glyph in Times New Roman
    return md


def keep_tables_together(tex: str) -> str:
    """Set every table in a smaller font from outside the longtable (a size change inside it
    breaks longtable's page breaking: rows printed over the page header), and ask for room for the
    whole table first (up to most of a page), so that a short table is not split. When the table
    follows its heading directly, the room is asked for before the heading, so that the heading
    is never left alone at the foot of a page."""
    heading = re.compile(r"(?:\\hypertarget\{[^{}]*\}\{%\s*)?\\(?:sub)*section\*?\{[^{}]*\}\\label\{[^{}]*\}\}?\s*"
                         r"(?:\{\\def\\LTcaptype\{none\}[^\n]*\n)?$")
    out, pos = [], 0
    for m in re.finditer(r"\\begin\{longtable\}.*?\\end\{longtable\}", tex, flags=re.S):
        before = tex[pos:m.start()]
        rows = m.group(0).count("\\\\")
        need = min(4 + 1.7 * rows, 30)
        h = heading.search(before)
        if h:
            before = before[:h.start()] + f"\\needspace{{{need + 4:.0f}\\baselineskip}}" + before[h.start():]
        out.append(before + f"\\needspace{{{need:.0f}\\baselineskip}}{{\\small\n{m.group(0)}\n}}")
        pos = m.end()
    out.append(tex[pos:])
    return "".join(out)


def build(fonts: Path) -> None:
    BUILD.mkdir(exist_ok=True)
    (BUILD / "handbook.md").write_text(source())
    (BUILD / "header.tex").write_text(HEADER.replace("@FONTS@", str(fonts)))
    subprocess.run([tool("pandoc"), "handbook.md", "-o", "handbook.tex", "--standalone",
                    "-f", "markdown-implicit_figures", "-t", "latex",
                    "-V", "documentclass=article", "-V", "papersize=a4", "-V", "fontsize=12pt",
                    "-V", "geometry:margin=2.1cm", "-V", "colorlinks=true", "-V", "linkcolor=headblue",
                    "-V", "urlcolor=headblue", "-H", "header.tex"], cwd=BUILD, check=True)
    tex = BUILD / "handbook.tex"
    tex.write_text(keep_tables_together(tex.read_text()))
    r = subprocess.run([tool("tectonic"), "--keep-logs", "handbook.tex"], cwd=BUILD, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"tectonic failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    log = (BUILD / "handbook.log").read_text(errors="replace")
    missing = sorted(set(re.findall(r"Missing character: There is no (.) ", log)))
    if missing:
        sys.exit(f"characters missing from the font: {missing}")
    over = re.findall(r"Overfull \\hbox \((\d+\.\d+)pt too wide\)", log)
    big = [float(x) for x in over if float(x) > 3]
    if big:
        print(f"warning: {len(big)} overfull lines (max {max(big):.1f} pt); see {BUILD / 'handbook.log'}")
    shutil.copy(BUILD / "handbook.pdf", OUT)
    import pypdfium2 as pdfium
    print(f"wrote {OUT.relative_to(ROOT)} ({len(pdfium.PdfDocument(str(OUT)))} pages)")


def render(pages: str) -> None:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(OUT))
    want = sorted({int(p) for p in pages.split(",")} if pages != "all" else range(1, len(doc) + 1))
    (BUILD / "pages").mkdir(parents=True, exist_ok=True)
    for old in (BUILD / "pages").glob("p*.png"):
        old.unlink()
    for n in want:
        img = doc[n - 1].render(scale=1.4).to_pil()
        img.save(BUILD / "pages" / f"p{n:02d}.png")
    print(f"rendered {len(want)} pages to {(BUILD / 'pages').relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", help="comma-separated page numbers to render, or 'all'")
    ap.add_argument("--copy-to", type=Path, help="also copy the PDF into this folder")
    args = ap.parse_args()
    cfg = load_config("configs/default.yaml")
    fonts = resolve_path(cfg, "report_fonts").resolve()
    if not (fonts / "times.ttf").is_file():
        sys.exit(f"Times New Roman not found in {fonts} (paths.report_fonts)")
    build(fonts)
    if args.pages:
        render(args.pages)
    if args.copy_to:
        shutil.copy(OUT, args.copy_to / OUT.name)
        print(f"copied to {args.copy_to / OUT.name}")


if __name__ == "__main__":
    main()
