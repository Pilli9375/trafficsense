"""The report's Biodata pages from a private, gitignored file.

The repository is public, so the students' mobile numbers, e-mail addresses, home addresses and
photos are never committed. They live in `paths.biodata` (YAML, under the gitignored
data/external/) and the photos in `paths.biodata_photos` (symlinks to the files on D). The report
build reads them from there:

    load_optional()   the private file -> Student list, or None with the reason (file missing)
    personalise()     the biodata divs of docs/report/80_biodata.md with the private details added
    process_photo()   a photo cropped (only as much as needed) to the 3.5 x 4.5 cm box, as JPEG
    insert_photos()   the photos into the built .docx, in the photo box of each page
    check_personal()  the personal .docx/.pdf: four pages, each complete, nothing blank
    check_no_leaks()  no tracked file (text, inside .docx/.zip, PDF text, image) holds any of it

Fails loudly: a malformed private file, a name or register number that differs from the report,
or a photo that cannot be read stops the build. Only a *missing* file (or a missing photo) falls
back to the blank lines of the public report, and the build prints which one it used.
"""
from __future__ import annotations

import hashlib
import io
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml

BOX_RATIO = 3.5 / 4.5               # photo box, width / height (a passport photo)
IMG_W_CM = 3.3                      # the picture inside the 3.5 x 4.5 cm box, clear of its border
IMG_H_CM = IMG_W_CM / BOX_RATIO
EMU_PER_CM = 360000
MAX_PX = (620, 797)                 # about 180 dpi at 3.5 x 4.5 cm: enough for print, small in the .docx
PHOTO_MARKER = "[[photo:{reg}]]"    # written by thesis.lua where a photo goes, replaced by insert_photos()
FIELDS = ("reg", "name", "mobile", "email", "address", "photo")
DHASH_MAX_DIST = 10                 # of 64 bits: a tracked image this close to a photo counts as the photo


class BiodataError(ValueError):
    pass


@dataclass
class Student:
    reg: str
    name: str
    mobile: str
    email: str
    address: str
    photo: str                      # file name inside paths.biodata_photos
    photo_path: Path | None = None  # None: the file is missing (the photo box stays empty)


# --- the private file --------------------------------------------------------------------------

def _validate(s: dict, i: int) -> Student:
    where = f"student {i + 1}"
    for k in FIELDS:
        v = s.get(k)
        if not isinstance(v, str) or not v.strip():
            raise BiodataError(f"{where}: '{k}' is missing or empty (write phone numbers in quotes)")
    s = {k: s[k].strip() for k in FIELDS}
    if not re.fullmatch(r"[6-9]\d{9}", s["mobile"]):
        raise BiodataError(f"{where}: the mobile number must be 10 digits starting with 6-9")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", s["email"]):
        raise BiodataError(f"{where}: the e-mail address is not valid")
    if re.search(r'["|{}\\\n]|\s{2,}', s["address"]) or len(s["address"]) > 150:
        raise BiodataError(f"{where}: the address has a character that cannot be written to the page "
                           '(a quote, |, braces, backslash, a newline or a double space) or is too long')
    for k in ("name", "reg", "photo"):
        if re.search(r'["|{}\\\n]', s[k]):
            raise BiodataError(f"{where}: '{k}' has a character that is not allowed")
    return Student(**s)


def load(yaml_path: Path, photos_dir: Path) -> list[Student]:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("students"), list):
        raise BiodataError(f"{yaml_path}: expected a 'students:' list")
    students = [_validate(s, i) for i, s in enumerate(data["students"])]
    regs = [s.reg for s in students]
    if len(set(regs)) != len(regs):
        raise BiodataError(f"{yaml_path}: a register number is listed twice")
    for s in students:
        p = photos_dir / s.photo
        if p.name != s.photo:
            raise BiodataError(f"{s.reg}: photo must be a file name, not a path ({s.photo!r})")
        s.photo_path = p if p.is_file() else None
    return students


def load_optional(yaml_path: Path, photos_dir: Path) -> tuple[list[Student] | None, str]:
    """(students, "") or (None, reason) when the private file does not exist. A file that exists
    but is malformed raises BiodataError: that is a mistake to fix, not a reason to go blank."""
    if not yaml_path.is_file():
        return None, f"private file {yaml_path} not found"
    return load(yaml_path, photos_dir), ""


# --- the markdown ---------------------------------------------------------------------------------

DIV = re.compile(r'::: \{\.biodata name="([^"]+)" reg="([^"]+)" email="([^"]+)"\}')


