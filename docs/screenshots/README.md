# Dashboard screenshots

Made by `python scripts/screenshot_dashboard.py` (Playwright, Chromium, 1366×768). The same pages and
states at 1920×1080 are saved on D (`<paths.dashboard_media>/screenshots/1920/`, not in git).
`<page>.png` is the whole page, `<page>_viewport.png` the first screen.

* `overview.png`, `overview_viewport.png`; `overview_source.png` with a source chip opened.
* `live_detection_preview.png` before a run; `live_detection.png` and `live_detection_viewport.png` after
  running the detector on the bundled sample clip. Their FPS were measured on the GTX 1650 when the
  screenshots were taken.
* `network_replay.png` and `network_replay_viewport.png` as loaded; `network_replay_playing.png`
  mid-playback (between two logged seconds, so positions are interpolated); `network_replay_follow.png`
  with the camera following the ambulance; `network_replay_sim.png` as simulated (not mirrored);
  `network_replay_info.png` with "How it is drawn" open.
* `results.png` and `results_viewport.png` (Signal control); `results_2.png` to `results_5.png` are the
  other tabs (Ambulances, Model size, Camera errors, Detector).
