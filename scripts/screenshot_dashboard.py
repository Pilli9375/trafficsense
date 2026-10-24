"""Launch the dashboard and take a screenshot of every page with Playwright (Chromium).

    python scripts/screenshot_dashboard.py                 # 1366x768, into docs/screenshots/
    python scripts/screenshot_dashboard.py --out <dir> --width 1366 --height 768

Live Detection is screenshotted after running the detector on the bundled sample clip.
Needs: pip install -e ".[dashboard]" playwright && python -m playwright install chromium
"""
import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from trafficsense.config import repo_root

PAGES = [("overview", ""), ("live_detection", "live_detection"), ("network_replay", "network_replay"),
         ("results", "results")]
RESULT_TABS = ["Signal control", "Ambulances", "Model size · exploratory", "Camera errors", "Detector"]


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
    page.wait_for_timeout(1000)   # plotly draws after the layout settles


def full_shot(page, path: Path, width: int, height: int) -> None:
    """Streamlit scrolls inside its own container, so grow the viewport to the content height."""
    h = main_height(page)
    page.set_viewport_size({"width": width, "height": max(height, int(h) + 40)})
    page.wait_for_timeout(2000)
    page.screenshot(path=str(path))
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(500)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--width", type=int, default=1366)
    ap.add_argument("--height", type=int, default=768)
    args = ap.parse_args()
    root = repo_root()
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
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
            page = browser.new_page(viewport={"width": args.width, "height": args.height}, device_scale_factor=1)
            for name, path in PAGES:
                page.goto(f"{url}/{path}")
                wait_ready(page)
                if name == "live_detection":
                    page.get_by_role("button", name="Run detector").click()
                    page.wait_for_selector("text=Frames processed", timeout=600000)
                    wait_ready(page)
                page.screenshot(path=str(out / f"{name}_viewport.png"))
                full_shot(page, out / f"{name}.png", args.width, args.height)
                print(f"{name}: {out / (name + '.png')}")
                if name == "results":
                    for i, tab in enumerate(RESULT_TABS[1:], start=2):
                        page.get_by_role("tab", name=tab).click()
                        wait_ready(page)
                        full_shot(page, out / f"results_{i}.png", args.width, args.height)
                        print(f"results tab {tab}: {out / f'results_{i}.png'}")
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)


if __name__ == "__main__":
    main()
