"""The capstone final-review deck: its checked text, its build and its checker."""
import hashlib
import re
import shutil
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Pt

from trafficsense.config import repo_root
from trafficsense.report import slides, slides_content as C

ROOT = repo_root()
DECK = slides.paths()[2]
TEMPLATE = slides.paths()[0]
needs_deck = pytest.mark.skipif(not DECK.is_file(), reason="deck not built")


def all_strings(spec: C.Slide):
    yield from spec.bullets
    yield from spec.table_labels
    for _, items in spec.columns:
        yield from items
    for t in spec.tables:
        if isinstance(t, C.Literal):
            yield from t.header
            for r in t.rows:
                yield from r


def test_tagged_number_is_checked_and_tag_removed():
    assert slides.prep("MaxPressure ATT 88.1<!--=f.off.mp.att--> s", "t") == "MaxPressure ATT 88.1 s"


def test_wrong_tag_untagged_number_and_unknown_key_fail():
    with pytest.raises(slides.SourceError):
        slides.prep("ATT 99.9<!--=f.off.mp.att--> s", "t")
    with pytest.raises(slides.SourceError):
        slides.prep("ATT 88.1 s", "t")
    with pytest.raises(slides.SourceError):
        slides.prep("ATT 88.1<!--=f.no.such.key--> s", "t")


def test_markup_runs():
    assert slides.runs_of("a **b** `c`") == [("a ", False), ("b", True), (" c", False)]


@pytest.mark.parametrize("key", list(C.SLIDES))
def test_every_slide_text_and_notes_pass_the_report_checker(key):
    spec = C.SLIDES[key]
    for text in all_strings(spec):
        slides.prep(text, f"slide {key}")
    notes = slides.prep(spec.notes, f"notes {key}")
    assert 3 <= len([x for x in re.split(r"(?<=[.!?])\s+", notes) if x]) <= 5
    assert len(spec.bullets) + sum(len(i) for _, i in spec.columns) <= 5


def test_the_deck_has_the_template_slides_plus_at_most_two_extra_outcome_slides():
    keys = slides.ORDER
    assert len(keys) <= 18 and keys[:12] == [str(i) for i in range(1, 13)] and keys[-3:] == ["14", "15", "16"]
    assert set(C.SLIDES) == set(keys)


def test_report_tables_resolve_to_one_row_and_column_each():
    for spec in C.SLIDES.values():
        for t in spec.tables:
            if isinstance(t, C.Table):
                header, rows = slides.table_cells(t)
                assert len(rows) == len(t.rows) and all(len(r) == len(header) for r in rows)


def test_bibliography_is_the_reports_text():
    refs = slides.references()
    assert len(refs) >= 25 and all(n in refs for n in C.BIBLIOGRAPHY) and 6 <= len(C.BIBLIOGRAPHY) <= 8
    assert "Webster" in refs[1] and "CoLLMLight" in refs[8]


@needs_deck
def test_committed_deck_passes_every_check():
    assert slides.check(DECK) == []


def mutate(tmp_path, fn) -> list[str]:
    path = tmp_path / "deck.pptx"
    shutil.copyfile(DECK, path)
    prs = Presentation(str(path))
    fn(prs)
    prs.save(str(path))
    return slides.check(path)


def first_body_run(slide):
    return next(r for sh in slide.shapes if sh.name == "Bullets" for p in sh.text_frame.paragraphs for r in p.runs)


@needs_deck
@pytest.mark.parametrize("name,fn,expect", [
    ("placeholder", lambda p: setattr(first_body_run(p.slides[2]), "text", "[Title of the Project]"), "placeholder"),
    ("phone", lambda p: setattr(first_body_run(p.slides[2]), "text", "call 9876543210"), "phone"),
    ("address", lambda p: setattr(first_body_run(p.slides[2]), "text", "write to a@b.com"), "e-mail"),
    ("new number", lambda p: setattr(first_body_run(p.slides[2]), "text", "ATT fell by 73.31 s"), "73.31"),
    ("small font", lambda p: setattr(first_body_run(p.slides[2]).font, "size", Pt(12)), "minimum"),
    ("no notes", lambda p: setattr(p.slides[4].notes_slide.notes_text_frame, "text", ""), "no speaker notes"),
    ("long notes", lambda p: setattr(p.slides[4].notes_slide.notes_text_frame, "text", "A. B. C. D. E. F."), "sentences"),
    ("title", lambda p: setattr(next(s for s in p.slides[3].shapes if s.name == "TextShape 1").text_frame.paragraphs[0].runs[0], "text", "Other"), "title"),
    ("overflow", lambda p: setattr(next(s for s in p.slides[6].shapes if s.name == "Bullets"), "height", 400000), "tall but its box"),
])
def test_checker_catches(tmp_path, name, fn, expect):
    probs = mutate(tmp_path, fn)
    assert any(expect in x for x in probs), probs


@needs_deck
def test_checker_catches_missing_github_link_and_photo(tmp_path):
    def drop(prs):
        last = prs.slides[len(prs.slides) - 1]
        for sh in last.shapes:
            if sh.name == "GitHub link":
                sh.text_frame.paragraphs[0].runs[0].text = "GitHub"
    assert any("GitHub link missing" in x for x in mutate(tmp_path, drop))

    def photo(prs):
        s = prs.slides[2]
        s.shapes.add_picture(str(ROOT / "docs/ppt/figures/agent_loop_slide.png"), 0, 0).name = "Photo"
        pic = s.shapes[-1]
        pic._element.nvPicPr.cNvPr.set("descr", "a photo")
        from PIL import Image
        Image.new("RGB", (20, 20), "red").save(tmp_path / "x.png")
        s.shapes.add_picture(str(tmp_path / "x.png"), 0, 0).name = "Photo2"
    assert any("not a report figure" in x for x in mutate(tmp_path, photo))


@pytest.mark.skipif(not TEMPLATE.is_file(), reason="university template not present")
def test_build_from_template_is_clean_and_leaves_the_template_alone(tmp_path):
    before = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    out = slides.build(out=tmp_path / "d.pptx", work=tmp_path / "w")
    assert hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() == before
    assert slides.check(out) == []
    prs = Presentation(str(out))
    assert len(prs.slides) == 18
