# Dashboard screenshots

Made by `python scripts/screenshot_dashboard.py --offline` (Playwright, Chromium, 1366×768, every request
that is not to the app blocked), saved as lossless WebP. The same pages and states at 1920×1080 are saved on
D (`<paths.dashboard_media>/screenshots/1920/`, not in git). `<page>.webp` is the whole page,
`<page>_viewport.webp` the first screen.

* `overview.webp`, `overview_viewport.webp`; `overview_source.webp` with a source chip opened.
* `live_detection_preview.webp` before a run; `live_detection.webp` and `live_detection_viewport.webp` after
  running the detector on the bundled sample clip. Their FPS were measured on the GTX 1650 when the
  screenshots were taken.
* `network_replay.webp` and `network_replay_viewport.webp` as loaded (as simulated, north up);
  `network_replay_playing.webp` mid-playback (between two logged seconds, so positions are interpolated);
  `network_replay_follow.webp` with the camera following the ambulance; `network_replay_keepleft.webp` in the
  keep-left view (the left-right mirror, north still up); `network_replay_info.webp` with "How it is drawn"
  open.
* `results.webp` and `results_viewport.webp` (Signal control); `results_2.webp` to `results_5.webp` are the
  other tabs (Ambulances, Model size, Camera errors, Detector).
