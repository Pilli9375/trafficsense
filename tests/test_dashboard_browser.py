"""Browser checks of the dashboard's layout: nothing sticks out of its card, and nothing covers or clips a
label drawn on the replay canvas, at several screen widths, in every replay view and zoom level.

The app is started on a free port and driven with Playwright's Chromium. Skipped when Playwright is not
installed, when Chromium cannot start here (it needs libnspr4, libnss3 and libasound2: docs/dashboard.md,
Screenshots, says how to provide them without root), or when the replays kept on D are absent.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time

import pytest

from trafficsense.config import load_config, repo_root

sync_api = pytest.importorskip("playwright.sync_api")

WIDTHS = (1280, 1366, 1920)
TABS = ("Signal control", "Ambulances", "Model size · exploratory", "Camera errors", "Detector")
TIMES = (955, 1100)          # replay seconds to check (the default ambulance is on the map at both)
ZOOMS = ((), ("Zoom in",) * 3, ("Reset zoom and pan",), ("Zoom out",) * 2)   # 1, 2.7x, 1, 0.6 (the minimum)

# The page and the shadow roots of the custom components (the replay draws inside one).
ROOTS = "[document, ...Array.from(document.querySelectorAll('*')).map(e => e.shadowRoot).filter(Boolean)]"

# Elements (not absolutely positioned, not popovers, not inside SVG or Plotly) that extend past their card.
OVERFLOW_JS = r"""() => {
  const boxes = '.ts-card, .ts-tile, .ts-take, .ts-step, [class*="st-key-card-"], [class*="st-key-panel-"], .ts-duo, '
              + '.ts-hero .cmp > div, .ts-side-status, .ts-head, .rp-head, .rp-foot';
  const bad = [];
  @ROOTS.flatMap(root => Array.from(root.querySelectorAll(boxes))).forEach(box => {
    const r = box.getBoundingClientRect();
    box.querySelectorAll('*').forEach(e => {
      if (e.closest('.ts-src-pop') || e.closest('.ts-hero-grid') || e.closest('.js-plotly-plot') || e.closest('svg')) return;
      const cs = getComputedStyle(e);
      if (cs.position === 'absolute' || cs.position === 'fixed' || cs.display === 'none' || cs.visibility === 'hidden') return;
      const q = e.getBoundingClientRect();
      if (!q.width || !q.height) return;
      if (q.right > r.right + 1 || q.left < r.left - 1 || q.bottom > r.bottom + 1)
        bad.push([String(box.className).slice(0, 40), String(e.className || e.tagName).slice(0, 40), (e.textContent || '').trim().slice(0, 30)]);
    });
  });
  return bad;
}""".replace("@ROOTS", ROOTS)

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


def test_nothing_overflows_its_card(browser, app):     # browser first: skip before starting the app
    bad = []
    for w in WIDTHS:
        page = browser.new_page(viewport={"width": w, "height": 900})
        for path in ("", "live_detection", "network_replay"):
            page.goto(f"{app}/{path}")
            _settle(page, 5000)
            bad += [(w, path or "overview", *x) for x in page.evaluate(OVERFLOW_JS)]
        page.goto(f"{app}/results")
        _settle(page, 5000)
        for tab in TABS:
            page.get_by_role("tab", name=tab).click()
            page.wait_for_timeout(1500)
            bad += [(w, f"results/{tab}", *x) for x in page.evaluate(OVERFLOW_JS)]
        page.close()
    assert not bad, bad[:10]


def test_replay_labels_never_covered_or_clipped(browser, app):
    """In both views, the grid and the follow camera, at every zoom level: every label the canvas drew lies
    inside the canvas, and no panel element overlaps the canvas."""
    problems, checked = [], 0
    for w in WIDTHS:
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
    assert checked == len(WIDTHS) * len(TIMES) * 2 * 2 * len(ZOOMS) * 2
    assert not problems, problems[:5]
