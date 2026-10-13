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

Replacement results are written to `outputs/runs/<timestamp>_<scenario>_<controller>_s<seed>/`
with full provenance in `summary.json` (see `CLAUDE.md`).
