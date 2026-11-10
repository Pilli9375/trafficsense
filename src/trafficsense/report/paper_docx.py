"""Word (.docx) version of the IEEE paper, built from docs/paper/paper.tex on IEEE's Word template.

    python scripts/make_paper.py          # also builds docs/paper/paper.docx and paper_docx.pdf
    python scripts/make_paper.py --check  # also checks them (no LibreOffice needed)

The Word file is *derived* from paper.tex, never typed again: after make_paper.py has refreshed
the tables and the tagged numbers (``\\V{key}{number}``), this module reads the same text and
writes the same words, numbers, tables, figures and references into IEEE's own Word template
(``docs/paper/conference-template-letter.docx``, "US letter", the file IEEE publishes). The
template supplies the page (Letter), the two-column layout, Times 10 pt body text, the title
and author styles, the heading, caption and reference styles and their automatic numbering
("I.", "A.", "Fig. 1.", "TABLE I.", "[1]"); this module only chooses which style each part of
the paper gets. How:

* pandoc parses the LaTeX (inline markup, citations through citeproc with the IEEE CSL style,
  the same references.bib-derived refs.bib) into an AST; tables, floats and the author block are
  read from the LaTeX by the code below, because their structure is not in the AST.
* ``\\ref`` numbers are computed here (sections "V-A", figures "1", tables "I") in the order the
  template's automatic numbering will count them; the floats stay where they are in the source.
* Maths that is only numbers, signs, letters and superscript marks becomes ordinary text; every
  other formula is converted to a native Word equation (OMML) by pandoc.
* The vector figures (figures/*.pdf) are rendered to 300 dpi PNG (Word cannot embed a PDF page).
* Anything the converter does not know (an unknown LaTeX command, a raw block) is an error, not
  silently dropped.

The template is a *Strict* Open XML package (as saved by Word), so the document part is written
in the same namespaces. Checks (`check()`): built from the current sources, Letter size, two
columns in the body, no template or placeholder text left, every tagged number of the LaTeX
present in the Word file, identifiers as listed, the references numbered 1..n in citation order,
and at most eight pages in the PDF that LibreOffice made from the .docx (page counts from
LibreOffice can differ by a line or two from Word's).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from trafficsense.report import numbers, paper

PAPER_DIR = paper.PAPER_DIR
TEMPLATE = PAPER_DIR / "conference-template-letter.docx"
DOCX = PAPER_DIR / "paper.docx"
DOCX_PDF = PAPER_DIR / "paper_docx.pdf"
CSL = Path("docs/report/template/ieee.csl")
FIG_DPI = 300

W = "http://purl.oclc.org/ooxml/wordprocessingml/main"
R = "http://purl.oclc.org/ooxml/officeDocument/relationships"
M = "http://purl.oclc.org/ooxml/officeDocument/math"
NS = {"w": W}
NBSP = "\u00a0"
MINUS = "\u2212"

PAGE_W, PAGE_H = 612, 792          # pt, Letter
MARGIN_X = 45.35                   # pt, the template's two-column section
COLUMN_GAP = 18                    # pt
TEXT_W = PAGE_W - 2 * MARGIN_X
COL_W = (TEXT_W - COLUMN_GAP) / 2

# What must not appear in the Word file: guidance and placeholders of IEEE's template and of ours.
LEFTOVERS = ["{{", "}}", "TBD", "TODO", "XXX", "Paper Title", "(use style", "Given Name", "line 1:",
             "Identify applicable funding", "Heading 1)", "Heading 2)", "live” template", "©20XX"]


# Word has no floats: a figure or table stays where the source puts it, so a float that does not
# fit at the foot of a column jumps to the next column and leaves a gap (LaTeX would fill the gap
# with text). FLOAT_SHIFT moves a float later (+n) or earlier (-n) by n body blocks (paragraphs,
# headings, lists) from its place in paper.tex, as tuned on the LibreOffice rendering; floats
# keep their order, so the numbers of figures and tables do not change.
FLOAT_SHIFT: dict[str, int] = {"fig:overview": -1, "tab:amb": -1, "fig:size": -1, "tab:cam": -2,
                               "fig:cam": -2}


class DocxError(Exception):
    pass


def char_em(ch: str) -> float:
    """Rough advance width of a character in Times, in em (only to size the table columns)."""
    if ch.isdigit():
        return 0.5
    if ch in "mMwW\u00b1":
        return 0.8 if ch != "W" else 0.94
    if ch.isupper():
        return 0.68
    if ch in " .,:;'|":
        return 0.25
    if ch in "ilIjtf()[]/-":
        return 0.3
    if ch in "+=\u2212":
        return 0.56
    return 0.45


def est_width(text: str, size: float = 8.0, bold: bool = False) -> float:
    return sum(char_em(c) for c in text) * size * (1.06 if bold else 1.0)


# --- reading paper.tex ---------------------------------------------------------------------

def braced(text: str, i: int) -> tuple[str, int]:
    """The text inside the {...} that opens at text[i], and the index after its closing brace."""
    if text[i] != "{":
        raise DocxError(f"expected '{{' at {text[i:i + 30]!r}")
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    raise DocxError("unbalanced braces")


def command_args(text: str, name: str, n: int, start: int = 0) -> tuple[list[str], int, int] | None:
    """First call of \\name{..}{..}.. (n arguments) at or after start: (args, begin, end)."""
    m = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z])").search(text, start)
    if not m:
        return None
    i, args = m.end(), []
    for _ in range(n):
        while text[i] in " \n%":
            i = text.index("\n", i) + 1 if text[i] == "%" else i + 1
        a, i = braced(text, i)
        args.append(a)
    return args, m.start(), i


def plain(s: str) -> str:
    """LaTeX text of the front matter as plain text."""
    s = re.sub(r"\\(?:small|footnotesize|normalsize|large)\b\s*", "", s)
    s = s.replace("\\ ", " ").replace("~", NBSP).replace("\\%", "%").replace("\\&", "&")
    s = re.sub(r"\\texttt\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    if "\\" in s or "{" in s:
        raise DocxError(f"front matter not understood: {s!r}")
    return s


def strip_comments(tex: str) -> str:
    return "\n".join(paper.COMMENT.sub("", ln) for ln in tex.split("\n"))


def front_matter(tex: str) -> dict:
    """Title, subtitle, footnote, authors, abstract and keywords, read from paper.tex."""
    tex = strip_comments(tex)
    emails = {m.group(1): m.group(2) for m in re.finditer(
        r"\\newcommand\{\\Email([A-D])\}\{\\texttt\{([^{}]*)\}\}", tex)}
    capstone = re.search(r"\\newcommand\{\\CapstoneID\}\{([^{}]*)\}", tex)
    if len(emails) != 4 or not capstone:
        raise DocxError("paper.tex: expected \\EmailA..\\EmailD and \\CapstoneID")
    t = command_args(tex, "title", 1)
    if not t:
        raise DocxError("paper.tex has no \\title")
    title_src = t[0][0]
    thanks = command_args(title_src, "thanks", 1)
    if not thanks:
        raise DocxError("paper.tex: \\title has no \\thanks")
    head = title_src[:thanks[1]].rstrip("%\n ")
    main, _, sub = head.partition("\\\\")
    sub_arg = re.fullmatch(r"\s*\{\\large\s+(.*)\}\s*", sub, re.S)
    if not sub_arg:
        raise DocxError("paper.tex: expected a subtitle as {\\large ...} after \\\\ in \\title")
    thanks_txt = plain(thanks[0][0].replace("\\CapstoneID", capstone.group(1)))
    k = tex.index("\\newcommand{\\authorbox}[4]") + len("\\newcommand{\\authorbox}[4]")
    body, _ = braced(tex, k)
    lines = body.split("\\\\")
    if len(lines) != 4:
        raise DocxError("paper.tex: \\authorbox layout not understood")
    italic = re.findall(r"\\textit\{\\small ([^{}]*)\}", lines[1] + lines[2])
    place = re.search(r"\{\\small ([^{}\\]*)\}", lines[3])
    if len(italic) != 2 or not place:
        raise DocxError("paper.tex: \\authorbox layout not understood")
    affiliation = [plain(" ".join(italic)), plain(place.group(1))]
    author_src = command_args(tex, "author", 1)[0][0]
    authors, pos = [], 0
    while (a := command_args(author_src, "authorbox", 4, pos)):
        (_, name, reg, mail), _, pos = a
        r = re.fullmatch(r"\s*(?:\\regno\{([^{}]*)\})?\s*", reg)
        m = re.fullmatch(r"\s*(?:\\emailline\{\\Email([A-D])\})?\s*", mail)
        if not r or not m:
            raise DocxError(f"paper.tex: author {name!r} not understood")
        authors.append({"name": plain(name), "reg": r.group(1), "email": emails[m.group(1)] if m.group(1) else None})
    if len(authors) != 5 or not authors[-1]["name"].endswith("(Guide)"):
        raise DocxError("paper.tex: expected four students and the guide")
    ab = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    kw = re.search(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", tex, re.S)
    if not ab or not kw:
        raise DocxError("paper.tex: abstract or keywords missing")
    return {"title": plain(main), "subtitle": plain(sub_arg.group(1)), "thanks": thanks_txt,
            "affiliation": affiliation, "authors": authors,
            "abstract": ab.group(1).strip(), "keywords": kw.group(1).strip(), "tex": tex}


# --- the body: numbering, floats, tags -------------------------------------------------------

def roman(n: int) -> str:
    out = ""
    for v, s in [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]:
        while n >= v:
            out, n = out + s, n - v
    return out


def expand_tags(tex: str) -> str:
    """\\V{key}{12.3} -> 12.3 (a minus sign becomes U+2212, as the macro's math mode prints it)."""
    return paper.TAG.sub(lambda m: re.sub(r"^-", MINUS, m.group("num")), tex)


def body_of(tex: str) -> str:
    tex = strip_comments(tex)
    start = tex.index("\\section{Introduction}")
    end = tex.index("\\IEEEtriggeratref")
    return tex[start:end]


FLOAT = re.compile(r"\\begin\{(figure\*?|table)\}(?:\[[a-z]*\])?(.*?)\\end\{\1\}", re.S)
HEAD = re.compile(r"\\(section\*?|subsection)\{")


class Numbering:
    """Numbers as the template's automatic numbering counts them (document order)."""

    def __init__(self, body: str):
        self.labels: dict[str, str] = {}
        sec = sub = fig = tab = 0
        events = [(m.start(), "head", m) for m in HEAD.finditer(body)] + \
                 [(m.start(), "float", m) for m in FLOAT.finditer(body)]
        for _, kind, m in sorted(events, key=lambda e: e[0]):
            if kind == "head":
                name = m.group(1)
                title, end = braced(body, m.end() - 1)
                lab = re.match(r"\s*\\label\{([^{}]*)\}", body[end:])
                if name == "section":
                    sec, sub = sec + 1, 0
                    num = roman(sec)
                elif name == "subsection":
                    sub += 1
                    num = f"{roman(sec)}-{chr(64 + sub)}"
                else:
                    continue
                if lab:
                    self.labels[lab.group(1)] = num
            else:
                lab = re.search(r"\\label\{([^{}]*)\}", m.group(2))
                if m.group(1).startswith("figure"):
                    fig += 1
                    num = str(fig)
                else:
                    tab += 1
                    num = roman(tab)
                if not lab:
                    raise DocxError("a float without \\label")
                self.labels[lab.group(1)] = num

    def resolve(self, text: str) -> str:
        def one(m):
            if m.group(1) not in self.labels:
                raise DocxError(f"\\ref to unknown label {m.group(1)}")
            return self.labels[m.group(1)]
        return re.sub(r"\\ref\{([^{}]*)\}", one, text)


def split_cells(row: str) -> list[str]:
    cells, depth, cur, i = [], 0, "", 0
    while i < len(row):
        c = row[i]
        if c == "\\" and i + 1 < len(row):
            cur += row[i:i + 2]
            i += 2
            continue
        depth += (c == "{") - (c == "}")
        if c == "&" and depth == 0:
            cells.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur)
    return [c.strip() for c in cells]


