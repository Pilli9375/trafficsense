# Results Cheat Sheet

Every headline number, what it means in plain words, and where it comes from. "Lower is better"
for every time. The **Source** column names the result file in `outputs/`:

- **full** = `outputs/full/results.json` (main and ambulance experiments)
- **camera** = `outputs/camera_error/results.json` (camera errors)
- **detector** = `outputs/perception/detector_test.json`, `detector_val.json`, `detector_train.json`
- **benchmark** = `docs/llm_benchmark.md` (the LLM benchmark tables, checked against `outputs/llm_benchmark/`)
- **fresh clone** = `outputs/reproducibility/fresh_clone.json`

## Normal Traffic (Average Travel Time, Seconds, Mean of 3 Seeds)

| What | Number | In plain words | Source |
|:--------------------|:--|:-----------------------------------|:--|
| MaxPressure, off-peak | 88.1<!--=f.off.mp.att--> ± 1.0<!--=f.off.mp.att_sd--> | Best classical controller, light traffic | full |
| MaxPressure, peak | 115.5<!--=f.peak.mp.att--> ± 0.9<!--=f.peak.mp.att_sd--> | Best classical controller, heavy traffic | full |
| MaxPressure, Jinan 3x4 | 300.9<!--=f.jinan.mp.att--> | Real-world flow from CoLLMLight's data | full |
| LLM pre-registered, off-peak | 89.0<!--=f.off.llm.att--> (+0.9<!--=f.off.llm.vs_mp-->%) | Slightly slower than MaxPressure | full |
| LLM pre-registered, peak | 116.1<!--=f.peak.llm.att--> (+0.5<!--=f.peak.llm.vs_mp-->%) | Slightly slower; within seed noise | full |
| LLM pre-registered, Jinan | 303.2<!--=f.jinan.llm.att--> (+0.8<!--=f.jinan.llm.vs_mp-->%) | Slightly slower | full |
| Webster plan, peak | 116.3<!--=f.peak.web.att--> (+0.7<!--=f.peak.web.vs_mp-->%) | Effectively tied with MaxPressure at peak | full |
| Webster plan, off-peak | 100.4<!--=f.off.web.att--> (+13.9<!--=f.off.web.vs_mp-->%) | A fixed plan loses in light traffic | full |
| FixedTime 30 s, peak | 279.9<!--=f.peak.ft.att--> (+142.3<!--=f.peak.ft.vs_mp-->%) | The naive plan fails at peak | full |
| gemma4 (exploratory), peak | 113.7<!--=f.peak.gem.att--> (−1.5<!--=f.peak.gem.vs_mp-->%) | Faster at peak on all 3 seeds: a lead only | full |
| gemma4 (exploratory), off-peak | 90.5<!--=f.off.gem.att--> (+2.7<!--=f.off.gem.vs_mp-->%) | Slower off-peak | full |

## How the LLM Controller Behaves

| What | Number | In plain words | Source |
|:--------------------|:--|:-----------------------------------|:--|
| Model's answer differs from MaxPressure | 87<!--=l.amb.llm.differs-->–93<!--=l.peak.llm.differs-->% of calls | The small model disagrees a lot | full |
| Guard replaces the answer | 76<!--=l.amb.llm.guard-->–83<!--=l.peak.llm.guard-->% of calls | The guard catches most of it | full |
| Applied phase differs from MaxPressure | 10<!--=l.peak.llm.applied-->–11<!--=l.jinan.llm.applied-->% of calls | In practice it mostly acts like MaxPressure | full |
| Mean time per LLM call | 1.02<!--=l.peak.llm.lat-->–1.10<!--=l.jinan.llm.lat--> s | Fast enough for a 5 s decision interval | full |
| gemma4 time per call (peak) | 4.54<!--=l.peak.gem.lat--> s | Too slow for real time on our GPU | full |
| Benchmark: small models chose the lowest pressure | 77<!--=docs/llm_benchmark.md | llm_decisions | hybrid (guided) & qwen2.5 | lowest-pressure-->–86<!--=docs/llm_benchmark.md | llm_decisions | hybrid (guided) & llama3.2 | lowest-pressure-->% | They misread pressure | benchmark |

