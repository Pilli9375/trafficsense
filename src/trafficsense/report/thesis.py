"""Build the project report as a Word file in the college capstone thesis format, and its PDF.

The format is described in docs/report/format_spec.md; the college's example thesis
(`paths.thesis_format`, on D, not in git) supplies the base styles and the university logo.

    reference_docx()  a cleaned copy of the college styles, plus the styles pandoc and the filter
                      use, with every value from the spec (page, fonts, spacing, headings, captions)
    code_listings()   the appendix listings, generated from the repository files at HEAD
    postprocess()     footers, page-number sections, table text style, update-fields flag
    fill_lists()      contents, list of tables and list of figures with the page numbers measured
                      in the PDF (LibreOffice renders the cached field results as they are)
    render_pdf()      LibreOffice headless converts the .docx itself, with the real Times New Roman

Everything here fails loudly: a missing tool, font, file or marker stops the build.
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

# --- page (format_spec.md: US Letter, the college file's first-section margins) -------------
PAGE_W, PAGE_H = 12240, 15840                     # twips: 21.59 x 27.94 cm
MARGIN = dict(top=1440, right=1800, bottom=851, left=1800, header=720, footer=720, gutter=0)
TEXT_W = PAGE_W - MARGIN["left"] - MARGIN["right"]    # 8640 twips = 15.24 cm

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
FOOTER_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
FOOTER_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"

MARKERS = {"@@TOC@@": "toc", "@@LOT@@": "lot", "@@LOF@@": "lof"}

# Key source files listed in full in the appendix (Section "Source Code"); every other Python
# file is listed by path. The text is read from the repository at build time, never retyped.
LISTINGS = [
    "src/trafficsense/control/base.py",
    "src/trafficsense/control/maxpressure.py",
    "src/trafficsense/control/llm.py",
    "src/trafficsense/control/guided.py",
    "src/trafficsense/control/preemption.py",
    "src/trafficsense/llm/client.py",
    "src/trafficsense/llm/prompt.py",
    "src/trafficsense/sim/env.py",
    "src/trafficsense/sim/observation.py",
    "src/trafficsense/perception/errors.py",
]


# --- styles ---------------------------------------------------------------------------------

def _rpr(size=None, bold=False, italic=False, caps=False, font="Times New Roman", color=None):
    x = f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:cs="{font}"/>' if font else ""
    x += "<w:b/><w:bCs/>" if bold else "<w:b w:val=\"0\"/><w:bCs w:val=\"0\"/>"
    x += "<w:i/><w:iCs/>" if italic else "<w:i w:val=\"0\"/><w:iCs w:val=\"0\"/>"
    if caps:
        x += "<w:caps/>"
    x += f'<w:color w:val="{color or "000000"}"/>'
    if size:
        x += f'<w:sz w:val="{int(size * 2)}"/><w:szCs w:val="{int(size * 2)}"/>'
    return x


def _ppr(jc=None, before=0, after=0, line=240, first=None, left=None, hanging=None, keep_next=False,
         keep_lines=False, page_break=False, outline=None, tabs=None, widow=True):
    x = ""
    if keep_next:
        x += "<w:keepNext/>"
    if keep_lines:
        x += "<w:keepLines/>"
    if page_break:
        x += "<w:pageBreakBefore/>"
    x += "<w:widowControl/>" if widow else '<w:widowControl w:val="0"/>'
    if tabs:
        x += "<w:tabs>" + "".join(f'<w:tab w:val="{v}" w:pos="{p}"' + (f' w:leader="{ld}"' if ld else "") + "/>"
                                  for v, p, ld in tabs) + "</w:tabs>"
    x += f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" w:lineRule="auto"/>'
    ind = ""
    if left is not None:
        ind += f' w:left="{left}"'
    if first is not None:
        ind += f' w:firstLine="{first}"'
    if hanging is not None:
        ind += f' w:hanging="{hanging}"'
    x += "<w:ind" + (ind or ' w:left="0" w:firstLine="0"') + "/>"
    if jc:
        x += f'<w:jc w:val="{jc}"/>'
    if outline is not None:
        x += f'<w:outlineLvl w:val="{outline}"/>'
    return x


def _pstyle(sid, name, ppr, rpr, based="Normal", custom=True, nxt=None):
    c = ' w:customStyle="1"' if custom else ""
    n = f'<w:next w:val="{nxt}"/>' if nxt else ""
    return (f'<w:style w:type="paragraph"{c} w:styleId="{sid}"><w:name w:val="{name}"/>'
            f'<w:basedOn w:val="{based}"/>{n}<w:qFormat/><w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')


def _cstyle(sid, name, rpr):
    return (f'<w:style w:type="character" w:customStyle="1" w:styleId="{sid}"><w:name w:val="{name}"/>'
            f'<w:qFormat/><w:rPr>{rpr}</w:rPr></w:style>')


BODY_LINE = 360            # 1.5 lines
BODY_AFTER = 240           # 12 pt after each paragraph (format_spec.md)
INDENT = 720               # 0.5 in first-line indent
TAB_RIGHT = [("right", TEXT_W, None)]


def our_styles() -> dict[str, str]:
    """styleId -> <w:style> XML for every style the report uses (values from format_spec.md)."""
    s = {
        "Normal": ('<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
                   f'<w:qFormat/><w:pPr>{_ppr()}</w:pPr><w:rPr>{_rpr(12)}<w:lang w:val="en-GB"/></w:rPr></w:style>'),
        "BodyText": _pstyle("BodyText", "Body Text", _ppr("both", 0, BODY_AFTER, BODY_LINE, first=INDENT), "", custom=False),
        "FirstParagraph": _pstyle("FirstParagraph", "First Paragraph", _ppr("both", 0, BODY_AFTER, BODY_LINE, first=INDENT),
                                  "", based="BodyText"),
        # list items (pandoc: "Compact" for tight lists); the list numbering supplies the indent
        "Compact": _pstyle("Compact", "Compact", _ppr("both", 0, 80, BODY_LINE), "", based="BodyText"),
        "TableText": _pstyle("TableText", "Table Text", _ppr("left", 20, 20, 240), _rpr(10)),
        "TableHeader": _pstyle("TableHeader", "Table Header", _ppr("left", 20, 20, 240, keep_next=True), _rpr(10, bold=True),
                               based="TableText"),
        "Heading1": _pstyle("Heading1", "heading 1", _ppr("center", 0, 480, BODY_LINE, keep_next=True, keep_lines=True,
                                                          page_break=True, outline=0), _rpr(14, bold=True, caps=True),
                            custom=False, nxt="BodyText"),
        "Heading2": _pstyle("Heading2", "heading 2", _ppr("left", 240, 120, BODY_LINE, keep_next=True, keep_lines=True,
                                                          outline=1), _rpr(14, bold=True), custom=False, nxt="BodyText"),
        "Heading3": _pstyle("Heading3", "heading 3", _ppr("left", 200, 120, BODY_LINE, keep_next=True, keep_lines=True,
                                                          outline=2), _rpr(13, bold=True), custom=False, nxt="BodyText"),
        "FrontHeading": _pstyle("FrontHeading", "Front Heading", _ppr("center", 0, 480, BODY_LINE, keep_next=True,
                                                                      page_break=True, outline=0),
                                _rpr(14, bold=True, caps=True)),
        "MinorHeading": _pstyle("MinorHeading", "Minor Heading", _ppr("left", 120, 60, BODY_LINE, keep_next=True,
                                                                      keep_lines=True), _rpr(12, bold=True)),
        "Caption": _pstyle("Caption", "caption", _ppr("center", 60, 120, 240, keep_next=True, keep_lines=True),
                           _rpr(10, bold=True), custom=False),
        "CaptionNote": _pstyle("CaptionNote", "Caption Note", _ppr("both", 0, 240, 240), _rpr(10)),
        "TableNote": _pstyle("TableNote", "Table Note", _ppr("both", 0, 120, 240, keep_next=True), _rpr(10)),
        "TableSpacer": ('<w:style w:type="paragraph" w:customStyle="1" w:styleId="TableSpacer"><w:name w:val="Table Spacer"/>'
                        '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="exact"/>'
                        '</w:pPr><w:rPr><w:sz w:val="16"/></w:rPr></w:style>'),
        "FigureImage": _pstyle("FigureImage", "Figure Image", _ppr("center", 120, 60, 240, keep_next=True), ""),
        "SourceCode": _pstyle("SourceCode", "Source Code", _ppr("left", 0, 120, 240, widow=False),
                              _rpr(8, font="Consolas")),
        "CodeLine": _pstyle("CodeLine", "Code Line", _ppr("left", 0, 0, 240, left=567, hanging=567, widow=False),
                            _rpr(8, font="Consolas")),
        "TOC1": _pstyle("TOC1", "toc 1", _ppr("left", 120, 0, 276, tabs=[("right", TEXT_W - 10, "dot")]),
                        _rpr(12, bold=True), custom=False, nxt="BodyText"),
        "TOC2": _pstyle("TOC2", "toc 2", _ppr("left", 0, 0, 276, left=440, tabs=[("right", TEXT_W - 10, "dot")]),
                        _rpr(12), custom=False),
        "TOC3": _pstyle("TOC3", "toc 3", _ppr("left", 0, 0, 276, left=880, tabs=[("right", TEXT_W - 10, "dot")]),
                        _rpr(12), custom=False),
        "TableofFigures": _pstyle("TableofFigures", "table of figures",
                                  _ppr("left", 0, 60, 276, left=1134, hanging=1134, tabs=[("right", TEXT_W - 10, "dot")]),
                                  _rpr(12), custom=False),
        "Bibliography": _pstyle("Bibliography", "Bibliography", _ppr("left", 0, 120, 276, left=567, hanging=567),
                                _rpr(11), custom=False),
        # title page and certificate
        "TPTitle": _pstyle("TPTitle", "TP Title", _ppr("center", 240, 240, 276), _rpr(16, bold=True)),
        "TPBold": _pstyle("TPBold", "TP Bold", _ppr("center", 360, 0, 276), _rpr(12, bold=True)),
        "TPPlain": _pstyle("TPPlain", "TP Plain", _ppr("center", 120, 0, 276), _rpr(12)),
        "TPItalic": _pstyle("TPItalic", "TP Italic", _ppr("center", 480, 0, 276), _rpr(12, italic=True)),
        "TPName": _pstyle("TPName", "TP Name", _ppr("center", 120, 0, 276), _rpr(14, bold=True)),
        "TPLogo": _pstyle("TPLogo", "TP Logo", _ppr("center", 600, 360, 240), ""),
        "TPLarge": _pstyle("TPLarge", "TP Large", _ppr("center", 120, 0, 276), _rpr(14)),
        "TPLargeItalic": _pstyle("TPLargeItalic", "TP Large Italic", _ppr("center", 240, 0, 276), _rpr(14, italic=True)),
        "CertificateText": _pstyle("CertificateText", "Certificate Text", _ppr("both", 240, 240, BODY_LINE), _rpr(14)),
        "SignRight": _pstyle("SignRight", "Sign Right", _ppr("right", 720, 0, BODY_LINE), _rpr(12)),
        "SignCentre": _pstyle("SignCentre", "Sign Centre", _ppr("center", 480, 0, BODY_LINE), _rpr(12)),
        "SignRow": _pstyle("SignRow", "Sign Row", _ppr("left", 720, 0, BODY_LINE, tabs=TAB_RIGHT), _rpr(12)),
        "BiodataLine": _pstyle("BiodataLine", "Biodata Line", _ppr("left", 0, 60, BODY_LINE, left=120,
                                                                   tabs=[("left", 2200, None)]), _rpr(12)),
        "BiodataPhoto": _pstyle("BiodataPhoto", "Biodata Photo", _ppr("left", 60, 0, 240), _rpr(10)),
        "NoteText": _pstyle("NoteText", "Note Text", _ppr("both", 1440, 0, 276, page_break=True), _rpr(18, bold=True)),
        # character styles
        "NoteRed": _cstyle("NoteRed", "Note Red", '<w:color w:val="FF0000"/>'),
        "VerbatimChar": _cstyle("VerbatimChar", "Verbatim Char",
                                '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="21"/>'
                                '<w:szCs w:val="21"/>'),
        "TableSmall": _cstyle("TableSmall", "Table Small", '<w:sz w:val="18"/><w:szCs w:val="18"/>'),
        "TableTiny": _cstyle("TableTiny", "Table Tiny", '<w:sz w:val="16"/><w:szCs w:val="16"/>'),
        "Hyperlink": ('<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
                      '<w:rPr><w:color w:val="000000"/></w:rPr></w:style>'),
        # table style: single 0.5 pt black grid (the college file's Table Grid), bold header row
        "Table": ('<w:style w:type="table" w:default="1" w:styleId="Table"><w:name w:val="Table"/>'
                  '<w:basedOn w:val="TableNormal"/><w:qFormat/><w:pPr><w:spacing w:before="0" w:after="0" '
                  'w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
                  '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblBorders>'
                  + "".join(f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                            for e in ("top", "left", "bottom", "right", "insideH", "insideV"))
                  + '</w:tblBorders><w:tblCellMar><w:top w:w="20" w:type="dxa"/><w:left w:w="85" w:type="dxa"/>'
                  '<w:bottom w:w="20" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                  '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/></w:rPr><w:tcPr><w:vAlign w:val="bottom"/>'
                  '</w:tcPr></w:tblStylePr></w:style>'),
    }
    return s


DOC_DEFAULTS = ('<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" '
                'w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/>'
                '<w:lang w:val="en-GB" w:eastAsia="en-US" w:bidi="ar-SA"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
                '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>')

_STYLE = re.compile(r'<w:style\b[^>]*w:styleId="([^"]+)"[^>]*>.*?</w:style>', re.S)


def merged_styles(college_styles: str, pandoc_styles: str) -> str:
    """The college styles.xml with docDefaults and our styles replacing theirs, plus the pandoc
    styles neither defines (footnotes, definition lists, ...)."""
    ours = our_styles()
    college_ids = {m[1] for m in _STYLE.finditer(college_styles)}
    out = re.sub(r"<w:docDefaults>.*?</w:docDefaults>", DOC_DEFAULTS, college_styles, count=1, flags=re.S)
    if DOC_DEFAULTS not in out:
        raise ValueError("college styles.xml has no <w:docDefaults>")
    out = _STYLE.sub(lambda m: ours[m[1]] if m[1] in ours else m[0], out)
    extra = [ours[k] for k in ours if k not in college_ids]
    extra += [m[0] for m in _STYLE.finditer(pandoc_styles) if m[1] not in college_ids and m[1] not in ours]
    return out.replace("</w:styles>", "".join(extra) + "</w:styles>")


def _sect(final: bool) -> str:
    m = MARGIN
    num = '<w:pgNumType w:fmt="decimal" w:start="1"/>' if final else ""
    return (f'<w:sectPr><w:footerReference w:type="default" r:id="rIdTSFooter"/>'
            f'<w:pgSz w:w="{PAGE_W}" w:h="{PAGE_H}"/><w:pgMar w:top="{m["top"]}" w:right="{m["right"]}" '
            f'w:bottom="{m["bottom"]}" w:left="{m["left"]}" w:header="{m["header"]}" w:footer="{m["footer"]}" '
            f'w:gutter="0"/>{num}</w:sectPr>')


def reference_docx(college: Path, pandoc: str, out: Path) -> None:
    """pandoc's default reference.docx with the merged styles and the spec's page."""
    if not college.is_file():
        raise FileNotFoundError(f"college thesis format not found: {college} (paths.thesis_format; see configs/default.yaml)")
    base = subprocess.run([pandoc, "--print-default-data-file", "reference.docx"], capture_output=True, check=True).stdout
    tmp = out.with_suffix(".base.docx")
    tmp.write_bytes(base)
    with zipfile.ZipFile(college) as cz:
        college_styles = cz.read("word/styles.xml").decode("utf-8")
    with zipfile.ZipFile(tmp) as z, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as o:
        for n in z.namelist():
            b = z.read(n)
            if n == "word/styles.xml":
                b = merged_styles(college_styles, b.decode("utf-8")).encode("utf-8")
            elif n == "word/document.xml":
                d = b.decode("utf-8")
                d = re.sub(r"<w:sectPr>.*?</w:sectPr>", _sect(True).replace(
                    '<w:footerReference w:type="default" r:id="rIdTSFooter"/>', ""), d, flags=re.S)
                b = d.encode("utf-8")
            o.writestr(n, b)
    tmp.unlink()


def extract_logo(college: Path, out_dir: Path) -> Path:
    """The first image of the college file's title page (the university logo)."""
    with zipfile.ZipFile(college) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        first_sect = doc[:doc.index("<w:sectPr")]
        m = re.search(r'r:embed="(rId\d+)"', first_sect)
        if not m:
            raise ValueError(f"{college}: no image on the title page")
        t = re.search(r'Id="%s"[^>]*Target="([^"]+)"' % m[1], rels) or re.search(r'Target="([^"]+)"[^>]*Id="%s"' % m[1], rels)
        if not t:
            raise ValueError(f"{college}: logo relationship {m[1]} not found")
        data = z.read("word/" + t[1])
    out = out_dir / ("logo" + Path(t[1]).suffix)
    out.write_bytes(data)
    return out


