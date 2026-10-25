"""Check (and refresh) every number in a Markdown document against the data.

A number that comes from the data carries an invisible tag right after it:

    MaxPressure's ATT was 88.1<!--=f.off.mp.att--> s.

The tag is an HTML comment, so GitHub and pandoc (docx, PDF) do not show it. Its key is either

* a fact name from `trafficsense.report.facts` (a value read from outputs/ or configs/), or
* a cell of a table in a doc whose own `--check` script verifies it against outputs/:
  `<!--=docs/results.md | results_llm | peak & guarded | Latency mean-->` = the table between
  `<!-- BEGIN:results_llm -->` and `<!-- END:results_llm -->`, the one row containing every
  `&`-separated text, the one column whose header contains the last text. An optional
  `| n` picks the n-th number in the cell (0 = first).

The shown number must equal the fact rounded to the decimals shown, or the n-th number of the
cell. A `%` or a leading `+` is part of the display only.

Generated tables sit between `<!-- BEGIN:name -->` / `<!-- END:name -->` markers and are
rewritten by the script that owns the document.

`lint()` finds numbers that carry no tag. Allowed untagged: numbers inside code, inside
generated blocks, link targets and comments; years; chapter / section / figure / table /
appendix references; reference numbers in square brackets; list numbering; small counts
(0-12); and the phrases in ALLOWED_PHRASES (product names and versions, not measurements).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

NUM = r"[+\-−]?\d[\d,]*(?:\.\d+)?%?"
TAG = re.compile(r"(?P<num>" + NUM + r")<!--=(?P<key>[^>]*?)-->")
BLOCK = re.compile(r"<!-- BEGIN:(?P<name>[\w.\-]+) -->\n(?P<body>.*?)<!-- END:(?P=name) -->", re.S)
CELL_NUM = re.compile(NUM)

# Not measurements: names, versions and fixed hardware facts. Matched case-sensitively.
ALLOWED_PHRASES = [
    r"GTX 1650", r"RTX \d+", r"Ubuntu 22\.04", r"Python 3\.1[0-3](?:\.\d+)?", r"Python 3\.x",
    r"WSL ?2", r"YOLOv\d+\w*", r"ICLR 20\d\d", r"pandoc 3\.\d+(?:\.\d+)?", r"16 GB RAM",
    r"4 GB", r"Ryzen 5 4600H", r"CUDA 12\.\d", r"SIL Open Font License 1\.1", r"OFL 1\.1",
    r"Apache-2\.0", r"Apache License 2\.0", r"CC BY(?:-NC)?(?:-SA)? \d\.\d", r"Tectonic 0\.\d+(?:\.\d+)?",
    r"IEEE 802\.\d+\w*", r"Llama 3\.\d", r"Gemma \d", r"Qwen ?2\.5", r"MIT", r"IRC:\s?\d+",
    r"pybind11", r"ISO \d+", r"ID\d+", r"COCO", r"sm_75", r"A4", r"\d+(?:st|nd|rd|th)",
    r"Nemotron 3 Ultra", r"Nemotron 3 Super", r"DeepSeek V\d(?:\.\d)?", r"v\d(?:\.\d)*",
]


@dataclass
class Problem:
    line: int
    text: str
    message: str

    def __str__(self):
        return f"line {self.line}: {self.message}: {self.text!r}"


def to_float(s: str) -> float:
    s = s.replace("−", "-").replace(",", "").rstrip("%")
    return float(s)


def decimals(s: str) -> int:
    s = s.rstrip("%")
    return len(s.split(".")[1]) if "." in s else 0


def fmt_like(value: float, shown: str) -> str:
    """value written the way `shown` is written: same decimals, sign style, % and thousands commas."""
    d = decimals(shown)
    body = f"{abs(value):,.{d}f}" if "," in shown else f"{abs(value):.{d}f}"
    if float(body.replace(",", "")) == 0:
        sign = "+" if shown[0] == "+" else ""
    elif value < 0:
        sign = "−" if shown[0] == "−" else "-"
    else:
        sign = "+" if shown[0] == "+" else ""
    return sign + body + ("%" if shown.endswith("%") else "")


# --- tables in other docs -------------------------------------------------------------------

def parse_table(body: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in body.splitlines() if ln.startswith("|")]
    if len(lines) < 2:
        raise ValueError("block has no Markdown table")
    split = lambda ln: [c.strip() for c in ln.strip().strip("|").split("|")]
    return split(lines[0]), [split(ln) for ln in lines[2:]]


class DocTables:
    def __init__(self, root: Path):
        self.root = root
        self.cache: dict[str, dict[str, tuple]] = {}

    def table(self, doc: str, block: str):
        if doc not in self.cache:
            p = self.root / doc
            if not p.is_file():
                raise KeyError(f"doc {doc} not found")
            self.cache[doc] = {m["name"]: m["body"] for m in BLOCK.finditer(p.read_text())}
        try:
            return parse_table(self.cache[doc][block])
        except KeyError:
            raise KeyError(f"no block {block!r} in {doc}") from None

    def cell_number(self, key: str) -> str:
        parts = [p.strip() for p in key.split("|")]
        if len(parts) not in (4, 5):
            raise KeyError("table key must be 'doc | block | row texts | column [| n]'")
        doc, block, rowsel, colsel = parts[:4]
        n = int(parts[4]) if len(parts) == 5 else 0
        header, rows = self.table(doc, block)
        cols = [i for i, h in enumerate(header) if colsel in h]
        if len(cols) != 1:
            raise KeyError(f"column {colsel!r} matches {len(cols)} columns in {doc}:{block}")
        want = [w.strip() for w in rowsel.split("&")]
        hit = [r for r in rows if all(w in " | ".join(r) for w in want)]
        if len(hit) != 1:
            raise KeyError(f"row {rowsel!r} matches {len(hit)} rows in {doc}:{block}")
        nums = CELL_NUM.findall(hit[0][cols[0]])
        if len(nums) <= n:
            raise KeyError(f"cell {hit[0][cols[0]]!r} has no number #{n}")
        return nums[n]


# --- tags -----------------------------------------------------------------------------------

def resolve(key: str, facts: dict, tables: DocTables):
    """('fact', value) or ('cell', text)."""
    key = key.strip()
    if "|" in key:
        return "cell", tables.cell_number(key)
    if key not in facts:
        raise KeyError(f"unknown fact {key!r}")
    return "fact", facts[key].value


def matches(shown: str, kind: str, ref) -> bool:
    if kind == "fact":
        want = fmt_like(ref, shown)
        return math.isclose(to_float(want), to_float(shown), abs_tol=0)
    return to_float(ref) == to_float(shown) and decimals(ref) == decimals(shown)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check_tags(text: str, facts: dict, tables: DocTables) -> tuple[list[Problem], int]:
    probs, n = [], 0
    for m in TAG.finditer(text):
        n += 1
        try:
            kind, ref = resolve(m["key"], facts, tables)
        except (KeyError, ValueError) as e:
            probs.append(Problem(line_of(text, m.start()), m.group(0), str(e)))
            continue
        if not matches(m["num"], kind, ref):
            want = fmt_like(ref, m["num"]) if kind == "fact" else ref
            probs.append(Problem(line_of(text, m.start()), m.group(0), f"data says {want}"))
    return probs, n


def refresh_tags(text: str, facts: dict, tables: DocTables) -> str:
    def sub(m):
        kind, ref = resolve(m["key"], facts, tables)
        new = fmt_like(ref, m["num"]) if kind == "fact" else ref
        return f"{new}<!--={m['key']}-->"
    return TAG.sub(sub, text)


def render_blocks(text: str, blocks: dict[str, str], where: str = "document") -> str:
    for name, body in blocks.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(text):
            raise KeyError(f"marker for block {name!r} missing in {where}")
        text = pat.sub(lambda _: f"{begin}\n{body.rstrip()}\n{end}", text)
    return text


# --- lint -----------------------------------------------------------------------------------

_STRIP = [
    re.compile(r"^```.*?^```", re.S | re.M),             # fenced code
    re.compile(r"^---\n.*?\n---\n", re.S),                 # YAML front matter
    BLOCK,                                                 # generated blocks
    TAG,                                                   # tagged numbers
    re.compile(r"<!--.*?-->", re.S),                       # comments
    re.compile(r"`[^`\n]+`"),                              # inline code
    re.compile(r"\]\([^)]*\)"),                            # link / image targets
    re.compile(r"\{[#.][^}]*\}"),                          # pandoc attributes
    re.compile(r"<[^>\n]+>"),                              # HTML tags
    re.compile(r"https?://\S+"),
    re.compile(r"\{\{[A-Z_]+\}\}"),                        # placeholders the user fills
]
_CONTEXT = re.compile(
    r"\b(?:Chapter|Chapters|Section|Sections|Figure|Figures|Table|Tables|Appendix|Phase|Step|Steps|"
    r"Eq\.|Equation|step|steps|section|chapter|table|figure|Sec\.|Fig\.|Tab\.|Ch\.)"
    r"\s+(?:\d+(?:\.\d+)*[a-z]?(?:\s*(?:–|-|,|and|to)\s*\d+(?:\.\d+)*[a-z]?)*)")
_YEAR = re.compile(r"(?<![\d.,])(?:19[5-9]\d|20[0-2]\d)[a-z]?(?![\d.])")
_CITE = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
_LIST = re.compile(r"^\s*\d+\.\s", re.M)
_STANDALONE = re.compile(r"(?<![\w.\-−+/:])" + NUM + r"(?![\w])")


def _blank(text: str, pat: re.Pattern) -> str:
    return pat.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def lint(text: str, small: int = 12) -> list[Problem]:
    t = text
    for p in _STRIP:
        t = _blank(t, p)
    for p in [re.compile(x) for x in ALLOWED_PHRASES] + [_CONTEXT, _YEAR, _CITE, _LIST]:
        t = _blank(t, p)
    probs = []
    for m in _STANDALONE.finditer(t):
        s = m.group(0)
        if s.rstrip("%") == s and "." not in s and "," not in s and abs(int(s.replace("−", "-"))) <= small:
            continue
        ln = line_of(t, m.start())
        probs.append(Problem(ln, text.splitlines()[ln - 1].strip()[:120], f"untagged number {s}"))
    return probs
