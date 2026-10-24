"""Launch the dashboard and screenshot every page and state with Playwright (Chromium).

    python scripts/screenshot_dashboard.py                       # 1366x768 and 1920x1080
    python scripts/screenshot_dashboard.py --sizes 1366x768      # one size
    python scripts/screenshot_dashboard.py --out <dir>

The first size goes to --out (docs/screenshots), every other size to --out/<width>/. Per size:
  overview(.png|_viewport.png), overview_source.png (a source chip opened),
  live_detection_preview.png (before a run), live_detection(.png|_viewport.png) (after running the
  detector on the bundled sample clip; its FPS are measured when the screenshot is taken),
  network_replay(.png|_viewport.png) (as loaded), network_replay_playing.png (mid-playback, the
  ambulance on screen), network_replay_follow.png (camera following the ambulance),
  network_replay_sim.png (as simulated, not mirrored), network_replay_info.png ("How it is drawn"),
  results(.png|_viewport.png) and results_2.png ... results_5.png (the other tabs).
Each PNG is reduced to a 256-colour palette (Pillow) so the set stays small in git; the dark UI
shows no visible difference. --full-colour keeps Chromium's original PNGs.
Needs: pip install -e ".[dashboard,screenshots]" && python -m playwright install chromium
"""
import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from trafficsense.config import repo_root

RESULT_TABS = ["Signal control", "Ambulances", "Model size · exploratory", "Camera errors", "Detector"]
PLAY_FROM = 955     # replay: seek here, then play briefly (the default ambulance is on screen in both runs)


PALETTE = True


def save(page, path: Path) -> None:
    page.screenshot(path=str(path))
    if PALETTE:
        Image.open(path).convert("RGB").quantize(256, method=Image.Quantize.FASTOCTREE,
                                                 dither=Image.Dither.FLOYDSTEINBERG).save(path, optimize=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main_height(page) -> int:
    return int(page.evaluate("() => (document.querySelector('[data-testid=\"stMain\"]') || document.body).scrollHeight"))


def wait_ready(page) -> None:
    """Wait until the script has finished and the page height has stopped changing."""
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=60000)
    page.wait_for_timeout(1500)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=600000)
    last, stable = -1, 0
    for _ in range(120):
        h = main_height(page)
        stable = stable + 1 if h == last else 0
        if stable >= 3:
            break
        last = h
        page.wait_for_timeout(700)
    page.wait_for_timeout(1500)   # entrance animations and plotly draw after the layout settles


def full_shot(page, path: Path, width: int, height: int) -> None:
    """Streamlit scrolls inside its own container, so grow the viewport to the content height."""
    page.set_viewport_size({"width": width, "height": max(height, main_height(page) + 40)})
    page.wait_for_timeout(2000)
    save(page, path)
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(600)


def scrolled_shot(page, locator, path: Path) -> None:
    """A viewport screenshot with `locator` scrolled to the top of the screen."""
    locator.evaluate("(e) => e.scrollIntoView({block: 'start'})")
    page.wait_for_timeout(900)
    save(page, path)


def seek(page, t: float) -> None:
    page.locator(".rp-range").evaluate("(r, t) => { r.value = t; r.dispatchEvent(new Event('input', {bubbles: true})); }", t)


def shoot(page, url: str, out: Path, width: int, height: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    say = lambda name: print(f"{width}x{height} {name}: {out / name}")

    page.goto(f"{url}/")
    wait_ready(page)
    save(page, out / "overview_viewport.png")
    full_shot(page, out / "overview.png", width, height)
    page.locator(".ts-hero details.ts-src summary").click()
    page.wait_for_timeout(600)
    save(page, out / "overview_source.png")
    say("overview")

    page.goto(f"{url}/live_detection")
    wait_ready(page)
    full_shot(page, out / "live_detection_preview.png", width, height)
    page.get_by_role("button", name="Run detector").click()
    page.wait_for_selector(".pl-stats .pl-stat", timeout=600000)
    wait_ready(page)
    page.locator(".pl-btn").click()              # play the annotated clip for a moment, then pause
    page.wait_for_timeout(2600)
    page.locator(".pl-btn").click()
    save(page, out / "live_detection_viewport.png")
    full_shot(page, out / "live_detection.png", width, height)
    say("live_detection")

    page.goto(f"{url}/network_replay")
    wait_ready(page)
    page.wait_for_selector(".rp-panel canvas", timeout=120000)
    page.wait_for_timeout(1500)
    save(page, out / "network_replay_viewport.png")
    full_shot(page, out / "network_replay.png", width, height)
    tool = page.locator(".rp-tool")
    page.get_by_role("button", name="2×").click()
    seek(page, PLAY_FROM)
    page.get_by_role("button", name="Play").click()
    page.wait_for_timeout(1300)
    page.get_by_role("button", name="Pause").click()
    scrolled_shot(page, tool, out / "network_replay_playing.png")
    page.get_by_role("button", name="Follow ambulance").click()
    page.wait_for_timeout(1500)
    scrolled_shot(page, tool, out / "network_replay_follow.png")
    page.get_by_role("button", name="Grid").click()
    page.get_by_role("button", name="As simulated").click()
    page.wait_for_timeout(1200)
    scrolled_shot(page, tool, out / "network_replay_sim.png")
    page.get_by_role("button", name="Keep left").click()
    page.locator(".rp-info summary").click()
    page.wait_for_timeout(600)
    scrolled_shot(page, tool, out / "network_replay_info.png")
    say("network_replay")

    page.goto(f"{url}/results")
    wait_ready(page)
    save(page, out / "results_viewport.png")
    full_shot(page, out / "results.png", width, height)
    for i, tab in enumerate(RESULT_TABS[1:], start=2):
        page.get_by_role("tab", name=tab).click()
        wait_ready(page)
        full_shot(page, out / f"results_{i}.png", width, height)
    say("results")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--sizes", default="1366x768,1920x1080", help="comma-separated WIDTHxHEIGHT")
    ap.add_argument("--full-colour", action="store_true", help="keep Chromium's PNGs (no 256-colour palette)")
    args = ap.parse_args()
    global PALETTE
    PALETTE = not args.full_colour
    root = repo_root()
    sizes = [tuple(int(v) for v in s.split("x")) for s in args.sizes.split(",")]
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "src/trafficsense/dashboard/app.py",
                             "--server.headless", "true", "--server.port", str(port)],
                            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(120):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for i, (w, h) in enumerate(sizes):
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                shoot(page, url, root / args.out / ("" if i == 0 else str(w)), w, h)
                page.close()
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)


if __name__ == "__main__":
    main()