def column_spec(spec: str) -> list[dict]:
    spec = re.sub(r"@\{(?:[^{}]|\{[^{}]*\})*\}", "", spec)
    spec = re.sub(r">\{(?:[^{}]|\{[^{}]*\})*\}", "", spec)
    cols = []
    for m in re.finditer(r"p\{([\d.]+)\\columnwidth\}|([lcr])", spec):
        if m.group(1):
            cols.append({"align": "left", "frac": float(m.group(1))})
        else:
            cols.append({"align": {"l": "left", "c": "center", "r": "right"}[m.group(2)], "frac": None})
    rest = re.sub(r"p\{[\d.]+\\columnwidth\}|[lcr]", "", spec).strip()
    if not cols or rest:
        raise DocxError(f"column spec not understood: {spec!r}")
    return cols


def parse_table(src: str) -> dict:
    cap, _, _ = command_args(src, "caption", 1) or (None, 0, 0)
    if not cap:
        raise DocxError("table without caption")
    m = re.search(r"\\begin\{tabular\}", src)
    spec, after = braced(src, m.end())
    end = src.index("\\end{tabular}")
    cols = column_spec(spec)
    inner = src[after:end]
    notes = []
    note = command_args(src[end:], "parbox", 2)
    if note:
        notes.append(re.sub(r"^\\scriptsize\s*", "", note[0][1].strip()))
    rows, pending_rule, pending_cmid = [], None, []
    for raw in re.split(r"\\\\(?![A-Za-z])", inner):
        txt = raw
        rule = pending_rule
        cmid = list(pending_cmid)
        for tok in re.finditer(r"\\(toprule|midrule|bottomrule)|\\cmidrule(?:\([lr]*\))?\{(\d+)-(\d+)\}", txt):
            if tok.group(1) == "bottomrule":
                rule = "bottom"
            elif tok.group(1):
                rule = rule or tok.group(1).replace("rule", "")
            else:
                cmid.append((int(tok.group(2)), int(tok.group(3))))
        txt = re.sub(r"\\(?:toprule|midrule|bottomrule)|\\cmidrule(?:\([lr]*\))?\{\d+-\d+\}", "", txt).strip()
        pending_rule, pending_cmid = None, []
        if not txt:
            if rule == "bottom":
                rows[-1]["rule_below"] = True
            continue
        cells, col = [], 1
        for c in split_cells(txt):
            mc = re.fullmatch(r"\\multicolumn\{(\d+)\}\{([lcr])\}\{(.*)\}", c, re.S)
            span, align, content = (int(mc.group(1)), {"l": "left", "c": "center", "r": "right"}[mc.group(2)],
                                    mc.group(3)) if mc else (1, cols[min(col, len(cols)) - 1]["align"], c)
            cells.append({"text": content.strip(), "span": span, "align": align, "col": col})
            col += span
        if col - 1 != len(cols):
            raise DocxError(f"table row has {col - 1} columns, spec has {len(cols)}: {txt[:60]!r}")
        rows.append({"cells": cells, "rule": rule, "cmid": cmid, "rule_below": False})
    heads = 0
    for r in rows[1:]:
        if r["rule"] == "mid":
            break
        heads += 1
    for i, r in enumerate(rows):
        r["header"] = i <= heads and any(x["rule"] == "mid" for x in rows)
    return {"caption": cap[0] if isinstance(cap, list) else cap, "cols": cols, "rows": rows, "notes": notes}


