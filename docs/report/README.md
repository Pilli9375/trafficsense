# Project report

The report is written as Markdown chapters (`NN_*.md`, built in file-name order) and built into
`report.docx` and `report.pdf`, which are committed so they can be read without building.

```bash
python scripts/make_report.py           # regenerate tables, figures and tagged numbers from outputs/
python scripts/make_report.py --check   # fail if any number differs from outputs/ (also run by pytest)
python scripts/build_report.py          # check, then build report.docx and report.pdf
python scripts/build_report.py --pages 1-12   # also render those PDF pages to build/pages/ (git-ignored)
```

**Tools.** pandoc 3 and Tectonic (a self-contained LaTeX engine). Both are single binaries;
`build_report.py` finds them on `PATH` or in `~/.local/bin`. Tectonic downloads the LaTeX packages
it needs on its first run. `pypdfium2` (in `.venv`) renders pages for the layout check.

**How numbers are tied to the data.** Tables sit between `<!-- BEGIN:name -->` / `<!-- END:name -->`
markers and are written by `src/trafficsense/report/tables.py`. Any other number from the data
carries an invisible tag, `88.1<!--=f.off.mp.att-->`, naming a fact read from `outputs/`
(`src/trafficsense/report/facts.py`) or a cell of a table in a checked doc
(`<!--=docs/results.md | results_llm | peak & guarded | Latency mean-->`). Do not type a result
number untagged: the check fails on it. `python scripts/make_report.py --sources` lists every
tagged number's source file. Figures in `figures/` are drawn from `outputs/` by
`src/trafficsense/report/figures.py`, each with a `.data.json` of the values plotted.

**What the build checks.** The PDF's figure, table, chapter and section numbers must equal the Word
file's; no text or table may run into the margin; every page must be A4 (wide tables are on A4
landscape pages); there must be no undefined reference.

**Word file.** Word asks to update fields when the file is opened: answer *Yes* to fill the
contents and the lists of figures and tables. Page numbers are in the footer.

## Before submitting: fill in the placeholders

`00_front_matter.md` (title page, certificate, declaration, acknowledgement) has placeholders in
double braces. Replace them in the Markdown and rebuild, or edit the Word file directly:

`{{DEGREE}}`, `{{BRANCH}}`, `{{STUDENT_NAME_1..3}}`, `{{ROLL_NUMBER_1..3}}`, `{{GUIDE_NAME}}`,
`{{GUIDE_DESIGNATION}}`, `{{GUIDE_THANKS}}`, `{{HOD_NAME}}`, `{{PRINCIPAL_NAME}}`, `{{DEPARTMENT}}`,
`{{COLLEGE}}`, `{{COLLEGE_LOGO}}`, `{{UNIVERSITY}}`, `{{CITY}}`, `{{MONTH}}`, `{{YEAR}}`,
`{{ACADEMIC_YEAR}}`, `{{VIVA_DATE}}`, `{{REVIEW_COMMITTEE}}`, `{{PLACE}}`, `{{DATE}}`,
`{{PERSONAL_THANKS}}`. With fewer than three students, delete the unused name lines. For a logo,
put the image in `figures/` and replace `{{COLLEGE_LOGO}}` with `![](figures/logo.png){width=30%}`.
Check your university's format (margins, font, spacing, binding side) against
`template/metadata.yaml` and `template/preamble.tex`: A4, 12 pt, 1.5 line spacing, 1.5 inch
left margin.

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
