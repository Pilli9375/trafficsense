"""The Word version of the IEEE paper (trafficsense.report.paper_docx, scripts/make_paper.py)."""
import re
import zipfile
from pathlib import Path

import pytest

from trafficsense.config import repo_root
from trafficsense.report import paper, paper_docx as pd

ROOT = repo_root()


def test_roman_numbers_and_ref_numbers_follow_the_documents_order():
    assert [pd.roman(n) for n in (1, 4, 8, 9)] == ["I", "IV", "VIII", "IX"]
    body = ("\\section{A}\\label{s:a}\n\\subsection{B}\\label{s:b}\n\\subsection{C}\\label{s:c}\n"
            "\\section*{Thanks}\n\\section{D}\\label{s:d}\n\\subsection{E}\\label{s:e}\n"
            "\\begin{table}[t]\\caption{t}\\label{t:1}\\end{table}\n"
            "\\begin{figure*}[t]\\caption{f}\\label{f:1}\\end{figure*}\n"
            "\\begin{figure}[t]\\caption{g}\\label{f:2}\\end{figure}\n")
    n = pd.Numbering(body)
    assert n.resolve("Section~\\ref{s:c}, \\ref{s:e}, Table~\\ref{t:1}, Fig.~\\ref{f:2}") == \
        "Section~I-B, II-A, Table~I, Fig.~2"
    with pytest.raises(pd.DocxError, match="unknown label"):
        n.resolve("\\ref{nope}")


def test_tags_become_their_number_with_a_real_minus_sign():
    assert pd.expand_tags("\\V{a.b}{+0.9}\\% and \\V{c}{-1.5}") == "+0.9\\% and \u22121.5"


def test_a_booktabs_table_is_read_with_rules_spans_and_header_rows():
    src = ("\\caption{Cam.}\n\\begin{tabular}{@{}l@{\\hspace{4pt}}cc@{}}\n\\toprule\n"
           " & \\multicolumn{2}{c}{Off} \\\\\n\\cmidrule(l){2-3}\nCtl & a & b \\\\\n\\midrule\n"
           "MP & $+4.8$ {\\scriptsize[$4.1$, $5.4$]} & x \\\\\n\\bottomrule\n\\end{tabular}\n"
           "\\par\\vspace{2pt}\n\\parbox{\\columnwidth}{\\scriptsize Note $^{a}$ text.}\n")
    t = pd.parse_table(src)
    assert [c["align"] for c in t["cols"]] == ["left", "center", "center"]
    heads = [r["header"] for r in t["rows"]]
    assert heads == [True, True, False]
    assert t["rows"][0]["rule"] == "top" and t["rows"][2]["rule"] == "mid" and t["rows"][2]["rule_below"]
    assert t["rows"][1]["cmid"] == [(2, 3)]
    assert [(c["col"], c["span"]) for c in t["rows"][0]["cells"]] == [(1, 1), (2, 2)]
    assert t["notes"] == ["Note $^{a}$ text."]
    with pytest.raises(pd.DocxError, match="columns"):
        pd.parse_table("\\caption{x}\\begin{tabular}{lc}\na & b & c \\\\\n\\end{tabular}")


def test_column_specs_with_paragraph_columns():
    cols = pd.column_spec("@{}l>{\\raggedright\\arraybackslash}p{0.73\\columnwidth}@{}")
    assert [c["align"] for c in cols] == ["left", "left"] and cols[1]["frac"] == 0.73
    with pytest.raises(pd.DocxError):
        pd.column_spec("l|X")


def test_simple_maths_is_text_and_structure_becomes_an_equation():
    for tex in ("+4.8", "121.5 \\pm 0.2", "^{a}", "\\mathbf{0.563}", "r=0.8", "x", "P \\ge 0.5"):
        assert pd.math_class(tex) == "text", tex
    for tex in ("P(p)=\\sum_{(l,m)\\in p}(x_l-x_m)", "R^*=5500", "P_{\\mathrm{top}}"):
        assert pd.math_class(tex) == "omml", tex
    w = pd.Writer({})
    xml = pd.math_text_runs("-0.4", {}, w.run)
    assert "\u2212" in xml and "0.4" in xml and "<w:vertAlign" not in xml
    assert "superscript" in pd.math_text_runs("^{a,b}", {}, w.run)


def test_unconverted_latex_is_an_error_not_silently_dropped():
    with pytest.raises(pd.DocxError, match="unconverted LaTeX"):
        pd.Writer({}).inlines([{"t": "RawInline", "c": ["latex", "\\weird"]}])
    with pytest.raises(pd.DocxError, match="no equation conversion"):
        pd.Writer({}).inlines([{"t": "Math", "c": [{"t": "InlineMath"}, "x_1"]}])


