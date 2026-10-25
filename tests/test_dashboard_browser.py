"""Browser checks of the dashboard's layout, from a phone to a wide screen: nothing sticks out of its card,
scrolls sideways, is cut off or spills over its neighbour, and no opened panel leaves the screen; the sidebar
can always be reopened; the Overview hero's comparison cells line up; nothing covers or clips a label drawn on
the replay canvas in any view or zoom level; and the detection player keeps its layout after a real run.

The app is started on a free port and driven with Playwright's Chromium. Skipped when Playwright is not
installed, when Chromium cannot start here (it needs libnspr4, libnss3 and libasound2: docs/dashboard.md,
Screenshots, says how to provide them without root), or when the files kept on D are absent.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time

import pytest

from trafficsense.config import load_config, repo_root

sync_api = pytest.importorskip("playwright.sync_api")

# a phone; the narrowest window with the sidebar open (Streamlit opens it only above 768 px, so the main column
# is ~420 px); an XGA projector; laptops; full HD
WIDTHS = (390, 769, 1024, 1280, 1366, 1920)
LABEL_WIDTHS = (390, 1024, 1366, 1920)   # the replay label check (slow): stacked panels and three side-by-side sizes
TABS = ("Signal control", "Ambulances", "Model size · exploratory", "Camera errors", "Detector")
TIMES = (955, 1100)          # replay seconds to check (the default ambulance is on the map at both)
ZOOMS = ((), ("Zoom in",) * 3, ("Reset zoom and pan",), ("Zoom out",) * 2)   # 1, 2.7x, 1, 0.6 (the minimum)

# The page and the shadow roots of the custom components (the replay and the player draw inside one).
ROOTS = "[document, ...Array.from(document.querySelectorAll('*')).map(e => e.shadowRoot).filter(Boolean)]"

# Layout faults a reader would see, as lists of [where, element, text]:
#   outside  an element sticking out of its card (boxes below), not counting out-of-flow content (popovers,
#            tooltips, the screen-reader-only table header) and the charts and drawings, which lay out themselves;
#   scrolls  an element that scrolls sideways (Streamlit's own tab bar excepted: it scrolls with arrow buttons
#            when its tabs do not fit, which is its design);
#   cut      text cut off with an ellipsis;
#   spills   text wider than its own box, running over whatever is next to it;
#   tiny     text in a scaled drawing (an SVG with a viewBox) rendered under 9.5 px;
#   page     the page itself scrolling sideways.
# Content the reader cannot see is skipped: the closed sidebar and the inside of a closed <details>.
LAYOUT_JS = r"""() => {
  const roots = @ROOTS;
  const unseen = (e) => e.closest('[data-testid="stSidebar"][aria-expanded="false"]') || e.closest('details:not([open]) > :not(summary)');
  const name = (e) => String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName).slice(0, 40);
  const text = (e) => (e.textContent || '').trim().slice(0, 40);
  const out = {outside: [], scrolls: [], cut: [], spills: [], tiny: [], page: []};
  const boxes = '.ts-card, .ts-tile, .ts-take, .ts-step, [class*="st-key-card-"], [class*="st-key-panel-"], .ts-duo, '
              + '.ts-hero .cmp > div, .ts-side-status, .ts-head, .ts-arch-flow .nd, .rp-head, .rp-foot, .rp-tool, .rp-card, '
              + '.pl-card, .pl-stat, .pl-bar';
  roots.flatMap(r => Array.from(r.querySelectorAll(boxes))).forEach(box => {
    if (unseen(box)) return;
    const r = box.getBoundingClientRect();
    if (!r.width) return;
    box.querySelectorAll('*').forEach(e => {
      if (e.closest('.js-plotly-plot') || e.closest('svg') || unseen(e)) return;
      for (let x = e; x && x !== box; x = x.parentElement) {
        const p = getComputedStyle(x).position;
        if (p === 'absolute' || p === 'fixed') return;
      }
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const q = e.getBoundingClientRect();
      if (!q.width || !q.height) return;
      if (q.right > r.right + 1 || q.left < r.left - 1 || q.bottom > r.bottom + 1) out.outside.push([name(box), name(e), text(e)]);
    });
  });
  roots.flatMap(r => Array.from(r.querySelectorAll('*'))).forEach(e => {
    if (e.closest('.js-plotly-plot') || unseen(e)) return;
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && e.scrollWidth > e.clientWidth + 1 && !e.matches('[role="tablist"]'))
      out.scrolls.push([name(e), e.scrollWidth, e.clientWidth, text(e)]);
    if (cs.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1) out.cut.push([name(e), e.scrollWidth, e.clientWidth, text(e)]);
    if (cs.overflowX === 'visible' && e.clientWidth && e.scrollWidth > e.clientWidth + 1 && !e.closest('svg')
        && Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim()))
      out.spills.push([name(e), e.scrollWidth, e.clientWidth, text(e)]);
    const svg = e.tagName === 'text' && e.ownerSVGElement, vb = svg && svg.viewBox && svg.viewBox.baseVal;
    if (vb && vb.width) {
      const px = parseFloat(cs.fontSize) * svg.getBoundingClientRect().width / vb.width;
      if (px && px < 9.5) out.tiny.push([name(svg), Math.round(px * 10) / 10, text(e)]);
    }
  });
  const d = document.documentElement, m = document.querySelector('[data-testid="stMain"]');
  if (d.scrollWidth > d.clientWidth + 1 || (m && m.scrollWidth > m.clientWidth + 1)) out.page.push([d.scrollWidth, m && m.scrollWidth]);
  return out;
}""".replace("@ROOTS", ROOTS)

# Every "source" panel and the replay's "How it is drawn", opened together by script: the ones whose panel leaves
# the screen sideways (on a phone, chips that wrapped to the left of their card hung their panels off the left
# edge; a chip at the right edge whose panel opened rightwards did so at every width).
POPOVER_JS = r"""() => {
  const roots = @ROOTS, vw = document.documentElement.clientWidth, bad = [];
  const pops = roots.flatMap(r => Array.from(r.querySelectorAll('details.ts-src, details.rp-info')))
    .filter(d => !d.closest('[data-testid="stSidebar"][aria-expanded="false"]'));
  pops.forEach(d => { d.open = true; });
  pops.forEach(d => {
    const r = d.querySelector('.ts-src-pop, .pop').getBoundingClientRect();
    if (r.width && (r.left < -0.5 || r.right > vw + 0.5))
      bad.push([String(d.className), Math.round(r.left), Math.round(r.right), (d.dataset.tsSrc || '').slice(0, 40)]);
  });
  pops.forEach(d => { d.open = false; });
  return bad;
}""".replace("@ROOTS", ROOTS)

# Per cell of the Overview hero's comparison row: its name, whether the colour dot sits on the name's first line
# (left of it), the cell's top (cells in one row share it) and where the value ends.
HERO_JS = r"""() => @ROOTS.flatMap(root => Array.from(root.querySelectorAll('.ts-hero .cmp > div'))).map(cell => {
  const k = cell.querySelector('.k'), d = k.querySelector('.ts-dot').getBoundingClientRect();
  const name = Array.from(k.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
  const range = document.createRange();
  range.selectNodeContents(name);
  const line = range.getClientRects()[0], mid = d.top + d.height / 2;
  return {name: name.textContent.trim(), dot_with_name: mid > line.top && mid < line.bottom && d.right <= line.left + 1,
          top: cell.getBoundingClientRect().top, value_bottom: cell.querySelector('.v').getBoundingClientRect().bottom};
})""".replace("@ROOTS", ROOTS)

# Per replay panel: the label boxes the canvas drew (its own record), the canvas size, and whether any panel
# element (header, footer, timer, zoom, compass) overlaps the canvas.
LABELS_JS = r"""() => @ROOTS.flatMap(root => Array.from(root.querySelectorAll('.rp-panel'))).map(panel => {
  const area = panel.querySelector('.rp-canvas').getBoundingClientRect();
  const canvas = panel.querySelector('canvas');
  const [w, h] = (canvas.dataset.size || '0,0').split(',').map(Number);
  const labels = JSON.parse(canvas.dataset.labels || '[]');
  const covering = Array.from(panel.querySelectorAll('.rp-head, .rp-foot, .rp-who, .rp-timer, .rp-zoom, .rp-compass'))
    .map(e => e.getBoundingClientRect())
    .filter(o => o.right > area.left + 0.5 && o.left < area.right - 0.5 && o.bottom > area.top + 0.5 && o.top < area.bottom - 0.5).length;
  const outside = labels.filter(([x, y, bw, bh]) => x < -0.5 || y < -0.5 || x + bw > w + 0.5 || y + bh > h + 0.5);
  return {n: labels.length, outside, covering, w, h};
})""".replace("@ROOTS", ROOTS)

# Whether the sidebar is open, whether the button that reopens it is on screen, and whether the page starts below it.
SIDEBAR_JS = r"""() => {
  const sb = document.querySelector('[data-testid="stSidebar"]'), btn = document.querySelector('[data-testid="stExpandSidebarButton"]');
  const b = btn ? btn.getBoundingClientRect() : null, m = document.querySelector('[data-testid="stMainBlockContainer"]');
  const content = m.getBoundingClientRect().top + parseFloat(getComputedStyle(m).paddingTop);
  return {expanded: sb.getAttribute('aria-expanded'), button: !!(b && b.width > 0 && b.height > 0 && getComputedStyle(btn).visibility !== 'hidden'),
          below_button: !b || !b.width || content >= b.bottom};
}"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app():
    cfg = load_config("configs/default.yaml")
    if not (repo_root() / cfg["paths"]["replays"]).exists():
        pytest.skip("replays not present (kept on D, see configs/default.yaml)")
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "src/trafficsense/dashboard/app.py",
                             "--server.headless", "true", "--server.port", str(port)],
                            cwd=repo_root(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=30)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception as e:     # browser or its system libraries missing
            pytest.skip(f"Chromium cannot start here ({type(e).__name__}); see docs/dashboard.md, Screenshots")
        yield b
        b.close()


