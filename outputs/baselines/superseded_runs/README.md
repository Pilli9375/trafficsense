# Superseded baseline runs

These six runs used controller name `maxpressure` with a 15 s decision interval and 10 s min
green, the default chosen by the decision-interval sweep (`docs/baselines.md`, section 1).
After the min-green sweep (`docs/baselines.md`, section 2) the `maxpressure` default became a
5 s interval with a 15 s min green, and the 15 s-interval setting became the controller
`maxpressure_15s`. The runs were moved here, not deleted, so that `outputs/baselines/runs/`
uses one setting per controller name. They are reproduced by the `maxpressure_15s` runs in
`outputs/baselines/runs/` (same flow files, same settings).