def parse_float(kind: str, src: str, n: int) -> dict:
    label = re.search(r"\\label\{([^{}]*)\}", src).group(1)
    if kind.startswith("figure"):
        g = re.search(r"\\includegraphics\[width=([\d.]*)\\(columnwidth|textwidth)\]\{([^{}]*)\}", src)
        cap = command_args(src, "caption", 1)
        if not g or not cap:
            raise DocxError("figure without \\includegraphics or \\caption")
        frac = float(g.group(1) or 1) * (TEXT_W if g.group(2) == "textwidth" else COL_W)
        return {"kind": "figure", "wide": kind.endswith("*") or g.group(2) == "textwidth", "width": frac,
                "path": g.group(3), "caption": cap[0][0], "label": label}
    t = parse_table(src)
    t["kind"], t["label"] = "table", label
    return t


# --- pandoc ---------------------------------------------------------------------------------

def pandoc_exe() -> str:
    exe = shutil.which("pandoc") or str(Path.home() / ".local/bin/pandoc")
    if not Path(exe).is_file():
        raise SystemExit("pandoc not found on PATH or in ~/.local/bin")
    return exe


def run_pandoc(args: list[str], text: str, cwd: Path) -> bytes:
    r = subprocess.run([pandoc_exe(), *args], input=text.encode(), cwd=cwd, capture_output=True)
    if r.returncode != 0:
        raise DocxError(f"pandoc failed: {r.stderr.decode()[-1500:]}")
    return r.stdout


def parse_latex(text: str, cwd: Path, extra: list[str] = ()) -> dict:
    return json.loads(run_pandoc(["-f", "latex", "-t", "json", *extra], text, cwd))


def snippet_blocks(snips: list[str], cwd: Path) -> list[list]:
    """Inline AST of each snippet (a cell, caption, note ...), one pandoc call for all of them."""
    out: list[list] = [[] for _ in snips]
    idx = [i for i, s in enumerate(snips) if s.strip()]
    if not idx:
        return out
    doc = parse_latex("\n\n".join(prep_inline(snips[i]) for i in idx), cwd)
    blocks = doc["blocks"]
    if len(blocks) != len(idx) or any(b["t"] not in ("Para", "Plain") for b in blocks):
        raise DocxError(f"snippet conversion gave {len(blocks)} blocks for {len(idx)} snippets")
    for i, b in zip(idx, blocks):
        out[i] = b["c"]
    return out


def prep_inline(s: str) -> str:
    s = re.sub(r"\\model\{", r"\\texttt{", s)
    s = re.sub(r"\{\\(?:scriptsize|footnotesize|small)(?![A-Za-z])\s*((?:[^{}]|\{[^{}]*\})*)\}", r"\\textsc{\1}", s)
    return s


# --- inline -> Word runs ----------------------------------------------------------------------

SIMPLE_MATH = re.compile(r"^(?:[A-Za-z]|\d+(?:\.\d+)?|[+\-=,.\[\]() ]|\\pm|\\ge|\\le|\\star|\\ |\^\{[a-z,]+\}"
                         r"|\\mathbf\{[\d.]+\})+$")


def math_class(tex: str) -> str:
    return "text" if SIMPLE_MATH.match(tex.strip()) and "_" not in tex else "omml"


