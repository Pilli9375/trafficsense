"""Build and check the capstone final-review deck (scripts/build_slides.py, scripts/check_slides.py).

The university's template (16 slides, mandatory) is copied and filled: its layouts, fonts, colours,
logo and page-number ornament stay; only the text boxes of each slide are filled and visuals added.
Slide text comes from `slides_content.py`; each number there is tagged like the report's and is
checked against outputs/ with the report's own checker (`numbers.py`), so a deck number cannot
differ from the report's. Tables are cut from the report's generated tables, the bibliography is
read from report.docx, figures and screenshots are the report's own.
"""
from __future__ import annotations

import copy
import hashlib
import re
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from trafficsense.config import load_config, repo_root, resolve_path
from trafficsense.report import numbers, slides_content as C
from trafficsense.report.facts import facts

ROOT = repo_root()
SW, SH = 9144000, 5143500
LM, CW = 250000, 8644000                 # content left edge and width
CT, CB = 1010000, 4680000                # content top and bottom (below the heading, above the page number)
CT_SPLIT = 1330000                       # content top on the three outcome slides (two-line heading)
MIN_PT = 16                              # smallest body text (the bibliography and page numbers excepted)
FONT, SERIF = "Gill Sans MT", "Times New Roman"
BROWN, TEAL, HEADFILL, BAND = "572314", "3891A7", "572314", "F7EFEA"
LOGO_BOX = (7500000, 100000, 9100000, 530000)      # x0, y0, x1, y1 of the university logo
NUM_BOX = (8500000, 4700000, SW, SH)               # the round page-number ornament
OUTLINE_GROUPS = {   # outline heading -> template slide numbers it covers
    "Introduction": ["3", "4", "5"], "Background & Related Work/ Literature Review": ["6", "7"],
    "Proposed Solution": ["8", "9", "10"], "Implementation and Results ": ["11", "13a", "13b", "13c"],
    "Summary ( Findings, Limitations, Future Directions )": ["14"], "Bibliography": ["15"]}
ORDER = [str(i) for i in range(1, 13)] + ["13a", "13b", "13c", "14", "15", "16"]
PLACEHOLDERS = ["[Title of the Project]", "Name of the Student(s)", "Prof. /", "Prof. /Dr", "Lorem", "Click to add"]


# --- checked text ---------------------------------------------------------------------------

class SourceError(Exception):
    pass


def _tools():
    return facts(), numbers.DocTables(ROOT)


def prep(text: str, where: str, lint: bool = True) -> str:
    """Check the tagged numbers of `text` against outputs/ (and that none is untagged); return the
    text as shown (tags and markup characters removed)."""
    fs, dt = _tools()
    probs, _ = numbers.check_tags(text, fs, dt)
    if lint:
        probs += numbers.lint(text)
    if probs:
        raise SourceError(f"{where}: " + "; ".join(str(p) for p in probs))
    return re.sub(r"<!--.*?-->", "", text)


def runs_of(text: str) -> list[tuple[str, bool]]:
    """Split `**bold**` markup into (text, bold) runs; backticks are dropped."""
    out, bold = [], False
    for part in re.split(r"(\*\*)", text.replace("`", "")):
        if part == "**":
            bold = not bold
        elif part:
            out.append((part, bold))
    return out


