"""Generated tables of README.md and the report. Each function returns Markdown for one
`<!-- BEGIN:name -->` block. Values come from `facts()` (outputs/ and configs/) or from tables in
docs whose own --check scripts verify them, never from literals."""
from __future__ import annotations

from pathlib import Path

from trafficsense.report.numbers import DocTables


def md(header, rows, align=None):
    align = align or ["---"] + ["--:"] * (len(header) - 1)
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(align) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def pm(fs, k, nd=1):
    return f"{fs[k + '.att'].value:.{nd}f} ± {fs[k + '.att_sd'].value:.{nd}f}"


def pct(v, nd=1):
    return f"{v:+.{nd}f}%".replace("-", "−")


def readme_headline(fs, dt) -> str:
    rows = []
    for sc, name in (("off", "Indian 2x2, off-peak (3 seeds)"), ("peak", "Indian 2x2, peak (3 seeds)"),
                     ("jinan", "Jinan 3x4, real flow (3 seeds)")):
        mp = fs[f"f.{sc}.mp.att"].value
        row = [f"ATT (s), {name}", pm(fs, f"f.{sc}.mp"), pm(fs, f"f.{sc}.web"),
               f"{pm(fs, f'f.{sc}.llm')} ({pct(fs[f'f.{sc}.llm.vs_mp'].value)})"]
        row.append(f"{pm(fs, f'f.{sc}.gem')} ({pct(fs[f'f.{sc}.gem.vs_mp'].value)})" if f"f.{sc}.gem.att" in fs else "not run")
        rows.append(row)
    e = lambda a: f"{fs[f'e.{a}.amb'].value:.1f}"
    rows.append([f"Ambulance travel time (s), mean of {fs['e.mp.amb_n'].value:.0f} signal-relevant trips, 5 seeds",
                 e("mp"), e("web"), f"{e('llm')} (preemption rule: {e('pre')})", e("gem")])
    rows.append(["ATT change with junction-camera counts (off-peak / peak)",
                 f"{pct(fs['c.off.mp.junction.pct'].value)} / {pct(fs['c.peak.mp.junction.pct'].value)}",
                 "unaffected (reads no counts)",
                 f"{pct(fs['c.off.llm.junction.pct'].value)} / {pct(fs['c.peak.llm.junction.pct'].value)}", "not run"])
    return md(["", "MaxPressure", "Webster fixed time", "**LLM, pre-registered** (guarded, `llama3.2:3b`)",
               "LLM, exploratory (`gemma4:e4b`)"], rows, ["---", "--:", "--:", "--:", "--:"])


TABLES = {
    "readme_headline": readme_headline,
}


def blocks(root: Path, fs, dt: DocTables) -> dict[str, str]:
    return {name: f(fs, dt) for name, f in TABLES.items()}