# --- code listings ----------------------------------------------------------------------------

def _git(root: Path, *args) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def _docline(path: Path) -> str:
    """First line of the module docstring, or '' if there is none."""
    m = re.match(r'\s*(?:#[^\n]*\n\s*)*[rub]*("""|\'\'\')\s*(.*?)(?:\n|\1)', path.read_text(), re.S)
    return m[2].strip() if m else ""


def code_listings(root: Path) -> str:
    """Markdown (with raw OpenXML) for the appendix: each key file in full, numbered lines, then a
    table of every other Python file. Refuses to build from files that differ from HEAD."""
    # the listings and the file table name a commit: every source file must be as in that commit
    dirty = _git(root, "status", "--porcelain", "--untracked-files=all", "--", "src", "scripts")
    dirty = "\n".join(ln for ln in dirty.splitlines() if "__pycache__" not in ln)
    if dirty:
        raise RuntimeError(f"commit these files first; the code listings must match a commit:\n{dirty}")
    commit = _git(root, "rev-parse", "--short=10", "HEAD")
    out = [f"Every listing below is the file as it is in commit `{commit}` of the project repository, "
           "printed by the report build (line numbers on the left); none is retyped. Long lines wrap.\n"]
    for rel in LISTINGS:
        p = root / rel
        lines = p.read_text().expandtabs(4).split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        out.append(f"### `{rel}`\n\n{_docline(p) or 'No module docstring.'} {len(lines)} lines.\n")
        width = len(str(len(lines)))
        paras = []
        for i, ln in enumerate(lines, 1):
            text = html.escape(f"{i:>{width}}  {ln}", quote=False)
            paras.append(f'<w:p><w:pPr><w:pStyle w:val="CodeLine"/></w:pPr><w:r><w:t xml:space="preserve">{text}'
                         "</w:t></w:r></w:p>")
        out.append("```{=openxml}\n" + "\n".join(paras) + "\n```\n")
    tracked = _git(root, "ls-files", "src/*.py", "scripts/*.py", "scripts/*.sh").split("\n")
    rows = []
    for rel in sorted(t for t in tracked if t and t not in LISTINGS and "/_vendor/" not in t and not t.endswith("__init__.py")):
        p = root / rel
        n = len(p.read_text().splitlines())
        desc = _docline(p) if rel.endswith(".py") else (p.read_text().splitlines()[1].lstrip("# ") if n > 1 else "")
        desc = desc.replace("|", "/").rstrip(".") or "(no description)"
        rows.append(f"| `{rel}` | {n} | {desc} |")
    out.append("### Other source files\n\nThe remaining source files, by path, with their length and the first "
               "line of their own description (module docstring or header comment). Tests are in `tests/`, "
               "configuration in `configs/`.\n")
    out.append("::: {#tbl:other-files}\n| File | Lines | Description |\n|:---------------------------|-----:|:"
               "-------------------------------------------|\n" + "\n".join(rows)
               + f"\n\n: Source files not listed in full, in commit `{commit}`.\n:::\n")
    return "\n".join(out)


