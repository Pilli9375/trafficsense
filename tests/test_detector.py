"""Detector training helpers (no GPU, no Ultralytics training)."""
import hashlib
import json

import pytest

from trafficsense.config import load_config
from trafficsense.perception import detector


def test_sample_lines_is_seeded_ordered_subset():
    lines = [f"img{i}" for i in range(100)]
    a = detector.sample_lines(lines, 0.1, 0)
    assert len(a) == 10 and a == detector.sample_lines(lines, 0.1, 0)
    assert a == sorted(a, key=lines.index)
    assert a != detector.sample_lines(lines, 0.1, 1)
    assert detector.sample_lines(lines[:3], 0.01, 0) and len(detector.sample_lines(lines[:3], 0.01, 0)) == 1
    with pytest.raises(ValueError):
        detector.sample_lines(lines, 0, 0)


def test_run_state(tmp_path):
    assert detector.run_state(tmp_path) == "new"
    (tmp_path / "weights").mkdir()
    (tmp_path / "weights" / "last.pt").write_bytes(b"x")
    assert detector.run_state(tmp_path) == "resumable"
    (tmp_path / detector.DONE_MARKER).write_text("{}")
    assert detector.run_state(tmp_path) == "finished"


def test_sha256(tmp_path):
    p = tmp_path / "w.pt"
    p.write_bytes(b"abc" * 1000)
    assert detector.sha256(p) == hashlib.sha256(b"abc" * 1000).hexdigest()


def test_train_overrides_from_default_config():
    cfg = load_config("configs/default.yaml")
    o = detector.train_overrides(cfg["perception"]["train"], cfg["perception"]["imgsz"])
    assert o == {"imgsz": 640, "epochs": 50, "patience": 10, "batch": 8, "amp": False, "workers": 8,
                 "cache": False, "seed": 0, "deterministic": True}
    with pytest.raises(KeyError, match="amp"):
        detector.train_overrides({k: v for k, v in cfg["perception"]["train"].items() if k != "amp"}, 640)


def test_read_log_and_gpu_summary(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps({"event": "epoch", "epoch": e}) for e in (1, 2, 2)) + "\n")
    assert [r["epoch"] for r in detector.read_log(log)] == [1, 2, 2]
    assert detector.read_log(tmp_path / "missing.jsonl") == []
    csv = tmp_path / "gpu.csv"
    csv.write_text("time,gpu_util_pct,mem_used_mib\n1,90,2000\n2,100,2500\n")
    assert detector.summarize_gpu_csv(csv) == {"samples": 2, "util_mean_pct": 95.0, "mem_used_max_mib": 2500.0}


def test_batch_images_last_batch_is_remainder():
    assert [detector.batch_images(i, 8, 20) for i in (1, 2, 3, 4)] == [8, 8, 4, 0]


def _stub_trainer(loss_items, batch_size=8, n_images=20):
    import types
    import torch
    return types.SimpleNamespace(batch_size=batch_size, train_loader=types.SimpleNamespace(dataset=range(n_images)),
                                 epoch=0, epochs=1, loss=torch.tensor(1.0), loss_items=loss_items,
                                 tloss=loss_items, metrics={"metrics/mAP50(B)": 0.1}, fitness=0.1)


@pytest.fixture
def no_cuda(monkeypatch):
    import torch
    for name in ("reset_peak_memory_stats", "synchronize"):
        monkeypatch.setattr(torch.cuda, name, lambda: None)
    for name in ("max_memory_allocated", "max_memory_reserved"):
        monkeypatch.setattr(torch.cuda, name, lambda: 0)


def test_train_monitor_logs_epoch_and_stops_on_nan(tmp_path, no_cuda):
    import torch
    mon = detector.TrainMonitor(tmp_path / "log.jsonl", batch=8, skip=1)
    t = _stub_trainer({"box_loss": torch.tensor(1.0), "cls_loss": torch.tensor(2.0)})
    mon.on_train_epoch_start(t)
    for _ in range(3):
        mon.on_train_batch_start(t)
        mon.on_train_batch_end(t)
    mon.on_train_epoch_end(t)
    mon.on_fit_epoch_end(t)
    rec = detector.read_log(tmp_path / "log.jsonl")[0]
    assert rec["train_images"] == 20 and rec["batch"] == 8
    assert rec["train_losses"] == {"box_loss": 1.0, "cls_loss": 2.0} and rec["losses_finite"]

    t.loss_items = {"box_loss": torch.tensor(float("nan"))}
    mon.on_train_batch_start(t)
    with pytest.raises(RuntimeError, match="Non-finite"):
        mon.on_train_batch_end(t)
    assert detector.read_log(tmp_path / "log.jsonl")[-1]["event"] == "nonfinite_loss"


def test_train_monitor_stops_when_batch_is_halved(tmp_path, no_cuda):
    import torch
    mon = detector.TrainMonitor(tmp_path / "log.jsonl", batch=8)
    t = _stub_trainer({"box_loss": torch.tensor(1.0)}, batch_size=4)
    mon.on_train_epoch_start(t)
    mon.on_train_batch_start(t)
    with pytest.raises(RuntimeError, match="Batch size changed"):
        mon.on_train_batch_end(t)


def test_final_validation_is_not_logged_as_an_epoch(tmp_path, no_cuda):
    import torch
    mon = detector.TrainMonitor(tmp_path / "log.jsonl", batch=8)
    t = _stub_trainer({"box_loss": torch.tensor(1.0)})
    mon.on_train_epoch_start(t)
    mon.on_train_batch_start(t)
    mon.on_train_batch_end(t)
    mon.on_train_epoch_end(t)
    mon.on_fit_epoch_end(t)
    mon.on_fit_epoch_end(t)   # Ultralytics' final validation of best.pt, no training epoch before it
    assert [r["event"] for r in detector.read_log(tmp_path / "log.jsonl")] == ["epoch", "final_eval"]
