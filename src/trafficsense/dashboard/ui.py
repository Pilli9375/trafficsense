"""UI building blocks shared by the pages: header, badges, source chips, chart cards, banners, tables.

Every block that shows data names its source with a small "ⓘ source" chip: a <details> element
whose panel lists each file and the git commit that last changed it (data.sources()). The chips
carry the file list in `data-ts-src`, which tests/test_dashboard.py reads.
"""
from __future__ import annotations

import functools
import html as _html
from typing import Callable, Iterable, Sequence

import plotly.graph_objects as go
import streamlit as st

from trafficsense.dashboard import data, theme

PLOT_CONFIG = theme.PLOT_CONFIG

# honesty labels -> badge style
BADGE_KIND = {"pre-registered": "pre", "exploratory": "expl", "no significance test": "warn", "post-hoc": "post",
              "hosted, not local": "warn", "dashcam proxy": "warn", "no tracking": "warn", "measured now": "ok",
              "frozen before test": "pre", "selection rule": "pre", "ambulances not noised": "warn",
              "replayed, verified": "ok", "interpolated between logged seconds": "plain"}

ICONS = {  # 16 px line icons (stroke = currentColor)
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.8 2.8M14.9 14.9l2.8 2.8M6.3 17.7l2.8-2.8M14.9 9.1l2.8-2.8"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
}


def esc(s: object) -> str:
    return _html.escape(str(s))


def icon(name: str, size: int = 16) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def html(body: str) -> None:
    """Render trusted HTML built by the pages (numbers come from the data files). st.markdown keeps
    inline SVG; st.html would strip it. Keep `body` on one line: a blank line would end the HTML block."""
    st.markdown(body, unsafe_allow_html=True)


def script(js: str) -> None:
    """Run a small script in the page (st.html executes it; st.markdown would not)."""
    st.html(js, unsafe_allow_javascript=True)


def count_up() -> None:
    """Animate every .ts-count number rendered so far (see COUNT_UP_JS)."""
    script(COUNT_UP_JS)


# ---- badges & source chips --------------------------------------------------------------------
def badge(text: str, kind: str | None = None) -> str:
    k = BADGE_KIND.get(text, "") if kind is None else kind
    return f'<span class="ts-badge {k}">{esc(text)}</span>'


def badges(items: Iterable[str | tuple[str, str]]) -> str:
    out = [badge(i) if isinstance(i, str) else badge(*i) for i in items]
    return f'<div class="ts-badges">{"".join(out)}</div>' if out else ""


def source_chip(*rels: str, align: str = "right") -> str:
    """'ⓘ source' chip; its panel lists every file with the commit that last changed it."""
    rows = "".join(f'<div class="ts-src-row"><span class="f">{esc(f)}</span><span class="g">{esc(g)}</span></div>'
                   for f, g in data.sources(*rels))
    files = "|".join(esc(r) for r in rels)
    side = " left" if align == "left" else ""
    return (f'<details class="ts-src{side}" data-ts-src="{files}"><summary>{icon("info", 13)}source</summary>'
            f'<div class="ts-src-pop"><div class="ts-src-h">Source · file and last commit</div>{rows}</div></details>')


# ---- page structure -----------------------------------------------------------------------------
def page_header(eyebrow: str, title: str, subtitle: str, tags: Iterable[str | tuple[str, str]] = ()) -> None:
    html(f'<div class="ts-head"><div class="ts-eyebrow">{esc(eyebrow)}</div><h1 class="ts-title">{esc(title)}</h1>'
         f'<p class="ts-sub">{subtitle}</p>{badges(tags)}</div>')


def takeaway(text_html: str, tags: Iterable[str | tuple[str, str]] = (), *sources: str) -> None:
    """One-line takeaway banner at the top of a tab; text_html is built from data values."""
    chip = source_chip(*sources) if sources else ""
    tag_html = "".join(badge(t) if isinstance(t, str) else badge(*t) for t in tags)
    html(f'<div class="ts-take"><div class="ic">{icon("spark", 16)}</div><div class="tx">{text_html}</div>'
         f'<div class="bd">{tag_html}{chip}</div></div>')


def why(body_html: str, label: str = "Why / How to read", expanded: bool = False) -> None:
    with st.expander(label, expanded=expanded, icon=":material/menu_book:"):
        html(f'<div class="ts-why">{body_html}</div>')


