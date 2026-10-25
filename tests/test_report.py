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


def _build_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_report", ROOT / "scripts/build_report.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_short_captions_use_the_first_sentence():
    b = _build_module()
    tex = r"\caption{System architecture. The {simulator} holds it.}\label{fig:a} \caption{One sentence only.}"
    assert b.short_captions(tex) == (r"\caption[System architecture.]{System architecture. The {simulator} holds it.}"
                                     r"\label{fig:a} \caption{One sentence only.}")


def test_filter_numbers_figures_tables_and_appendices(tmp_path):
    import json
    import shutil
    pandoc = shutil.which("pandoc") or str(Path.home() / ".local/bin/pandoc")
    if not Path(pandoc).is_file():
        pytest.skip("pandoc not installed")
    md = ("# Front {.unnumbered}\n\n# One {#sec:one}\n\n## Part {#sec:part}\n\n![a](x.png){#fig:a}\n\n"
          "::: {#tbl:t}\n| a | b |\n|---|---|\n| 1 | 2 |\n\n: cap\n:::\n\n# Two\n\n![b](x.png){#fig:b}\n\n"
          "# Extra {.appendix #sec:app}\n\n![c](x.png){#fig:c}\n\nSee @fig:b, @tbl:t, @sec:part and @sec:app.\n")
    src = tmp_path / "t.md"
    src.write_text(md)
    out = tmp_path / "n.json"
    r = subprocess.run([pandoc, str(src), "--lua-filter", str(ROOT / "docs/report/template/report.lua"),
                        "-t", "plain"], capture_output=True, text=True,
                       env={**__import__("os").environ, "REPORT_NUMBERS_JSON": str(out)})
    assert r.returncode == 0, r.stderr
    nums = {k: v["num"] for k, v in json.loads(out.read_text()).items()}
    assert nums == {"sec:one": "1", "sec:part": "1.1", "fig:a": "1.1", "tbl:t": "1.1", "fig:b": "2.1",
                    "sec:app": "A", "fig:c": "A.1", "two": "2"}
    assert "See Figure 2.1, Table 1.1, Section 1.1 and Appendix A." in r.stdout