def test_floats_move_by_shift_but_never_change_order():
    f1, f2 = {"label": "a"}, {"label": "b"}
    items = [("block", 1), ("float", f1), ("block", 2), ("block", 3), ("float", f2), ("block", 4)]
    assert [x if k == "block" else x["label"] for k, x in pd.place_floats(items)] == [1, "a", 2, 3, "b", 4]
    old = dict(pd.FLOAT_SHIFT)
    try:
        pd.FLOAT_SHIFT.update({"a": 2})
        assert [x if k == "block" else x["label"] for k, x in pd.place_floats(items)] == [1, 2, 3, "a", "b", 4]
        pd.FLOAT_SHIFT.update({"a": 4})
        with pytest.raises(pd.DocxError, match="reorder"):
            pd.place_floats(items)
    finally:
        pd.FLOAT_SHIFT.clear()
        pd.FLOAT_SHIFT.update(old)


def test_a_float_may_not_be_moved_across_a_heading():
    f = {"label": "a"}
    items = [("block", {"t": "Para"}), ("float", f), ("block", {"t": "Header"}), ("block", {"t": "Para"})]
    old = dict(pd.FLOAT_SHIFT)
    try:
        pd.FLOAT_SHIFT.update({"a": 1})
        with pytest.raises(pd.DocxError, match="across a heading"):
            pd.place_floats(items)
        pd.FLOAT_SHIFT.update({"a": -1})
        assert [k for k, _ in pd.place_floats(items)] == ["float", "block", "block", "block"]
    finally:
        pd.FLOAT_SHIFT.clear()
        pd.FLOAT_SHIFT.update(old)


def test_front_matter_is_read_from_paper_tex_and_fails_loudly_without_it():
    fm = pd.front_matter((ROOT / paper.TEX).read_text())
    assert fm["title"].startswith("TrafficSense") and len(fm["authors"]) == 5
    assert [a["reg"] for a in fm["authors"][:4]] == ["23BCE8195", "23BCE8015", "23BCE8288", "23BCE9470"]
    assert all(a["email"].endswith("@vitapstudent.ac.in") for a in fm["authors"][:4])
    assert fm["authors"][4]["name"] == "Dr. Mohd Irfan (Guide)" and not fm["authors"][4]["email"]
    assert fm["affiliation"][1] == "Amaravati, India"
    with pytest.raises(pd.DocxError):
        pd.front_matter("\\title{x}")


def test_every_float_in_the_paper_is_numbered_and_the_labels_resolve():
    body = pd.body_of((ROOT / paper.TEX).read_text())
    n = pd.Numbering(body)
    assert n.labels["tab:tools"] == "I" and n.labels["fig:overview"] == "1"
    assert re.fullmatch(r"[IVX]+-[A-Z]", n.labels["sec:validation"])
    assert "\\ref" not in n.resolve(body)


def test_the_committed_word_file_passes_its_checks_and_is_built_from_the_template():
    docx = ROOT / pd.DOCX
    assert docx.is_file() and (ROOT / pd.DOCX_PDF).is_file()
    z = zipfile.ZipFile(docx)
    tpl = zipfile.ZipFile(ROOT / pd.TEMPLATE)
    # IEEE's styles and numbering are the template's, byte for byte
    for part in ("word/styles.xml", "word/numbering.xml", "word/theme/theme1.xml", "word/fontTable.xml"):
        assert z.read(part) == tpl.read(part), part
    text = z.read("word/document.xml").decode()
    for style in ("papertitle", "Abstract", "Heading1", "Heading2", "BodyText", "figurecaption",
                  "tablehead", "references", "bulletlist"):
        assert f'w:pStyle w:val="{style}"' in text, style
    assert "<m:oMath>" in text                      # native Word equations
    assert text.count("<w:drawing>") == 6           # the six figures


def test_the_word_check_catches_a_changed_document(tmp_path):
    import json
    import shutil
    root = tmp_path
    for f in (pd.DOCX, pd.DOCX_PDF, paper.TEX, paper.BIB, pd.TEMPLATE, pd.CSL):
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, root / f)
    shutil.copytree(ROOT / paper.PAPER_DIR / "figures", root / paper.PAPER_DIR / "figures")
    rec = json.loads((ROOT / paper.BUILD_RECORD).read_text())["docx"]
    assert pd.check(root, rec) == []
    # a leftover placeholder and a changed number
    with zipfile.ZipFile(root / pd.DOCX) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    doc = parts["word/document.xml"].decode().replace("Introduction", "Introduction {{TBD}}", 1)
    parts["word/document.xml"] = doc.encode()
    with zipfile.ZipFile(root / pd.DOCX, "w") as z:
        for n, b in parts.items():
            z.writestr(n, b)
    errs = pd.check(root, rec)
    assert any("leftover text '{{'" in e for e in errs) and any("not the file recorded" in e for e in errs)
    assert pd.check(root, None)
    assert Path(root / pd.DOCX).is_file()