def _settle(page, extra_ms: int) -> None:
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=60000)
    page.wait_for_timeout(1500)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=600000)
    page.wait_for_timeout(extra_ms)


def _faults(page, where: str) -> list:
    faults = [(where, kind, *x) for kind, items in page.evaluate(LAYOUT_JS).items() for x in items]
    return faults + [(where, "popover", *x) for x in page.evaluate(POPOVER_JS)]


def test_no_layout_faults(browser, app):     # browser first: skip before starting the app
    """Every page and Results tab, loaded at each width (so the sidebar starts as it would there)."""
    bad = []
    for w in WIDTHS:
        page = browser.new_page(viewport={"width": w, "height": 900})
        for path in ("", "live_detection", "network_replay"):
            page.goto(f"{app}/{path}")
            _settle(page, 4000)
            bad += _faults(page, f"{w} {path or 'overview'}")
        page.goto(f"{app}/results")
        _settle(page, 4000)
        for tab in TABS:
            # a click by script: on a phone the tab may be scrolled out of Streamlit's tab bar
            page.get_by_role("tab", name=tab).evaluate("e => e.click()")
            page.wait_for_timeout(1800)
            bad += _faults(page, f"{w} results/{tab}")
        page.close()
    assert not bad, bad[:10]


def test_sidebar_can_always_be_reopened(browser, app):
    """The sidebar starts closed on a phone and open on a laptop, where it can be closed. Either way the button
    that reopens it is on screen, the page starts below it, and it works (theme.css once hid it together with
    Streamlit's toolbar, leaving no way back to the page links)."""
    page = browser.new_page(viewport={"width": 390, "height": 800})
    page.goto(app)
    _settle(page, 1500)
    s = page.evaluate(SIDEBAR_JS)
    assert s == {"expanded": "false", "button": True, "below_button": True}, s
    page.locator('[data-testid="stExpandSidebarButton"]').click()
    page.wait_for_timeout(1000)
    assert page.evaluate(SIDEBAR_JS)["expanded"] == "true"
    page.close()

    page = browser.new_page(viewport={"width": 1366, "height": 800})
    page.goto(app)
    _settle(page, 1500)
    assert page.evaluate(SIDEBAR_JS)["expanded"] == "true"
    # the collapse button shows on hover; a click by script is the same click
    page.locator('[data-testid="stSidebarCollapseButton"]').evaluate("e => (e.querySelector('button') || e).click()")
    page.wait_for_timeout(1000)
    s = page.evaluate(SIDEBAR_JS)
    assert s == {"expanded": "false", "button": True, "below_button": True}, s
    page.locator('[data-testid="stExpandSidebarButton"]').click()
    page.wait_for_timeout(1000)
    assert page.evaluate(SIDEBAR_JS)["expanded"] == "true"
    page.close()