def math_text_runs(tex: str, fmt: dict, run) -> str:
    """Numbers, signs, single letters and ^{a} marks as ordinary runs (letters italic, as in math)."""
    out, i, tex = [], 0, tex.strip()
    sym = {"\\pm": "\u00b1", "\\ge": "\u2265", "\\le": "\u2264", "\\star": "\u22c6", "\\ ": NBSP}
    while i < len(tex):
        m = re.compile(r"\\mathbf\{([\d.]+)\}|\^\{([a-z,]+)\}|\\pm|\\ge|\\le|\\star|\\ |\d+(?:\.\d+)?|[A-Za-z]|.").match(tex, i)
        tok = m.group(0)
        i = m.end()
        if m.group(1):
            out.append(run(m.group(1), {**fmt, "b": True}))
        elif m.group(2):
            out.append(run(m.group(2), {**fmt, "sup": True}))
        elif tok in sym:
            out.append(run(sym[tok], fmt))
        elif tok.isalpha():
            out.append(run(tok, {**fmt, "i": True}))
        else:
            out.append(run(tok.replace("-", MINUS) if tok == "-" else tok, fmt))
    return "".join(out)


class Writer:
    """Turns pandoc inline AST into Word runs; collects the OMML formulas it needs."""

    def __init__(self, omml: dict[str, str]):
        self.omml = omml
        self.cites = 0
        self.text: list[str] = []

    @staticmethod
    def rpr(fmt: dict) -> str:
        x = ""
        if fmt.get("code"):
            x += '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>'
        if fmt.get("b"):
            x += "<w:b/><w:bCs/>"
        if fmt.get("i"):
            x += "<w:i/><w:iCs/>"
        if fmt.get("sc"):
            x += "<w:smallCaps/>"
        size = fmt.get("sz") or (17 if fmt.get("code") and not fmt.get("table") else None)
        if size:
            x += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        if fmt.get("sup"):
            x += '<w:vertAlign w:val="superscript"/>'
        if fmt.get("sub"):
            x += '<w:vertAlign w:val="subscript"/>'
        return f"<w:rPr>{x}</w:rPr>" if x else ""

    def run(self, text: str, fmt: dict) -> str:
        if not text:
            return ""
        self.text.append(text)
        return f'<w:r>{self.rpr(fmt)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

    def flat(self, items: list) -> str:
        """Plain text of inlines (for alt text)."""
        out = []
        for it in items:
            t, c = it["t"], it.get("c")
            out.append(c if t == "Str" else " " if t in ("Space", "SoftBreak") else
                       self.flat(c) if t in ("Emph", "Strong", "SmallCaps", "Superscript", "Subscript") else
                       c[1] if t == "Code" else self.flat(c[1]) if t in ("Span", "Link") else
                       c[1] if t == "Math" else "")
        return re.sub(r"\s+", " ", "".join(out)).strip()

    def inlines(self, items: list, fmt: dict | None = None) -> str:
        fmt = fmt or {}
        out = []
        for it in items:
            t, c = it["t"], it.get("c")
            if t == "Str":
                out.append(self.run(c, fmt))
            elif t == "Space":
                out.append(self.run(" ", fmt))
            elif t == "SoftBreak":
                out.append(self.run(" ", fmt))
            elif t == "LineBreak":
                out.append("<w:r><w:br/></w:r>")
            elif t == "Emph":
                out.append(self.inlines(c, {**fmt, "i": True}))
            elif t == "Strong":
                out.append(self.inlines(c, {**fmt, "b": True}))
            elif t == "Code":
                out.append(self.run(c[1], {**fmt, "code": True}))
            elif t == "SmallCaps":        # \scriptsize groups of the tables (prep_inline)
                out.append(self.inlines(c, {**fmt, "sz": 14}))
            elif t == "Superscript":
                out.append(self.inlines(c, {**fmt, "sup": True}))
            elif t == "Subscript":
                out.append(self.inlines(c, {**fmt, "sub": True}))
            elif t == "Quoted":
                q = ("\u201c", "\u201d") if c[0]["t"] == "DoubleQuote" else ("\u2018", "\u2019")
                out.append(self.run(q[0], fmt) + self.inlines(c[1], fmt) + self.run(q[1], fmt))
            elif t in ("Span", "Cite", "Link"):
                out.append(self.inlines(c[1] if t != "Cite" else c[1], fmt))
            elif t == "Math":
                tex = c[1]
                if math_class(tex) == "text":
                    out.append(math_text_runs(tex, fmt, self.run))
                else:
                    if tex not in self.omml:
                        raise DocxError(f"no equation conversion for {tex!r}")
                    out.append(self.omml[tex])
                    self.text.append(tex)
            elif t in ("RawInline", "RawBlock"):
                raise DocxError(f"unconverted LaTeX: {c[1][:80]!r}")
            else:
                raise DocxError(f"inline element {t} not handled")
        return "".join(out)


def collect_math(node, found: set):
    if isinstance(node, dict):
        if node.get("t") == "Math" and math_class(node["c"][1]) == "omml":
            found.add(node["c"][1])
        for v in node.values():
            collect_math(v, found)
    elif isinstance(node, list):
        for v in node:
            collect_math(v, found)


def omml_for(formulas: set, cwd: Path) -> dict[str, str]:
    """Native Word equations: pandoc converts each formula; its <m:oMath> is lifted out."""
    forms = sorted(formulas)
    if not forms:
        return {}
    # representation only: the operand of a sum goes in braces, so it is the sum's operand in Word
    word = [re.sub(r"(\\sum_\{(?:[^{}]|\{[^{}]*\})*\})\(((?:[^()]|\([^()]*\))*)\)", r"\1{(\2)}", f) for f in forms]
    data = run_pandoc(["-f", "latex", "-t", "docx", "-o", "-"], "\n\n".join(f"${f}$" for f in word), cwd)
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    paras = re.findall(r"<w:p>.*?</w:p>|<w:p [^>]*>.*?</w:p>", xml, re.S)
    got = [re.findall(r"<m:oMath>.*?</m:oMath>", p, re.S) for p in paras]
    if len(got) != len(forms) or any(len(g) != 1 for g in got):
        raise DocxError("equation conversion did not give one formula per paragraph")
    # sum limits beside the sign (inline equations), not above and below it
    return {f: g[0].replace('m:val="undOvr"', 'm:val="subSup"') for f, g in zip(forms, got)}


# --- Word XML pieces -------------------------------------------------------------------------

def pt(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".") + "pt"


def para(style: str, content: str, ppr: str = "") -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{ppr}</w:pPr>{content}</w:p>'