def report_sources() -> str:
    """All text a number on a slide may come from: the report, its extended material, the README
    and the checked docs, with the invisible tags removed."""
    paths = (sorted((ROOT / "docs/report").glob("[0-9][0-9]_*.md")) + sorted((ROOT / "docs/report/extended").glob("*.md"))
             + sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"])
    text = "\n".join(p.read_text() for p in paths if p.is_file())
    return re.sub(r"<!--.*?-->", "", text)


def numbers_in(text: str) -> list[str]:
    return [m.group(0).lstrip("+-−").rstrip("%").replace(",", "") for m in re.finditer(numbers.NUM, text)]


# --- tables from the report -----------------------------------------------------------------

def table_cells(t: C.Table) -> tuple[list[str], list[list[str]]]:
    header, rows = numbers.DocTables(ROOT).table(t.doc, t.block)
    cols = []
    for sel in t.cols:
        hit = [i for i, h in enumerate(header) if sel in h]
        if len(hit) != 1:
            raise SourceError(f"{t.doc}:{t.block}: column {sel!r} matches {len(hit)} columns")
        cols.append(hit[0])
    out = []
    for sel in t.rows:
        hit = [r for r in rows if sel in " | ".join(r)]
        if len(hit) != 1:
            raise SourceError(f"{t.doc}:{t.block}: row {sel!r} matches {len(hit)} rows")
        out.append([hit[0][c].replace("`", "") for c in cols])
    if t.labels:
        for r, lab in zip(out, t.labels):
            r[0] = lab
    return (t.headers or [header[c] for c in cols]), out


def references() -> dict[int, str]:
    """The report's reference list (numbers and text) from report.docx."""
    docx = ROOT / "docs/report/report.docx"
    with zipfile.ZipFile(docx) as z:
        xml = etree.fromstring(z.read("word/document.xml"))
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paras = ["".join(t.text or "" for t in p.iter(W + "t")) for p in xml.iter(W + "p")]
    start = max(i for i, t in enumerate(paras) if t.strip() == "References")
    refs = {}
    for t in paras[start + 1:]:
        m = re.match(r"\[(\d+)\]\s+(.*)", t.strip())
        if m:
            refs[int(m.group(1))] = m.group(2)
        elif t.strip() == "Biodata":
            break
    return refs


# --- pptx helpers ---------------------------------------------------------------------------

def _rpr(parent, size, bold=False, color="000000", font=FONT, italic=False):
    rpr = etree.SubElement(parent, qn("a:rPr"), lang="en-US", sz=str(int(size * 100)), b="1" if bold else "0", dirty="0")
    if italic:
        rpr.set("i", "1")
    fill = etree.SubElement(rpr, qn("a:solidFill"))
    etree.SubElement(fill, qn("a:srgbClr"), val=color)
    etree.SubElement(rpr, qn("a:latin"), typeface=font)
    etree.SubElement(rpr, qn("a:cs"), typeface=font)
    return rpr


def add_par(txBody, text, size, bullet=True, bold_all=False, color="000000", before=6, font=FONT, align=None, lvl_marL=285750):
    p = etree.SubElement(txBody, qn("a:p"))
    ppr = etree.SubElement(p, qn("a:pPr"))
    if align:
        ppr.set("algn", align)
    if bullet:
        ppr.set("marL", str(lvl_marL)); ppr.set("indent", str(-lvl_marL))
    ppr.append(etree.fromstring(f'<a:lnSpc xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:spcPct val="100000"/></a:lnSpc>'))
    ppr.append(etree.fromstring(f'<a:spcBef xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:spcPts val="{before * 100}"/></a:spcBef>'))
    if bullet:
        bc = etree.SubElement(ppr, qn("a:buClr")); etree.SubElement(bc, qn("a:srgbClr"), val=TEAL)
        etree.SubElement(ppr, qn("a:buFont"), typeface="Wingdings", charset="2")
        etree.SubElement(ppr, qn("a:buChar"), char="")
    else:
        etree.SubElement(ppr, qn("a:buNone"))
    for t, b in runs_of(text):
        r = etree.SubElement(p, qn("a:r"))
        _rpr(r, size, bold_all or b, color, font)
        etree.SubElement(r, qn("a:t")).text = t
    return p


def add_textbox(slide, x, y, w, h, name, anchor="t"):
    tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    body = tf._txBody
    bp = body.find(qn("a:bodyPr"))
    for k, v in dict(lIns="45720", tIns="0", rIns="45720", bIns="0", anchor=anchor).items():
        bp.set(k, v)
    for ch in list(bp):
        bp.remove(ch)
    etree.SubElement(bp, qn("a:noAutofit"))
    for p in body.findall(qn("a:p")):
        body.remove(p)
    return tb, body


def add_bullets(slide, bullets, x, y, w, h, size, name="Bullets", before=8):
    tb, body = add_textbox(slide, x, y, w, h, name)
    for b in bullets:
        add_par(body, prep(b, f"slide bullet {b[:30]!r}"), size, before=before)
    return tb


def add_label(slide, text, x, y, w, size=MIN_PT + 2, color=BROWN, h=330000):
    if not text:
        return None
    tb, body = add_textbox(slide, x, y, w, h, "Label")
    add_par(body, prep(text, f"label {text[:30]!r}"), size, bullet=False, bold_all=True, color=color, before=0)
    return tb


def fit_picture(slide, path: Path, x, y, w, h, alt, name="Figure", align="center"):
    from PIL import Image
    iw, ih = Image.open(path).size
    s = min(w / iw, h / ih)
    pw, ph = int(iw * s), int(ih * s)
    px = x + (w - pw) // 2 if align == "center" else x
    pic = slide.shapes.add_picture(str(path), Emu(px), Emu(y), Emu(pw), Emu(ph))
    pic.name = name
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def add_table(slide, header, rows, x, y, w, col_w, size, row_h=None, name="Table", first_bold=False, from_report=False):
    n, m = len(rows) + 1, len(header)
    rh = row_h or int(size * 12700 * 1.2 + 110000)
    gf = slide.shapes.add_table(n, m, Emu(x), Emu(y), Emu(w), Emu(rh * n))
    gf.name = name
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for k in ("firstRow", "bandRow"):
        tblPr.set(k, "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"
    tot = sum(col_w)
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Emu(int(w * cw / tot))
    for r in range(n):
        tbl.rows[r].height = Emu(rh)
    for r in range(n):
        for c in range(m):
            raw = header[c] if r == 0 else rows[r - 1][c]
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Emu(70000)
            cell.margin_top = cell.margin_bottom = Emu(20000)
            cell.vertical_anchor = __import__("pptx.enum.text", fromlist=["MSO_ANCHOR"]).MSO_ANCHOR.MIDDLE
            body = cell.text_frame._txBody
            for p in body.findall(qn("a:p")):
                body.remove(p)
            head = r == 0
            add_par(body, prep(raw, f"table cell {raw[:30]!r}", lint=not from_report), size, bullet=False,
                    bold_all=head or (first_bold and c == 0), color="FFFFFF" if head else "000000", before=0)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(HEADFILL if head else (BAND if r % 2 == 0 else "FFFFFF"))
    return gf


def set_notes(slide, text, where):
    slide.notes_slide.notes_text_frame.text = prep(text, f"notes {where}")


def shape_by_name(slide, name):
    return next(s for s in slide.shapes if s.name == name)


def clear_body_after_heading(body_shape):
    """Keep the template's first paragraph (the topic line), drop the empty ones after it."""
    body = body_shape.text_frame._txBody
    ps = body.findall(qn("a:p"))
    for p in ps[1:]:
        body.remove(p)


def tidy_title(slide, y=15000, h=520000):
    t = shape_by_name(slide, "TextShape 1")
    t.left, t.top, t.width, t.height = Emu(107504), Emu(y), Emu(7300000), Emu(h)
    t.text_frame._txBody.find(qn("a:bodyPr")).set("anchor", "ctr")
    for br in list(t.text_frame._txBody.iter(qn("a:br"))):
        br.getparent().remove(br)
    bp = t.text_frame._txBody.find(qn("a:bodyPr"))      # the template scales some titles (51 pt x 47.5 %): one size for all
    for ch in list(bp):
        bp.remove(ch)
    etree.SubElement(bp, qn("a:noAutofit"))
    for r in list(t.text_frame._txBody.iter(qn("a:rPr"))) + list(t.text_frame._txBody.iter(qn("a:endParaRPr"))):
        r.set("sz", "2400")
    for r in list(t.text_frame._txBody.iter(qn("a:r"))):     # runs that were only line-break padding
        tx = r.find(qn("a:t"))
        if tx is not None and not (tx.text or "").strip():
            r.getparent().remove(r)
    return t


def set_slide_number(slide, n):
    for s in slide.shapes:
        for f in s._element.iter(qn("a:fld")):
            if f.get("type") == "slidenum":
                f.find(qn("a:t")).text = str(n)


def clone_slide(prs, src):
    new = prs.slides.add_slide(src.slide_layout)
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)
    for shp in src.shapes:
        if shp.shape_type == 13:
            p = new.shapes.add_picture(BytesIO(shp.image.blob), shp.left, shp.top, shp.width, shp.height)
            p.name = shp.name
            p._element.nvPicPr.cNvPr.set("descr", shp._element.nvPicPr.cNvPr.get("descr") or "")
        else:
            new.shapes._spTree.append(copy.deepcopy(shp._element))
    return new


def mark_template_pictures(slide, alt):
    for s in slide.shapes:
        if s.shape_type == 13 and not s._element.nvPicPr.cNvPr.get("descr"):
            s._element.nvPicPr.cNvPr.set("descr", alt)


# --- slide fillers --------------------------------------------------------------------------

def fig_path(rel: str) -> Path:
    p = ROOT / rel
    if not p.is_file():
        raise FileNotFoundError(f"{rel} is missing")
    return p


def fill_title(slide, spec):
    box = shape_by_name(slide, "TextShape 1")
    ps = box.text_frame._txBody.findall(qn("a:p"))
    for br in ps[0].iter(qn("a:br")):
        br.getparent().remove(br)
    for r in ps[0].findall(qn("a:r"))[1:]:
        ps[0].remove(r)
    box.height = Emu(1350000)
    p2 = ps[1]
    runs = p2.findall(qn("a:r"))
    runs[0].find(qn("a:t")).text = C.TITLE
    runs[0].find(qn("a:rPr")).set("sz", "2400")
    for r in p2.findall(qn("a:endParaRPr")):
        r.set("sz", "2400")
    sup = shape_by_name(slide, "TextShape 2")
    sup.top = Emu(1600000)
    rs = sup.text_frame._txBody.findall(qn("a:p"))[0].findall(qn("a:r"))
    rs[2].find(qn("a:t")).text = C.SUPERVISOR
    for r in rs[3:]:
        r.getparent().remove(r)
    for r in rs:
        if r.find(qn("a:t")) is not None and r.get("err"):
            pass
    sup_bp = sup.text_frame._txBody.find(qn("a:bodyPr"))
    for ch in list(sup_bp):
        sup_bp.remove(ch)
    etree.SubElement(sup_bp, qn("a:noAutofit"))
    stu = shape_by_name(slide, "CustomShape 3")
    stu.top, stu.width = Emu(2150000), Emu(5800000)
    for t in stu._element.iter(qn("a:t")):
        if t.text == "Name of the Student(s) with Regd. No.:":
            t.text = "Students with Regd. No.:"
    body = stu.text_frame._txBody
    ps = body.findall(qn("a:p"))
    # "SDP Id:" + value
    runs = ps[0].findall(qn("a:r"))
    last = runs[-1]
    val = copy.deepcopy(last)
    val.find(qn("a:t")).text = " " + C.SDP_ID
    val.find(qn("a:rPr")).find(qn("a:solidFill")).find(qn("a:srgbClr")).set("val", "000000")
    last.addnext(val)
    for p in ps[2:]:
        body.remove(p)
    for name, reg in C.STUDENTS:
        add_par(body, f"{name} – {reg}", 16, bullet=False, bold_all=True, before=3)
    for p in body.findall(qn("a:p")):          # the template's own text is 14 pt: raise it to the body minimum
        for r in p.iter(qn("a:rPr")):
            if r.get("sz") and int(r.get("sz")) < 1600:
                r.set("sz", "1600")
    for ep in body.iter(qn("a:endParaRPr")):
        ep.set("sz", "1600")
    stu.text_frame._txBody.find(qn("a:bodyPr")).set("wrap", "square")
    scope = shape_by_name(slide, "CustomShape 4")
    scope.width = Emu(SW - scope.left - 120000)          # the template's box ran past the slide edge
    for r in scope._element.iter(qn("a:rPr")):
        if not r.get("sz"):
            r.set("sz", "1800")


def fill_outline(slide, spec, numbering):
    """The template's list, unchanged, with the slide numbers added to each part; split over two
    boxes (parts 1-2 and 3-6) so that no part is cut by a column break."""
    tidy_title(slide)
    body = shape_by_name(slide, "TextShape 2")
    right = copy.deepcopy(body._element)
    body._element.addnext(right)
    for box, keep in ((body._element, slice(0, 7)), (right, slice(7, None))):
        tx = box.find(qn("p:txBody"))
        ps = tx.findall(qn("a:p"))
        for p in ps[keep][::-1] if False else [q for i, q in enumerate(ps) if i not in range(*keep.indices(len(ps)))]:
            tx.remove(p)
        bp = tx.find(qn("a:bodyPr"))
        for ch in list(bp):
            bp.remove(ch)
        etree.SubElement(bp, qn("a:noAutofit"))
    right.find(qn("p:nvSpPr")).find(qn("p:cNvPr")).set("id", "99")
    right.find(qn("p:nvSpPr")).find(qn("p:cNvPr")).set("name", "Outline right")
    for el, x, w in ((body._element, 250000, 4200000), (right, 4650000, 4250000)):
        off = el.find(qn("p:spPr")).find(qn("a:xfrm"))
        off.find(qn("a:off")).set("x", str(x)); off.find(qn("a:off")).set("y", "700000")
        off.find(qn("a:ext")).set("cx", str(w)); off.find(qn("a:ext")).set("cy", "3950000")
        for p in el.find(qn("p:txBody")).findall(qn("a:p")):
            txt = "".join(t.text or "" for t in p.iter(qn("a:t")))
            sub = p.find(qn("a:pPr")).get("marL") == "822960"
            if txt in numbering and not sub:
                r = p.findall(qn("a:r"))
                r[-1].find(qn("a:t")).text = r[-1].find(qn("a:t")).text.rstrip() + f"  (slides {numbering[txt]})"
            for r in list(p.iter(qn("a:rPr"))) + list(p.iter(qn("a:endParaRPr"))):
                r.set("sz", "1600" if sub else "1800")
                if not sub and r.tag == qn("a:rPr"):
                    r.set("b", "1")
            sb = p.find(qn("a:pPr")).find(qn("a:spcBef"))
            if sb is not None:
                for ch in list(sb):
                    sb.remove(ch)
                etree.SubElement(sb, qn("a:spcPts"), val="300" if sub else "800")


def fill_content(slide, key, spec: C.Slide):
    split = key in ("13a", "13b", "13c")
    tidy_title(slide)
    head = shape_by_name(slide, "TextShape 2")
    clear_body_after_heading(head)
    head.left, head.top, head.width, head.height = Emu(179512), Emu(560000), Emu(8700000), Emu(420000 if not split else 740000)
    bp = head.text_frame._txBody.find(qn("a:bodyPr"))
    for ch in list(bp):
        bp.remove(ch)
    etree.SubElement(bp, qn("a:noAutofit"))
    for k, v in dict(lIns="90000", tIns="0", rIns="90000", bIns="0", anchor="t").items():
        bp.set(k, v)
    hp = head.text_frame._txBody.find(qn("a:p"))
    for r in hp.iter(qn("a:rPr")):
        r.set("sz", "2000")
    for r in hp.iter(qn("a:endParaRPr")):
        r.set("sz", "2000")
    if spec.heading_suffix:
        add_par(head.text_frame._txBody, spec.heading_suffix.strip(), 18, bullet=False, bold_all=True, color=TEAL, before=2)
    top = CT_SPLIT if split else CT
    L = spec.layout
    H = CB - top
    pic = lambda rel, alt, x, y, w, h, **kw: fit_picture(slide, fig_path(rel), x, y, w, h, alt, **kw)

    def tab(t, x, y, w, size, col_w, **kw):
        rep = isinstance(t, C.Table)
        header, rows = table_cells(t) if rep else (t.header, t.rows)
        return add_table(slide, header, rows, x, y, w, col_w, size, from_report=rep, **kw)

    if L == "text":
        add_bullets(slide, spec.bullets, LM, top + 60000, CW, H, 20, before=12)
    elif L == "text_image":
        add_bullets(slide, spec.bullets, LM, top + 40000, 4850000, H, 18, before=10)
        pic(spec.image, spec.alt, 5200000, top - 20000, 3700000, 3690000)
    elif L == "text_table":
        add_bullets(slide, spec.bullets, LM, top + 40000, 4350000, H, 16, before=9)
        x = 4750000
        add_label(slide, spec.table_labels[0], x, top, 4150000, size=16)
        tab(spec.tables[0], x, top + 400000, 4150000, 16, [3, 2] if len(spec.tables[0].header if isinstance(spec.tables[0], C.Literal) else spec.tables[0].cols) == 2 else [2, 1])
    elif L == "columns":
        for (h, items), x, w in zip(spec.columns, (LM, 5450000), (5000000, 3440000)):
            add_label(slide, h, x, top, w, size=20, color=TEAL)
            add_bullets(slide, items, x, top + 420000, w, H - 420000, 18, before=10)
    elif L == "table":
        tab(spec.tables[0], LM, top + 60000, CW, 18, [5, 6], row_h=520000)
    elif L == "image":
        pic(spec.image, spec.alt, 95000, top - 20000, SW - 190000, H + 20000)
    elif L == "text_image_bottom":
        add_bullets(slide, spec.bullets, LM, top, CW, 1820000, 16, before=5)
        pic(spec.image, spec.alt, LM, top + 1900000, CW, H - 1900000)
    elif L == "two_tables":
        w = 4250000
        for i, (t, x) in enumerate(zip(spec.tables, (LM, LM + w + 150000))):
            tab(t, x, top + 150000, w, 16, [5, 6], row_h=470000)
    elif L == "table_bullets":
        tab(spec.tables[0], LM, top + 10000, CW, 16, [2.6, 2.2, 2.2, 2.2], row_h=330000)
        add_bullets(slide, spec.bullets, LM, top + 2150000, CW, 1200000, 16, before=8)
    elif L == "two_tables_stacked":
        add_label(slide, spec.table_labels[0], LM, top - 30000, CW, size=16, h=280000)
        tab(spec.tables[0], LM, top + 250000, CW, 16, [3.4, 2, 2], row_h=300000)
        add_label(slide, spec.table_labels[1], LM, top + 1830000, CW, size=16, h=280000)
        tab(spec.tables[1], LM, top + 2110000, CW, 16, [2, 3, 3], row_h=300000)
    elif L == "text_two_images":
        add_bullets(slide, spec.bullets, LM, top - 20000, CW, 830000, 16, before=2)
        ih = 2200000
        iw = int(ih * 16 / 9)
        gap = 330000
        x0 = LM + (CW - 2 * iw - gap) // 2
        for (rel, alt, cap), x in zip(spec.images, (x0, x0 + iw + gap)):
            pic(rel, alt, x, top + 830000, iw, ih, align="left")
            add_label(slide, cap, x, top + 830000 + ih + 10000, iw, size=16, color=TEAL, h=290000)
    elif L == "summary":
        y = top - 40000
        for i, (h, items) in enumerate(spec.columns):
            if i:                                  # the first group's heading is the template's own line
                add_label(slide, h, LM, y, CW, size=20, color=BROWN, h=320000)
                y += 330000
            hh = sum(par_height(prep(it, "summary"), 16, CW - 91440 - 285750) + 4 * 12700 for it in items) + 60000
            add_bullets(slide, items, LM, y, CW, hh, 16, before=4)
            y += hh + 90000
    else:
        raise ValueError(f"unknown layout {L}")


def fill_bibliography(slide, spec):
    t = shape_by_name(slide, "Title 1")
    t.left, t.top, t.width, t.height = Emu(107504), Emu(15000), Emu(7300000), Emu(520000)
    sub = shape_by_name(slide, "Subtitle 2")
    sub.left, sub.top, sub.width, sub.height = Emu(250000), Emu(680000), Emu(8650000), Emu(4000000)
    body = sub.text_frame._txBody
    bp = body.find(qn("a:bodyPr"))
    for ch in list(bp):
        bp.remove(ch)
    etree.SubElement(bp, qn("a:noAutofit"))
    for k, v in dict(lIns="45720", tIns="0", rIns="45720", bIns="0", anchor="t").items():
        bp.set(k, v)
    for p in body.findall(qn("a:p")):
        body.remove(p)
    refs = references()
    for n in C.BIBLIOGRAPHY:
        text = refs[n]
        p = add_par(body, f"[{n}]  {text}", 12, bullet=False, before=5, font=FONT, align="l")
        ppr = p.find(qn("a:pPr"))
        ppr.set("marL", "380000"); ppr.set("indent", "-380000")
        for r in p.iter(qn("a:rPr")):
            r.set("lang", "en-IN")


def fill_closing(slide, spec):
    tb, b2 = add_textbox(slide, 800000, 4130000, 7500000, 420000, "GitHub link")
    p = add_par(b2, f"GitHub: {C.GITHUB}", 20, bullet=False, bold_all=True, color="000000", before=0, align="ctr")
    r = p.findall(qn("a:r"))[0]
    run = tb.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = C.GITHUB


# --- build ----------------------------------------------------------------------------------

def paths():
    cfg = load_config("configs/default.yaml")
    return resolve_path(cfg, "slides_template"), resolve_path(cfg, "slides_work"), resolve_path(cfg, "slides_out")


def build(out: Path | None = None, work: Path | None = None) -> Path:
    from trafficsense.report import slides_figures
    template, work0, out0 = paths()
    work, out = work or work0, out or out0
    if not template.is_file():
        raise FileNotFoundError(f"the university template is missing: {template}")
    work.mkdir(parents=True, exist_ok=True)
    copy_path = work / "template_copy.pptx"
    shutil.copyfile(template, copy_path)                  # the template itself is never edited
    slides_figures.draw(ROOT / slides_figures.OUT)
    slides_figures.draw_loop(ROOT / slides_figures.OUT_LOOP)
    prs = Presentation(str(copy_path))
    src = {str(i + 1): s for i, s in enumerate(prs.slides)}
    if len(src) != 16:
        raise SourceError(f"the template has {len(src)} slides, expected 16")
    for k in ("13b", "13c"):
        src[k] = clone_slide(prs, src["13"])
    src["13a"] = src.pop("13")
    deck = {k: src[k] for k in ORDER}
    lst = prs.slides._sldIdLst
    el_of = {int(e.get("id")): e for e in lst}
    elements = [el_of[deck[k].slide_id] for k in ORDER]
    for e in list(lst):
        lst.remove(e)
    for e in elements:
        lst.append(e)
    numbering = {}
    for head, keys in OUTLINE_GROUPS.items():
        nums = [ORDER.index(k) + 1 for k in keys]
        numbering[head] = f"{nums[0]}" if len(nums) == 1 else f"{nums[0]}–{nums[-1]}"
    for k in ORDER:
        s, spec = deck[k], C.SLIDES[k]
        if k == "1":
            fill_title(s, spec)
        elif k == "2":
            fill_outline(s, spec, numbering)
        elif k == "15":
            fill_bibliography(s, spec)
        elif k == "16":
            fill_closing(s, spec)
        else:
            fill_content(s, k, spec)
        set_notes(s, spec.notes, k)
        set_slide_number(s, ORDER.index(k) + 1)
        mark_template_pictures(s, "University logo" if k != "16" else "Thank you (template graphic)")
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


# --- render ---------------------------------------------------------------------------------

LINK_FONTS = ["GIL_____.TTF", "GILB____.TTF", "GILI____.TTF", "GILBI___.TTF", "times.ttf", "timesbd.ttf", "timesi.ttf",
              "timesbi.ttf", "arial.ttf", "arialbd.ttf", "ariali.ttf", "wingding.ttf", "symbol.ttf"]


def render_pdf(pptx: Path, out_dir: Path) -> Path:
    """LibreOffice headless: pptx -> PDF in `out_dir`, with the template's fonts (Gill Sans MT, Times
    New Roman, Wingdings) linked from the Windows font folder into a private profile."""
    from trafficsense.report import thesis
    cfg = load_config("configs/default.yaml")
    fonts = resolve_path(cfg, "report_fonts")
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = out_dir / "lo-profile"
    (profile / "user/fonts").mkdir(parents=True, exist_ok=True)
    for f in LINK_FONTS:
        if (fonts / f).is_file() and not (profile / "user/fonts" / f).exists():
            (profile / "user/fonts" / f).symlink_to((fonts / f).resolve())
    exe, env = thesis.soffice()
    r = subprocess.run([exe, "--headless", "--norestore", f"-env:UserInstallation=file://{profile}", "--convert-to", "pdf",
                        "--outdir", str(out_dir), str(pptx)], capture_output=True, text=True, env=env, timeout=600)
    pdf = out_dir / (pptx.stem + ".pdf")
    if r.returncode != 0 or not pdf.is_file():
        raise RuntimeError(f"LibreOffice failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return pdf


def render_pngs(pdf: Path, out_dir: Path, scale=1.6) -> list[Path]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    outs = []
    for i in range(len(doc)):
        p = out_dir / f"slide_{i + 1:02d}.png"
        doc[i].render(scale=scale).to_pil().save(p)
        outs.append(p)
    return outs


# --- checks ---------------------------------------------------------------------------------

def _text_of(shape) -> str:
    if shape.has_text_frame:
        return shape.text_frame.text
    return ""


def slide_texts(slide) -> list[str]:
    out = []
    for s in slide.shapes:
        if s.has_text_frame:
            out.append(s.text_frame.text)
        elif s.has_table:
            for row in s.table.rows:
                for c in row.cells:
                    out.append(c.text_frame.text)
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\x0b", " ")).strip()


def slide_title(slide) -> str:
    for s in slide.shapes:
        if s.name in ("TextShape 1", "Title 1") and s.has_text_frame:
            return _norm(s.text_frame.text)
    return ""


def _font_file(fonts: Path, bold: bool, face: str) -> Path | None:
    names = {("Gill Sans MT", False): "GIL_____.TTF", ("Gill Sans MT", True): "GILB____.TTF",
             ("Times New Roman", False): "times.ttf", ("Times New Roman", True): "timesbd.ttf"}
    f = fonts / names.get((face, bold), "GIL_____.TTF")
    return f if f.is_file() else None


def text_height(par_runs, size_pt, width_emu, fonts: Path, face=FONT) -> float | None:
    """Estimated height in EMU of the wrapped paragraph (words measured with the real font)."""
    from PIL import ImageFont
    width_pt = width_emu / 12700
    words = []
    for text, bold in par_runs:
        f = _font_file(fonts, bold, face)
        if f is None:
            return None
        font = ImageFont.truetype(str(f), 100)
        for w in re.findall(r"\S+\s*", text):
            words.append(font.getlength(w) * size_pt / 100)
    lines, cur = 1, 0.0
    for w in words:
        if cur > 0 and cur + w > width_pt:
            lines += 1
            cur = w
        else:
            cur += w
    return lines * size_pt * 1.2 * 12700


def par_height(text: str, size: float, width: int) -> int:
    """Height in EMU of one wrapped paragraph in the template's font (an estimate that is exact
    enough to stack text boxes; the check recomputes it for every box)."""
    cfg = load_config("configs/default.yaml")
    h = text_height(runs_of(text), size, width, resolve_path(cfg, "report_fonts"))
    if h is None:
        raise FileNotFoundError("Gill Sans MT not found in paths.report_fonts: cannot size the text")
    return int(h)


# --- the checker ----------------------------------------------------------------------------

TEMPLATE_TITLES = ["Capstone Final Review", "Presentation Outline", "Introduction", "Introduction", "Introduction",
                   "Background & Related Work", "Background & Related Work", "Proposed Solution", "Proposed Solution",
                   "Proposed Solution", "Implementation and Results", "Implementation and Results",
                   "Implementation and Results", "Summary", "Bibliography", ""]
# the deck's slide order: template slides 1-12, 13 once to three times, then 14-16
PHONE = re.compile(r"(?<![\w.])\+?\d[\d ()\-]{8,}\d(?![\w])")
ADDRESS = re.compile(r"\b(?:Street|Plot No|Door No|H\.? ?No|Pincode|PIN code)\b|\b\d{6}\b|@", re.I)
OUTLINE_NUM = re.compile(r"\(slides? [\d–]+\)")


def _par_runs(p):
    return [(r.text, bool(r.font.bold)) for r in p.runs]


def _est_text_height(shape, fonts: Path):
    """Estimated height (EMU) of a text box's paragraphs, or None if the font is not available."""
    tf = shape.text_frame
    bp = tf._txBody.find(qn("a:bodyPr"))
    li, ri = int(bp.get("lIns", 91440)), int(bp.get("rIns", 91440))
    ti, bi = int(bp.get("tIns", 45720)), int(bp.get("bIns", 45720))
    total = ti + bi
    for p in tf.paragraphs:
        ppr = p._p.find(qn("a:pPr"))
        marL = int(ppr.get("marL", 0)) if ppr is not None else 0
        sizes = [r.font.size.pt for r in p.runs if r.font.size]
        size = max(sizes) if sizes else 18.0
        before = 0
        if ppr is not None and ppr.find(qn("a:spcBef")) is not None:
            pts = ppr.find(qn("a:spcBef")).find(qn("a:spcPts"))
            before = int(pts.get("val")) / 100 * 12700 if pts is not None else 0
        face = (p.runs[0].font.name if p.runs and p.runs[0].font.name else FONT)
        h = text_height(_par_runs(p) or [(" ", False)], size, shape.width - li - ri - marL, fonts, face)
        if h is None:
            return None
        total += h + before
    return total


def _est_table_height(shape, fonts: Path):
    tbl = shape.table
    total = 0
    for r, row in enumerate(tbl.rows):
        need = row.height
        for c, cell in enumerate(row.cells):
            w = tbl.columns[c].width - cell.margin_left - cell.margin_right
            h = 0
            for p in cell.text_frame.paragraphs:
                sizes = [x.font.size.pt for x in p.runs if x.font.size]
                th = text_height([(x.text, bool(x.font.bold)) for x in p.runs] or [(" ", False)], max(sizes) if sizes else 18, w, fonts)
                if th is None:
                    return None
                h += th
            need = max(need, h + cell.margin_top + cell.margin_bottom)
        total += need
    return total


def _is_template_part(shape) -> bool:
    if shape.shape_type == 13 and shape.name.startswith(("Picture",)):
        return True
    return any(f.get("type") == "slidenum" for f in shape._element.iter(qn("a:fld"))) or shape.name == "CustomShape 6"


def check(pptx: Path | None = None) -> list[str]:
    """Return every problem found in the deck (an empty list = it passes)."""
    _, _, out = paths()
    pptx = pptx or out
    if not pptx.is_file():
        return [f"{pptx} does not exist (run scripts/build_slides.py)"]
    prs = Presentation(str(pptx))
    probs: list[str] = []
    sl = list(prs.slides)
    if len(sl) > 18:
        probs.append(f"{len(sl)} slides (at most 18)")
    if (prs.slide_width, prs.slide_height) != (SW, SH):
        probs.append("slide size is not the template's 16:9")
    # titles and order
    titles = [slide_title(s) for s in sl]
    exp = TEMPLATE_TITLES[:12] + [TEMPLATE_TITLES[12]] * (len(sl) - 15) + TEMPLATE_TITLES[13:]
    for i, (t, e) in enumerate(zip(titles, exp), 1):
        ok = t.startswith(e) if i == 1 else t == e
        if not ok:
            probs.append(f"slide {i}: title {t!r}, template has {e!r}")
    if len(titles) != len(exp):
        probs.append("slide count does not follow the template order")
    sources = set(numbers_in(report_sources()))
    ids = list(numbers.THESIS_IDENTIFIERS)
    fonts = resolve_path(load_config("configs/default.yaml"), "report_fonts")
    n_all = len(sl)
    allowed_pics = {hashlib.sha256(p.read_bytes()).hexdigest() for d in ("docs/report/figures", "docs/ppt/figures")
                    for p in (ROOT / d).glob("*.png")}
    for i, s in enumerate(sl, 1):
        where = f"slide {i}"
        texts = slide_texts(s)
        blob = "\n".join(texts)
        for ph in PLACEHOLDERS:
            if ph in blob:
                probs.append(f"{where}: template placeholder text {ph!r} left")
        flat = blob
        for ident in ids:
            flat = flat.replace(ident, "")
        if PHONE.search(flat):
            probs.append(f"{where}: looks like a phone number: {PHONE.search(flat).group(0)!r}")
        if ADDRESS.search(flat):
            probs.append(f"{where}: looks like an address or e-mail: {ADDRESS.search(flat).group(0)!r}")
        # numbers: every one must be in the report's sources (the bibliography is compared to report.docx below)
        if i != n_all - 1:
            body = OUTLINE_NUM.sub("", flat)
            for n in numbers_in(re.sub(r"https?://\S+", "", body)):
                if n not in sources:
                    probs.append(f"{where}: number {n} is not in the report sources")
        # notes
        notes = s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
        if not notes:
            probs.append(f"{where}: no speaker notes")
        else:
            k = len([x for x in re.split(r"(?<=[.!?])\s+", notes) if x])
            if not 3 <= k <= 5:
                probs.append(f"{where}: speaker notes have {k} sentences (3 to 5)")
            for n in numbers_in(notes):
                if n not in sources:
                    probs.append(f"{where}: notes number {n} is not in the report sources")
        # slide number
        for sh in s.shapes:
            for f in sh._element.iter(qn("a:fld")):
                if f.get("type") == "slidenum" and f.find(qn("a:t")).text != str(i):
                    probs.append(f"{where}: page number shows {f.find(qn('a:t')).text}")
        # fonts and bullets
        small = 1100 if i == n_all - 1 else MIN_PT * 100
        for sh in s.shapes:
            if _is_template_part(sh) and sh.shape_type != 1:
                continue
            for r in sh._element.iter(qn("a:rPr")):
                if r.get("sz") and int(r.get("sz")) < small and not any(f.get("type") == "slidenum" for f in sh._element.iter(qn("a:fld"))):
                    probs.append(f"{where}: {sh.name} has {int(r.get('sz')) / 100:g} pt text (minimum {small / 100:g})")
                    break
        nb = sum(1 for sh in s.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs
                 if p._p.find(qn("a:pPr")) is not None and p._p.find(qn("a:pPr")).get("marL") == "285750"
                 and p._p.find(qn("a:pPr")).find(qn("a:buChar")) is not None)
        if i != n_all - 1 and nb > 5:
            probs.append(f"{where}: {nb} bullets (at most 5)")
        # pictures: only the report's figures, the logo and the template's closing graphic
        for sh in s.shapes:
            if sh.shape_type == 13:
                descr = sh._element.nvPicPr.cNvPr.get("descr") or ""
                if not descr:
                    probs.append(f"{where}: picture {sh.name} has no alt text")
                if not (descr.startswith(("University logo", "Thank you (template")) or hashlib.sha256(sh.image.blob).hexdigest() in allowed_pics):
                    probs.append(f"{where}: picture {sh.name} is not a report figure, the logo or the template graphic")
        # geometry: inside the slide, clear of the logo and the page number, nothing overlapping
        boxes = []
        for sh in s.shapes:
            if sh.left is None:
                continue
            x0, y0, x1, y1 = sh.left, sh.top, sh.left + sh.width, sh.top + sh.height
            tpl = _is_template_part(sh)
            if sh.has_text_frame and not tpl and sh.text_frame.text.strip():
                est = _est_text_height(sh, fonts)
                keeps = sh._element.find(qn("p:txBody")).find(qn("a:bodyPr")).find(qn("a:spAutoFit")) is not None
                if est is not None and est > sh.height * 1.03 and not keeps:
                    probs.append(f"{where}: text in {sh.name} is about {est / 12700:.0f} pt tall but its box is {sh.height / 12700:.0f} pt")
                if est is not None:
                    y1 = y0 + max(est, 0 if keeps else 0)
                    y1 = max(y1, y0 + min(sh.height, est))
            if sh.has_table:
                est = _est_table_height(sh, fonts)
                if est is not None:
                    y1 = y0 + est
            if tpl:
                continue
            if x0 < -1000 or y0 < -1000 or x1 > SW + 1000 or y1 > SH + 1000:
                probs.append(f"{where}: {sh.name} extends beyond the slide")
            if i not in (1, n_all) and not (sh.name in ("TextShape 1", "Title 1")):
                lx0, ly0, lx1, ly1 = LOGO_BOX
                if x0 < lx1 and x1 > lx0 and y0 < ly1 and y1 > ly0:
                    probs.append(f"{where}: {sh.name} overlaps the logo")
                nx0, ny0, nx1, ny1 = NUM_BOX
                if x0 < nx1 and x1 > nx0 and y0 < ny1 and y1 > ny0 and sh.shape_type != 13:
                    probs.append(f"{where}: {sh.name} overlaps the page number")
                elif x0 < nx1 and x1 > nx0 and y0 < ny1 and y1 > ny0:
                    probs.append(f"{where}: picture {sh.name} overlaps the page number")
            if sh.name not in ("TextShape 1", "Title 1"):
                boxes.append((sh.name, x0, y0, x1, y1))
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                n1, ax0, ay0, ax1, ay1 = boxes[a]
                n2, bx0, by0, bx1, by1 = boxes[b]
                if ax0 < bx1 - 5000 and ax1 > bx0 + 5000 and ay0 < by1 - 5000 and ay1 > by0 + 5000 and i not in (1, 16, n_all):
                    probs.append(f"{where}: {n1} overlaps {n2}")
    # title slide
    t1 = "\n".join(slide_texts(sl[0]))
    for need in [C.TITLE, C.SUPERVISOR, C.SDP_ID, "SCOPE", "VIT-AP University"] + [f"{n} – {r}" for n, r in C.STUDENTS]:
        if need not in t1:
            probs.append(f"slide 1: {need!r} missing")
    # bibliography = the report's reference text
    refs = references()
    bib = "\n".join(slide_texts(sl[-2]))
    for n in C.BIBLIOGRAPHY:
        if f"[{n}]  {refs[n]}" not in bib:
            probs.append(f"bibliography: [{n}] differs from the report's reference list")
    if not 6 <= sum(1 for ln in bib.splitlines() if re.match(r"\[\d+\]", ln)) <= 8:
        probs.append("bibliography should have 6 to 8 references")
    # closing slide
    last = sl[-1]
    lt = "\n".join(slide_texts(last))
    if not any(sh.shape_type == 13 and (sh._element.nvPicPr.cNvPr.get("descr") or "").startswith("Thank you")
               for sh in last.shapes):
        probs.append("last slide: the template's 'Thank you' picture is missing")
    if C.GITHUB not in lt:
        probs.append("last slide: GitHub link missing")
    links = [r.target_ref for r in last.part.rels.values() if r.is_external]
    if C.GITHUB not in links:
        probs.append("last slide: the GitHub link is not a hyperlink")
    return probs


def font_sizes(pptx: Path | None = None) -> list[tuple[int, float | None, str]]:
    """(slide number, smallest explicit text size in pt, where) per slide, page numbers excepted."""
    prs = Presentation(str(pptx or paths()[2]))
    out = []
    for i, s in enumerate(prs.slides, 1):
        low = (None, "")
        for sh in s.shapes:
            if any(f.get("type") == "slidenum" for f in sh._element.iter(qn("a:fld"))):
                continue
            for r in sh._element.iter(qn("a:rPr")):
                if r.get("sz") and (low[0] is None or int(r.get("sz")) < low[0]):
                    low = (int(r.get("sz")), sh.name)
        out.append((i, low[0] / 100 if low[0] else None, low[1]))
    return out