# --- post-processing --------------------------------------------------------------------------

FOOTER_XML = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="{W_NS}" xmlns:r="{R_NS}">'
              '<w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="center"/></w:pPr>'
              '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
              '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r>'
              '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>')
FOOTER_FIRST_XML = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="{W_NS}" xmlns:r="{R_NS}">'
                    '<w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr></w:p></w:ftr>')


def _read(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def _write(path: Path, parts: dict[str, bytes]) -> None:
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as o:
        for n, b in parts.items():
            o.writestr(n, b)
    tmp.replace(path)


LONG_TABLE_CHARS = 1500     # text characters above which a table may break across pages (about a third of a page)


def postprocess(docx: Path, authors: list[str], title: str) -> None:
    parts = _read(docx)
    doc = parts["word/document.xml"].decode("utf-8")
    if 'r:id="rIdTSFooter"' not in doc:
        raise ValueError("no front-matter section break (div .frontmatter-end) in the document")
    if doc.count("<w:sectPr") != 2:
        raise ValueError(f"expected 2 sections (front matter, body), found {doc.count('<w:sectPr')}")
    # the body section: Arabic page numbers from 1
    doc = re.sub(r"<w:sectPr>(?:(?!<w:sectPr).)*?</w:sectPr>\s*</w:body>", _sect(True) + "</w:body>", doc, flags=re.S)
    if "</w:sectPr></w:body>" not in doc:
        raise ValueError("could not replace the final section properties")
    # tables: cell paragraphs in the table text style (pandoc writes "Compact"), and a 12 pt
    # spacer after each table so the next paragraph does not touch it
    def table(m):
        t = m[0]
        if "BiodataLine" in t:
            return t
        # grid-table cells hold Body Text / First Paragraph paragraphs (first-line indent): those too
        t = re.sub(r'<w:pStyle w:val="(?:Compact|BodyText|FirstParagraph)"\s*/>', '<w:pStyle w:val="TableText"/>', t)

        # header rows bold (LibreOffice ignores the table style's first-row formatting); no row is
        # split across pages
        def row(r):
            x = r[0]
            if "<w:tblHeader" in x:
                x = x.replace('<w:pStyle w:val="TableText"/>', '<w:pStyle w:val="TableHeader"/>')
            if "<w:trPr>" in x:
                return x.replace("<w:trPr>", "<w:trPr><w:cantSplit/>", 1)
            return x.replace("<w:tr>", "<w:tr><w:trPr><w:cantSplit/></w:trPr>", 1)
        t = re.sub(r"<w:tr>.*?</w:tr>", row, t, flags=re.S)
        # a short table (up to 20 rows and LONG_TABLE_CHARS characters of text) stays on one page
        # with its caption: every row but the last keeps with the next. A longer one may break
        # between rows (rows never split; the header row repeats; the caption, the header row and
        # the first row stay together because the caption and the header style keep with next)
        rows = re.findall(r"<w:tr>.*?</w:tr>", t, re.S)
        if len(rows) <= 20 and len(re.sub(r"<[^>]+>", "", t)) <= LONG_TABLE_CHARS:
            for r in rows[:-1]:
                t = t.replace(r, r.replace('<w:pStyle w:val="TableText"/>', '<w:pStyle w:val="TableText"/><w:keepNext/>'), 1)
        return t + '<w:p><w:pPr><w:pStyle w:val="TableSpacer"/></w:pPr></w:p>'
    doc = re.sub(r"<w:tbl>.*?</w:tbl>", table, doc, flags=re.S)
    # a lead-in paragraph (text ends with a colon) that is followed by a list keeps with the list
    def lead_in(m):
        x = m[0]
        if not re.sub(r"<[^>]+>", "", x).rstrip().endswith(":") or "<w:keepNext" in x:
            return x
        return re.sub(r"(<w:pStyle [^>]*/>)", r"\1<w:keepNext/>", x, count=1)
    doc = re.sub(r"<w:p>(?:(?!</w:p>).)*?</w:p>(?=\s*<w:p><w:pPr><w:pStyle [^>]*/><w:numPr>)", lead_in, doc, flags=re.S)
    # inline images: no wrap distance (LibreOffice otherwise shifts them 0.125 in to the right)
    doc = doc.replace("<wp:inline>", '<wp:inline distT="0" distB="0" distL="0" distR="0">')
    parts["word/document.xml"] = doc.encode("utf-8")
    parts["word/footer_ts.xml"] = FOOTER_XML.encode("utf-8")
    parts["word/footer_ts_first.xml"] = FOOTER_FIRST_XML.encode("utf-8")
    rels = parts["word/_rels/document.xml.rels"].decode("utf-8")
    rels = rels.replace("</Relationships>",
                        f'<Relationship Id="rIdTSFooter" Type="{FOOTER_REL}" Target="footer_ts.xml"/>'
                        f'<Relationship Id="rIdTSFooterFirst" Type="{FOOTER_REL}" Target="footer_ts_first.xml"/>'
                        "</Relationships>")
    parts["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    ct = parts["[Content_Types].xml"].decode("utf-8")
    ct = ct.replace("</Types>", f'<Override PartName="/word/footer_ts.xml" ContentType="{FOOTER_CT}"/>'
                                f'<Override PartName="/word/footer_ts_first.xml" ContentType="{FOOTER_CT}"/></Types>')
    parts["[Content_Types].xml"] = ct.encode("utf-8")
    st = parts["word/settings.xml"].decode("utf-8")
    if "<w:updateFields" not in st:     # Word asks to update the fields (contents, lists) on opening
        st = re.sub(r"(<w:settings[^>]*>)", r'\1<w:updateFields w:val="true"/>', st, count=1)
    parts["word/settings.xml"] = st.encode("utf-8")
    core = parts["docProps/core.xml"].decode("utf-8")
    core = re.sub(r"<dc:title>.*?</dc:title>|<dc:title/>", "", core)
    core = re.sub(r"<dc:creator>.*?</dc:creator>|<dc:creator/>", "", core)
    core = core.replace("</cp:coreProperties>", f"<dc:title>{html.escape(title)}</dc:title>"
                                                 f"<dc:creator>{html.escape('; '.join(authors))}</dc:creator></cp:coreProperties>")
    parts["docProps/core.xml"] = core.encode("utf-8")
    _write(docx, parts)


# --- contents and lists -----------------------------------------------------------------------

@dataclass
class Entry:
    kind: str           # toc | lot | lof
    level: int
    text: str           # as shown in the list
    key: str            # what to look for in the PDF page text
    page: str = ""


def _text(xml: str) -> str:
    return html.unescape("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml)))


def _norm(s: str) -> str:
    s = s.replace("­", "")
    s = re.sub(r"[ \t     ]+", " ", s)
    return re.sub(r" *\r?\n *", "\n", s).strip()


def entries(doc: str) -> list[Entry]:
    """Contents entries (TC fields) and caption entries (SEQ Table / SEQ Figure), in order."""
    out = []
    for p in re.findall(r"<w:p\b.*?</w:p>", doc, re.S):
        for m in re.finditer(r'<w:instrText[^>]*>\s*TC\s+(?:"|&quot;)(.*?)(?:"|&quot;)\s+\\l\s+(\d)', p):
            text = html.unescape(m[1])
            visible = _norm(_text(p))
            if re.match(r"\d+ ", text) and "." not in text.split(" ")[0]:
                key = "CHAPTER " + text.split(" ")[0]          # chapter: its first line
            elif re.match(r"[\d.]+ ", text):
                key = visible                                        # section: number and title
            else:
                key = visible.upper()                                # front heading, in capitals
            out.append(Entry("toc", int(m[2]), text.replace(" ", "  "), key))
        if 'w:val="Caption"' in p:
            kind = "lot" if "SEQ Table" in p else ("lof" if "SEQ Figure" in p else None)
            if kind:
                t = _norm(_text(p))
                out.append(Entry(kind, 1, t, t))
    return out


def _roman(n: int) -> str:
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    s = ""
    for v, r in vals:
        while n >= v:
            s += r
            n -= v
    return s


def page_numbers(es: list[Entry], pages: list[str]) -> None:
    """Find each entry on the PDF pages, in document order, and set its printed page number."""
    texts = [_norm(t) for t in pages]

    def find(key: str, start: int) -> int:
        pat = re.compile(r"(?:^|\n)" + r"[ \n]".join(re.escape(w) for w in _norm(key).split(" ")[:12]))
        for i in range(start, len(texts)):
            if pat.search(texts[i]):
                return i
        raise ValueError(f"not found in the PDF after page {start + 1}: {key!r}")

    cur = 0
    found = {}
    for e in (e for e in es if e.kind == "toc"):
        cur = find(e.key, cur)
        found[id(e)] = cur
    body = min(found[id(e)] for e in es if e.kind == "toc" and e.key == "CHAPTER 1")
    for kind in ("lot", "lof"):
        cur = body
        for e in (e for e in es if e.kind == kind):
            cur = find(e.key, cur)
            found[id(e)] = cur
    for e in es:
        i = found[id(e)]
        e.page = _roman(i + 1) if i < body else str(i - body + 1)


def _toc_para(style: str, text: str, page: str, prefix: str = "", suffix: str = "") -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{prefix}<w:r><w:t xml:space="preserve">'
            f'{html.escape(text, quote=False)}</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>{page}</w:t></w:r>{suffix}</w:p>')


def fill_lists(docx: Path, pages: list[str] | None) -> list[Entry]:
    """Write the contents and the two lists as the cached results of their fields (in place).
    `docx` must still hold the marker results written by thesis.lua: the build fills a fresh
    copy of the pandoc output on every pass. With pages=None the page numbers are left empty."""
    parts = _read(docx)
    doc = parts["word/document.xml"].decode("utf-8")
    es = entries(doc)
    if pages is not None:
        page_numbers(es, pages)
    style = {"toc": lambda e: f"TOC{e.level}", "lot": lambda e: "TableofFigures", "lof": lambda e: "TableofFigures"}
    for marker, kind in MARKERS.items():
        items = [e for e in es if e.kind == kind]
        if not items:
            raise ValueError(f"no entries for the {kind} list")
        pat = re.compile(r'<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                         r'<w:r><w:instrText xml:space="preserve">([^<]*)</w:instrText></w:r>'
                         r'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>' + re.escape(marker) +
                         r'</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
        found = pat.findall(doc)
        if len(found) != 1:
            raise ValueError(f"expected one {marker} field, found {len(found)}")
        begin = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve">'
                 f'{found[0]}</w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>')
        end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        paras = [_toc_para(style[kind](e), e.text, e.page, begin if i == 0 else "", end if i == len(items) - 1 else "")
                 for i, e in enumerate(items)]
        doc = pat.sub(lambda _: "".join(paras), doc)
    parts["word/document.xml"] = doc.encode("utf-8")
    _write(docx, parts)
    return es


# --- PDF ----------------------------------------------------------------------------------------

def soffice() -> tuple[str, dict]:
    """LibreOffice and the environment it needs here (see the docstring of scripts/build_report.py)."""
    exe = os.environ.get("SOFFICE") or shutil.which("soffice")
    if not exe:
        hits = sorted((Path.home() / ".local/opt/libreoffice/squashfs-root/opt").glob("libreoffice*/program/soffice"))
        exe = str(hits[-1]) if hits else None
    if not exe or not Path(exe).is_file():
        raise SystemExit("LibreOffice not found: set SOFFICE or install it (see scripts/build_report.py)")
    env = dict(os.environ)
    libs = os.environ.get("SOFFICE_LIBS") or str(Path.home() / ".cache/pw-libs/root/usr/lib/x86_64-linux-gnu")
    if Path(libs).is_dir():
        env["LD_LIBRARY_PATH"] = libs + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    return exe, env


FONT_FILES = ["times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf",
              "consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf",
              "cambria.ttc", "symbol.ttf"]          # equations (Cambria Math) and bullets (Symbol)


def render_pdf(docx: Path, out_dir: Path, fonts_dir: Path, work: Path) -> Path:
    """LibreOffice headless: docx -> PDF, with Times New Roman and Consolas linked (not copied)
    into a private LibreOffice profile."""
    missing = [f for f in FONT_FILES if not (fonts_dir / f).is_file()]
    if missing:
        raise FileNotFoundError(f"fonts missing in {fonts_dir} (paths.report_fonts): {missing}")
    profile = work / "lo-profile"
    (profile / "user/fonts").mkdir(parents=True, exist_ok=True)
    for f in FONT_FILES:
        link = profile / "user/fonts" / f
        if not link.exists():
            link.symlink_to((fonts_dir / f).resolve())
    exe, env = soffice()
    r = subprocess.run([exe, "--headless", "--norestore", f"-env:UserInstallation=file://{profile}",
                        "--convert-to", "pdf", "--outdir", str(out_dir), str(docx)],
                       capture_output=True, text=True, env=env, timeout=900)
    pdf = out_dir / (docx.stem + ".pdf")
    if r.returncode != 0 or not pdf.is_file():
        raise RuntimeError(f"LibreOffice failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return pdf


def pdf_pages(pdf: Path) -> list[str]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    try:
        return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    finally:
        doc.close()


def pdf_fonts(pdf: Path) -> set[str]:
    return {m.decode() for m in re.findall(rb"/BaseFont\s*/(?:[A-Z]{6}\+)?([A-Za-z0-9\-,]+)", pdf.read_bytes())}