def test_hero_cells_line_up(browser, app):
    """Overview hero, comparison row (four cells, or two rows of two on a narrow page): every colour dot sits on
    the first line of its name (the 'exploratory' badge wraps below the name, inside its cell, which the layout
    test checks), and the values of the cells in one row share one line whatever their labels' lengths."""
    for w in WIDTHS:
        page = browser.new_page(viewport={"width": w, "height": 900})
        page.goto(app)
        _settle(page, 2000)
        cells = page.evaluate(HERO_JS)
        page.close()
        assert len(cells) == 4, (w, cells)
        assert all(c["dot_with_name"] for c in cells), (w, cells)
        rows: dict[int, list[float]] = {}
        for c in cells:
            rows.setdefault(round(c["top"]), []).append(c["value_bottom"])
        assert len(rows) in (1, 2), (w, cells)
        for bottoms in rows.values():
            assert max(bottoms) - min(bottoms) <= 1, (w, cells)


def test_replay_labels_never_covered_or_clipped(browser, app):
    """In both views, the grid and the follow camera, at every zoom level: every label the canvas drew lies
    inside the canvas, and no panel element overlaps the canvas."""
    problems, checked = [], 0
    for w in LABEL_WIDTHS:
        page = browser.new_page(viewport={"width": w, "height": 900})
        page.goto(f"{app}/network_replay")
        _settle(page, 4000)
        page.wait_for_selector(".rp-panel canvas", timeout=120000)
        for t in TIMES:
            page.locator(".rp-range").evaluate(
                "(r, t) => { r.value = t; r.dispatchEvent(new Event('input', {bubbles: true})); }", t)
            for side in ("As simulated", "Keep left"):
                page.get_by_role("button", name=side).click()
                for mode in ("Grid", "Follow ambulance"):
                    page.get_by_role("button", name=mode).click()
                    for clicks in ZOOMS:
                        for name in clicks:
                            page.get_by_role("button", name=name).first.click()
                        page.wait_for_timeout(1100)          # the camera eases to its target
                        # the whole grid at zoom 1 always shows labels (a check that the canvas records them);
                        # zoomed in, the view can show a stretch with no junction or queue to label
                        whole = mode == "Grid" and clicks in ((), ("Reset zoom and pan",))
                        for i, panel in enumerate(page.evaluate(LABELS_JS)):
                            checked += 1
                            if panel["outside"] or panel["covering"] or (whole and not panel["n"]):
                                problems.append((w, t, side, mode, clicks[:1], i, panel))
                    page.get_by_role("button", name="Reset zoom and pan").first.click()
        page.close()
    assert checked == len(LABEL_WIDTHS) * len(TIMES) * 2 * 2 * len(ZOOMS) * 2
    assert not problems, problems[:5]


def test_detection_player_layout(browser, app):
    """After a real run of the detector on the sample clip, the player (frames, controls, per-class rows, chart
    and the measured speeds) has no layout fault at any width."""
    cfg = load_config("configs/default.yaml")
    weights = (repo_root() / cfg["paths"]["detector_runs"] / "detector" / cfg["perception"]["train"]["run_name"]
               / "weights" / "best.pt")
    clip = repo_root() / cfg["paths"]["dashboard_media"] / cfg["dashboard"]["detection"]["sample_clip"]["file"]
    if not (weights.is_file() and clip.is_file()):
        pytest.skip("detector weights or sample clip not present (kept on D, see configs/default.yaml)")
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    page.goto(f"{app}/live_detection")
    _settle(page, 2000)
    page.get_by_role("button", name="Run detector").click()
    page.wait_for_function(f"() => {ROOTS}.some(r => r.querySelector('.pl-stat'))", timeout=600000)
    bad = []
    for w in WIDTHS:
        page.set_viewport_size({"width": w, "height": 900})
        page.wait_for_timeout(2000)
        bad += _faults(page, f"{w} player")
    page.close()
    assert not bad, bad[:10]