def card_header(title: str, subtitle: str | None = None, sources: Sequence[str] = (),
                tags: Iterable[str | tuple[str, str]] = ()) -> str:
    sub = f'<div class="ts-card-sub">{subtitle}</div>' if subtitle else ""
    tag_html = "".join(badge(t) if isinstance(t, str) else badge(*t) for t in tags)
    chip = source_chip(*sources) if sources else ""
    return (f'<div class="ts-card-h"><div class="t"><div class="ts-card-title">{esc(title)}</div>{sub}</div>'
            f'{tag_html}{chip}</div>')


def chart(fig: go.Figure, *sources: str, key: str, title: str | None = None, subtitle: str | None = None,
          height: int | None = None, grow: str | None = None, tags: Iterable[str | tuple[str, str]] = ()) -> None:
    """A chart in a card: title, optional one-line subtitle, honesty badges and the source chip.
    grow='h' / 'v' animates bars growing from their baseline on load."""
    if height is not None:
        fig.update_layout(height=height)
    # Streamlit paints its own theme over values that only the template sets; set them on the figure
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=theme.FONT, color=theme.TEXT_2, size=12.5),
                      hoverlabel=dict(bgcolor=theme.SURFACE_2, bordercolor=theme.BORDER_2, align="left",
                                      font=dict(family=theme.FONT, color=theme.TEXT, size=12.5)))
    if title is None:      # LEGACY call from a page not yet on the new kit
        st.plotly_chart(fig, theme=None, width="stretch", config=PLOT_CONFIG, key=key)
        caption_source(*sources)
        return
    prefix = {"h": "card-h-", "v": "card-v-"}.get(grow or "", "card-")
    with st.container(key=f"{prefix}{key}"):
        html(card_header(title, subtitle, sources, tags))
        st.plotly_chart(fig, theme=None, width="stretch", config=PLOT_CONFIG, key=key)


@functools.lru_cache(maxsize=16)
def _asset(name: str, mtime: float) -> str:
    return (theme.ASSETS / name).read_text(encoding="utf-8")


def component(name: str, root_class: str, css: str, js: str) -> Callable:
    """Register a custom (v2) component from assets/ and return its mount function. Called on every run:
    the registry is per runtime (AppTest starts a new one), and an identical definition re-registers quietly."""
    files = {f: (theme.ASSETS / f).stat().st_mtime for f in (css, js)}
    return st.components.v2.component(name, html=f'<div class="{root_class}"></div>',
                                      css=_asset(css, files[css]), js=_asset(js, files[js]))


def card(inner_html: str) -> str:
    return f'<div class="ts-card">{inner_html}</div>'


