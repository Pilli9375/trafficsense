"""Design tokens of the dashboard: colours, type, the shared Plotly template and the global CSS.

Dark "mission control" look: a near-black page, one accent (electric teal) for the UI, semantic
colours that keep one meaning everywhere (green = good / green light, amber = transition,
red = queue / bad), and the ambulance in red and white.

Data colours are separate from those. Series colours are the dataviz skill's validated dark
categorical palette (CVD-safe in this fixed order; every slot >= 3:1 on SURFACE). Colour follows
the entity (a controller keeps its colour on every page), never its rank.

The tokens here, assets/theme.css and .streamlit/config.toml describe the same theme; change
them together.
"""
from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

ASSETS = Path(__file__).parent / "assets"

# ---- surfaces and ink -------------------------------------------------------------------------
BG = "#07090d"           # page
BG_2 = "#090c11"         # sidebar
SURFACE = "#0e1219"      # cards, charts
SURFACE_2 = "#131923"    # hover, insets, tooltips
SURFACE_3 = "#19202c"
BORDER = "#1d2532"       # 1px hairlines
BORDER_2 = "#2a3444"     # hover / emphasis
GRID = "#161d28"         # chart gridlines
TEXT = "#e6edf3"
TEXT_2 = "#a3afbd"       # secondary (8.4:1 on SURFACE)
TEXT_3 = "#7d8896"       # muted captions (5.2:1 on SURFACE)
FONT = 'Geist, Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
MONO = '"Geist Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'

# ---- one accent + semantic colours ------------------------------------------------------------
ACCENT = "#19e6d2"       # electric teal: UI accent only (active nav, focus, primary action)
GREEN = "#22c55e"        # good / green light
AMBER = "#f5a524"        # transition (yellow) phase / caution
RED = "#f43f5e"          # queue / bad
AMBULANCE = "#ff3b3b"

# kept for the Live Detection page and older callers
GREEN_SIGNAL = GREEN
YELLOW_SIGNAL = AMBER

# ---- data colours -----------------------------------------------------------------------------
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
NEUTRAL = "#6b7785"

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
    ("llm_guided_mp_v3", "llama3.2:3b"): ("llama3.2:3b hybrid (exploratory)", "#a3afbd"),
}
SHORT = {
    ("maxpressure", None): "MaxPressure", ("llm_guarded_mp", "llama3.2:3b"): "LLM main",
    ("llm_guided_mp_v3", "gemma4:e4b"): "gemma4 hybrid", ("fixedtime_webster", None): "Webster",
    ("fixedtime", None): "Fixed-time", ("llm_guided_mp_v3", "nvidia/nemotron-3-ultra-550b-a55b"): "Nemotron hybrid",
    ("preemption_mp", None): "MP + preemption", ("llm_guided_mp_v3", "llama3.1:8b"): "llama3.1:8b hybrid",
    ("llm_guided_mp_v3", "qwen2.5:3b"): "qwen2.5:3b hybrid", ("llm_guided_mp_v3", "llama3.2:3b"): "llama3.2:3b hybrid",
}
EXPLORATORY = {("llm_guided_mp_v3", m) for m in ("gemma4:e4b", "nvidia/nemotron-3-ultra-550b-a55b", "llama3.1:8b",
                                                 "qwen2.5:3b", "llama3.2:3b")}
# Detector classes: boxes are drawn on camera images, so these stay saturated.
CLASS_COLOURS = {"car": SERIES[0], "motorcycle": SERIES[1], "autorickshaw": SERIES[2], "bus": SERIES[3],
                 "truck": SERIES[4], "bicycle": SERIES[6], "person": SERIES[7]}
# Vehicles on the replay map: composite encoding. Every vehicle is drawn to its own length and
# width (configs/scenarios/indian_2x2.yaml), so size separates the classes small (motorcycle),
# medium (car, auto) and large (bus, truck); hue separates the two of each size class, with
# pairs that pass the dataviz validator all-pairs on the asphalt colour (car/auto: normal-vision
# dE 26.5, CVD 15.9; bus/truck: 24.6, 17.3). No green, amber or red: those mean signal states.
VEHICLE_COLOURS = {"motorcycle": "#a3afbd", "auto_rickshaw": "#d55181", "car": "#3987e5", "bus": "#9085e9",
                   "truck": "#199e70", "ambulance": "#ffffff"}
ASPHALT = "#1b2129"
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


def is_exploratory(controller: str, model: str | None) -> bool:
    return (controller, model) in EXPLORATORY


def rgba(hex_colour: str, alpha: float) -> str:
    h = hex_colour.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


# ---- the shared Plotly template ---------------------------------------------------------------
def _template() -> go.layout.Template:
    t = go.layout.Template()
    axis = dict(gridcolor=GRID, gridwidth=1, zerolinecolor=BORDER_2, zerolinewidth=1, linecolor=BORDER,
                tickcolor=BORDER, tickfont=dict(color=TEXT_3, size=11.5), ticks="", showline=False,
                title=dict(font=dict(color=TEXT_2, size=12), standoff=10), automargin=True)
    t.layout = go.Layout(
        font=dict(family=FONT, color=TEXT_2, size=12.5),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES, xaxis=axis, yaxis=axis,
        legend=dict(font=dict(color=TEXT_2, size=12), bgcolor="rgba(0,0,0,0)", orientation="h",
                    yanchor="bottom", y=1.02, xanchor="left", x=0, title=dict(text=""), itemsizing="constant"),
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=BORDER_2, align="left", namelength=-1,
                        font=dict(family=FONT, color=TEXT, size=12.5)),
        hovermode="closest",
        margin=dict(l=8, r=12, t=12, b=8),
        bargap=0.42,
        annotationdefaults=dict(font=dict(color=TEXT_2, size=11.5, family=FONT), arrowcolor=TEXT_3, showarrow=False),
        shapedefaults=dict(line=dict(color=BORDER_2, width=1)),
    )
    t.data.bar = [go.Bar(marker=dict(cornerradius=4, line=dict(width=0)), textfont=dict(color=TEXT, family=FONT))]
    t.data.scatter = [go.Scatter(marker=dict(line=dict(color=SURFACE, width=2)))]
    return t


pio.templates["trafficsense"] = _template()
pio.templates.default = "trafficsense"

# Plotly's config for every chart: no mode bar (charts are read, not edited), no logo.
PLOT_CONFIG = {"displayModeBar": False, "displaylogo": False, "scrollZoom": False, "responsive": True}


def css() -> str:
    """The global stylesheet (assets/theme.css), wrapped for st.html. Streamlit's sanitizer drops a
    <style> whose text contains '<', so inline SVG data URIs in the file must be URL-encoded."""
    text = (ASSETS / "theme.css").read_text(encoding="utf-8")
    if "<" in text:
        raise ValueError("assets/theme.css contains '<' (URL-encode SVG data URIs as %3C ... %3E)")
    return "<style>" + text + "</style>"
