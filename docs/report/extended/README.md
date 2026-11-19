# Extended material of the project report

The project report (`docs/report/report.pdf`, at most 57 pages) was written for the college's
capstone format and keeps only the important content: objectives, method, progress, results,
discussion and references. Everything that did not fit is kept here, as plain Markdown, so nothing
is lost. The full source code is in this repository (<https://github.com/Pilli9375/trafficsense>);
the report prints none of it.

| File | What it holds | Where the report summarises it |
|---|---|---|
| [`01_literature_survey.md`](01_literature_survey.md) | the full background and literature survey, with Webster's and MaxPressure's formulas and the comparison table | Section 1.2 |
| [`02_system_and_method.md`](02_system_and_method.md) | simulation layer, decision loop, validation against CoLLMLight's code, the FixedTime bug, scenario and demand calibration, detector dataset and training, error model, experimental method, pre-registration | Chapter 2 |
| [`03_results_full.md`](03_results_full.md) | the complete results chapter: every per-run table, the design rounds of the LLM benchmark, discussion, threats to validity | Chapter 4 |
| [`04_prompts.md`](04_prompts.md) | every prompt version (v1, v2, v3, guided, guided v3), an example user message, a logged decision | Section 2.1 |
| [`05_configuration.md`](05_configuration.md) | the configuration files in force | Table 6.1 |
| [`06_reproducibility.md`](06_reproducibility.md) | the full command list, the fresh-clone check, data not in the repository | Chapter 6 |
| [`07_full_tables.md`](07_full_tables.md) | every baseline run, the tuning sweep, the validation tables, benchmark choices, hosted-model runs | Chapter 4 |
| [`08_deployment_not_costed.md`](08_deployment_not_costed.md) | what a real deployment would additionally need (not costed) | Chapter 3 |

**How to read these files.** They are the full text of sections the report condenses, converted
from the report's Pandoc source to plain Markdown: a reference such as "section “Validation”"
names the section by its title, and a citation such as `[webster1958]` is a key of
[`../references.bib`](../references.bib). Every number is tagged and checked against `outputs/` by
`python scripts/make_report.py --check`, exactly like the report's own numbers; the tables are
generated from `outputs/`.