def personalise(md: str, students: list[Student]) -> str:
    """Add each student's private details to their biodata div (matched by register number and
    name). The e-mail of the div (the university one, used on the public page) is replaced by the
    private one. A student without a readable photo gets no photo attribute: empty photo box."""
    by_reg = {s.reg: s for s in students}
    seen = []

    def sub(m):
        name, reg, _ = m.groups()
        s = by_reg.get(reg)
        if s is None:
            raise BiodataError(f"the report has a biodata page for {reg} but the private file has no such student")
        if s.name != name:
            raise BiodataError(f"{reg}: the private file says {s.name!r}, the report says {name!r}")
        seen.append(reg)
        photo = f' photo="{s.reg}"' if s.photo_path else ""
        return (f'::: {{.biodata name="{name}" reg="{reg}" email="{s.email}" mobile="{s.mobile}" '
                f'address="{s.address}"{photo}}}')

    out = DIV.sub(sub, md)
    if not seen:
        raise BiodataError("no biodata divs found in the report sources")
    extra = sorted(set(by_reg) - set(seen))
    if extra:
        raise BiodataError(f"the private file has students that are not in the report: {extra}")
    return out


# --- photos ---------------------------------------------------------------------------------------

def _trim_frame(im):
    """Cut off a thin dark frame drawn at the very edge of a photo (one of ours has it): the box
    has its own border. A dark line within 4 % of an edge, with a bright area just inside it."""
    import numpy as np
    g = np.asarray(im.convert("L"), dtype=float)
    h, w = g.shape
    lim = {"top": (g.mean(axis=1), h), "bottom": (g.mean(axis=1)[::-1], h),
           "left": (g.mean(axis=0), w), "right": (g.mean(axis=0)[::-1], w)}
    cut = {}
    for side, (prof, n) in lim.items():
        reach = max(3, int(0.04 * n))
        dark = [i for i in range(reach) if prof[i] < 60 and prof[min(n - 1, i + max(4, reach // 2))] > 100]
        cut[side] = (dark[-1] + 3) if dark else 0       # 2 px inside the last dark line
    return im.crop((cut["left"], cut["top"], im.width - cut["right"], im.height - cut["bottom"]))


def process_photo(path: Path) -> bytes:
    """The photo as JPEG bytes in the box's 7:9 shape. Nothing is stretched: the picture is cropped
    only as much as the shape needs (the sides evenly; from the bottom first, so heads stay) and
    scaled down (never up) to MAX_PX. Same input, same bytes."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = _trim_frame(im.convert("RGB"))
    w, h = im.size
    if w / h > BOX_RATIO:                                 # too wide: crop the sides evenly
        nw = round(h * BOX_RATIO)
        x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    elif w / h < BOX_RATIO:                               # too tall: crop, mostly from the bottom
        nh = round(w / BOX_RATIO)
        y = round((h - nh) * 0.15)
        im = im.crop((0, y, w, y + nh))
    if im.width > MAX_PX[0]:
        im = im.resize(MAX_PX, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92, subsampling=0)
    return buf.getvalue()


def _drawing(rid: str, n: int, descr: str) -> str:
    cx, cy = round(IMG_W_CM * EMU_PER_CM), round(IMG_H_CM * EMU_PER_CM)
    return (f'<w:p><w:pPr><w:pStyle w:val="BiodataPhoto"/><w:spacing w:before="0" w:after="0" w:line="240" '
            f'w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{9000 + n}" name="Biodata photo {n}" descr="{descr}"/>'
            f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{9000 + n}" name="biodata_{n}.jpg"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def insert_photos(docx: Path, students: list[Student]) -> int:
    """Replace each photo marker written by thesis.lua with the processed photo. Returns how many."""
    import html
    from trafficsense.report.thesis import _read, _write
    parts = _read(docx)
    doc = parts["word/document.xml"].decode("utf-8")
    rels = parts["word/_rels/document.xml.rels"].decode("utf-8")
    n = 0
    for s in students:
        if not s.photo_path:
            continue
        marker = PHOTO_MARKER.format(reg=s.reg)
        pat = re.compile(r'<w:p><w:pPr><w:pStyle w:val="BiodataPhoto"/></w:pPr><w:r><w:t xml:space="preserve">'
                         + re.escape(marker) + r"</w:t></w:r></w:p>")
        if len(pat.findall(doc)) != 1:
            raise BiodataError(f"expected one photo box for {s.reg} in the document, found {len(pat.findall(doc))}")
        n += 1
        rid = f"rIdBioPhoto{n}"
        target = f"media/biodata_{n}.jpg"
        parts["word/" + target] = process_photo(s.photo_path)
        rels = rels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                            f'officeDocument/2006/relationships/image" Target="{target}"/></Relationships>')
        doc = pat.sub(lambda _: _drawing(rid, n, html.escape(f"Photo of {s.name}", quote=True)), doc)
    if "[[photo:" in doc:
        raise BiodataError("a photo marker is left in the document")
    ct = parts["[Content_Types].xml"].decode("utf-8")
    if n and not re.search(r'Extension="jpe?g"', ct):
        ct = ct.replace("</Types>", '<Default Extension="jpg" ContentType="image/jpeg"/></Types>')
    parts["[Content_Types].xml"] = ct.encode("utf-8")
    parts["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    parts["word/document.xml"] = doc.encode("utf-8")
    _write(docx, parts)
    return n


# --- check of the personal build ------------------------------------------------------------------

def _text(xml: str) -> str:
    import html
    xml = re.sub(r"<w:tab\s*/>", "<w:t> </w:t>", xml)
    return html.unescape("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml)))


def _norm(s: str) -> str:
    return re.sub(r"[\s   ]+", " ", s).strip()


def top_level_tables(doc: str) -> list[str]:
    out, depth, start = [], 0, 0
    for m in re.finditer(r"<w:tbl>|</w:tbl>", doc):
        if m[0] == "<w:tbl>":
            if depth == 0:
                start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                out.append(doc[start:m.end()])
    return out


def check_personal(docx: Path, pdf: Path, students: list[Student]) -> list[str]:
    """Problems with the personal build (empty list = fine): four biodata pages in the Word file
    and in the PDF, each with the student's name, register number, 10-digit phone, e-mail, address
    and photo, nothing left blank, in the order of the title page."""
    errors: list[str] = []
    with zipfile.ZipFile(docx) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        media = {n: z.read(n) for n in z.namelist() if n.startswith("word/media/")}
    tables = [t for t in top_level_tables(doc) if "BiodataLine" in t]
    if len(tables) != len(students):
        errors.append(f"Word file: {len(students)} biodata pages expected, found {len(tables)}")
    for s, t in zip(students, tables):
        lines = [_norm(_text(p)) for p in re.findall(r"<w:p\b.*?</w:p>", t, re.S) if "BiodataLine" in p]
        txt = " | ".join(x for x in lines if x)
        for label, value in (("Name", s.name), ("Register No.", s.reg), ("Mobile Number", s.mobile),
                             ("E-mail", s.email), ("Permanent Address", s.address)):
            if f"{label} : {value}" not in txt:
                errors.append(f"Word file, {s.reg}: '{label} : <value>' missing or wrong")
        if not re.fullmatch(r"\d{10}", s.mobile):
            errors.append(f"{s.reg}: the phone number is not 10 digits")
        paras = [_norm(_text(x)) for x in re.findall(r"<w:p\b.*?</w:p>", t, re.S)]
        if any("___" in x for x in paras):
            errors.append(f"Word file, {s.reg}: a blank line is left on the page")
        if any(x == "Photo" or x.startswith("[[photo") for x in paras):
            errors.append(f"Word file, {s.reg}: the photo box still holds its placeholder text")
        rid = re.search(r'<w:drawing>.*?r:embed="([^"]+)"', t, re.S)
        if not rid:
            errors.append(f"Word file, {s.reg}: no photo in the box")
            continue
        target = re.search(r'Id="%s"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Id="%s"' % (rid[1], rid[1]), rels)
        name = "word/" + next(g for g in target.groups() if g) if target else ""
        if name not in media:
            errors.append(f"Word file, {s.reg}: the photo part {name!r} is missing")
        elif s.photo_path is None:
            errors.append(f"{s.reg}: the photo file {s.photo!r} is missing")
        elif media[name] != process_photo(s.photo_path):
            errors.append(f"Word file, {s.reg}: the embedded photo is not {s.photo}")
    errors += _check_pdf_pages(pdf, students)
    return errors


def _check_pdf_pages(pdf: Path, students: list[Student]) -> list[str]:
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    errors = []
    doc = pdfium.PdfDocument(str(pdf))
    try:
        pages = [i for i in range(len(doc)) if "Register No." in doc[i].get_textpage().get_text_range()]
        if len(pages) != len(students):
            errors.append(f"PDF: {len(students)} biodata pages expected, found {len(pages)}")
        for s, i in zip(students, pages):
            pg = doc[i]
            text = _norm(pg.get_textpage().get_text_range())
            for label, value in (("name", s.name), ("register number", s.reg), ("phone", s.mobile),
                                 ("e-mail", s.email), ("address", s.address)):
                if value not in text:
                    errors.append(f"PDF page {i + 1} ({s.reg}): {label} not on the page")
            if "___" in text:
                errors.append(f"PDF page {i + 1} ({s.reg}): a blank line is left on the page")
            imgs = [o for o in pg.get_objects() if o.type == raw.FPDF_PAGEOBJ_IMAGE]
            if len(imgs) != 1:
                errors.append(f"PDF page {i + 1} ({s.reg}): {len(imgs)} images on the page, expected the 1 photo")
            else:
                l, b, r, t = imgs[0].get_bounds()
                if r - l < 60 or t - b < 80:
                    errors.append(f"PDF page {i + 1} ({s.reg}): the photo is only {r - l:.0f} x {t - b:.0f} pt")
    finally:
        doc.close()
    return errors


# --- no personal data in tracked files --------------------------------------------------------------

def _tolerant(digits: str) -> re.Pattern:
    """The digits with optional spaces, dots or hyphens between them (a phone number written 98765 43210)."""
    return re.compile(r"(?<!\d)" + r"[\s.\-]?".join(digits) + r"(?!\d)")


def _dhash(im) -> int:
    from PIL import Image
    g = im.convert("L").resize((9, 8), Image.LANCZOS)
    px = g.tobytes()
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (px[y * 9 + x] > px[y * 9 + x + 1])
    return bits


def _image_hashes(data: bytes):
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            return _dhash(im.convert("RGB"))
    except Exception:
        return None


def _members(name: str, data: bytes):
    """The file itself and, for .docx/.zip, everything inside (one level of nesting)."""
    yield name, data
    if name.lower().endswith((".docx", ".zip", ".odt", ".xlsx", ".pptx")):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for n in z.namelist():
                    if not n.endswith("/"):
                        yield from _members(f"{name}!{n}", z.read(n))
        except zipfile.BadZipFile:
            pass


def _pdf_text(data: bytes) -> str:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(data)
    try:
        return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    finally:
        doc.close()


def check_no_leaks(root: Path, students: list[Student]) -> tuple[list[str], int]:
    """Search every git-tracked file for the students' phone numbers, e-mail addresses, home
    addresses and photos: in plain text, inside .docx/.zip files, in the text of PDFs, and among
    tracked images (the photo file itself, its processed form, or a picture that looks the same).
    Returns (problems, number of files searched). The private details are never printed."""
    files = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.split(b"\0")
    tracked = [f.decode() for f in files if f]
    phones = {s.reg: _tolerant(s.mobile) for s in students}
    texts = {s.reg: [re.compile(re.escape(s.email), re.I), re.compile(re.escape(s.address), re.I)]
             for s in students}
    originals = {}
    for s in students:
        if s.photo_path:
            raw_bytes = s.photo_path.read_bytes()
            proc = process_photo(s.photo_path)
            originals[s.reg] = ({hashlib.sha256(raw_bytes).hexdigest(), hashlib.sha256(proc).hexdigest()},
                                [h for h in (_image_hashes(raw_bytes), _image_hashes(proc)) if h is not None])
    problems = []
    for rel in tracked:
        p = root / rel
        if not p.is_file():
            continue
        data = p.read_bytes()
        for name, blob in _members(rel, data):
            hay = [blob.decode("latin-1")]
            if blob[:5] == b"%PDF-":
                hay.append(_pdf_text(blob))
            else:
                hay.append(blob.decode("utf-8", "ignore"))
            for s in students:
                if any(phones[s.reg].search(h) for h in hay):
                    problems.append(f"{name}: contains the phone number of {s.reg}")
                if any(rx.search(h) for h in hay for rx in texts[s.reg]):
                    problems.append(f"{name}: contains the e-mail or address of {s.reg}")
                if s.reg in originals:
                    shas, dh = originals[s.reg]
                    if hashlib.sha256(blob).hexdigest() in shas:
                        problems.append(f"{name}: is the photo of {s.reg}")
                    elif name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")):
                        h = _image_hashes(blob)
                        if h is not None and any(bin(h ^ x).count("1") <= DHASH_MAX_DIST for x in dh):
                            problems.append(f"{name}: looks like the photo of {s.reg}")
    return problems, len(tracked)


# --- the personal build against the public one ------------------------------------------------------

def list_pages(docx: Path) -> list[str]:
    """The contents, list of tables and list of figures as printed (text and page number per line)."""
    with zipfile.ZipFile(docx) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    return [_norm(_text(p)) for p in re.findall(r"<w:p\b.*?</w:p>", doc, re.S)
            if re.search(r'<w:pStyle w:val="(?:TOC\d|TableofFigures)"', p[:200])]


def pdf_page_count(pdf: Path) -> int:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    try:
        return len(doc)
    finally:
        doc.close()


def compare_with_public(personal: tuple[Path, Path], public: tuple[Path, Path]) -> list[str]:
    """The personal copy must have the same page count and the same contents/list page numbers
    as the public report: the personal details replace blank lines on pages that exist anyway."""
    errors = []
    pn, qn = pdf_page_count(personal[1]), pdf_page_count(public[1])
    if pn != qn:
        errors.append(f"page count differs: personal {pn}, public {qn}")
    a, b = list_pages(personal[0]), list_pages(public[0])
    if not a:
        errors.append("no contents/list entries found in the personal Word file")
    if a != b:
        diff = [(x, y) for x, y in zip(a, b) if x != y][:3]
        errors.append(f"contents/lists differ from the public report ({len(a)} vs {len(b)} entries): {diff}")
    return errors
