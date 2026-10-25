"""Build the project report from docs/report/*.md into docs/report/report.docx and report.pdf.

    python scripts/build_report.py                 # check numbers, build both, check layout
    python scripts/build_report.py --pages 1,12-14 # also render those PDF pages to PNG
    python scripts/build_report.py --skip-check    # build even if make_report.py --check fails

Tools: pandoc (>= 3.1, on PATH or ~/.local/bin) for both formats, with the Lua filter
docs/report/template/report.lua and citeproc (references.bib, IEEE CSL); the PDF goes through
LaTeX with tectonic (on PATH or ~/.local/bin). The Word reference document (fonts, spacing,
margins, page numbers) is generated from pandoc's default at build time, so no binary template
is kept in git.

Checks after the build (any failure exits 1):
* `make_report.py --check` passed first (every number equals outputs/), unless --skip-check;
* LaTeX's figure, table, chapter and section numbers equal the filter's (the DOCX numbers);
* no reference is undefined and no citation key is missing;
* no overfull box wider than OVERFULL_PT (text or tables running into the margin);
* every page of the PDF is A4.
Page images go to the scratch directory given by --png-dir (default: docs/report/build/pages).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from trafficsense.config import repo_root

ROOT = repo_root()
REP = ROOT / "docs/report"
TPL = REP / "template"
OVERFULL_PT = 2.0


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
    # generated-block markers would separate tables from their captions
    text = re.sub(r"^<!-- (?:BEGIN|END):[\w.\-]+ -->\n", "", text, flags=re.M)
    # LaTeX runs in a temporary folder: figure paths must be absolute
    text = text.replace("](figures/", f"]({REP / 'figures'}/")
    out = tmp / "report.md"
    out.write_text(text)
    return out


def pandoc_args(src: Path) -> list[str]:
    return [tool("pandoc"), str(src), "--from", "markdown+raw_html+raw_tex+fenced_divs+bracketed_spans",
            "--resource-path", f"{REP}:{ROOT}", "--lua-filter", str(TPL / "report.lua"),
            "--citeproc", "--bibliography", str(REP / "references.bib"), "--csl", str(TPL / "ieee.csl"),
            "--metadata-file", str(TPL / "metadata.yaml"), "--columns", "60"]


# --- Word ------------------------------------------------------------------------------------

STYLE_PATCH = {
    # styleId: (pPr, rPr) inner XML
    "Normal": ('<w:spacing w:after="120" w:line="360" w:lineRule="auto"/>',
               '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'),
    "VerbatimChar": ("", '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'),   # size follows the text
    "BodyText": ('<w:spacing w:before="120" w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/>', ""),
    "FirstParagraph": ('<w:spacing w:before="120" w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/>', ""),
    # Compact: table cells and tight lists. No size here: 12 pt comes from the document defaults,
    # 9 pt in tables from the table style (paragraph style > table style > defaults in Word).
    "Compact": ('<w:spacing w:before="0" w:after="40" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/>', ""),
    "Heading1": ('<w:keepNext/><w:spacing w:before="240" w:after="240"/><w:jc w:val="center"/><w:outlineLvl w:val="0"/>',
                 '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:color w:val="000000"/>'
                 '<w:sz w:val="32"/><w:szCs w:val="32"/>'),
    "Heading2": ('<w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="1"/>',
                 '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:color w:val="000000"/>'
                 '<w:sz w:val="28"/><w:szCs w:val="28"/>'),
    "Heading3": ('<w:keepNext/><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="2"/>',
                 '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:color w:val="000000"/>'
                 '<w:sz w:val="24"/><w:szCs w:val="24"/>'),
    "ImageCaption": ('<w:spacing w:before="60" w:after="240"/><w:jc w:val="center"/>',
                     '<w:i w:val="0"/><w:sz w:val="20"/><w:szCs w:val="20"/>'),
    "TableCaption": ('<w:keepNext/><w:spacing w:before="240" w:after="60"/><w:jc w:val="center"/>',
                     '<w:i w:val="0"/><w:sz w:val="20"/><w:szCs w:val="20"/>'),
    "CaptionedFigure": ('<w:keepNext/><w:jc w:val="center"/>', ""),
    "Figure": ('<w:keepNext/><w:jc w:val="center"/>', ""),
    "Bibliography": ('<w:spacing w:after="80" w:line="276" w:lineRule="auto"/><w:ind w:left="567" w:hanging="567"/>',
                     '<w:sz w:val="22"/><w:szCs w:val="22"/>'),
}
SMALL_TABLES = "".join(
    f'<w:style w:type="character" w:customStyle="1" w:styleId="{sid}"><w:name w:val="{name}"/>'
    f'<w:qFormat/><w:rPr><w:sz w:val="{hp}"/><w:szCs w:val="{hp}"/></w:rPr></w:style>'
    for sid, name, hp in (("TableSmall", "Table Small", 15), ("TableTiny", "Table Tiny", 13)))
CENTERED = ('<w:style w:type="paragraph" w:customStyle="1" w:styleId="Centered"><w:name w:val="Centered"/>'
            '<w:basedOn w:val="BodyText"/><w:qFormat/><w:pPr><w:jc w:val="center"/></w:pPr></w:style>')
FOOTER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
          '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
          '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>'
          '<w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>')
# A4, margins: left 1.5 in (binding), others 1 in
SECT = ('<w:sectPr><w:footerReference w:type="default" r:id="rIdFooterTS"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="2160" w:header="708" w:footer="708" w:gutter="0"/>'
        '</w:sectPr>')


def patch_style(styles: str, sid: str, ppr: str, rpr: str) -> str:
    m = re.search(rf'(<w:style [^>]*w:styleId="{sid}"[^>]*>)(.*?)(</w:style>)', styles, re.S)
    if not m:
        raise SystemExit(f"style {sid} not in pandoc's reference.docx")
    body = m.group(2)
    body = re.sub(r"<w:pPr>.*?</w:pPr>|<w:pPr\s*/>", "", body, flags=re.S)
    body = re.sub(r"<w:rPr>.*?</w:rPr>|<w:rPr\s*/>", "", body, flags=re.S)
    body += (f"<w:pPr>{ppr}</w:pPr>" if ppr else "") + (f"<w:rPr>{rpr}</w:rPr>" if rpr else "")
    return styles[:m.start()] + m.group(1) + body + m.group(3) + styles[m.end():]


def reference_docx(tmp: Path) -> Path:
    raw = subprocess.run([tool("pandoc"), "--print-default-data-file", "reference.docx"],
                         capture_output=True, check=True).stdout
    src = tmp / "default.docx"
    src.write_bytes(raw)
    out = tmp / "reference.docx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                s = data.decode()
                for sid, (ppr, rpr) in STYLE_PATCH.items():
                    s = patch_style(s, sid, ppr, rpr)
                s = s.replace("</w:styles>", CENTERED + SMALL_TABLES + "</w:styles>")
                m = re.search(r'(<w:style [^>]*w:styleId="Table"[^>]*>.*?)(<w:tblPr>)', s, re.S)
                if not m:
                    raise SystemExit("table style 'Table' not in pandoc's reference.docx")
                s = s[:m.end(1)] + '<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>' + s[m.end(1):]
                data = s.encode()
            elif item.filename == "word/document.xml":
                s = data.decode()
                if 'xmlns:r=' not in s:
                    s = s.replace("<w:document ", '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ', 1)
                s = re.sub(r"<w:sectPr>.*?</w:sectPr>", SECT, s, flags=re.S)
                data = s.encode()
            elif item.filename == "word/_rels/document.xml.rels":
                s = data.decode().replace("</Relationships>",
                    '<Relationship Id="rIdFooterTS" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships/footer" Target="footer1.xml"/></Relationships>')
                data = s.encode()
            elif item.filename == "[Content_Types].xml":
                s = data.decode().replace("</Types>",
                    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-'
                    'officedocument.wordprocessingml.footer+xml"/></Types>')
                data = s.encode()
            zout.writestr(item, data)
        zout.writestr("word/footer1.xml", FOOTER)
    return out


def ask_word_to_update_fields(docx: Path):
    """Word fills the contents and the lists of figures / tables when the file is opened."""
    tmp = docx.with_suffix(".tmp")
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/settings.xml" and b"updateFields" not in data:
                data = data.replace(b"</w:settings>", b'<w:updateFields w:val="true"/></w:settings>')
            zout.writestr(item, data)
    tmp.replace(docx)


def build_docx(src: Path, tmp: Path, numbers_json: Path) -> Path:
    out = REP / "report.docx"
    env = {**os.environ, "REPORT_NUMBERS_JSON": str(numbers_json)}
    r = subprocess.run(pandoc_args(src) + ["--to", "docx", "--reference-doc", str(reference_docx(tmp)),
                                           "-o", str(out)], env=env, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"pandoc (docx) failed:\n{r.stderr}")
    warn(r.stderr, "docx")
    ask_word_to_update_fields(out)
    return out


# --- PDF -------------------------------------------------------------------------------------

def build_pdf(src: Path, tmp: Path, numbers_json: Path) -> tuple[Path, Path]:
    tex = tmp / "report.tex"
    env = {**os.environ, "REPORT_NUMBERS_JSON": str(numbers_json)}
    r = subprocess.run(pandoc_args(src) + ["--to", "latex", "--standalone", "--top-level-division", "chapter",
                                           "--number-sections", "--include-in-header", str(TPL / "preamble.tex"),
                                           "-o", str(tex)], env=env, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"pandoc (latex) failed:\n{r.stderr}")
    warn(r.stderr, "latex")
    tex.write_text(short_captions(tex.read_text()))
    r = subprocess.run([tool("tectonic"), "--keep-intermediates", "--keep-logs", "--outdir", str(tmp), str(tex)],
                       capture_output=True, text=True, cwd=tmp)
    if r.returncode:
        raise SystemExit(f"tectonic failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    out = REP / "report.pdf"
    shutil.copyfile(tmp / "report.pdf", out)
    return out, tmp / "report.log"


def short_captions(tex: str) -> str:
    """\\caption{Long text. More.} -> \\caption[Long text.]{Long text. More.}: the lists of figures
    and tables show the first sentence of each caption only."""
    out, i = [], 0
    while True:
        j = tex.find("\\caption{", i)
        if j < 0:
            out.append(tex[i:])
            return "".join(out)
        k, depth = j + len("\\caption{"), 1
        cut = None
        while depth:
            c = tex[k]
            if c == "{" and tex[k - 1] != "\\":
                depth += 1
            elif c == "}" and tex[k - 1] != "\\":
                depth -= 1
            elif c == "." and depth == 1 and cut is None and tex[k + 1:k + 2] in (" ", "\n"):
                cut = k + 1
            k += 1
        full = tex[j + len("\\caption{"):k - 1]
        start = j + len("\\caption{")
        if cut is not None and cut - start < len(full.rstrip()):
            short = re.sub(r"\\label\{[^}]*\}", "", tex[start:cut]).strip()
            out.append(tex[i:j] + "\\caption[" + short + "]{" + full + "}")
        else:
            out.append(tex[i:k])
        i = k


def warn(stderr: str, what: str):
    bad = [ln for ln in stderr.splitlines() if ln.strip() and "[WARNING]" in ln]
    if bad:
        raise SystemExit(f"pandoc ({what}) warnings:\n" + "\n".join(bad))


# --- checks ----------------------------------------------------------------------------------

def latex_numbers(aux: Path) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux.read_text(errors="replace")):
        out[m.group(1)] = m.group(2)
    return out


def checks(pdf: Path, log: Path, numbers_json: Path) -> list[str]:
    errors = []
    filt = json.loads(numbers_json.read_text())
    tex = latex_numbers(log.with_suffix(".aux"))
    for lab, x in filt.items():
        if tex.get(lab) != x["num"]:
            errors.append(f"numbering: {lab} is {x['kind']} {x['num']} in DOCX but {tex.get(lab)} in the PDF")
    logtext = log.read_text(errors="replace")
    for m in re.finditer(r"Overfull \\hbox \((\d+\.\d+)pt too wide\)[^\n]*\n?([^\n]*)", logtext):
        if float(m.group(1)) > OVERFULL_PT:
            errors.append(f"overfull box {m.group(1)} pt: {m.group(2)[:100]!r}")
    if re.search(r"undefined references|Reference `[^']+' on page", logtext):
        errors.append("LaTeX reports undefined references")
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    for i in range(len(doc)):
        w, h = doc[i].get_size()
        if sorted((round(w), round(h))) != [595, 842]:   # A4, portrait or landscape (wide tables)
            errors.append(f"page {i + 1} is not A4 ({w:.0f} x {h:.0f} pt)")
    print(f"PDF: {len(doc)} pages; {len(filt)} numbered labels agree between DOCX and PDF" if not errors else "")
    return errors


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
            img = doc[p - 1].render(scale=1.4).to_pil()
            img.save(out_dir / f"page_{p:03d}.png")
    print(f"rendered {len(pages)} page(s) to {out_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-check", action="store_true")
    ap.add_argument("--pages", default="")
    ap.add_argument("--png-dir", default=str(REP / "build/pages"))
    ap.add_argument("--only", choices=["docx", "pdf"])
    args = ap.parse_args()
    if not args.skip_check:
        r = subprocess.run([sys.executable, str(ROOT / "scripts/make_report.py"), "--check"], cwd=ROOT)
        if r.returncode:
            raise SystemExit("make_report.py --check failed: the report's numbers do not match outputs/")
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        src = combined(tmp)
        numbers_json = tmp / "numbers.json"
        errors = []
        if args.only != "pdf":
            print(f"wrote {build_docx(src, tmp, numbers_json).relative_to(ROOT)}")
        if args.only != "docx":
            pdf, log = build_pdf(src, tmp, numbers_json)
            print(f"wrote {pdf.relative_to(ROOT)}")
            errors += checks(pdf, log, numbers_json)
            if args.pages:
                render_pages(pdf, args.pages, Path(args.png_dir))
    if errors:
        print("\n".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    main()
