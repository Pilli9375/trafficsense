"""Browser checks of the dashboard's layout: nothing sticks out of its card, at several screen widths.

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
