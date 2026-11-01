"""Check the built report (docs/report/report.docx and its PDF) against the college format in
docs/report/format_spec.md.

    python scripts/check_report_format.py            # exit 1 on any problem
    python scripts/check_report_format.py --docx X.docx --pdf X.pdf

Checks (each failure is printed):
* the spec still states the values checked here (page, margins, body font and spacing);
* page: US Letter and the spec's margins in every section; Word asks to update fields;
* styles: Times New Roman 12 pt body, 1.5 line spacing, justified, 0.5 in first-line indent;
  chapter, section and subsection headings bold 14 / 14 / 13 pt; captions;
* order: title page, certificate, acknowledgements, abstract, contents, list of tables, list of
  figures, Chapters 1-6 with their required sections, references, biodata, NOTE;
* page numbers: lower-case roman front matter (title page unnumbered), Arabic from 1 at Chapter 1;
* captions: "Figure n Title" with SEQ fields numbered 1, 2, ... through the report, below the
  figure; "Table c.n Title" above the table, c = chapter, n from 1 in each chapter;
* contents and both lists: live fields whose entries all carry a page number;
* biodata: four pages, each with the student's name, register number and e-mail, and blank lines
  for mobile number and permanent address; the NOTE about the CD is present;
* no leftover placeholder ({{...}}, TBD, TODO, [fill in], XXXX, build markers) and none of the
  outdated claims of the old contribution sheets, in the Word file or the PDF;
* PDF: every page US Letter, Times New Roman embedded, nothing printed outside the side margins,
  no section heading alone at the foot of a page, and the same page numbers as the contents.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path

from trafficsense.config import repo_root

ROOT = repo_root()
REP = ROOT / "docs/report"

# what format_spec.md says, checked below (the spec must keep saying it)
SPEC_PHRASES = ["US Letter, 21.59 x 27.94 cm", "top 2.54 cm, bottom 1.50 cm, left 3.175 cm, right 3.175 cm",
                "Times New Roman 12 pt, line spacing 1.5", "first-line indent 0.5 in", "`Figure n Title`",
                "`Table c.n Title`", "lower-case roman", "Arabic, restarting at 1 on the first page of Chapter 1"]
PAGE = (12240, 15840)
MARGINS = {"top": 1440, "right": 1800, "bottom": 851, "left": 1800}

CHAPTERS = ["INTRODUCTION", "PROPOSED SYSTEM AND METHODOLOGY", "COST ANALYSIS", "RESULTS AND DISCUSSIONS",
            "CONCLUSION AND FUTURE WORK", "APPENDIX"]
FRONT = ["Certificate", "Acknowledgements", "Abstract", "Table of Contents", "List of Tables", "List of Figures"]
REQUIRED_SECTIONS = ["1.1 Objectives", "1.2 Background and Literature Survey", "1.3 Organization of the Report",
                     "1.4 Team Contributions", "2.1 Proposed System", "2.2 Working Methodology", "2.3 Standards",
                     "2.4 System Details", "2.4.1 Software Details", "2.4.2 Hardware Details",
                     "3.1 List of Components and Their Cost", "5.1 Conclusion", "5.2 Future Work"]
STUDENTS = [("C Bhargav Kumar", "23BCE8195", "bhargav.23bce8195@vitapstudent.ac.in"),
            ("Achalla Akul Lakhan", "23BCE8015", "akul.23bce8015@vitapstudent.ac.in"),
            ("Darsi Amit", "23BCE8288", "amit.23bce8288@vitapstudent.ac.in"),
            ("Mylapalli Abhishek Raj", "23BCE9470", "abhishek.23bce9470@vitapstudent.ac.in")]
PLACEHOLDERS = [r"\{\{", r"\}\}", r"\bTBD\b", r"\bTODO\b", r"(?i)\[fill in\]", r"\bXXXX", r"\bYYYY", r"@@[A-Z]+@@",
                r"(?i)lorem ipsum", r"(?i)\[(?:your|insert|enter) [^\]]*\]", r"(?i)update field to build"]
# claims of the outdated contribution sheets that are not true of this project (never to appear)
BANNED = [r"(?<![\d.])70\.5(?!\d)", r"(?<![\d,])42,?652(?![\d,])", r"(?i)RTX\s*4050", r"(?i)YOLOv8m\b", r"(?i)mock\s+Ollama", r"(?i)random\s+baseline"]
TITLE_LINES = ["TRAFFICSENSE: AN AI-BASED SMART TRAFFIC MANAGEMENT SYSTEM", "A CAPSTONE PROJECT REPORT",
               "Capstone Project ID: 3328F4C8 · Fall Semester 2026-27", "BACHELOR OF TECHNOLOGY",
               "COMPUTER SCIENCE AND ENGINEERING", "DR. MOHD IRFAN", "SCHOOL OF COMPUTER SCIENCE AND ENGINEERING",
               "VIT-AP UNIVERSITY", "AMARAVATI- 522237", "NOVEMBER 2026"]


def text_of(xml: str) -> str:
    """Visible text of some document XML; a tab counts as a space."""
    xml = re.sub(r"<w:tab\s*/>", "<w:t> </w:t>", xml)
    return html.unescape("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml)))


def para_text(xml: str, skip_styles=()) -> str:
    """Text paragraph by paragraph (one per line), leaving out paragraphs in `skip_styles`."""
    return "\n".join(text_of(p) for p in re.findall(r"<w:p\b.*?</w:p>", xml, re.S) if style_of(p) not in skip_styles)


def norm(s: str) -> str:
    return re.sub(r"[\s   ]+", " ", s).strip()


def style_of(p: str) -> str:
    m = re.search(r'<w:pStyle w:val="([^"]+)"', p[:400])
    return m[1] if m else ""


def body_blocks(doc: str) -> list[tuple[str, str]]:
    """Top-level body blocks in order: ('p', xml) or ('tbl', xml)."""
    body = doc[doc.index("<w:body>") + len("<w:body>"):doc.rindex("</w:body>")]
    out, i = [], 0
    while i < len(body):
        if body.startswith("<w:p>", i) or body.startswith("<w:p ", i):
            j = body.index("</w:p>", i) + len("</w:p>")
            out.append(("p", body[i:j]))
        elif body.startswith("<w:tbl>", i):
            depth, j = 0, i
            while True:
                a, b = body.find("<w:tbl>", j), body.find("</w:tbl>", j)
                if a != -1 and a < b:
                    depth, j = depth + 1, a + 7
                else:
                    depth, j = depth - 1, b + 8
                    if depth == 0:
                        break
            out.append(("tbl", body[i:j]))
        else:
            j = body.find("<", i + 1)
            j = len(body) if j == -1 else j
        i = j
    return out


def style_xml(styles: str, sid: str) -> str:
    m = re.search(r'<w:style\b[^>]*w:styleId="%s".*?</w:style>' % re.escape(sid), styles, re.S)
    return m[0] if m else ""


def check_docx(docx: Path, spec: str) -> tuple[list[str], dict]:
    errors = []
    for ph in SPEC_PHRASES:
        if ph not in spec:
            errors.append(f"format_spec.md no longer says {ph!r}: update the spec and this check together")
    with zipfile.ZipFile(docx) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        styles = re.sub(r"\s+/>", "/>", z.read("word/styles.xml").decode("utf-8"))
        settings = z.read("word/settings.xml").decode("utf-8")
        others = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                         if re.match(r"word/(footer|header)\w*\.xml|docProps/\w+\.xml", n))

    # page and sections
    sects = re.findall(r"<w:sectPr\b.*?</w:sectPr>", doc, re.S)
    if len(sects) != 2:
        errors.append(f"expected 2 sections (front matter, body), found {len(sects)}")
    for i, s in enumerate(sects):
        sz = re.search(r'<w:pgSz w:w="(\d+)" w:h="(\d+)"', s)
        if not sz or (int(sz[1]), int(sz[2])) != PAGE:
            errors.append(f"section {i + 1}: page is not US Letter portrait ({sz and sz.groups()})")
        for k, v in MARGINS.items():
            m = re.search(rf'w:{k}="(\d+)"', s[s.find("<w:pgMar"):])
            if not m or int(m[1]) != v:
                errors.append(f"section {i + 1}: {k} margin {m and m[1]} twips, spec says {v}")
    if sects:
        if 'w:fmt="lowerRoman"' not in sects[0] or "<w:titlePg/>" not in sects[0]:
            errors.append("front matter: page numbers must be lower-case roman, none on the title page")
        if not re.search(r'<w:pgNumType w:fmt="decimal" w:start="1"/>', sects[-1]):
            errors.append("body: page numbers must be Arabic, starting at 1")
    if '<w:updateFields w:val="true"/>' not in settings:
        errors.append("settings.xml: Word is not asked to update fields on opening")

    # styles
    def has(sid, *parts):
        x = style_xml(styles, sid)
        missing = [p for p in parts if p not in x]
        if not x or missing:
            errors.append(f"style {sid}: missing {missing or 'the style'}")
    tnr = 'w:ascii="Times New Roman"'
    has("Normal", tnr, '<w:sz w:val="24"/>')
    for sid in ("BodyText", "FirstParagraph"):
        has(sid, 'w:line="360"', '<w:jc w:val="both"/>', 'w:firstLine="720"')
    has("Heading1", "<w:b/>", '<w:sz w:val="28"/>', "<w:caps/>", '<w:jc w:val="center"/>', "<w:pageBreakBefore/>", tnr)
    has("Heading2", "<w:b/>", '<w:sz w:val="28"/>', tnr)
    has("Heading3", "<w:b/>", '<w:sz w:val="26"/>', tnr)
    has("FrontHeading", "<w:b/>", '<w:sz w:val="28"/>', "<w:caps/>", '<w:jc w:val="center"/>', "<w:pageBreakBefore/>")
    has("Caption", "<w:b/>", '<w:jc w:val="center"/>', tnr)
    if "Times New Roman" not in re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles, re.S)[0]:
        errors.append("docDefaults: the default font is not Times New Roman")

    blocks = body_blocks(doc)
    paras = [(i, x) for i, (k, x) in enumerate(blocks) if k == "p"]

    # title page (before the first front heading)
    first_front = next(i for i, x in paras if style_of(x) == "FrontHeading")
    title_text = norm(" ".join(text_of(x) for i, x in paras if i < first_front))
    for line in TITLE_LINES:
        if norm(line) not in title_text:
            errors.append(f"title page: {line!r} missing")
    for name, reg, _ in STUDENTS:
        if f"{name.upper()} ({reg})" not in title_text:
            errors.append(f"title page: {name.upper()} ({reg}) missing")
    if not any("<w:drawing>" in x for i, x in paras if i < first_front):
        errors.append("title page: the university logo is missing")

    # order of the front headings and chapters
    seq = []
    for i, x in paras:
        st = style_of(x)
        if st == "FrontHeading":
            seq.append(("front", norm(text_of(x)), i))
        elif st == "Heading1":
            seq.append(("chapter", norm(text_of(x)), i))
    want = ([("front", f) for f in FRONT] + [("chapter", f"CHAPTER {n}{t}") for n, t in enumerate(CHAPTERS, 1)]
            + [("front", "References")] + [("front", "Biodata")] * 4)
    got = [(k, t) for k, t, _ in seq]
    # chapter headings read "CHAPTER 1" + line break + title; the text has no space in between
    def key(seq_):    # headings are shown in capitals by their style: compare without case and spaces
        return [(k, t.replace(" ", "").upper()) for k, t in seq_]
    if key(got) != key(want):
        errors.append(f"order of front headings and chapters differs from the spec:\n  got  {got}\n  want {want}")
    note = [x for i, x in paras if style_of(x) == "NoteText"]
    if len(note) != 1 or "It is MANDATORY" not in text_of(note[0]) or "Compact Disk (CD)" not in text_of(note[0]):
        errors.append("the NOTE about the CD (It is MANDATORY ... Compact Disk (CD) ...) is missing")
    elif paras[-1][1] != note[0] and not all(style_of(x) == "" and not text_of(x) for i, x in paras if i > blocks.index(("p", note[0]))):
        errors.append("the NOTE must be the last page")

    # required sections
    heads = [norm(text_of(x)) for i, x in paras if style_of(x) in ("Heading2", "Heading3")]
    for s in REQUIRED_SECTIONS:
        if s not in heads:
            errors.append(f"section {s!r} missing (Heading 2/3)")

    # the front matter ends right before Chapter 1
    sect_idx = next((i for i, x in paras if "<w:sectPr" in x), None)
    ch1 = next((i for k, t, i in seq if k == "chapter"), None)
    if sect_idx is None or ch1 is None or not all(blocks[j][0] == "p" and not text_of(blocks[j][1])
                                                  for j in range(sect_idx + 1, ch1)):
        errors.append("the roman-numbered section must end directly before Chapter 1")

    # captions
    chapter, fig_n, tbl_n = 0, 0, {}
    for i, (k, x) in enumerate(blocks):
        if k != "p":
            continue
        st = style_of(x)
        if st == "Heading1":
            chapter += 1
        if st != "Caption":
            continue
        t = norm(text_of(x))
        if "SEQ Figure" in x:
            fig_n += 1
            if not re.match(rf"Figure {fig_n} \S", t):
                errors.append(f"figure caption {t[:50]!r}: expected 'Figure {fig_n} Title' (continuous numbering)")
            prev = blocks[i - 1]
            if prev[0] != "p" or style_of(prev[1]) != "FigureImage" or "<w:drawing>" not in prev[1]:
                errors.append(f"figure caption {t[:40]!r} is not directly below its figure")
        elif "SEQ Table" in x:
            tbl_n[chapter] = tbl_n.get(chapter, 0) + 1
            if not re.match(rf"Table {chapter}\.{tbl_n[chapter]} \S", t):
                errors.append(f"table caption {t[:50]!r}: expected 'Table {chapter}.{tbl_n[chapter]} Title'")
            nxt = [b for b in blocks[i + 1:i + 3]]
            if not any(b[0] == "tbl" for b in nxt):
                errors.append(f"table caption {t[:40]!r} is not directly above its table")
            if ("\\r 1" in x) != (tbl_n[chapter] == 1):
                errors.append(f"table caption {t[:40]!r}: only the first table of a chapter restarts (\\r 1)")
        else:
            errors.append(f"caption without a SEQ field: {t[:50]!r}")
    if fig_n == 0 or not tbl_n:
        errors.append("no figure or table captions found")

    # contents and lists
    lists = {}
    for name, instr in (("contents", 'TOC \\f \\l "1-3" \\h \\z'), ("list of tables", 'TOC \\h \\z \\c "Table"'),
                        ("list of figures", 'TOC \\h \\z \\c "Figure"')):
        m = re.search(r"<w:instrText[^>]*>\s*" + re.escape(html.escape(instr, quote=True)) + r"\s*</w:instrText>.*?"
                      r'<w:fldChar w:fldCharType="end"/>', doc, re.S)
        m = m or re.search(r"<w:instrText[^>]*>\s*" + re.escape(instr) + r"\s*</w:instrText>.*?"
                           r'<w:fldChar w:fldCharType="end"/>', doc, re.S)
        if not m:
            errors.append(f"{name}: no live field")
            continue
        entries = re.findall(r"<w:r><w:t xml:space=\"preserve\">([^<]*)</w:t></w:r><w:r><w:tab/></w:r>"
                             r"<w:r><w:t>([^<]*)</w:t></w:r>", m[0])
        if not entries:
            errors.append(f"{name}: no entries")
        bad = [e for e in entries if not re.fullmatch(r"[ivxlc]+|\d+", e[1])]
        if bad:
            errors.append(f"{name}: entries without a page number: {bad[:3]}")
        lists[name] = [(html.unescape(a), b) for a, b in entries]
    if len(lists.get("list of figures", [])) != fig_n:
        errors.append(f"list of figures has {len(lists.get('list of figures', []))} entries, captions {fig_n}")
    if len(lists.get("list of tables", [])) != sum(tbl_n.values()):
        errors.append(f"list of tables has {len(lists.get('list of tables', []))} entries, captions {sum(tbl_n.values())}")

    # biodata
    bio = [i for k, t, i in seq if t == "Biodata"]
    for (name, reg, email), i in zip(STUDENTS, bio):
        tbl = blocks[i + 1] if i + 1 < len(blocks) else ("", "")
        lines = [norm(text_of(p)) for p in re.findall(r"<w:p\b.*?</w:p>", tbl[1], re.S)] if tbl[0] == "tbl" else []
        joined = " | ".join(lines)
        for label, value in (("Name", name), ("Register No.", reg), ("E-mail", email)):
            if f"{label} : {value}" not in joined:
                errors.append(f"biodata of {name}: '{label} : {value}' missing")
        for label in ("Mobile Number", "Permanent Address"):
            if not re.search(re.escape(label) + r" : _{10,}", joined):
                errors.append(f"biodata of {name}: {label} must be a blank line (underscores)")
        if "Photo" not in joined:
            errors.append(f"biodata of {name}: the photo box is missing")
        if re.search(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)", joined):
            errors.append(f"biodata of {name}: contains what looks like a phone number")
    if len(bio) != len(STUDENTS):
        errors.append(f"expected {len(STUDENTS)} biodata pages, found {len(bio)}")

    # placeholders and banned claims, anywhere in the Word file. Code listings are left out of the
    # placeholder scan only: Python's "{{" (a literal brace in an f-string) is code, not a placeholder.
    code = ("CodeLine", "SourceCode")
    alltext = para_text(doc) + "\n" + para_text(others) + "\n" + " ".join(re.findall(r"<dc:\w+>([^<]*)<", others))
    prose = para_text(doc, code) + "\n" + para_text(others)
    instr_text = " ".join(re.findall(r"<w:instrText[^>]*>([^<]*)<", doc))
    for pat in PLACEHOLDERS:
        for src, t in (("text", prose), ("fields", instr_text)):
            m = re.search(pat, t)
            if m:
                errors.append(f"placeholder left in the Word file ({src}): {t[max(0, m.start() - 30):m.end() + 30]!r}")
    for pat in BANNED:
        m = re.search(pat, alltext)
        if m:
            errors.append(f"outdated claim in the Word file: {alltext[max(0, m.start() - 40):m.end() + 40]!r}")
    return errors, {"lists": lists, "headings": [norm(text_of(x)) for i, x in paras if style_of(x) in ("Heading2", "Heading3")]}


def check_pdf(pdf: Path, info: dict) -> list[str]:
    import ctypes
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    from trafficsense.report.thesis import pdf_fonts
    errors = []
    doc = pdfium.PdfDocument(str(pdf))
    left, right = MARGINS["left"] / 20, (PAGE[0] - MARGINS["right"]) / 20
    texts, prose_parts = [], []
    heads = {h for h in info["headings"]}
    for i in range(len(doc)):
        pg = doc[i]
        w, h = pg.get_size()
        if (round(w), round(h)) != (612, 792):
            errors.append(f"PDF page {i + 1} is not US Letter ({w:.0f} x {h:.0f} pt)")
        tp = pg.get_textpage()

        def obj_text(obj):
            n = raw.FPDFTextObj_GetText(obj.raw, tp.raw, None, 0)
            buf = ctypes.create_string_buffer(n * 2)
            raw.FPDFTextObj_GetText(obj.raw, tp.raw, ctypes.cast(buf, ctypes.POINTER(ctypes.c_ushort)), n)
            return buf.raw.decode("utf-16-le", "ignore").rstrip("\x00")

        for obj in pg.get_objects():
            if obj.type not in (raw.FPDF_PAGEOBJ_TEXT, raw.FPDF_PAGEOBJ_IMAGE):
                continue
            if obj.type == raw.FPDF_PAGEOBJ_TEXT:
                fbuf = ctypes.create_string_buffer(256)
                raw.FPDFFont_GetBaseFontName(raw.FPDFTextObj_GetFont(obj.raw), fbuf, 256)
                if not fbuf.value.decode().startswith("Consolas"):     # code is set in Consolas
                    prose_parts.append(obj_text(obj))
            l, b, r, t = obj.get_bounds()
            if l < left - 3 or r > right + 3:
                s = obj_text(obj) if obj.type == raw.FPDF_PAGEOBJ_TEXT else ""
                errors.append(f"PDF page {i + 1}: {'text' if s else 'image'} outside the margins "
                              f"(x {l:.0f} to {r:.0f} pt, text area {left:.0f} to {right:.0f}): {s[:40]!r}")
        t = tp.get_text_range()
        texts.append(t)
        lines = [norm(x) for x in t.splitlines() if norm(x)]
        if len(lines) >= 2:
            last = lines[-2] if re.fullmatch(r"[ivxlc]+|\d+", lines[-1]) else lines[-1]
            if last in heads:
                errors.append(f"PDF page {i + 1}: heading {last!r} alone at the foot of the page")
    fonts = pdf_fonts(pdf)
    if not any(f.startswith("TimesNewRoman") for f in fonts):
        errors.append(f"PDF does not embed Times New Roman: {sorted(fonts)}")
    joined = "\n".join(texts)
    for pat in BANNED:
        m = re.search(pat, joined)
        if m:
            errors.append(f"outdated claim in the PDF: {joined[max(0, m.start() - 40):m.end() + 40]!r}")
    # placeholders: in all text except code (set in Consolas), which prints Python's "{{" literally
    prose = " ".join(prose_parts)
    for pat in PLACEHOLDERS:
        m = re.search(pat, prose)
        if m:
            errors.append(f"placeholder in the PDF: {prose[max(0, m.start() - 40):m.end() + 40]!r}")
    # the contents' page numbers are those the PDF shows
    from trafficsense.report.thesis import entries, page_numbers
    with zipfile.ZipFile(REP / "report.docx") as z:
        es = entries(z.read("word/document.xml").decode("utf-8"))
    try:
        page_numbers(es, texts)
        shown = [p for name in ("contents", "list of tables", "list of figures") for _, p in info["lists"].get(name, [])]
        want = [e.page for k in ("toc", "lot", "lof") for e in es if e.kind == k]
        if shown != want:
            diff = [(a, b) for a, b in zip(shown, want) if a != b][:5]
            errors.append(f"page numbers in the contents/lists differ from the PDF: {diff}")
    except ValueError as e:
        errors.append(f"PDF: {e}")
    doc.close()
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docx", default=str(REP / "report.docx"))
    ap.add_argument("--pdf", default=str(REP / "report.pdf"))
    args = ap.parse_args()
    spec = (REP / "format_spec.md").read_text()
    errors, info = check_docx(Path(args.docx), spec)
    errors += check_pdf(Path(args.pdf), info)
    if errors:
        print("\n".join(errors))
        print(f"{len(errors)} problem(s)")
        sys.exit(1)
    print(f"report.docx and report.pdf follow format_spec.md "
          f"({len(info['lists'].get('contents', []))} contents entries, "
          f"{len(info['lists'].get('list of tables', []))} tables, {len(info['lists'].get('list of figures', []))} figures)")


if __name__ == "__main__":
    main()
