"""The README / report number checker (trafficsense.report)."""
import subprocess
import sys
from pathlib import Path

import pytest

from trafficsense.config import repo_root
from trafficsense.report import numbers
from trafficsense.report.facts import Fact, facts

ROOT = repo_root()
FS = {"a": Fact(88.13342, "x.json"), "neg": Fact(-1.5445, "x.json"), "big": Fact(2177.0, "x.json"),
      "zero": Fact(0.0, "x.json")}


class NoTables(numbers.DocTables):
    def __init__(self):
        super().__init__(ROOT)


def check(text):
    return numbers.check_tags(text, FS, NoTables())[0]


def test_matching_number_passes_at_any_shown_precision():
    assert check("ATT 88.1<!--=a--> s, 88<!--=a-->, 88.133<!--=a-->") == []


def test_wrong_number_fails_and_says_what_the_data_says():
    probs = check("ATT 88.2<!--=a--> s")
    assert len(probs) == 1 and "88.1" in probs[0].message


def test_sign_percent_unicode_minus_and_commas():
    assert check("−1.5%<!--=neg--> and -1.54%<!--=neg--> and 2,177<!--=big--> and +0.0%<!--=zero-->") == []
    assert check("+1.5%<!--=neg-->") != []


def test_unknown_key_fails():
    assert "unknown fact" in check("1.0<!--=nope-->")[0].message


def test_refresh_rewrites_to_the_data_keeping_the_format():
    out = numbers.refresh_tags("x 90.0<!--=a--> y +9.9%<!--=neg-->", FS, NoTables())
    assert out == "x 88.1<!--=a--> y -1.5%<!--=neg-->"


def test_table_cell_reference(tmp_path):
    (tmp_path / "d.md").write_text("<!-- BEGIN:t -->\n| Name | ATT (s) |\n|---|---|\n"
                                   "| MaxPressure | 88.1 ± 1.0 |\n| Webster | 100.4 ± 4.1 |\n<!-- END:t -->\n")
    dt = numbers.DocTables(tmp_path)
    ok = "88.1<!--=d.md | t | MaxPressure | ATT--> ± 4.1<!--=d.md | t | Webster | ATT | 1-->"
    assert numbers.check_tags(ok, {}, dt)[0] == []
    assert numbers.check_tags("88.2<!--=d.md | t | MaxPressure | ATT-->", {}, dt)[0]
    assert "matches 2 rows" in numbers.check_tags("1<!--=d.md | t | e | ATT-->", {}, dt)[0][0].message


def test_lint_flags_untagged_measurements_only():
    text = ("MaxPressure's ATT was 88.1 s in 2024, see Section 7.2 and Table 7.1 [12].\n"
            "We used 3 seeds on a GTX 1650 with Python 3.10, `run 3600` and 640<!--=a-->.\n"
            "1. first item\n<!-- BEGIN:t -->\n| 99.9 |\n<!-- END:t -->\n")
    probs = numbers.lint(text)
    assert [p.message for p in probs] == ["untagged number 88.1"]
    assert numbers.lint("a queue of 17 vehicles") and numbers.lint("+4.8% slower")


def test_every_fact_names_its_source_file():
    fs = facts(ROOT)
    assert len(fs) > 500
    for k, f in fs.items():
        assert (ROOT / f.source).is_file(), k