## Ambulances (Peak + Ambulances, 5 Seeds, 29 Signal-Relevant Ambulances)

| What | Number | In plain words | Source |
|:--------------------|:--|:-----------------------------------|:--|
| MaxPressure | 130.1<!--=e.mp.amb--> s (stopped 62.3<!--=e.mp.amb_stop--> s) | Ignores ambulances | full |
| Webster plan | 123.5<!--=e.web.amb--> s | Also ignores them | full |
| LLM pre-registered | 88.9<!--=e.llm.amb--> s (stopped 21.2<!--=e.llm.amb_stop--> s) | 31.7<!--=e.llm.amb_cut_vs_mp-->% faster than MaxPressure | full |
| Preemption rule | 81.2<!--=e.pre.amb--> s (stopped 14.1<!--=e.pre.amb_stop--> s) | Still the best | full |
| gemma4 (exploratory) | 82.2<!--=e.gem.amb--> s | Close to preemption | full |
| Network ATT, LLM vs MaxPressure | 116.4<!--=e.llm.att--> vs 115.7<!--=e.mp.att--> s | Other traffic does not pay (spread ±2.3<!--=e.mp.att_sd--> s) | full |

## Camera Errors (Change in ATT Against Perfect Counts)

| What | Number | In plain words | Source |
|:--------------------|:--|:-----------------------------------|:--|
| MaxPressure, junction camera | +4.8<!--=c.off.mp.junction.pct-->% off-peak, +2.3<!--=c.peak.mp.junction.pct-->% peak | A few percent slower | camera |
| MaxPressure, crowded / far | +8.2<!--=c.off.mp.crowded.pct-->% off-peak, +4.4<!--=c.peak.mp.crowded.pct-->% peak | Worse camera, worse result | camera |
| LLM arm, junction camera | +5.1<!--=c.off.llm.junction.pct-->% off-peak, +1.6<!--=c.peak.llm.junction.pct-->% peak | About as much as MaxPressure | camera |
| Webster plan | +0.0<!--=c.off.web.junction.pct-->% | Reads no counts: unaffected | camera |
| Peak, junction camera: MaxPressure vs Webster | 118.2<!--=c.peak.mp.junction.att--> vs 116.3<!--=c.peak.web.junction.att--> s | At peak, adaptive control loses its lead | camera |
| Half of vehicles missed, nothing else wrong | +3.0<!--=c.sweep.off.p50.pct-->% off-peak | Misses alone cost little | camera |
| False detections alone (post-hoc) | +3.8<!--=c.dec.false.off.pct-->% of +4.8<!--=c.dec.all.off.pct-->% off-peak | Phantom vehicles do most of the damage | camera |

## Detector (YOLOv8n on IDD, Test Split)

| What | Number | In plain words | Source |
|:--------------------|:--|:-----------------------------------|:--|
| mAP50 / mAP50-95 | 0.563<!--=d.test.map50--> / 0.375<!--=d.test.map5095--> | Reasonable for a small model on crowded scenes | detector |
| Validation mAP50 | 0.602<!--=d.val.map50--> | Slightly higher on validation, as expected | detector |
| Test images / boxes | 10,225<!--=d.test.images--> / 88,753<!--=d.test.gt--> | Never used in training | detector |
| Confidence threshold | 0.3<!--=d.conf--> | Frozen on validation before the test | detector |
| Training time | 13.3<!--=d.train_h--> h, best epoch 49<!--=d.best_epoch--> | Still improving slowly at the end | detector |

## Counts and Checks

| What | Number | In plain words | Source |
|:--------------------|:--|:-----------------------------------|:--|
| Full-experiment runs | 67<!--=f.runs--> | Main comparison | full |
| Camera-error runs | 130<!--=c.runs--> | Camera experiment | camera |
| Repeated baseline runs identical | 27<!--=f.reproduced--> of 27<!--=f.reproduced_of--> | Deterministic and repeatable | full |
| Fresh-clone deterministic runs identical | 42<!--=r.det_runs_identical--> of 42<!--=r.det_runs--> | Reproduced from a fresh copy | fresh clone |
| Fresh-clone LLM answers identical | 121<!--=r.llm_identical_answers--> | A short LLM run repeated exactly | fresh clone |