def table(rows: list[dict], *, num: Iterable[str] = (), wide: str | None = None, max_height: int | None = None,
          colours: dict[str, str] | None = None, first: str | None = None) -> str:
    """A read-only HTML table (cells wrap, unlike st.dataframe). `num` columns are right-aligned
    in the mono face; `colours` maps a value of the `first` column to its entity colour (dot)."""
    if not rows:
        return ""
    cols = list(rows[0])
    num = set(num)

    def cls(c: str) -> str:
        return " ".join(x for x in (("num" if c in num else ""), ("wide" if c == wide else "")) if x)

    head = "".join(f'<th class="{cls(c)}">{esc(c)}</th>' for c in cols)
    body = []
    for r in rows:
        cells = []
        for c in cols:
            v = r[c]
            if c == first and colours and v in colours:
                v_html = f'<span class="who"><span class="ts-dot" style="background:{colours[v]}"></span>{esc(v)}</span>'
            else:
                v_html = esc(v)
            cells.append(f'<td class="{cls(c)}">{v_html}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    style = f' style="max-height:{max_height}px"' if max_height else ""
    return f'<div class="ts-table"{style}><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def missing(e: data.MissingData) -> None:
    st.error(f"**Data file missing:** `{e.path}`  \n{e.hint}", icon=":material/error:")


# ---- number formats -------------------------------------------------------------------------------
def pct(x: float, digits: int = 1, sign: bool = True) -> str:
    return f"{x:+.{digits}f}%" if sign else f"{x:.{digits}f}%"


def mean_std(ms: list[float], digits: int = 1) -> str:
    return f"{ms[0]:.{digits}f} ± {ms[1]:.{digits}f}"


# Count-up: elements with class ts-count hold their final text (a number read from the data);
# on load this animates from zero to it and then writes the original text back unchanged.
COUNT_UP_JS = """<script>(() => {
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('.ts-count:not([data-done])').forEach((el) => {
    el.setAttribute('data-done', '1');
    const text = el.textContent, m = text.match(/^([^0-9]*)([0-9][0-9,]*\\.?[0-9]*)(.*)$/);
    if (!m || reduce) return;
    const target = parseFloat(m[2].replace(/,/g, '')), dec = (m[2].split('.')[1] || '').length;
    const t0 = performance.now(), dur = 1100, ease = (x) => 1 - Math.pow(1 - x, 3);
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      el.textContent = k < 1 ? m[1] + (target * ease(k)).toFixed(dec) + m[3] : text;
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
})();</script>"""


# ---- LEGACY: helpers of the old page design, kept until every page is on the kit above ----------------
def header(eyebrow: str, title: str, lede: str | None = None) -> None:
    st.markdown(f'<div class="ts-eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title, anchor=False)
    if lede:
        st.markdown(f'<p class="ts-lede">{lede}</p>', unsafe_allow_html=True)


def caption_source(*rels: str) -> None:
    st.caption(data.source(*rels))


def note(body_html: str, tags: Iterable[tuple[str, str]] = ()) -> None:
    tag_html = "".join(f'<span class="ts-tag {cls}">{esc(t)}</span>' for t, cls in tags)
    st.markdown(f'<div class="ts-note">{tag_html}{body_html}</div>', unsafe_allow_html=True)


def row(label: str, value: str, colour: str | None = None, delta: str | None = None) -> str:
    dot = f'<span class="ts-dot" style="background:{colour}"></span>' if colour else ""
    d = f'<span class="delta">{esc(delta)}</span>' if delta is not None else ""
    return (f'<div class="ts-row">{dot}<span class="lab" title="{esc(label)}">{esc(label)}</span>'
            f'<span class="val">{esc(value)}</span>{d}</div>')


def bar_row(label: str, value: str, colour: str, frac: float) -> str:
    frac = max(0.0, min(1.0, frac))
    return (f'<div class="ts-brow"><span class="ts-dot" style="background:{colour}"></span>'
            f'<span class="lab" title="{esc(label)}">{esc(label)}</span><span class="track">'
            f'<span class="fill" style="width:{frac * 100:.1f}%;background:{colour}"></span></span>'
            f'<span class="val">{esc(value)}</span></div>')


def duo_card(title: str, unit: str, items: list[tuple[str, str, str]]) -> str:
    """Two (or more) values side by side: items = (who, colour, value)."""
    cols = "".join(f'<div><div class="who"><span class="ts-dot" style="background:{c}"></span> {esc(w)}</div>'
                   f'<div class="ts-kpi">{esc(v)}<small>{esc(unit)}</small></div></div>' for w, c, v in items)
    return f'<div class="ts-card"><h4>{esc(title)}</h4><div class="ts-duo">{cols}</div></div>'


def kpi_card(title: str, value: str, unit: str, sub: str, rows_html: str = "") -> str:
    rows = f'<div class="ts-rows">{rows_html}</div>' if rows_html else ""
    return (f'<div class="ts-card"><h4>{esc(title)}</h4><div class="ts-kpi">{esc(value)}<small>{esc(unit)}</small></div>'
            f'<div class="ts-sub">{sub}</div>{rows}</div>')


def html_table(df, max_height: int | None = None, wide: str | None = None) -> None:
    """A read-only table whose cells wrap (st.dataframe truncates long text). `wide` names the column
    that takes the remaining width."""
    head = "".join(f'<th class="{"wide" if c == wide else ""}">{esc(c)}</th>' for c in df.columns)
    body = "".join("<tr>" + "".join(f'<td class="{"wide" if c == wide else ""}">{esc(v)}</td>'
                                     for c, v in zip(df.columns, r)) + "</tr>" for r in df.itertuples(index=False))
    style = f' style="max-height:{max_height}px"' if max_height else ""
    st.markdown(f'<div class="ts-table"{style}><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def html_block(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def legend_off(fig: go.Figure) -> go.Figure:
    fig.update_layout(showlegend=False)
    return fig


def style_axes(fig: go.Figure, x_title: str = "", y_title: str = "") -> go.Figure:
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text=y_title)
    return fig
