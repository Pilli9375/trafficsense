"""Design tokens of the dashboard: colours, type, spacing, the Plotly template and the page CSS.

Dark, minimal. Series colours are the dataviz skill's validated dark categorical palette
(CVD-safe in this fixed order; every slot >= 3.5:1 on SURFACE). Colour follows the entity
(a controller keeps its colour on every page), never its rank. Status colours are only used
for signal state (green / yellow), always together with a label or a shape.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

BG = "#0f0f11"           # page
SURFACE = "#18181b"      # cards, charts
SURFACE_2 = "#1f1f23"    # hover / inset
BORDER = "#27272a"
GRID = "#26262b"
TEXT = "#ededef"
TEXT_2 = "#a1a1aa"       # secondary (6.9:1 on SURFACE)
TEXT_3 = "#8b8b94"       # muted captions (4.9:1 on SURFACE)
FONT = 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'

SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
NEUTRAL = "#71717a"
GREEN_SIGNAL = "#0ca30c"   # status "good": a green signal
YELLOW_SIGNAL = "#fab219"  # status "warning": the transition (yellow) phase
VEHICLE = "#7c7c86"

# Entity -> (label, colour). Keyed by controller and model; the same entity has the same colour
# everywhere. Models outside the main comparison (3B hybrids of the model-size study) are neutral.
ENTITIES = {
    ("maxpressure", None): ("MaxPressure", SERIES[0]),
    ("llm_guarded_mp", "llama3.2:3b"): ("LLM main · llama3.2:3b, guarded", SERIES[1]),
    ("llm_guided_mp_v3", "gemma4:e4b"): ("gemma4:e4b hybrid (exploratory)", SERIES[2]),
    ("fixedtime_webster", None): ("Webster fixed-time", SERIES[3]),
    ("fixedtime", None): ("Fixed-time", SERIES[4]),
    ("llm_guided_mp_v3", "nvidia/nemotron-3-ultra-550b-a55b"): ("Nemotron 3 Ultra hybrid (exploratory, hosted)", SERIES[5]),
    ("preemption_mp", None): ("MaxPressure + preemption", SERIES[6]),
    ("llm_guided_mp_v3", "llama3.1:8b"): ("llama3.1:8b hybrid (exploratory)", SERIES[7]),
    ("llm_guided_mp_v3", "qwen2.5:3b"): ("qwen2.5:3b hybrid (exploratory)", NEUTRAL),
    ("llm_guided_mp_v3", "llama3.2:3b"): ("llama3.2:3b hybrid (exploratory)", "#a1a1aa"),
}
SHORT = {
    ("maxpressure", None): "MaxPressure", ("llm_guarded_mp", "llama3.2:3b"): "LLM main",
    ("llm_guided_mp_v3", "gemma4:e4b"): "gemma4 hybrid", ("fixedtime_webster", None): "Webster",
    ("fixedtime", None): "Fixed-time", ("llm_guided_mp_v3", "nvidia/nemotron-3-ultra-550b-a55b"): "Nemotron hybrid",
    ("preemption_mp", None): "MP + preemption", ("llm_guided_mp_v3", "llama3.1:8b"): "llama3.1:8b hybrid",
    ("llm_guided_mp_v3", "qwen2.5:3b"): "qwen2.5:3b hybrid", ("llm_guided_mp_v3", "llama3.2:3b"): "llama3.2:3b hybrid",
}
CLASS_COLOURS = {"car": SERIES[0], "motorcycle": SERIES[1], "autorickshaw": SERIES[2], "bus": SERIES[3],
                 "truck": SERIES[4], "bicycle": SERIES[6], "person": SERIES[7]}
SCENARIO_LABELS = {"indian_2x2_offpeak": "Indian 2x2 · off-peak", "indian_2x2_peak": "Indian 2x2 · peak",
                   "jinan_3x4": "Jinan 3x4 (real flow)", "indian_2x2_peak_amb": "Indian 2x2 · peak + ambulances"}
LEVEL_LABELS = {"perfect": "Exact counts", "junction": "Junction camera", "crowded": "Crowded / far camera"}


def entity(controller: str, model: str | None) -> tuple[str, str]:
    key = (controller, model)
    if key not in ENTITIES:
        raise KeyError(f"No label/colour for controller {controller!r} with model {model!r}")
    return ENTITIES[key]


MODEL_SHORT = {"nvidia/nemotron-3-ultra-550b-a55b": "Nemotron 3 Ultra"}


def model_short(model: str) -> str:
    return MODEL_SHORT.get(model, model)


def short(controller: str, model: str | None) -> str:
    return SHORT[(controller, model)]


def _template() -> go.layout.Template:
    t = go.layout.Template()
    axis = dict(gridcolor=GRID, zerolinecolor="#3f3f46", linecolor=BORDER, tickcolor=BORDER,
                tickfont=dict(color=TEXT_2, size=12), title=dict(font=dict(color=TEXT_2, size=12)),
                showline=False, ticks="")
    t.layout = go.Layout(
        font=dict(family=FONT, color=TEXT_2, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES, xaxis=axis, yaxis=axis,
        legend=dict(font=dict(color=TEXT_2, size=12), bgcolor="rgba(0,0,0,0)", orientation="h",
                    yanchor="bottom", y=1.02, xanchor="left", x=0, title=dict(text="")),
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=BORDER, font=dict(family=FONT, color=TEXT, size=12)),
        margin=dict(l=8, r=8, t=36, b=8),
        title=dict(font=dict(color=TEXT, size=14), x=0, xanchor="left"),
        bargap=0.35,
    )
    return t


pio.templates["trafficsense"] = _template()
pio.templates.default = "trafficsense"

CSS = f"""
<style>
:root {{ --ts-surface: {SURFACE}; --ts-border: {BORDER}; --ts-text: {TEXT}; --ts-text-2: {TEXT_2}; --ts-text-3: {TEXT_3}; }}
html, body, [class*="css"] {{ font-family: {FONT}; }}
#MainMenu, footer, [data-testid="stDecoration"] {{ visibility: hidden; height: 0; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}
h1, h2, h3 {{ letter-spacing: -0.02em; color: {TEXT}; }}
h1 {{ font-weight: 650; font-size: 1.85rem !important; }}
h2 {{ font-weight: 600; font-size: 1.3rem !important; margin-top: 0.4rem; }}
h3 {{ font-weight: 600; font-size: 1.05rem !important; }}
h5 {{ font-weight: 600; font-size: 0.92rem !important; color: {TEXT}; padding: 0.4rem 0 0 0 !important; }}
p, li {{ color: {TEXT_2}; line-height: 1.6; }}
[data-testid="stCaptionContainer"] p {{ color: {TEXT_3}; font-size: 0.78rem; }}
[data-testid="stSidebar"] {{ background: {BG}; border-right: 1px solid {BORDER}; }}
code {{ color: {TEXT}; background: {SURFACE_2}; font-family: {MONO}; font-size: 0.85em; }}

