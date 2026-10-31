"""Check (and refresh) every number in the IEEE paper (docs/paper/paper.tex) against the data.

The paper uses the report's tag system (trafficsense.report.numbers) in LaTeX form. A number
from the data is written through a macro that prints its second argument and ignores the
first:

    MaxPressure's ATT was \\V{f.off.mp.att}{88.1}~s.

The key is a fact from `trafficsense.report.facts` or a `doc | block | row | column` cell of a
checked doc, exactly as in the report; the shown number must equal the data rounded to the
decimals shown. Generated tables sit between `% BEGIN:name` and `% END:name` comment lines and
are written from facts by TABLES below.

`lint()` fails on numbers in the document body that carry no tag. Allowed untagged: numbers in
generated tables, comments, \\cite / \\ref / \\label / \\texttt arguments, lengths (3.5in,
0.9\\columnwidth), years, small counts (0-12), the report's ALLOWED_PHRASES (product names and
versions), and the IDENTIFIERS below. Identifiers (registration numbers, the capstone term and
ID) are not results: they are listed one by one, and `check_identifiers()` requires each to
appear as listed and rejects any other registration-number-shaped token.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from trafficsense.report import numbers
from trafficsense.report.numbers import Problem, line_of

PAPER_DIR = Path("docs/paper")
TEX = PAPER_DIR / "paper.tex"
BIB = PAPER_DIR / "refs.bib"
PDF = PAPER_DIR / "paper.pdf"
BUILD_RECORD = PAPER_DIR / "paper.build.json"
ZIP = PAPER_DIR / "paper_overleaf.zip"
REPORT_BIB = Path("docs/report/references.bib")
MAX_PAGES = 6
ABSTRACT_WORDS = (150, 250)

# Identifiers, not results (from the capstone project diary). Each must appear exactly as here.
IDENTIFIERS = {
    "Reg. No. of C Bhargav Kumar": "23BCE8195",
    "Reg. No. of Achalla Akul Lakhan": "23BCE8015",
    "Reg. No. of Darsi Amit": "23BCE8288",
    "Reg. No. of Mylapalli Abhishek Raj": "23BCE9470",
    "Capstone term": "Fall 2026-27",
    "Capstone ID": "3328F4C8",
}
OPTIONAL_IDENTIFIERS: dict[str, str] = {}
REG_NO = re.compile(r"\b\d{2}[A-Z]{3}\d{4}\b")
PLACEHOLDER = re.compile(r"\\\{\\\{[A-Z0-9_\\]+\\\}\\\}")

TAG = re.compile(r"\\V\{(?P<key>[^{}]*)\}\{(?P<num>" + numbers.NUM + r")\}")
ANY_TAG = re.compile(r"\\V\{")
COMMENT = re.compile(r"(?<!\\)%.*")
BLOCK = re.compile(r"^% BEGIN:(?P<name>[\w.\-]+)\n(?P<body>.*?)^% END:(?P=name)$", re.S | re.M)


# --- tags ------------------------------------------------------------------------------------

def check_tags(text: str, facts: dict, tables: numbers.DocTables) -> tuple[list[Problem], int]:
    probs, n = [], 0
    good = {m.start() for m in TAG.finditer(text)}
    for m in ANY_TAG.finditer(numbers._blank(text, COMMENT)):
        if m.start() not in good:
            probs.append(Problem(line_of(text, m.start()), text[m.start():m.start() + 60],
                                 "malformed tag (want \\V{key}{number})"))
    for m in TAG.finditer(text):
        n += 1
        try:
            kind, ref = numbers.resolve(m["key"], facts, tables)
        except (KeyError, ValueError) as e:
            probs.append(Problem(line_of(text, m.start()), m.group(0), str(e)))
            continue
        if not numbers.matches(m["num"], kind, ref):
            want = numbers.fmt_like(ref, m["num"]) if kind == "fact" else ref
            probs.append(Problem(line_of(text, m.start()), m.group(0), f"data says {want}"))
    return probs, n


def refresh_tags(text: str, facts: dict, tables: numbers.DocTables) -> str:
    def sub(m):
        kind, ref = numbers.resolve(m["key"], facts, tables)
        new = numbers.fmt_like(ref if kind == "fact" else numbers.to_float(ref), m["num"])
        return f"\\V{{{m['key']}}}{{{new}}}"
    return TAG.sub(sub, text)


def render_blocks(text: str, blocks: dict[str, str]) -> str:
    found = {m["name"] for m in BLOCK.finditer(text)}
    for name in found - set(blocks):
        raise KeyError(f"paper has a block {name!r} that no table generator writes")
    for name, body in blocks.items():
        if name not in found:
            raise KeyError(f"marker for block {name!r} missing in the paper")
        pat = re.compile(r"^% BEGIN:" + re.escape(name) + r"\n.*?^% END:" + re.escape(name) + r"$", re.S | re.M)
        text = pat.sub(lambda _: f"% BEGIN:{name}\n{body.rstrip()}\n% END:{name}", text)
    return text


# --- lint ------------------------------------------------------------------------------------

_LATEX_STRIP = [
    BLOCK,
    TAG,
    COMMENT,
    re.compile(r"\\(?:cite|ref|label|eqref|url|texttt|bibliography|bibliographystyle|includegraphics|"
               r"begin|end|href)\*?(?:\[[^\]]*\])*(?:\{[^{}]*\})?"),
    re.compile(r"\\(?:vspace|hspace|setlength|addtolength|renewcommand|fontsize|setcounter|resizebox|"
               r"scalebox|IEEEtriggeratref)\*?(?:\{[^{}]*\}|\[[^\]]*\])*"),             # layout, not data
    re.compile(r"\d*\.?\d+\s*\\(?:columnwidth|linewidth|textwidth)"),
    re.compile(r"[-+]?\d*\.?\d+\s*(?:pt|mm|cm|in|em|ex|bp)\b"),
    PLACEHOLDER,
    re.compile(r"-{2,3}"),                                                  # en / em dashes, not minus signs
]


def body_only(text: str) -> str:
    """The text with everything before \\begin{document} blanked (line numbers kept)."""
    i = text.find("\\begin{document}")
    if i < 0:
        raise ValueError("no \\begin{document}")
    return re.sub(r"[^\n]", " ", text[:i]) + text[i:]


def lint(text: str, small: int = 12) -> list[Problem]:
    t = body_only(text)
    for p in _LATEX_STRIP:
        t = numbers._blank(t, p)
    for v in list(IDENTIFIERS.values()) + list(OPTIONAL_IDENTIFIERS.values()):
        t = numbers._blank(t, re.compile(re.escape(v)))
    for p in [re.compile(x) for x in numbers.ALLOWED_PHRASES] + [numbers._CONTEXT, numbers._YEAR, numbers._CITE]:
        t = numbers._blank(t, p)
    probs = []
    for m in numbers._STANDALONE.finditer(t):
        s = m.group(0)
        if s.rstrip("%") == s and "." not in s and "," not in s and abs(int(s.replace("−", "-"))) <= small:
            continue
        ln = line_of(t, m.start())
        probs.append(Problem(ln, text.splitlines()[ln - 1].strip()[:120], f"untagged number {s}"))
    return probs


def check_identifiers(text: str) -> list[str]:
    errors = [f"{label} {value!r} not found in the paper" for label, value in IDENTIFIERS.items() if value not in text]
    allowed = set(IDENTIFIERS.values()) | set(OPTIONAL_IDENTIFIERS.values())
    errors += [f"registration-number-like token {m.group(0)!r} is not a listed identifier"
               for m in REG_NO.finditer(text) if m.group(0) not in allowed]
    return errors


# --- other document checks -------------------------------------------------------------------

def abstract_words(text: str) -> int:
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.S)
    if not m:
        raise ValueError("no abstract")
    a = TAG.sub(lambda x: x["num"], m.group(1))
    a = COMMENT.sub("", a)
    a = re.sub(r"\\[a-zA-Z]+\*?", " ", a)
    a = re.sub(r"[{}$~\\]", " ", a)
    return len([w for w in a.split() if re.search(r"\w", w)])


def bib_entries(text: str) -> dict[str, str]:
    """{key: normalised title} of a .bib file."""
    out = {}
    for m in re.finditer(r"@\w+\{([^,\s]+),(.*?)\n\}", text, re.S):
        t = re.search(r"title\s*=\s*\{(.*?)\},?\s*\n", m.group(2), re.S)
        out[m.group(1)] = re.sub(r"[{}\s]+", " ", t.group(1)).strip() if t else ""
    return out


def check_citations(tex: str, bib: str, report_bib: str) -> list[str]:
    cited = {k.strip() for m in re.finditer(r"\\cite\{([^}]*)\}", tex) for k in m.group(1).split(",")}
    ours, report = bib_entries(bib), bib_entries(report_bib)
    errors = [f"\\cite{{{k}}} has no entry in {BIB}" for k in sorted(cited - set(ours))]
    errors += [f"{BIB}: entry {k} is never cited" for k in sorted(set(ours) - cited)]
    for k, title in ours.items():
        if k not in report:
            errors.append(f"{BIB}: {k} is not one of the report's verified references ({REPORT_BIB})")
        elif report[k] != title:
            errors.append(f"{BIB}: {k} title differs from the report's entry")
    return errors


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sources(root: Path) -> list[Path]:
    """The files the PDF and the Overleaf zip are made of, relative to docs/paper/."""
    d = root / PAPER_DIR
    return [Path("paper.tex"), Path("refs.bib")] + sorted(p.relative_to(d) for p in (d / "figures").glob("*.pdf"))


def pdf_pages(pdf: Path) -> int | None:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    return len(pdfium.PdfDocument(str(pdf)))


def check_build(root: Path) -> list[str]:
    rec_p, pdf = root / BUILD_RECORD, root / PDF
    if not rec_p.is_file() or not pdf.is_file():
        return [f"{PDF} or {BUILD_RECORD} missing (run scripts/make_paper.py)"]
    rec = json.loads(rec_p.read_text())
    errors = []
    now = {str(s): sha256(root / PAPER_DIR / s) for s in sources(root)}
    if rec.get("sources") != now:
        errors.append(f"{PDF} is out of date with its sources (run scripts/make_paper.py)")
    if rec.get("pdf_sha256") != sha256(pdf):
        errors.append(f"{PDF} is not the PDF recorded in {BUILD_RECORD} (run scripts/make_paper.py)")
    pages = pdf_pages(pdf)
    pages = rec.get("pages") if pages is None else pages
    if pages is None or pages > MAX_PAGES:
        errors.append(f"{PDF} has {pages} pages; the limit is {MAX_PAGES} including references")
    return errors


def write_zip(root: Path):
    """The Overleaf upload: tex, bib and figures at the paths the tex uses. Fixed timestamps."""
    with zipfile.ZipFile(root / ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for s in sources(root):
            info = zipfile.ZipInfo(str(s), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (root / PAPER_DIR / s).read_bytes())


def check_zip(root: Path) -> list[str]:
    if not (root / ZIP).is_file():
        return [f"{ZIP} missing (run scripts/make_paper.py)"]
    with zipfile.ZipFile(root / ZIP) as z:
        names = sorted(z.namelist())
        want = sorted(str(s) for s in sources(root))
        if names != want:
            return [f"{ZIP} holds {names}, expected {want}"]
        return [f"{ZIP}: {n} differs from docs/paper/{n} (run scripts/make_paper.py)"
                for n in names if z.read(n) != (root / PAPER_DIR / n).read_bytes()]


# --- tables ----------------------------------------------------------------------------------

def _n(v: float, nd: int = 1, sign: bool = False) -> str:
    s = f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"
    return f"${s}$"


def _pm(fs, k: str, nd: int = 1) -> str:
    return f"${fs[k + '.att'].value:.{nd}f} \\pm {fs[k + '.att_sd'].value:.{nd}f}$"


ARMS = [("ft", "FixedTime, 30\\,s"), ("web", "Webster plan"), ("mp", "MaxPressure (tuned)"),
        ("llm", "LLM guarded$^{a}$"), ("gem", "LLM hybrid$^{b}$")]


def tab_main(fs) -> str:
    rows = []
    for a, name in ARMS:
        cells = [_pm(fs, f"f.{sc}.{a}") if f"f.{sc}.{a}.att" in fs else "--" for sc in ("off", "peak", "jinan")]
        rows.append(f"{name} & " + " & ".join(cells) + r" \\")
        if a == "mp":
            rows.append(r"\midrule")
    return "\n".join([r"\begin{tabular}{@{}lccc@{}}", r"\toprule",
                      r"Controller & Off-peak & Peak & Jinan 3x4 \\", r"\midrule", *rows, r"\bottomrule",
                      r"\end{tabular}"])


AMB_ARMS = [("mp", "MaxPressure"), ("web", "Webster plan"), ("pre", "MP + preemption"),
            ("llm", "LLM guarded$^{a}$"), ("gem", "LLM hybrid$^{b}$")]


def tab_ambulance(fs) -> str:
    rows = []
    for a, name in AMB_ARMS:
        e = f"e.{a}"
        vs = "--" if a == "pre" else (f"{_n(fs[e + '.vs_pre'].value, sign=True)} "
                                      f"({fs[e + '.vs_pre_faster'].value:.0f}/{fs[e + '.vs_pre_slower'].value:.0f})")
        rows.append(f"{name} & {_n(fs[e + '.amb'].value)} & {_n(fs[e + '.amb_stop'].value)} & {vs} & "
                    f"{_pm(fs, e)}" + r" \\")
    return "\n".join([r"\begin{tabular}{@{}lcccc@{}}", r"\toprule",
                      r"Controller & Amb.\ TT & Stopped & vs preempt. & Network ATT \\", r"\midrule", *rows,
                      r"\bottomrule", r"\end{tabular}"])


CAM_ARMS = [("mp", "MaxPressure"), ("llm", "LLM$^{a}$"), ("web", "Webster")]


def tab_camera(fs) -> str:
    rows = []
    for a, name in CAM_ARMS:
        cells = []
        for sc in ("off", "peak"):
            for lvl in ("junction", "crowded"):
                k = f"c.{sc}.{a}.{lvl}"
                cells.append(f"{_n(fs[k + '.pct'].value, sign=True)} "
                             f"{{\\scriptsize[{_n(fs[k + '.pctmin'].value)}, {_n(fs[k + '.pctmax'].value)}]}}")
        rows.append(f"{name} & " + " & ".join(cells) + r" \\")
    return "\n".join([r"\begin{tabular}{@{}l@{\hspace{4pt}}cccc@{}}", r"\toprule",
                      r" & \multicolumn{2}{c}{Off-peak} & \multicolumn{2}{c}{Peak} \\",
                      r"\cmidrule(lr){2-3}\cmidrule(l){4-5}",
                      r"Controller & junction & crowded & junction & crowded \\", r"\midrule", *rows,
                      r"\bottomrule", r"\end{tabular}"])


TABLES = {"tab_main": tab_main, "tab_ambulance": tab_ambulance, "tab_camera": tab_camera}


def blocks(fs) -> dict[str, str]:
    return {k: f(fs) for k, f in TABLES.items()}