def test_readme_and_report_match_outputs():
    r = subprocess.run([sys.executable, "scripts/make_report.py", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_refresh_keeps_the_text_format_of_a_cell_reference(tmp_path):
    (tmp_path / "d.md").write_text("<!-- BEGIN:t -->\n| Name | Share |\n|---|---|\n| car | 45.1% |\n<!-- END:t -->\n")
    dt = numbers.DocTables(tmp_path)
    text = "cars are 45.1<!--=d.md | t | car | Share-->% and 40.0<!--=d.md | t | car | Share-->%"
    assert numbers.refresh_tags(text, {}, dt) == ("cars are 45.1<!--=d.md | t | car | Share-->% and "
                                                  "45.1<!--=d.md | t | car | Share-->%")


def _pandoc():
    import shutil
    pandoc = shutil.which("pandoc") or str(Path.home() / ".local/bin/pandoc")
    if not Path(pandoc).is_file():
        pytest.skip("pandoc not installed")
    return pandoc


def _filter(tmp_path, md, to="plain"):
    import json
    import os
    src = tmp_path / "t.md"
    src.write_text(md)
    out = tmp_path / "n.json"
    r = subprocess.run([_pandoc(), str(src), "--lua-filter", str(ROOT / "docs/report/template/thesis.lua"),
                        "-M", "logo=x.png", "-t", to], capture_output=True, text=True,
                       env={**os.environ, "REPORT_NUMBERS_JSON": str(out)})
    assert r.returncode == 0, r.stderr
    return {k: v["num"] for k, v in json.loads(out.read_text()).items()}, r.stdout


def test_filter_numbers_figures_continuously_and_tables_per_chapter(tmp_path):
    md = ("# Front {.unnumbered}\n\n# One {#sec:one}\n\n## Part {#sec:part}\n\n#### Minor {#sec:minor}\n\n"
          "![a. More.](x.png){#fig:a}\n\n::: {#tbl:t}\n| a | b |\n|---|---|\n| 1 | 2 |\n\n: cap\n:::\n\n"
          "# Two\n\n![b](x.png){#fig:b}\n\n::: {#tbl:u}\n| a |\n|---|\n| 1 |\n\n: cap\n:::\n\n"
          "See @fig:b, @tbl:u, @sec:part, @sec:minor and @sec:one.\n")
    nums, out = _filter(tmp_path, md)
    assert nums == {"sec:one": "1", "sec:part": "1.1", "sec:minor": "1.1", "fig:a": "1", "tbl:t": "1.1",
                    "fig:b": "2", "tbl:u": "2.1", "two": "2"}
    assert "See Figure 2, Table 2.1, Section 1.1, Section 1.1 and Chapter 1." in out.replace("\u00a0", " ")


def test_filter_captions_carry_seq_fields_and_keep_all_text(tmp_path):
    md = ("# One\n\n![Short title. The long explanation stays.](x.png){#fig:a}\n\n"
          "![Whole caption kept, e.g. this.](x.png){#fig:b short=\"Given title\"}\n\n"
          "::: {#tbl:t}\n| a |\n|---|\n| 1 |\n\n: First table. Note.\n:::\n\n"
          "::: {#tbl:u}\n| a |\n|---|\n| 1 |\n\n: Second.\n:::\n")
    _, xml = _filter(tmp_path, md, to="native")
    assert "SEQ Figure \\\\* ARABIC" in xml
    assert xml.count("SEQ Table \\\\* ARABIC \\\\r 1") == 1          # only the chapter's first table restarts
    assert '"Short"' in xml and '"title"' in xml and '"explanation"' in xml
    assert '"Given"' in xml and '"Whole"' in xml                       # short= title, whole caption as the note


def test_merged_styles_take_the_spec_values():
    from trafficsense.report import thesis
    college = ('<w:styles><w:docDefaults><w:rPrDefault/></w:docDefaults>'
               '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
               '<w:rPr><w:rFonts w:ascii="Calibri Light"/></w:rPr></w:style>'
               '<w:style w:type="paragraph" w:styleId="Header"><w:name w:val="header"/></w:style></w:styles>')
    pandoc = '<w:styles><w:style w:type="paragraph" w:styleId="Definition"><w:name w:val="Definition"/></w:style></w:styles>'
    out = thesis.merged_styles(college, pandoc)
    assert "Calibri Light" not in out and 'w:styleId="Header"' in out and 'w:styleId="Definition"' in out
    h1 = out[out.index('w:styleId="Heading1"'):]
    assert '<w:sz w:val="28"/>' in h1[:900] and "<w:pageBreakBefore/>" in h1[:900]
    assert "Times New Roman" in out[:out.index("</w:docDefaults>")]


def test_page_numbers_roman_front_matter_and_arabic_body():
    from trafficsense.report import thesis
    doc = ('<w:p><w:r><w:instrText> TC "Abstract" \\l 1 </w:instrText></w:r><w:r><w:t>Abstract</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>CHAPTER 1</w:t></w:r><w:r><w:instrText> TC "1\u2003Intro" \\l 1 </w:instrText></w:r></w:p>'
           '<w:p><w:r><w:t>1.1\u2003Aims</w:t></w:r><w:r><w:instrText> TC "1.1\u2003Aims" \\l 2 </w:instrText></w:r></w:p>'
           '<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>Figure 1 A plot</w:t></w:r>'
           '<w:r><w:instrText> SEQ Figure </w:instrText></w:r></w:p>')
    es = thesis.entries(doc)
    pages = ["title", "ABSTRACT\ntext", "contents: Abstract iii\n1.1 Aims 1", "CHAPTER 1\nINTRO", "1.1 Aims\nFigure 1 A plot"]
    thesis.page_numbers(es, pages)
    assert [(e.kind, e.text, e.page) for e in es] == [("toc", "Abstract", "ii"), ("toc", "1  Intro", "1"),
                                                     ("toc", "1.1  Aims", "2"), ("lof", "Figure 1 A plot", "2")]


def test_thesis_identifiers_are_allowed_but_nothing_else():
    assert numbers.lint("MYLAPALLI ABHISHEK RAJ (23BCE9470), AMARAVATI- 522237, Fall Semester 2026-27, "
                        "abhishek.23bce9470@vitapstudent.ac.in, Capstone Project ID: 3328F4C8") == []
    assert numbers.lint("PIN 522238") != []


def test_built_report_follows_the_college_format():
    """The committed report.docx / report.pdf against docs/report/format_spec.md."""
    if not (ROOT / "docs/report/report.docx").is_file():
        pytest.skip("report not built")
    r = subprocess.run([sys.executable, "scripts/check_report_format.py"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
