# Project report

The report is in the college's capstone thesis format (`format_spec.md`). It is written as Markdown
chapters (`NN_*.md`, built in file-name order) and built into **`report.docx`, the master**, and
`report.pdf`, LibreOffice's conversion of that same Word file. Both are committed so they can be
read without building.

```bash
python scripts/make_report.py                 # regenerate tables, figures and tagged numbers from outputs/
python scripts/make_report.py --check         # fail if any number differs from outputs/ (also run by pytest)
python scripts/build_report.py                # check, build report.docx and report.pdf, check the format
python scripts/build_report.py --pages 1-12   # also render those PDF pages to build/pages/ (git-ignored)
python scripts/check_report_format.py         # the built files against format_spec.md (also run by pytest)
```

**Order.** `00_title_page.md` (title page and certificate), `02_acknowledgements.md`,
`03_abstract.md`, `04_lists.md` (contents and lists; the roman-numbered front matter ends here),
Chapters 1 to 6 (`10_` to `60_`), `70_references.md`, `80_biodata.md`, `90_note.md`.

**Tools.** pandoc 3 (`~/.local/bin`), LibreOffice (the AppImage extracted in
`~/.local/opt/libreoffice`; see the docstring of `scripts/build_report.py`) and `pypdfium2`. The
build needs two gitignored symlinks named in `configs/default.yaml`: `paths.thesis_format`, the
college's example thesis on D (its styles are the base of ours and its logo goes on the title
page; it is never committed), and `paths.report_fonts`, the Windows font folder (Times New Roman
and Consolas for the PDF, linked, not copied).

**How numbers are tied to the data.** Tables sit between `<!-- BEGIN:name -->` / `<!-- END:name -->`
markers and are written by `src/trafficsense/report/tables.py`. Any other number from the data
carries an invisible tag, `88.1<!--=f.off.mp.att-->`, naming a fact read from `outputs/`
(`src/trafficsense/report/facts.py`) or a cell of a table in a checked doc
(`<!--=docs/results.md | results_llm | peak & guarded | Latency mean-->`). Do not type a result
number untagged: the check fails on it. The only untagged numbers allowed besides years, counts
and references are the thesis identifiers in `numbers.THESIS_IDENTIFIERS` (register numbers,
Capstone ID, date, e-mail addresses). Figures in `figures/` are drawn from `outputs/` by
`src/trafficsense/report/figures.py`, each with a `.data.json` of the values plotted.

**How the Word file is made** (`docs/report/template/thesis.lua`, `src/trafficsense/report/thesis.py`).
Chapters, sections, figures (numbered through the report) and tables (numbered per chapter) are
numbered by the filter; captions carry Word `SEQ` fields, and the contents and both lists are live
Word fields. The build converts the Word file to PDF, reads the page of every entry and writes the
page numbers into the fields, and converts again until nothing changes, so the lists are right
before Word updates them. Word asks to update fields when the file is opened: answering *Yes* is
safe. The code listings of the appendix are generated from the files at the current commit (the
build refuses if they have uncommitted changes).

**By hand after printing.** The certificate's examiner signatures and the Program Chair's and
Dean's names and signatures, and each student's mobile number, permanent address and photo
(biodata), are blank lines or boxes in the Word file, to be filled by hand or typed over in Word
for the printed copy. Never commit real phone numbers or addresses. Points for the team to
confirm are in `CONTRIBUTIONS_TO_CONFIRM.md`.

## References to verify

Every entry in `references.bib` is a real publication. These are the ones whose details you
should check against the source before submission:

* `lai2023llmlight` (LLMLight): cited as the arXiv preprint 2312.16044. Some listings give a KDD 2025
  publication; if your guide prefers the conference version, check the proceedings entry.
* `umapathi2019pcu` (JETIR 2019): the first author's full name and the page numbers (89–93) are as
  given in the project's scenario documentation; check them against the article.
* `itrans2009` (Two- and Three-Wheelers in India): a project report; the table and page numbers
  (Table 15, p. 35) were checked when the scenario was built, the publisher fields are ours.
* `nemotron3ultra`: a model card, not a paper; the access date is when the model was first called.
* `ollama`, `jocher2023yolov8`: software, cited by their repositories.
* The IDD terms of use could not be checked online; read them on the dataset's download page
  (idd.insaan.iiit.ac.in) and make sure the acknowledgement meets them.
