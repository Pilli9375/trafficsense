"""The report's private Biodata pages (trafficsense.report.biodata). Everything here is a test fake:
made-up students, made-up numbers, synthetic pictures; nothing real is in the repository."""
import io
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageDraw

from trafficsense.config import repo_root
from trafficsense.report import biodata

ROOT = repo_root()
FAKE = [
    dict(reg="23XXX0001", name="Test Student One", mobile="9000000001", email="one@example.invalid",
         address="1 Test Road, Testville", photo="one.png"),
    dict(reg="23XXX0002", name="Test Student Two", mobile="6000000002", email="two@example.invalid",
         address="2 Sample Street Exampleton Testland", photo="two.png"),
]


def picture(path: Path, size, frame=False):
    """A synthetic portrait-like picture: a gradient with a bright square 'face', optional black frame."""
    im = Image.new("RGB", size, (235, 235, 235))
    d = ImageDraw.Draw(im)
    for y in range(size[1]):
        d.line([(0, y), (size[0], y)], fill=(200 - y * 60 // size[1], 220, 235))
    w, h = size
    d.rectangle([w * 0.35, h * 0.15, w * 0.65, h * 0.45], fill=(250, 200, 160))
    if frame:
        d.rectangle([w * 0.02, h * 0.02, w * 0.98, h * 0.98], outline=(0, 0, 0), width=max(3, w // 200))
    im.save(path)
    return path


@pytest.fixture
def private(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    picture(photos / "one.png", (400, 520), frame=True)
    picture(photos / "two.png", (600, 500))
    f = tmp_path / "biodata.yaml"
    f.write_text(yaml.safe_dump({"students": FAKE}))
    return f, photos


DIVS = ('::: {.biodata name="Test Student One" reg="23XXX0001" email="one@univ.invalid"}\n:::\n\n'
        '::: {.biodata name="Test Student Two" reg="23XXX0002" email="two@univ.invalid"}\n:::\n')


# --- the file --------------------------------------------------------------------------------

def test_load_reads_students_and_photo_paths(private):
    f, photos = private
    st = biodata.load(f, photos)
    assert [s.reg for s in st] == ["23XXX0001", "23XXX0002"]
    assert st[0].photo_path == photos / "one.png"


def test_missing_file_is_reported_not_raised(tmp_path):
    st, why = biodata.load_optional(tmp_path / "nope.yaml", tmp_path)
    assert st is None and "not found" in why


def test_missing_photo_leaves_the_path_empty(private):
    f, photos = private
    (photos / "two.png").unlink()
    assert [s.photo_path is None for s in biodata.load(f, photos)] == [False, True]


@pytest.mark.parametrize("field,value,msg", [
    ("mobile", "12345", "10 digits"), ("mobile", "5000000001", "10 digits"),
    ("email", "not-an-email", "e-mail"), ("address", "A \"quoted\" road", "address"),
    ("address", "", "missing or empty"), ("name", None, "missing or empty")])
def test_malformed_file_fails_loudly(private, field, value, msg):
    f, photos = private
    bad = [dict(s) for s in FAKE]
    bad[0][field] = value
    f.write_text(yaml.safe_dump({"students": bad}))
    with pytest.raises(biodata.BiodataError, match=msg):
        biodata.load(f, photos)


def test_duplicate_register_number_fails(private):
    f, photos = private
    f.write_text(yaml.safe_dump({"students": [FAKE[0], FAKE[0]]}))
    with pytest.raises(biodata.BiodataError, match="twice"):
        biodata.load(f, photos)


def test_photo_must_be_a_file_name(private):
    f, photos = private
    bad = [dict(s) for s in FAKE]
    bad[0]["photo"] = "../x.png"
    f.write_text(yaml.safe_dump({"students": bad}))
    with pytest.raises(biodata.BiodataError, match="file name"):
        biodata.load(f, photos)


# --- the markdown ----------------------------------------------------------------------------------

def test_personalise_adds_details_and_replaces_the_email(private):
    st = biodata.load(*private)
    out = biodata.personalise(DIVS, st)
    assert 'email="one@example.invalid" mobile="9000000001" address="1 Test Road, Testville" photo="23XXX0001"' in out
    assert "univ.invalid" not in out


def test_personalise_without_a_photo_has_no_photo_attribute(private):
    f, photos = private
    (photos / "two.png").unlink()
    out = biodata.personalise(DIVS, biodata.load(f, photos))
    assert out.count("photo=") == 1


def test_personalise_checks_names_and_students(private):
    st = biodata.load(*private)
    with pytest.raises(biodata.BiodataError, match="private file says"):
        biodata.personalise(DIVS.replace("Test Student Two", "Somebody Else"), st)
    with pytest.raises(biodata.BiodataError, match="not in the report"):
        biodata.personalise(DIVS.split("\n\n")[0] + "\n", st)
    with pytest.raises(biodata.BiodataError, match="no such student"):
        biodata.personalise(DIVS.replace("23XXX0002", "23XXX0003"), st)
    with pytest.raises(biodata.BiodataError, match="no biodata divs"):
        biodata.personalise("nothing here", st)


# --- photos ----------------------------------------------------------------------------------------

def shape(data: bytes):
    return Image.open(io.BytesIO(data)).size


def test_photos_get_the_box_shape_without_stretching(tmp_path):
    wide = picture(tmp_path / "w.png", (1200, 900))
    tall = picture(tmp_path / "t.png", (800, 2000))
    exact = picture(tmp_path / "e.png", (350, 450))
    for p in (wide, tall, exact):
        w, h = shape(biodata.process_photo(p))
        assert abs(w / h - biodata.BOX_RATIO) < 0.005
    assert shape(biodata.process_photo(exact)) == (350, 450)         # nothing to crop, never scaled up
    assert shape(biodata.process_photo(wide))[0] <= biodata.MAX_PX[0]


def test_crop_keeps_the_picture_content_not_a_squeezed_copy(tmp_path):
    p = picture(tmp_path / "w.png", (1200, 900))
    im = Image.open(io.BytesIO(biodata.process_photo(p)))
    # the 'face' square is 30 % x 30 % of the original height-limited crop: still square
    px = im.load()
    xs = [x for x in range(im.width) if px[x, int(im.height * 0.3)][0] > 240]
    ys = [y for y in range(im.height) if px[im.width // 2, y][0] > 240]
    assert abs(len(xs) / len(ys) - (0.30 * 1200) / (0.30 * 900)) < 0.08


def test_dark_edge_frame_is_trimmed(tmp_path):
    p = picture(tmp_path / "f.png", (800, 1000), frame=True)
    im = Image.open(io.BytesIO(biodata.process_photo(p))).convert("L")
    edge = [im.getpixel((x, im.height // 2)) for x in (0, 1, 2, im.width - 3, im.width - 2, im.width - 1)]
    assert min(edge) > 100


def test_processing_is_deterministic(tmp_path):
    p = picture(tmp_path / "d.png", (700, 900))
    assert biodata.process_photo(p) == biodata.process_photo(p)


# --- the Word file -----------------------------------------------------------------------------------

def line(label, value):
    return (f'<w:p><w:pPr><w:pStyle w:val="BiodataLine"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{label}</w:t></w:r>'
            f'<w:r><w:tab/></w:r><w:r><w:t xml:space="preserve">: {value}</w:t></w:r></w:p>')


def page(s, marker=None, blank=False):
    mobile = "_" * 30 if blank else s["mobile"]
    return ('<w:tbl><w:tblPr/><w:tr><w:tc><w:tbl><w:tr><w:tc><w:p><w:pPr><w:pStyle w:val="BiodataPhoto"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{marker or "Photo"}</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p/></w:tc><w:tc>'
            + line("Name", s["name"]) + line("Register No.", s["reg"]) + line("Mobile Number", mobile)
            + line("E-mail", s["email"]) + line("Permanent Address", s["address"]) + "</w:tc></w:tr></w:tbl>")


def make_docx(path: Path, students, blank=False, no_photo=()):
    """What pandoc + thesis.lua write: a photo marker in each box, or the word 'Photo' for a student in no_photo."""
    doc = ('<?xml version="1.0"?><w:document xmlns:w="w" xmlns:r="r" xmlns:wp="wp" xmlns:a="a" xmlns:pic="pic"><w:body>'
           + "".join(page(s, None if s["reg"] in no_photo else biodata.PHOTO_MARKER.format(reg=s["reg"]), blank)
                     for s in students) + "</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="r"></Relationships>')
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="t"><Default Extension="xml" ContentType="a/b"/></Types>')
    return path


def test_insert_photos_puts_the_processed_photo_in_each_box(private, tmp_path, monkeypatch):
    st = biodata.load(*private)
    docx = make_docx(tmp_path / "r.docx", FAKE)
    assert biodata.insert_photos(docx, st) == 2
    with zipfile.ZipFile(docx) as z:
        assert z.read("word/media/biodata_1.jpg") == biodata.process_photo(st[0].photo_path)
        doc = z.read("word/document.xml").decode()
        assert doc.count("<w:drawing>") == 2 and "[[photo:" not in doc
        assert 'Extension="jpg"' in z.read("[Content_Types].xml").decode()
    monkeypatch.setattr(biodata, "_check_pdf_pages", lambda pdf, students: [])
    assert biodata.check_personal(docx, tmp_path / "x.pdf", st) == []


def test_a_missing_photo_leaves_the_box_and_the_check_says_so(private, tmp_path, monkeypatch):
    f, photos = private
    (photos / "two.png").unlink()
    st = biodata.load(f, photos)
    docx = make_docx(tmp_path / "r.docx", FAKE, no_photo=["23XXX0002"])
    assert biodata.insert_photos(docx, st) == 1
    monkeypatch.setattr(biodata, "_check_pdf_pages", lambda pdf, students: [])
    errs = biodata.check_personal(docx, tmp_path / "x.pdf", st)
    assert errs and all("23XXX0002" in e for e in errs)
    assert any("placeholder" in e for e in errs) and any("no photo" in e for e in errs)


def test_check_personal_finds_blank_lines_wrong_values_and_missing_photos(private, tmp_path, monkeypatch):
    monkeypatch.setattr(biodata, "_check_pdf_pages", lambda pdf, students: [])
    st = biodata.load(*private)
    blank = make_docx(tmp_path / "b.docx", FAKE, blank=True)
    errs = biodata.check_personal(blank, tmp_path / "x.pdf", st)
    assert any("Mobile Number" in e for e in errs) and any("blank line" in e for e in errs)
    assert any("no photo" in e for e in errs)
    wrong = make_docx(tmp_path / "w.docx", [dict(FAKE[0], email="other@example.invalid"), FAKE[1]])
    biodata.insert_photos(wrong, st)
    errs = biodata.check_personal(wrong, tmp_path / "x.pdf", st)
    assert len(errs) == 1 and "E-mail" in errs[0]
    only_one = make_docx(tmp_path / "o.docx", FAKE[:1])
    assert any("2 biodata pages expected, found 1" in e for e in biodata.check_personal(only_one, tmp_path / "x.pdf", st))


# --- no personal data in tracked files -----------------------------------------------------------------

def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=repo, check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    (r / "README.md").write_text("Nothing personal, numbers like 9000000 and 90000000011 are not phones.\n")
    git(r, "add", "-A")
    return r


def leaks(repo, private):
    return biodata.check_no_leaks(repo, biodata.load(*private))[0]


def test_clean_repo_has_no_leaks(repo, private):
    assert leaks(repo, private) == []


def test_phone_email_and_address_in_a_tracked_file_are_found(repo, private):
    (repo / "a.txt").write_text("call 90000 00001 or mail ONE@example.invalid, 2 sample street exampleton testland\n")
    git(repo, "add", "-A")
    found = leaks(repo, private)
    assert any("phone number of 23XXX0001" in x for x in found)
    assert any("e-mail or address of 23XXX0001" in x for x in found)
    assert any("e-mail or address of 23XXX0002" in x for x in found)
    assert all("9000000001" not in x and "example.invalid" not in x for x in found)   # the details are not printed


def test_details_inside_a_tracked_docx_are_found(repo, private):
    with zipfile.ZipFile(repo / "r.docx", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w:t>6000000002</w:t>")
    git(repo, "add", "-A")
    assert any("r.docx!word/document.xml" in x and "23XXX0002" in x for x in leaks(repo, private))


def test_a_tracked_photo_is_found_exactly_resized_and_inside_a_docx(repo, private):
    f, photos = private
    shutil.copy(photos / "one.png", repo / "exact.png")
    big = Image.open(photos / "one.png")
    big.resize((200, 260)).save(repo / "small.jpg", quality=70)
    buf = io.BytesIO()
    big.save(buf, "PNG")
    with zipfile.ZipFile(repo / "r.docx", "w") as z:
        z.writestr("word/media/x.png", buf.getvalue())
    git(repo, "add", "-A")
    found = " ".join(leaks(repo, private))
    assert "exact.png: is the photo of 23XXX0001" in found
    assert "small.jpg: looks like the photo of 23XXX0001" in found
    assert "r.docx!word/media/x.png" in found


def test_a_different_picture_is_not_flagged(repo, private):
    im = Image.new("RGB", (300, 300), (255, 255, 255))
    ImageDraw.Draw(im).ellipse([20, 20, 280, 280], fill=(10, 120, 30))
    im.save(repo / "figure.png")
    git(repo, "add", "-A")
    assert leaks(repo, private) == []


# --- the Lua filter: blank lines stay, personal details replace them ---------------------------------------

pandoc = shutil.which("pandoc") or str(Path.home() / ".local/bin/pandoc")


@pytest.mark.skipif(not Path(pandoc).is_file(), reason="pandoc not installed")
def test_filter_writes_blank_lines_without_details_and_values_with_them(tmp_path):
    def run(md):
        src, out = tmp_path / "t.md", tmp_path / "t.docx"
        src.write_text(md)
        r = subprocess.run([pandoc, str(src), "--from", "markdown+fenced_divs", "--lua-filter",
                            str(ROOT / "docs/report/template/thesis.lua"), "-o", str(out)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        with zipfile.ZipFile(out) as z:
            return z.read("word/document.xml").decode()

    public = run(DIVS)
    assert public.count("_" * 30) == 2 * 4 and "Photo</w:t>" in public and "9000000001" not in public
    st = biodata.personalise(DIVS, [biodata.Student(**{k: v for k, v in FAKE[0].items()}, photo_path=Path("x")),
                                    biodata.Student(**{k: v for k, v in FAKE[1].items()}, photo_path=None)])
    personal = run(st)
    assert "9000000001" in personal and "1 Test Road, Testville" in personal and "[[photo:23XXX0001]]" in personal
    assert personal.count("[[photo:") == 1 and personal.count("Photo</w:t>") == 1     # student two: no photo, empty box
    assert "_" * 30 not in personal