.ts-eyebrow {{ color: {TEXT_3}; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
  font-weight: 600; margin-bottom: 0.25rem; }}
.ts-lede {{ color: {TEXT_2}; font-size: 1.02rem; max-width: 62rem; margin: 0 0 1.25rem 0; }}

.ts-card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px 18px;
  min-height: 100%; box-sizing: border-box; transition: border-color 200ms ease; }}
.ts-card:hover {{ border-color: #3f3f46; }}
.ts-card h4 {{ margin: 0 0 6px 0; font-size: 0.78rem; font-weight: 600; color: {TEXT_2};
  text-transform: uppercase; letter-spacing: 0.06em; }}
.ts-kpi {{ font-size: 2.1rem; font-weight: 650; color: {TEXT}; letter-spacing: -0.03em; line-height: 1.1;
  font-variant-numeric: tabular-nums; }}
.ts-kpi small {{ font-size: 0.95rem; font-weight: 500; color: {TEXT_2}; margin-left: 4px; }}
.ts-sub {{ color: {TEXT_2}; font-size: 0.82rem; margin-top: 2px; }}
.ts-rows {{ margin-top: 12px; border-top: 1px solid {BORDER}; padding-top: 8px; }}
.ts-row {{ display: flex; align-items: baseline; gap: 8px; padding: 3px 0; font-size: 0.84rem; }}
.ts-row .lab {{ color: {TEXT_2}; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.ts-row .val {{ color: {TEXT}; font-variant-numeric: tabular-nums; font-weight: 550; }}
.ts-row .delta {{ color: {TEXT_3}; font-variant-numeric: tabular-nums; width: 4.2rem; text-align: right; }}
.ts-dot {{ width: 8px; height: 8px; border-radius: 2px; display: inline-block; flex: none; transform: translateY(-1px); }}
.ts-brow {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 0.84rem; }}
.ts-brow .lab {{ color: {TEXT_2}; width: 46%; flex: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.ts-brow .track {{ flex: 1; height: 6px; background: {SURFACE_2}; border-radius: 3px; }}
.ts-brow .fill {{ display: block; height: 100%; border-radius: 3px; }}
.ts-brow .val {{ color: {TEXT}; width: 4.6rem; text-align: right; font-variant-numeric: tabular-nums; font-weight: 550; }}
.ts-duo {{ display: flex; gap: 16px; margin-top: 4px; }}
.ts-duo > div {{ flex: 1; min-width: 0; }}
.ts-duo .who {{ color: {TEXT_2}; font-size: 0.76rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ts-duo .ts-kpi {{ font-size: 1.6rem; white-space: nowrap; }}
/* equal-height cards in a row of columns */
[data-testid="stHorizontalBlock"]:has(.ts-card), [data-testid="stHorizontalBlock"]:has(.ts-step) {{ align-items: stretch; }}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ height: 100%; }}
[data-testid="stElementContainer"]:has(.ts-card), [data-testid="stElementContainer"]:has(.ts-step) {{ flex: 1 1 auto; }}
[data-testid="stMarkdownContainer"]:has(> .ts-card), [data-testid="stMarkdownContainer"]:has(> .ts-step) {{ margin-bottom: 0 !important; }}
[data-testid="stElementContainer"]:has(.ts-card) div:has(.ts-card),
[data-testid="stElementContainer"]:has(.ts-step) div:has(.ts-step) {{ height: 100%; }}

.ts-step {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 16px 18px 18px 18px;
  min-height: 100%; box-sizing: border-box; }}
.ts-step .n {{ color: {TEXT_3}; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }}
.ts-step .t {{ color: {TEXT}; font-weight: 600; margin: 4px 0 6px 0; }}
.ts-step p, .ts-step li {{ font-size: 0.88rem; margin: 0 0 4px 0; }}
.ts-step ul {{ padding-left: 1.1rem; margin: 0; }}

.ts-note {{ border: 1px solid {BORDER}; border-left: 3px solid #52525b; background: {SURFACE};
  border-radius: 8px; padding: 10px 14px; margin: 6px 0 12px 0; }}
.ts-note p, .ts-note li {{ font-size: 0.84rem; margin: 0 0 3px 0; }}
.ts-note b {{ color: {TEXT}; }}
.ts-tag {{ display: inline-block; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
  padding: 2px 8px; border-radius: 999px; border: 1px solid #3f3f46; color: {TEXT_2}; margin-right: 6px; }}
.ts-tag.warn {{ border-color: {YELLOW_SIGNAL}66; color: {YELLOW_SIGNAL}; }}

.ts-table {{ border: 1px solid {BORDER}; border-radius: 8px; overflow: auto; margin-bottom: 6px; }}
.ts-table table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
.ts-table th {{ position: sticky; top: 0; background: {SURFACE}; color: {TEXT_2}; font-weight: 600; text-align: left;
  padding: 6px 10px; border-bottom: 1px solid {BORDER}; white-space: nowrap; }}
.ts-table td {{ padding: 5px 10px; border-bottom: 1px solid {BORDER}; color: {TEXT}; vertical-align: top;
  white-space: nowrap; font-variant-numeric: tabular-nums; }}
.ts-table td.wide {{ white-space: normal; color: {TEXT_2}; min-width: 8rem; }}
.ts-table tr:last-child td {{ border-bottom: none; }}
[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
[data-testid="stTabs"] button p {{ font-size: 0.9rem; }}
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>
"""
