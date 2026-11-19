"""Check the team's study handbook (docs/handbook/*.md and its PDF).

    python scripts/check_handbook.py

1. Numbers. Every tagged number (`88.1<!--=f.off.mp.att-->`) must equal the data, exactly as the
   report's check does (trafficsense.report.numbers). Every untagged decimal or percentage is an
   error (it must be tagged). Every other untagged number above the small counts must appear in
   the report sources: the deck (slide text and speaker notes), README.md, docs/*.md,
   docs/report/*.md and docs/report/extended/*.md.
2. Coverage. A heading "Slide N: <title>" for each of the deck's slides, with the title read from
   the PPTX, and a section for each dashboard page named in dashboard/app.py.
3. Privacy. No phone numbers, PIN codes, e-mail addresses or address words; and, when the private
   biodata file exists, none of the students' private details (searched in the Markdown and in the
   PDF's text).
4. Placeholders. No TODO / TBD / FIXME / XXX / lorem / `{{...}}` / `[placeholder]` left over.
5. Member speaking guides (docs/handbook/members/<Name>.md and .pdf): all four exist, each PDF has
   3 to 4 pages, each has the eight parts and the same "project in 30 seconds" text, the numbers,
   privacy and placeholder checks above, and none of the outdated claims of the old pre-restart
   contribution sheets (BANNED).

Exit 1 on any problem.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root, resolve_path
from trafficsense.report import numbers
from trafficsense.report.facts import facts

ROOT = repo_root()
HB = ROOT / "docs/handbook"
PDF = HB / "TrafficSense_Study_Handbook.pdf"
DECK = ROOT / "docs/ppt/TrafficSense_Capstone_Final_Review.pptx"
APP = ROOT / "src/trafficsense/dashboard/app.py"

# Numbers that are not results: slide / part / question references and the reading plan's minutes.
HANDBOOK_CONTEXT = [
    re.compile(r"\b(?:Slides?|slides?|Parts?|part|[Qq]uestions?)\s+\d+(?:\s*(?:–|-|,|and|to)\s*\d+)*"),
    re.compile(r"(?<![\d.,])\d{1,3}\s+minutes?\b"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),                     # clock times in the time plans
    # definitions, not results: the IoU thresholds of mAP, a percentile, the browser zoom
    re.compile(r"IoU (?:is )?(?:at least )?0\.5|from 0\.5 to 0\.95|\b95% of|zoom at 100%"),
]


MEMBERS = HB / "members"
MEMBER_NAMES = ["Bhargav_Kumar", "Akul_Lakhan", "Darsi_Amit", "Abhishek_Raj"]
MEMBER_PARTS = ["The Project in 30 Seconds", "My Part in Plain Words", "What to Say", "My Slides and Dashboard Pages",
                "My Key Numbers", "Likely Questions About My Part", "Do Not Claim", "Five Terms I Must Explain Simply"]
# Outdated claims of the old individual contribution sheets, written before the project restart.
BANNED = re.compile(r"YOLOv8[ms]\b|70\.5\s*%|RTX\s*4050|random[- ]baseline|\b360[- ]?(?:step|s\b)|mock\s+(?:Ollama|LLM|server)",
                    re.I)


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def chapters() -> list[Path]:
    return sorted(HB.glob("[0-9][0-9]_*.md"))


def deck_slides() -> list[tuple[str, str]]:
    """(title, all text incl. notes) per slide. The title: slide 1 = the project title, slide 2 =
    the outline heading, slides 3-16 = the second text box (first line), slide 17 = its title
    placeholder, the closing slide = its link text."""
    from pptx import Presentation
    out = []
    for i, s in enumerate(Presentation(DECK).slides, 1):
        texts = [sh.text_frame.text.strip() for sh in s.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip() and not sh.text_frame.text.strip().isdigit()]
        allt = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
        allt += [c.text for sh in s.shapes if sh.has_table for r in sh.table.rows for c in r.cells]
        if s.has_notes_slide:
            allt.append(s.notes_slide.notes_text_frame.text)
        if s.shapes.title is not None:
            title = s.shapes.title.text.strip()
        elif i == 1:
            title = texts[0].splitlines()[-1]
        elif len(texts) > 1 and not texts[1].startswith("GitHub"):
            title = texts[1].splitlines()[0] if i > 2 else texts[0]
        else:
            title = texts[0].splitlines()[0]
        out.append((" ".join(title.split()), "\n".join(allt)))
    return out


def corpus_numbers(deck_text: str) -> set[str]:
    files = [ROOT / "README.md"] + sorted((ROOT / "docs").glob("*.md")) + sorted((ROOT / "docs/report").glob("*.md")) \
        + sorted((ROOT / "docs/report/extended").glob("*.md"))
    text = deck_text + "\n".join(f.read_text() for f in files)
    return {n.replace("−", "-").lstrip("+-") for n in re.findall(numbers.NUM, text)}


def check_numbers(text: str, where: str, fs, dt, corpus: set[str]) -> list[str]:
    errs = [f"{where}: {p}" for p in numbers.check_tags(text, fs, dt)[0]]
    t = text
    for p in numbers._STRIP:                           # code, comments, tags, links ... as the report lint
        t = numbers._blank(t, p)
    for p in [re.compile(x) for x in numbers.ALLOWED_PHRASES] + [re.compile(re.escape(x)) for x in numbers.THESIS_IDENTIFIERS] \
            + [numbers._CONTEXT, numbers._YEAR, numbers._CITE, numbers._LIST] + HANDBOOK_CONTEXT:
        t = numbers._blank(t, p)
    for m in numbers._STANDALONE.finditer(t):
        s = m.group(0)
        ln = numbers.line_of(t, m.start())
        line = text.splitlines()[ln - 1].strip()[:100]
        if "." in s or s.endswith("%"):
            errs.append(f"{where}: line {ln}: untagged decimal or percentage {s}: {line!r}")
            continue
        v = s.replace("−", "-").lstrip("+-")
        if abs(int(v.replace(",", ""))) <= 12:
            continue
        if v not in corpus:
            errs.append(f"{where}: line {ln}: number {s} is not in the report sources: {line!r}")
    return errs


PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)")
PIN = re.compile(r"(?<![\d,.])\d{6}(?![\d,.])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
ADDRESS = re.compile(r"\b(?:Permanent Address|Mobile|Phone No|D\.? ?No\.|H\.? ?No\.|Nagar|Colony|Mandal|District|PIN)\b")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|XXX|lorem ipsum)\b|\{\{[^}]*\}\}|\[placeholder\]|@@[A-Z]+@@", re.I)


def check_privacy(text: str, where: str) -> list[str]:
    errs = []
    for name, pat in (("phone number", PHONE), ("PIN code", PIN), ("e-mail address", EMAIL), ("address word", ADDRESS)):
        for m in pat.finditer(text):
            errs.append(f"{where}: possible {name}: {m.group(0)!r}")
    return errs


def private_details(text: str, where: str) -> list[str]:
    from trafficsense.report import biodata
    cfg = load_config("configs/default.yaml")
    students, why = biodata.load_optional(resolve_path(cfg, "biodata"), resolve_path(cfg, "biodata_photos"))
    if students is None:
        print(f"privacy: private biodata file not available ({why}); generic checks only")
        return []
    errs = []
    for s in students:
        if biodata._tolerant(s.mobile).search(text):
            errs.append(f"{where}: contains the phone number of {s.reg}")
        for v in (s.email, s.address):
            if v.lower() in text.lower():
                errs.append(f"{where}: contains the e-mail or address of {s.reg}")
    return errs


def pdf_text(pdf: Path = PDF) -> str | None:
    if not pdf.is_file():
        return None
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))


def check_members(fs, dt, corpus: set[str]) -> tuple[list[str], int]:
    import pypdfium2 as pdfium
    errs, ntags, intros = [], 0, {}
    for name in MEMBER_NAMES:
        md, pdf = MEMBERS / f"{name}.md", MEMBERS / f"{name}.pdf"
        rel = str(md.relative_to(ROOT))
        if not md.is_file():
            errs.append(f"{rel} is missing")
            continue
        text = md.read_text()
        ntags += len(numbers.TAG.findall(text))
        clean = numbers.TAG.sub(lambda m: m["num"], text)
        errs += check_numbers(text, rel, fs, dt, corpus)
        errs += check_privacy(clean, rel) + private_details(clean, rel)
        errs += [f"{rel}: leftover placeholder {m.group(0)!r}" for m in PLACEHOLDER.finditer(text)]
        errs += [f"{rel}: claim from the old contribution sheets: {m.group(0)!r}" for m in BANNED.finditer(clean)]
        heads = [" ".join(h.split()) for h in re.findall(r"^#\s+(.*?)\s*$", text, re.M)]
        if heads != MEMBER_PARTS:
            errs.append(f"{rel}: parts are {heads}, expected {MEMBER_PARTS}")
        m = re.search(r"^# The Project in 30 Seconds\n(.*?)\n# ", text, re.S | re.M)
        intros[name] = " ".join(m.group(1).split()) if m else ""
        pt = pdf_text(pdf)
        if pt is None:
            errs.append(f"{pdf.relative_to(ROOT)} is missing (python scripts/build_handbook.py --members)")
            continue
        n = len(pdfium.PdfDocument(str(pdf)))
        if not 3 <= n <= 4:
            errs.append(f"{pdf.name}: {n} pages, expected 3 to 4")
        errs += check_privacy(pt, pdf.name) + private_details(pt, pdf.name)
        errs += [f"{pdf.name}: claim from the old contribution sheets: {m.group(0)!r}" for m in BANNED.finditer(pt)]
        errs += [f"{pdf.name}: leftover placeholder {m.group(0)!r}" for m in PLACEHOLDER.finditer(pt)]
        if "<!--" in pt:
            errs.append(f"{pdf.name}: a number tag leaked into the PDF")
        if md.stat().st_mtime > pdf.stat().st_mtime:
            errs.append(f"{pdf.name} is older than {md.name}: rebuild it")
    if len(set(intros.values())) > 1:
        errs.append("the 'project in 30 seconds' text differs between the member guides")
    extra = MEMBERS / "TO_CONFIRM.md"
    if extra.is_file():
        errs += check_privacy(extra.read_text(), str(extra.relative_to(ROOT)))
    return errs, ntags


def main() -> None:
    files = chapters()
    if not files:
        sys.exit("no handbook chapters in docs/handbook/")
    fs, dt = facts(ROOT), numbers.DocTables(ROOT)
    slides = deck_slides()
    corpus = corpus_numbers("\n".join(t for _, t in slides))
    errs, ntags = [], 0
    full = ""
    for f in files:
        text = f.read_text()
        full += text + "\n"
        rel = str(f.relative_to(ROOT))
        ntags += len(numbers.TAG.findall(text))
        errs += check_numbers(text, rel, fs, dt, corpus)
        errs += check_privacy(numbers.TAG.sub(lambda m: m["num"], text), rel)
        errs += [f"{rel}: leftover placeholder {m.group(0)!r}" for m in PLACEHOLDER.finditer(text)]

    headings = [" ".join(h.split()) for h in re.findall(r"^#+\s+(.*?)\s*(?:\{[^}]*\})?$", full, re.M)]
    for i, (title, _) in enumerate(slides, 1):
        want = f"Slide {i}:"
        hit = [h for h in headings if h.startswith(want)]
        if not hit:
            errs.append(f"slide {i} ({title!r}) has no 'Slide {i}:' heading")
        elif i < len(slides) and squash(title) not in squash(hit[0]):
            errs.append(f"slide {i}: heading {hit[0]!r} does not carry the deck's title {title!r}")
        elif i == len(slides) and "github" not in hit[0].lower():
            errs.append(f"slide {i}: closing slide heading should name the GitHub link")
    pages = re.findall(r'st\.Page\([^)]*title="([^"]+)"', APP.read_text())
    if len(pages) != 4:
        errs.append(f"expected four dashboard pages in {APP.name}, found {pages}")
    for p in pages:
        if not any(h.startswith("Page") and h.endswith(p) for h in headings):
            errs.append(f"dashboard page {p!r} has no 'Page N: {p}' heading")

    clean = numbers.TAG.sub(lambda m: m["num"], full)
    errs += private_details(clean, "docs/handbook")
    pt = pdf_text()
    if pt is None:
        errs.append(f"{PDF.relative_to(ROOT)} is missing (build it first)")
    else:
        errs += check_privacy(pt, PDF.name)
        errs += private_details(pt, PDF.name)
        errs += [f"{PDF.name}: leftover placeholder {m.group(0)!r}" for m in PLACEHOLDER.finditer(pt)]
        if "<!--" in pt:
            errs.append(f"{PDF.name}: a number tag leaked into the PDF")

    merrs, mtags = check_members(fs, dt, corpus)
    errs += merrs

    if errs:
        print("\n".join(errs))
        print(f"{len(errs)} problem(s)")
        sys.exit(1)
    print(f"member guides OK: {len(MEMBER_NAMES)} guides, {mtags} tagged numbers match outputs/, 3-4 pages each, "
          "no old-sheet claims")
    print(f"handbook OK: {len(files)} chapters, {ntags} tagged numbers match outputs/, "
          f"{len(slides)} slides and {len(pages)} dashboard pages covered, no private data or placeholders")


if __name__ == "__main__":
    main()
