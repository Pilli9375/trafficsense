"""Small UI building blocks shared by the pages."""
from __future__ import annotations

import html
from typing import Iterable

import plotly.graph_objects as go
import streamlit as st

from trafficsense.dashboard import data, theme

PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]}


def esc(s: str) -> str:
    return html.escape(str(s))


def header(eyebrow: str, title: str, lede: str | None = None) -> None:
    st.markdown(f'<div class="ts-eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title, anchor=False)
    if lede:
        st.markdown(f'<p class="ts-lede">{lede}</p>', unsafe_allow_html=True)


def caption_source(*rels: str) -> None:
    st.caption(data.source(*rels))


def chart(fig: go.Figure, *sources: str, height: int | None = None, key: str | None = None) -> None:
    if height is not None:
        fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG, key=key)
    caption_source(*sources)


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


def missing(e: data.MissingData) -> None:
    st.error(f"**Data file missing:** `{e.path}`  \n{e.hint}", icon=":material/error:")


def pct(x: float, digits: int = 1, sign: bool = True) -> str:
    return f"{x:+.{digits}f}%" if sign else f"{x:.{digits}f}%"


def mean_std(ms: list[float], digits: int = 1) -> str:
    return f"{ms[0]:.{digits}f} ± {ms[1]:.{digits}f}"


def legend_off(fig: go.Figure) -> go.Figure:
    fig.update_layout(showlegend=False)
    return fig


def style_axes(fig: go.Figure, x_title: str = "", y_title: str = "") -> go.Figure:
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text=y_title)
    return fig

