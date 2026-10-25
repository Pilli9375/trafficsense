"""eval_detector.py statistics + make_perception_results.py tables, on hand-made detections."""
import importlib.util

import numpy as np
import pytest

from trafficsense.config import repo_root
from trafficsense.perception import errors


def load(name):
    spec = importlib.util.spec_from_file_location(name, repo_root() / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ev():
    return load("eval_detector")


@pytest.fixture(scope="module")
def mp():
    return load("make_perception_results")


def images():
    base = "/x/idd_yolo/images/{}/{}/{}.jpg"
    out = []
    for i, (cam, seq) in enumerate([("frontFar", "s1"), ("frontFar", "s1"), ("sideLeft", "s2")]):
        out.append({"im_file": base.format(cam, seq, f"{i:07d}"), "shape": (360, 640),
                    "det_xyxy": np.array([[0, 0, 100, 100], [200, 200, 210, 210]], float),
                    "det_conf": np.array([0.9, 0.4]), "det_cls": np.array([0, 3]),
                    "gt_xyxy": np.array([[0, 0, 100, 100], [300, 300, 340, 340]], float),
                    "gt_cls": np.array([0, 1])})
    return out


def test_groups_from_path(ev):
    g = ev.with_groups(images())
    assert [x["group"] for x in g] == ["frontFar/s1", "frontFar/s1", "sideLeft/s2"]
    assert [x["camera"] for x in g] == ["frontFar", "frontFar", "sideLeft"]


def test_preds_roundtrip(ev, tmp_path):
    ims = images()
    ims[1] = {**ims[1], "det_xyxy": np.zeros((0, 4)), "det_conf": np.zeros(0), "det_cls": np.zeros(0, int)}
    ev.save_preds(tmp_path / "p.npz", ims)
    back = ev.load_preds(tmp_path / "p.npz")
    assert len(back) == 3 and len(back[1]["det_conf"]) == 0
    assert np.allclose(back[2]["gt_xyxy"], ims[2]["gt_xyxy"]) and back[0]["shape"] == (360, 640)


def test_tables_render_and_check(ev, mp):
    m = errors.match_split(ev.with_groups(images()), 7)
    stats = ev.error_stats(m, 0.25)
    stats.pop("_k")
    assert stats["miss_rate"]["motorcycle"]["value"] == 1.0 and stats["misses"]["motorcycle"] == 3
    assert stats["false_det_per_image"]["bus"]["value"] == 1.0
    classes = list(ev.CLASSES)
    best = {"path": "/d/best.pt", "sha256": "ab" * 32}
    train = {"weights": {"best": best}, "epochs_run": 30, "stopped_early": True, "best_epoch": 20, "train_hours": 8.0,
             "best_val_metrics": {"metrics/mAP50(B)": 0.5, "metrics/mAP50-95(B)": 0.3},
             "pretrained": {"sha256": "cd" * 32}}
    ultra = {"mAP50": 0.6, "mAP50_95": 0.4, "per_class": {"car": {"mAP50": 0.7, "mAP50_95": 0.5}}}
    val = {"threshold": {"conf": 0.25, "mean_f1": 0.5}, "ultralytics": ultra}
    test = {"classes": classes, "errors": stats, "ultralytics": ultra, "conf_threshold": 0.25, "nms_iou": 0.7,
            "match_iou": 0.5}
    model = {"p_detect": {c: None if v["value"] is None else 1 - v["value"] for c, v in stats["miss_rate"].items()},
             "false_det_per_image": stats["false_det_per_image"]}
    tabs = mp.tables(train, val, test, model)
    doc = "intro\n" + "\n".join(f"<!-- BEGIN:{k} -->\nSTALE_TABLE\n<!-- END:{k} -->" for k in tabs) + "\nend\n"
    new = mp.render(doc, tabs)
    assert mp.render(new, tabs) == new and "STALE_TABLE" not in new
    assert "| motorcycle | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |" in new         # confusion row: all missed
    with pytest.raises(KeyError):
        mp.render("no markers", tabs)


def test_weights_path_comes_from_the_config(ev):
    # not from the absolute path detector_train.json recorded on the training machine
    cfg = {"paths": {"detector_runs": "data/external/detector_runs"}, "perception": {"train": {"run_name": "run1"}}}
    assert ev.run_dir(cfg) == repo_root() / "data/external/detector_runs/detector/run1"
