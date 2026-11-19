# Page budget (report.pdf, at most 57 pages, everything counted)

The faculty asked for a professional report of at most 57 pages: no source code in the report,
only the important content (objectives, method, progress, results, discussion, references), and
the code reached through the GitHub repository (<https://github.com/Pilli9375/trafficsense>).
The report was 131 pages. This file is the plan; the last column is filled in from the built PDF.

**What is not allowed to change** to reach the limit: page size, margins, Times New Roman 12,
1.5 line spacing, justification, heading and caption styles, chapter order and chapter-opening
pages, roman front matter / Arabic body, the contents and the lists, biodata, the NOTE page
(`format_spec.md`). Only the content is cut.

**Nothing is thrown away.** Cut material (full per-run tables, prompt versions v1 to v3, the
configuration files, long derivations, literature detail, the validation walk-through) is moved
to `docs/report/extended/` as Markdown, with its numbers tagged and checked by
`scripts/make_report.py --check` like the report's own. The report links to it.

| Part | Was | Budget | Stays in the report | Moves to `extended/` |
|---|---:|---:|---|---|
| Front matter (title, certificate, acknowledgements, abstract, contents 2, list of tables, list of figures) | 10 | 8 | all of it; shorter table and figure titles, contents to level 2 plus the 3-level 2.4.x | (nothing) |
| Ch 1 Introduction | 10 | 6 | objectives, contributions, scope, a ~3-page literature survey, organisation (with the GitHub link), team table | the long literature detail, Webster / MaxPressure derivations |
| Ch 2 Proposed System and Methodology | 23 | 12 | system, decision loop, controller variants, ambulance handling, camera-error layer, scenario and validation summary, experimental method, pre-registration (condensed), standards, software and hardware tables | validation walk-through and the FixedTime bug detail, demand calibration, dataset and training detail, fairness and statistics detail |
| Ch 3 Cost Analysis | 3 | 2 | the cost table, a short "not costed" note | the long deployment list |
| Ch 4 Results and Discussions | 26 | 16 | every headline result with its table or figure: baselines, LLM arms vs MaxPressure, ambulances, model size (exploratory), camera errors and the decomposition, detector, dashboard (smaller screenshots), discussion, threats to validity | every per-run table, design-round detail, the benchmark choice tables |
| Ch 5 Conclusion and Future Work | 2 | 2 | all | (nothing) |
| Ch 6 Appendix | 49 | 3 | source code and reproducibility (GitHub link, commit hash, 5 commands), one configuration table, abbreviations, pointer to `extended/` | configuration files, all prompts, reproducibility detail, full tables |
| References | 3 | 3 | only the entries cited, numbered in citation order | (nothing) |
| Biodata | 4 | 4 | one page per student | (nothing) |
| NOTE page | 1 | 1 | as is | (nothing) |
| **Total** | **131** | **57** | | |

**Removed outright:** every source-code listing (Section "Source Code", Table 6.7). Short
file and function names in the text stay.

**Justification of the budget.** It is the one suggested, unchanged. The reductions are large in
Ch 2 (23 to 12) and Ch 4 (26 to 16), but those chapters are where most of the repeated
explanation sits (the same pre-registration rule and the same scenario facts are explained in
Ch 1, Ch 2, Ch 4 and the appendix), so the cut is mostly de-duplication. Front matter is 8 pages
only if the contents fit on two pages and the two lists on one page each; that is done by
shortening titles, not by changing spacing.

**Rules the cut follows.** Every number that stays keeps its tag. No pre-registration or
exploratory label, limitation or threat to validity is weakened. Nothing is invented: a sentence
is shortened or moved, never made stronger.

## Final page map

Filled in at the end of the work from the built PDFs (public and personal).
