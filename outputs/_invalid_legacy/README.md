# Invalid legacy results — do not cite

Everything under this folder was produced by the pre-restructuring pipeline and is **not valid**
evidence. It is kept only for reference (and for the "before" comparison in the report) until the
rebuilt pipeline reproduces equivalent experiments. Do not quote numbers from here.

Why these results are invalid:

1. **LLM results came from a mock server.** The "LLM" decisions (`cooperative_decisions.json`,
   `simulation_results/trafficsense_*`, `isolated_*`, `ablation_summary.json`, ...) were produced
   against `tests/mock_ollama.py`, which returned random phases — not a real language model.
2. **YOLO was trained on synthetic coloured rectangles**, not real traffic imagery
   (`yolo_training/`, `perception_demo/`, `synthetic_perception.json`, `demo_perception.json`,
   `test_traffic.mp4`). The weights in `models/yolo/*.pt` (untracked) share this problem.
3. **Per-intersection states were identical.** The old environment summed every lane in the
   network for each intersection, so all intersections saw the same state
   (affects all `simulation_results/*`, including FixedTime and MaxPressure baselines).
4. **Wrong phase indices.** Phase 0 (a right-turn-only transition phase in the Synthetic 4x4
   roadnet) was treated as a green phase, and throughput was always 0 because of a non-existent
   keyword passed to `get_vehicles`.
5. **The old Indian 2x2 scenario could not carry traffic.** `indian_2x2_roadnet.json` (moved
   here from `data/synthetic/`) has empty `roadLinks`, so no vehicle could cross an
   intersection. It was replaced in Phase 2 by `data/scenarios/indian_2x2/` (see
   `docs/indian_scenario.md`).

Replacement results are written to `outputs/runs/<timestamp>_<scenario>_<controller>_s<seed>/`
with full provenance in `summary.json` (see `CLAUDE.md`).

## Stale documents and code (moved here in Phase 6)

Moved, not deleted, when the README and the report were rewritten from `outputs/`. They describe
the pre-restructuring project and contradict the current data; do not cite them.

* `docs/`: `DELIVERY_SUMMARY.md`, `SECOND_REVIEW_CHECKLIST.md`, `PROJECT_STATUS.md` and
  `weekly_progress.md` (the "Second Review Ready" status, mAP50 0.50 from the synthetic-rectangle
  detector, an RTX 4050, Gemma 3 4B as the controller); `COLLMLIGHT_ARCHITECTURE.md` and
  `INTEGRATION_POINTS.md` (the old plan of feeding a perception JSON into CoLLMLight's own code,
  which was never built that way); `DATASETS.md` (DriveIndia / DATS_2022, never used: the
  detector is trained on IDD, `docs/perception.md`).
* `docs/report/`: the old report draft (`report.md`), its `bibliography.bib` (placeholder
  entries) and the figure list. Replaced by the chapters in `docs/report/`.
* `code/`: `run_proper_sim.py`, `run_maxpressure_sim.py`, `run_ablation_study.py` (the old
  360-step simulations, hardcoded `/mnt/c` paths and `sys.path` hacks), `requirements.txt`
  (Windows-native install, replaced by `pyproject.toml`), and `tests/verify_*.py` (scripts with
  hardcoded `C:\` paths that checked the old files above; pytest never collected them).
* `docs/data/`: `dats_2022/` (notes for DATS_2022, never downloaded or used) and
  `unified_indian/data.yaml` (the class list of the old "unified" synthetic dataset). Moved from
  `data/raw/` and `data/processed/`.