def sect(cols: int, final: bool = False, first: bool = False, wide: bool = False) -> str:
    foot = '<w:footerReference w:type="first" r:id="rIdFooter"/>' if first else ""
    typ = "" if first else '<w:type w:val="continuous"/>'
    space = pt(COLUMN_GAP) if cols == 2 else "10.80pt"
    ncols = f'<w:cols w:num="{cols}" w:space="{space}"/>' if cols > 1 else '<w:cols w:space="36pt"/>'
    return (f"<w:sectPr>{foot}{typ}<w:pgSz w:w=\"{PAGE_W}pt\" w:h=\"{PAGE_H}pt\" w:code=\"1\"/>"
            f'<w:pgMar w:top="54pt" w:right="{pt(MARGIN_X)}" w:bottom="72pt" w:left="{pt(MARGIN_X)}" '
            f'w:header="36pt" w:footer="36pt" w:gutter="0pt"/>{ncols}{"<w:titlePg/>" if first else ""}'
            f'<w:docGrid w:linePitch="360"/></w:sectPr>')


def border(side: str, size: int) -> str:
    return f'<w:{side} w:val="single" w:sz="{size}" w:space="0" w:color="auto"/>'


class Package:
    def __init__(self):
        self.images: list[tuple[str, bytes]] = []
        self.drawing_id = 0

    def image(self, name: str, png: bytes, w_pt: float, h_pt: float, alt: str) -> str:
        self.images.append((name, png))
        rid = f"rIdImg{len(self.images)}"
        self.drawing_id += 1
        cx, cy = int(w_pt * 12700), int(h_pt * 12700)
        return (
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{self.drawing_id}" name="Figure {self.drawing_id}" descr="{escape(alt, {chr(34): "&quot;"})}"/>'
            f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData uri="http://purl.oclc.org/ooxml/drawingml/picture"><pic:pic>'
            f'<pic:nvPicPr><pic:cNvPr id="{self.drawing_id}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            f'</wp:inline></w:drawing></w:r>')


def render_figure(root: Path, rel: str, width_pt: float) -> tuple[bytes, float]:
    """PNG of a vector figure at FIG_DPI for the width it is shown at; returns (png, height in pt)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(root / PAPER_DIR / rel))
    page = doc[0]
    w, h = page.get_size()
    img = page.render(scale=FIG_DPI / 72 * max(1.0, width_pt / w)).to_pil().convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue(), width_pt * h / w


# --- building the document ---------------------------------------------------------------------

def place_floats(items: list) -> list:
    """Move floats by FLOAT_SHIFT blocks; their order (so their numbers) must not change."""
    blocks = [x for k, x in items if k == "block"]
    floats, n = [], 0
    for kind, x in items:
        if kind == "block":
            n += 1
        else:
            target = max(0, min(len(blocks), n + FLOAT_SHIFT.get(x["label"], 0)))
            lo, hi = sorted((n, target))
            if any(isinstance(b, dict) and b.get("t") == "Header" for b in blocks[lo:hi]):
                raise DocxError(f"FLOAT_SHIFT moves {x['label']} across a heading")
            floats.append([target, x])
    for a, b in zip(floats, floats[1:]):
        if b[0] < a[0]:
            raise DocxError(f"FLOAT_SHIFT would reorder {a[1]['label']} and {b[1]['label']}")
    out, fi = [], 0
    for i in range(len(blocks) + 1):
        while fi < len(floats) and floats[fi][0] <= i:
            out.append(("float", floats[fi][1]))
            fi += 1
        if i < len(blocks):
            out.append(("block", blocks[i]))
    return out


def build_xml(root: Path, tmp: Path) -> tuple[str, str, Package, Writer, list[str]]:
    tex = (root / paper.TEX).read_text()
    fm = front_matter(tex)
    body = body_of(tex)
    numbering = Numbering(body)

    floats: list[dict] = []

    def hold(m):
        floats.append(parse_float(m.group(1), m.group(2), len(floats)))
        return f"\n\nXFLOAT{len(floats) - 1}X\n\n"

    body = FLOAT.sub(hold, body)
    body = numbering.resolve(body)
    body = re.sub(r"\\label\{[^{}]*\}", "", body)
    body = expand_tags(body)
    body = prep_inline(body)
    body = body.replace("\\textsc{", "\\textsc{")      # (prep_inline only touches size groups)

    snips: list[str] = []

    def snip(s: str) -> int:
        snips.append(expand_tags(numbering.resolve(re.sub(r"\\label\{[^{}]*\}", "", s))))
        return len(snips) - 1

    plan = []                          # per float: indices of its snippets
    for f in floats:
        if f["kind"] == "figure":
            f["cap_i"] = snip(f["caption"])
        else:
            f["cap_i"] = snip(f["caption"])
            f["note_i"] = [snip(n) for n in f["notes"]]
            for r in f["rows"]:
                for c in r["cells"]:
                    c["i"] = snip(c["text"])
    ab_i, kw_i = snip(fm["abstract"]), snip(fm["keywords"])

    bib = str(root / paper.BIB)
    ast = parse_latex(body, root / PAPER_DIR, ["--citeproc", "--bibliography", bib, "--csl", str(root / CSL),
                                                "-M", "link-citations=false", "--wrap=none"])
    sn = snippet_blocks(snips, root / PAPER_DIR)
    formulas: set = set()
    collect_math(ast, formulas)
    collect_math(sn, formulas)
    wr = Writer(omml_for(formulas, tmp))
    pk = Package()
    out: list[str] = []
    sects: list[str] = []

    # ---- front matter
    title = fm["title"]
    out.append(para("papertitle", wr.run(title, {}) +
                    '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="1"/></w:r>',
                    '<w:keepNext/>'))
    out.append(para("papersubtitle", wr.run(fm["subtitle"], {}), '<w:spacing w:after="12pt"/>'))
    out.append(f"<w:p><w:pPr><w:pStyle w:val=\"Author\"/><w:spacing w:before=\"0pt\" w:after=\"0pt\"/>"
               f"{sect(1, first=True)}</w:pPr></w:p>")

    def author_block(a: dict, last: bool, section_end: str = "") -> str:
        lines = [(a["name"], {})]
        if a["reg"]:
            lines.append((f"Reg.{NBSP}No.{NBSP}{a['reg']}", {"sz": 18}))
        lines += [(fm["affiliation"][0], {"sz": 18, "i": True}), (fm["affiliation"][1], {"sz": 18})]
        if a["email"]:
            lines.append((a["email"], {"sz": 16}))
        runs = ""
        for k, (txt, f) in enumerate(lines):
            runs += ("<w:r><w:br/></w:r>" if k else "") + wr.run(txt, f)
        if not last:
            runs += '<w:r><w:br w:type="column"/></w:r>'
        return para("Author", runs, '<w:spacing w:before="0pt" w:after="2pt"/>' + section_end)

    people = fm["authors"]
    row1, row2 = people[:3], people[3:]
    for k, a in enumerate(row1):
        out.append(author_block(a, k == len(row1) - 1, sect(3) if k == len(row1) - 1 else ""))
    for k, a in enumerate(row2):
        out.append(author_block(a, k == len(row2) - 1, sect(2) if k == len(row2) - 1 else ""))

    def inl(i: int, fmt: dict | None = None) -> str:
        return wr.inlines(sn[i], fmt)

    out.append(para("Abstract", wr.run("Abstract\u2014", {"i": True}) + inl(ab_i),
                    '<w:spacing w:before="12pt" w:after="6pt"/>'))
    out.append(para("Keywords", wr.run("Keywords\u2014", {}) + inl(kw_i)))

    # ---- body
    def float_xml(f: dict) -> list[str]:
        xs = []
        if f["kind"] == "figure":
            png, h = render_figure(root, f["path"], f["width"])
            name = Path(f["path"]).with_suffix(".png").name
            alt = wr.flat(sn[f["cap_i"]])
            pic = pk.image(name, png, f["width"], h, alt)
            xs.append(para("Normal", pic, '<w:keepNext/><w:spacing w:before="6pt" w:after="0pt"/>'))
            xs.append(para("figurecaption", inl(f["cap_i"])))
            return xs
        cols = f["cols"]
        avail = COL_W - 2
        need = [0.0] * len(cols)
        longest_word = [0.0] * len(cols)
        for r in f["rows"]:
            for c in r["cells"]:
                if c["span"] != 1 or not c["text"]:
                    continue
                txt = wr.flat(sn[c["i"]])
                j = c["col"] - 1
                need[j] = max(need[j], est_width(txt, 8, r["header"]) + 5)
                longest_word[j] = max(longest_word[j], max(est_width(w, 8, r["header"]) for w in txt.split()) + 5)
        free = [j for j, c in enumerate(cols) if not c["frac"]]
        flex = avail - sum(c["frac"] * COL_W for c in cols if c["frac"])
        widths = [c["frac"] * COL_W if c["frac"] else 0.0 for c in cols]
        if sum(need[j] for j in free) <= flex:
            extra = (flex - sum(need[j] for j in free)) / len(free)
            for j in free:
                widths[j] = need[j] + extra
        else:
            floor = sum(longest_word[j] for j in free)
            room = max(flex - floor, 0.0)
            span = sum(need[j] - longest_word[j] for j in free) or 1.0
            for j in free:
                widths[j] = longest_word[j] + room * (need[j] - longest_word[j]) / span
            if floor > flex:
                widths = [w * flex / floor if j in free else w for j, w in enumerate(widths)]
        xs.append(para("tablehead", inl(f["cap_i"]), "<w:keepNext/>"))
        rows_xml = ""
        for ri, r in enumerate(f["rows"]):
            cells = ""
            for c in r["cells"]:
                span = c["span"]
                w = sum(widths[c["col"] - 1: c["col"] - 1 + span])
                top = ""
                if r["rule"] in ("top", "mid"):
                    top = border("top", 6 if r["rule"] == "top" else 4)
                for a, b in r["cmid"]:
                    if a <= c["col"] and c["col"] + span - 1 <= b:
                        top = border("top", 4)
                bottom = border("bottom", 6) if (ri == len(f["rows"]) - 1 and f["rows"][ri]["rule_below"]) else ""
                borders = f"<w:tcBorders>{top}{bottom}</w:tcBorders>" if (top or bottom) else ""
                grid = f'<w:gridSpan w:val="{span}"/>' if span > 1 else ""
                style = "tablecolhead" if r["header"] else "tablecopy"
                fmt = {"table": True}
                content = inl(c["i"], fmt) if c["text"] else ""
                keep = "<w:keepNext/>" if (ri < len(f["rows"]) - 1 or f["note_i"]) else ""   # table and note stay together
                p = para(style, content, f'{keep}<w:spacing w:before="1pt" w:after="1pt"/><w:jc w:val="{c["align"] if c["align"] != "left" else "start"}"/>')
                cells += f'<w:tc><w:tcPr><w:tcW w:w="{pt(w)}" w:type="dxa"/>{grid}{borders}</w:tcPr>{p}</w:tc>'
            rows_xml += f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>"
        grid_xml = "".join(f'<w:gridCol w:w="{pt(w)}"/>' for w in widths)
        xs.append(
            f'<w:tbl><w:tblPr><w:tblW w:w="{pt(sum(widths))}" w:type="dxa"/><w:jc w:val="center"/>'
            f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="0pt" w:type="dxa"/>'
            f'<w:start w:w="2.50pt" w:type="dxa"/><w:bottom w:w="0pt" w:type="dxa"/><w:end w:w="2.50pt" w:type="dxa"/>'
            f'</w:tblCellMar></w:tblPr><w:tblGrid>{grid_xml}</w:tblGrid>{rows_xml}</w:tbl>')
        for i in f["note_i"]:
            xs.append(para("tablefootnote", inl(i), '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'
                           '<w:spacing w:before="3pt" w:after="6pt"/><w:ind w:start="0pt" w:firstLine="0pt"/><w:jc w:val="both"/>'))
        if not f["note_i"]:
            xs.append(para("Normal", "", '<w:spacing w:before="0pt" w:after="6pt"/>'))
        return xs

    refs_div = None
    items = []
    for b in ast["blocks"]:
        first = b["c"][0] if b["t"] == "Para" and b["c"] else None
        m = re.fullmatch(r"XFLOAT(\d+)X", first["c"]) if first and first["t"] == "Str" and len(b["c"]) == 1 else None
        if m:
            items.append(("float", floats[int(m.group(1))]))
        elif b["t"] == "Div" and b["c"][0][0] == "refs":
            refs_div = b
        else:
            items.append(("block", b))
    unknown = set(FLOAT_SHIFT) - {f["label"] for f in floats}
    if unknown:
        raise DocxError(f"FLOAT_SHIFT names unknown floats: {sorted(unknown)}")
    items = place_floats(items)
    for kind, b in items:
        if kind == "float":
            f = b
            if f["kind"] == "figure" and f["wide"]:
                out.append(f'<w:p><w:pPr><w:pStyle w:val="Normal"/><w:spacing w:before="0pt" w:after="0pt"/>{sect(2)}</w:pPr></w:p>')
                out += float_xml(f)
                out.append(f'<w:p><w:pPr><w:pStyle w:val="Normal"/><w:spacing w:before="0pt" w:after="0pt"/>{sect(1)}</w:pPr></w:p>')
            else:
                out += float_xml(f)
            continue
        t = b["t"]
        if t == "Header":
            lvl, (hid, cls, _), inls = b["c"]
            style = "Heading5" if "unnumbered" in cls else {1: "Heading1", 2: "Heading2"}[lvl]
            out.append(para(style, wr.inlines(inls), "<w:keepNext/>" if style == "Heading5" else ""))
        elif t == "Para":
            out.append(para("BodyText", wr.inlines(b["c"])))
        elif t == "BulletList":
            for item in b["c"]:
                for blk in item:
                    if blk["t"] not in ("Para", "Plain"):
                        raise DocxError("nested list content not handled")
                    out.append(para("bulletlist", wr.inlines(blk["c"])))
        else:
            raise DocxError(f"block element {t} not handled")
    if refs_div is None:
        raise DocxError("no bibliography produced (citeproc)")

    out.append(para("Heading5", wr.run("References", {}), "<w:keepNext/>"))
    n = 0
    for entry in refs_div["c"][1]:
        n += 1
        inls = entry["c"][1][0]["c"]
        label = inls[0]
        want = f"[{n}]"
        if label["t"] != "Span" or "".join(x.get("c", " ") for x in label["c"][1] if x["t"] == "Str") != want:
            raise DocxError(f"reference {n} does not carry the label {want} (not in citation order?)")
        rest = [x for x in inls[1:]]
        rest = rest[0]["c"][1] if rest and rest[0]["t"] == "Span" and "csl-right-inline" in rest[0]["c"][0][1] else rest
        out.append(para("references", wr.inlines(rest), sect(2) if n == len(refs_div["c"][1]) else ""))
    out.append(para("Normal", "", '<w:spacing w:before="0pt" w:after="0pt"/>'))
    return "\n".join(out), json.dumps(fm["authors"]), pk, wr, [fm["title"], fm["keywords"]]


def front_properties(root: Path) -> dict:
    fm = front_matter((root / paper.TEX).read_text())
    return {"title": fm["title"], "authors": [a["name"] for a in fm["authors"]], "keywords": fm["keywords"]}


ROOT_NS = (
    f'xmlns:w="{W}" xmlns:r="{R}" xmlns:m="http://purl.oclc.org/ooxml/officeDocument/math" '
    'xmlns:wp="http://purl.oclc.org/ooxml/drawingml/wordprocessingDrawing" '
    'xmlns:a="http://purl.oclc.org/ooxml/drawingml/main" '
    'xmlns:pic="http://purl.oclc.org/ooxml/drawingml/picture"')


def assemble(root: Path, out: Path):
    """Write paper.docx: the template package with our document, footnote, footer and properties."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        body, _, pk, wr, _ = build_xml(root, tmp)
    tpl = zipfile.ZipFile(root / TEMPLATE)
    parts = {i.filename: tpl.read(i.filename) for i in tpl.infolist()}
    props = front_properties(root)
    final = sect(1)
    parts["word/document.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {ROOT_NS}><w:body>{body}{final}'
        "</w:body></w:document>").encode()
    # footnote: the capstone note of \thanks, on page 1
    fm = front_matter((root / paper.TEX).read_text())
    notes = parts["word/footnotes.xml"].decode()
    note = (f'<w:footnote w:id="1"><w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:rPr><w:vertAlign w:val="superscript"/>'
            f'<w:sz w:val="16"/></w:rPr><w:footnoteRef/></w:r><w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve"> {escape(fm["thanks"])}</w:t></w:r></w:p></w:footnote>')
    parts["word/footnotes.xml"] = notes.replace("</w:footnotes>", note + "</w:footnotes>").encode()
    # first-page footer: the template's copyright placeholder is conference-assigned text, left empty
    foot = parts["word/footer1.xml"].decode()
    foot = re.sub(r"<w:r [^>]*>.*?</w:r>|<w:r>.*?</w:r>", "", foot, flags=re.S)
    parts["word/footer1.xml"] = foot.encode()
    rels = parts["word/_rels/document.xml.rels"].decode()
    rels = re.sub(r'<Relationship Id="rId\d+" Type="[^"]*hyperlink"[^>]*/>', "", rels)
    rels = rels.replace('Id="rId8"', 'Id="rIdFooter"')
    extra = "".join(
        f'<Relationship Id="rIdImg{i}" Type="http://purl.oclc.org/ooxml/officeDocument/relationships/image" '
        f'Target="media/{n}"/>' for i, (n, _) in enumerate(pk.images, 1))
    parts["word/_rels/document.xml.rels"] = rels.replace("</Relationships>", extra + "</Relationships>").encode()
    for n, png in pk.images:
        parts[f"word/media/{n}"] = png
    ct = parts["[Content_Types].xml"].decode()
    parts["[Content_Types].xml"] = ct.replace("<Default Extension=\"xml\"", '<Default Extension="png" ContentType="image/png"/><Default Extension="xml"').encode()
    core = parts["docProps/core.xml"].decode()
    core = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{escape(props['title'])}</dc:title>", core)
    core = re.sub(r"<dc:creator>.*?</dc:creator>", f"<dc:creator>{escape(', '.join(props['authors']))}</dc:creator>", core)
    core = re.sub(r"<cp:keywords>.*?</cp:keywords>", f"<cp:keywords>{escape(re.sub(chr(10) + ' *', ' ', props['keywords']))}</cp:keywords>", core)
    core = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", core)
    core = re.sub(r"(<dcterms:(?:created|modified)[^>]*>)[^<]*", r"\g<1>2026-01-01T00:00:00Z", core)
    parts["docProps/core.xml"] = core.encode()
    app = parts["docProps/app.xml"].decode()
    app = re.sub(r"<(Pages|Words|Characters|Lines|Paragraphs|CharactersWithSpaces|TotalTime)>\d+</\1>", "", app)
    app = re.sub(r"<HeadingPairs>.*?</TitlesOfParts>", "", app, flags=re.S)
    app = app.replace("<Company>IEEE</Company>", "<Company></Company>")
    parts["docProps/app.xml"] = app.encode()
    order = ["[Content_Types].xml"] + [n for n in parts if n != "[Content_Types].xml"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, parts[n])


# --- LibreOffice: the PDF from the .docx ---------------------------------------------------------

def to_pdf(docx: Path, pdf: Path):
    from trafficsense.report import thesis
    exe, env = thesis.soffice()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        r = subprocess.run([exe, "--headless", "--norestore", f"-env:UserInstallation=file://{td}/profile",
                            "--convert-to", "pdf", "--outdir", str(td), str(docx)],
                           capture_output=True, text=True, env=env, timeout=300)
        made = td / (docx.stem + ".pdf")
        if r.returncode != 0 or not made.is_file():
            raise DocxError(f"LibreOffice failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
        shutil.copyfile(made, pdf)


# --- build record and checks ---------------------------------------------------------------------

def sources(root: Path) -> dict[str, str]:
    """sha256 of everything the Word file is made from, keyed by path relative to the repo root."""
    figures = sorted((root / PAPER_DIR / "figures").glob("*.pdf"))
    files = [paper.TEX, paper.BIB, TEMPLATE, CSL] + [f.relative_to(root) for f in figures]
    return {str(f): paper.sha256(root / f) for f in files}


def record(root: Path) -> dict:
    pdf = root / DOCX_PDF
    return {"docx_sha256": paper.sha256(root / DOCX), "pdf_sha256": paper.sha256(pdf),
            "pdf_pages": paper.pdf_pages(pdf), "sources": sources(root)}


def build(root: Path) -> dict:
    assemble(root, root / DOCX)
    to_pdf(root / DOCX, root / DOCX_PDF)
    rec = record(root)
    print(f"built {DOCX} and {DOCX_PDF} ({rec['pdf_pages']} pages)")
    return rec


def docx_text(path: Path) -> tuple[str, list[str], ET.Element]:
    z = zipfile.ZipFile(path)
    tree = ET.fromstring(z.read("word/document.xml"))
    paras = []
    for p in tree.iter(f"{{{W}}}p"):       # text runs and the text of native equations
        paras.append("".join(t.text or "" for t in p.iter() if t.tag in (f"{{{W}}}t", f"{{{M}}}t")))
    notes = ET.fromstring(z.read("word/footnotes.xml"))
    paras += ["".join(t.text or "" for t in p.iter(f"{{{W}}}t")) for p in notes.iter(f"{{{W}}}p")]
    return "\n".join(paras), paras, tree


def check(root: Path, rec: dict) -> list[str]:
    """Problems with paper.docx / paper_docx.pdf (empty list when fine); needs no LibreOffice."""
    docx, pdf = root / DOCX, root / DOCX_PDF
    if not docx.is_file() or not pdf.is_file() or not rec:
        return [f"{DOCX} / {DOCX_PDF} or their build record missing (run scripts/make_paper.py)"]
    errors = []
    if rec.get("sources") != sources(root):
        errors.append(f"{DOCX} is out of date with its sources (run scripts/make_paper.py)")
    if rec.get("docx_sha256") != paper.sha256(docx):
        errors.append(f"{DOCX} is not the file recorded in {paper.BUILD_RECORD} (run scripts/make_paper.py)")
    if rec.get("pdf_sha256") != paper.sha256(pdf):
        errors.append(f"{DOCX_PDF} is not the PDF recorded in {paper.BUILD_RECORD} (run scripts/make_paper.py)")
    pages = paper.pdf_pages(pdf)
    if pages is None or pages > paper.MAX_PAGES:
        errors.append(f"{DOCX_PDF} has {pages} pages; the limit is {paper.MAX_PAGES} including references")
    try:
        import pypdfium2 as pdfium
        w, h = pdfium.PdfDocument(str(pdf))[0].get_size()
        if (round(w), round(h)) != (PAGE_W, PAGE_H):
            errors.append(f"{DOCX_PDF}: page is {w:.0f}x{h:.0f} pt, not Letter {PAGE_W}x{PAGE_H}")
    except ImportError:
        pass
    try:
        text, paras, tree = docx_text(docx)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        return errors + [f"{DOCX} is not a readable Word file: {e}"]
    # page setup: Letter everywhere, the last (body) section in two columns
    sects = list(tree.iter(f"{{{W}}}sectPr"))
    for s in sects:
        sz = s.find("w:pgSz", NS)
        if sz is None or (sz.get(f"{{{W}}}w"), sz.get(f"{{{W}}}h")) != (f"{PAGE_W}pt", f"{PAGE_H}pt"):
            errors.append(f"{DOCX}: a section is not Letter size")
    body = tree.find("w:body", NS)
    counts, n = [], 0
    for el in body:
        if el.tag == f"{{{W}}}p":
            n += 1
            sp = el.find("w:pPr/w:sectPr", NS)
            if sp is not None:
                counts.append((n, sp))
                n = 0
        elif el.tag == f"{{{W}}}sectPr":
            counts.append((n, el))
    biggest = max(counts, key=lambda c: c[0])[1]
    cols = biggest.find("w:cols", NS)
    if cols is None or cols.get(f"{{{W}}}num") != "2":
        errors.append(f"{DOCX}: the body is not in two columns")
    for bad in LEFTOVERS:
        if bad in text:
            errors.append(f"{DOCX}: leftover text {bad!r}")
    errors += [f"{DOCX}: {e}" for e in paper.check_identifiers(text)]
    # every tagged number of paper.tex is in the Word text
    tex = strip_comments((root / paper.TEX).read_text())
    flat = text.replace(MINUS, "-")
    need: dict[str, int] = {}
    for m in paper.TAG.finditer(tex):
        need[m.group("num")] = need.get(m.group("num"), 0) + 1
    for num, k in need.items():
        have = len(re.findall(r"(?<![\d.])" + re.escape(num) + r"(?![\d])", flat))
        if have < k:
            errors.append(f"{DOCX}: number {num} is tagged {k}x in paper.tex but appears {have}x")
    # references: as many as refs.bib entries, styled 'references', numbered by the template
    styles = [p.find("w:pPr/w:pStyle", NS) for p in tree.iter(f"{{{W}}}p")]
    n_refs = sum(1 for s in styles if s is not None and s.get(f"{{{W}}}val") == "references")
    cited = len(paper.bib_entries((root / paper.BIB).read_text()))
    if n_refs != cited:
        errors.append(f"{DOCX}: {n_refs} reference paragraphs, refs.bib has {cited} entries")
    if re.search(r"\[\?\]|\[@|\bXFLOAT", text):
        errors.append(f"{DOCX}: unresolved citation or float marker")
    return errors
