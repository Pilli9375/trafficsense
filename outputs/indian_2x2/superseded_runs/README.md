# Superseded Indian 2x2 runs

These six runs used controller name `maxpressure` with the settings in force on 2026-10-14
before tuning (decision interval 5 s). After the decision-interval sweep
(`docs/baselines.md`, section 1) the `maxpressure` default became 15 s, and the 5 s setting
became the controller `maxpressure_5s`. The runs were moved here, not deleted, so that the
results in `outputs/indian_2x2/runs/` use one setting per controller name. They are
reproduced by the `maxpressure_5s` runs in `outputs/indian_2x2/runs/` (same flow files, same
settings).
