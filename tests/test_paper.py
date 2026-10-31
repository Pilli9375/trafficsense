"""The IEEE paper's number checker (trafficsense.report.paper, scripts/make_paper.py)."""
import subprocess
import sys

from trafficsense.config import repo_root
from trafficsense.report import numbers, paper
from trafficsense.report.facts import Fact

ROOT = repo_root()
FS = {"a": Fact(88.13342, "x.json"), "neg": Fact(-1.5445, "x.json")}
DOC = "\\documentclass{x}\n\\newcommand{\\V}[2]{#2}\n\\setlength{\\x}{99pt}\n\\begin{document}\n"


def tags(text):
    return paper.check_tags(text, FS, numbers.DocTables(ROOT))[0]


def test_tags_match_at_the_shown_precision_and_sign():
    assert tags("ATT \\V{a}{88.1}~s, \\V{a}{88}, \\V{neg}{-1.5}\\% and \\V{neg}{-1.54}") == []
    assert "data says 88.1" in tags("\\V{a}{88.2}")[0].message
    assert tags("\\V{neg}{+1.5}") and "unknown fact" in tags("\\V{nope}{1.0}")[0].message


def test_malformed_tags_fail_but_comments_are_ignored():
    assert "malformed" in tags("\\V{a}{about 88}")[0].message
    assert tags("% write numbers as \\V{key}{number}\n") == []


def test_table_cell_keys_may_contain_bars_and_ampersands(tmp_path):
    (tmp_path / "d.md").write_text("<!-- BEGIN:t -->\n| Name | ATT (s) |\n|---|---|\n| MP & x | 88.1 |\n<!-- END:t -->\n")
    assert paper.check_tags("\\V{d.md | t | MP & x | ATT}{88.1}", {}, numbers.DocTables(tmp_path))[0] == []


def test_refresh_rewrites_the_number_keeping_the_format():
    assert paper.refresh_tags("\\V{a}{90.0} \\V{neg}{+9.9}", FS, None) == "\\V{a}{88.1} \\V{neg}{-1.5}"


def test_lint_flags_untagged_numbers_in_the_body_only():
    body = ("MaxPressure was 88.1~s \\V{a}{88.1} in 2024 [3], see Section~\\ref{s:2} and \\cite{x2019}.\n"
            "\\includegraphics[width=0.9\\columnwidth]{f.pdf} \\vspace{-3pt} \\texttt{llama3.2:3b} on a GTX 1650.\n"
            "% a comment with 4750\n% BEGIN:tab\n99.9 & 12.5\n% END:tab\n3 seeds, 0--4.\n\\end{document}\n")
    assert [p.message for p in paper.lint(DOC + body)] == ["untagged number 88.1"]
    assert paper.lint(DOC + "a queue of 17 vehicles\n") and paper.lint(DOC + "rose 2375--4750 veh/h\n")


def test_identifiers_are_explicit_constants_not_an_allowlist():
    ids = " ".join(paper.IDENTIFIERS.values())
    assert paper.lint(DOC + ids + "\n") == []
    assert paper.check_identifiers(ids) == []
    missing = paper.check_identifiers(ids.replace("23BCE8195", ""))
    assert len(missing) == 1 and "C Bhargav Kumar" in missing[0]
    assert "not a listed identifier" in paper.check_identifiers(ids + " 23BCE9999")[0]


def test_abstract_word_count_reads_tagged_numbers_as_words():
    assert paper.abstract_words("\\begin{abstract}It fell to \\V{a}{88.1}~s (\\emph{fast}).\\end{abstract}") == 6


def test_citations_must_be_report_references(tmp_path):
    report = "@article{a1,\n  title = {One},\n  year = {2020}\n}\n@article{b2,\n  title = {Two},\n  year = {2020}\n}\n"
    ours = "@misc{a1,\n  title = {One},\n  year = {2020}\n}\n@misc{c3,\n  title = {Three},\n  year = {2020}\n}\n"
    errs = paper.check_citations("\\cite{a1,b2}", ours, report)
    assert any("b2" in e and "no entry" in e for e in errs)
    assert any("c3" in e and "never cited" in e for e in errs)
    assert any("c3" in e and "verified references" in e for e in errs)


def test_paper_matches_outputs_and_fits_eight_pages():
    r = subprocess.run([sys.executable, "scripts/make_paper.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_tools_table_reads_versions_from_the_lock_file(tmp_path):
    v = paper.lock_versions(ROOT)
    table = paper.tab_tools({"m.size.nemo": Fact(550, "x.json")}, ROOT)
    for pkg in ("streamlit", "ultralytics", "torch", "python", "cityflow"):
        assert v[pkg] in table
    (tmp_path / "requirements-lock.txt").write_text("# no header\nstreamlit==1.0\n")
    try:
        paper.lock_versions(tmp_path)
    except ValueError as e:
        assert "header" in str(e)
    else:
        raise AssertionError("a lock file without the Python / CityFlow header must fail")


def test_ollama_version_must_be_one_value(tmp_path):
    for i, ver in enumerate(("0.40.3", "0.41.0")):
        d = tmp_path / "outputs/full/runs" / f"r{i}"
        d.mkdir(parents=True)
        (d / "summary.json").write_text(
            '{"provenance": {"provider": "ollama", "llm": {"server_version": "%s"}}}' % ver)
    for d in paper.OLLAMA_RUNS[1:]:
        (tmp_path / d).mkdir(parents=True)
    try:
        paper.ollama_version(tmp_path)
    except ValueError as e:
        assert "0.40.3" in str(e) and "0.41.0" in str(e)
    else:
        raise AssertionError("two Ollama versions must fail")
