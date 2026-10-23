"""Detector error statistics on hand-made boxes."""
import numpy as np
import pytest

from trafficsense.perception import errors


def img(det, gt, group="seqA", camera="frontFar"):
    """det: [(x0, y0, x1, y1, conf, cls)], gt: [(x0, y0, x1, y1, cls)]."""
    d = np.array(det, float).reshape(-1, 6)
    g = np.array(gt, float).reshape(-1, 5)
    return {"group": group, "camera": camera, "det_xyxy": d[:, :4], "det_conf": d[:, 4], "det_cls": d[:, 5].astype(int),
            "gt_xyxy": g[:, :4], "gt_cls": g[:, 4].astype(int)}


def test_box_iou_and_size_bucket():
    a = np.array([[0, 0, 10, 10]], float)
    b = np.array([[0, 0, 10, 10], [5, 0, 15, 10], [20, 20, 30, 30]], float)
    assert np.allclose(errors.box_iou(a, b), [[1, 1 / 3, 0]])
    boxes = np.array([[0, 0, 31, 31], [0, 0, 32, 32], [0, 0, 95, 95], [0, 0, 96, 96]], float)
    assert errors.size_bucket(boxes).tolist() == [0, 1, 1, 2]


def test_greedy_match_highest_conf_first_and_class_agnostic():
    gt = np.array([[0, 0, 10, 10]], float)
    det = np.array([[0, 0, 10, 9], [0, 0, 10, 10]], float)
    # The lower-IoU detection has higher confidence, so it takes the box.
    det_gt, gt_det = errors.greedy_match(det, np.array([0.9, 0.5]), gt)
    assert det_gt.tolist() == [0, -1] and gt_det.tolist() == [0]
    # Below IoU 0.5: no match.
    det_gt, gt_det = errors.greedy_match(np.array([[5, 0, 15, 10]], float), np.array([0.9]), gt)
    assert det_gt.tolist() == [-1] and gt_det.tolist() == [-1]
    assert errors.greedy_match(np.zeros((0, 4)), np.zeros(0), gt)[1].tolist() == [-1]


@pytest.fixture
def split():
    big = (0, 0, 100, 100)
    return errors.match_split([
        # TP car (conf .9), confused motorcycle seen as car (conf .6), missed person, false bus (conf .3)
        img([(*big, .9, 0), (200, 200, 220, 220, .6, 0), (400, 400, 410, 410, .3, 3)],
            [(*big, 0), (200, 200, 220, 220, 1), (300, 300, 310, 310, 6)], group="seqA"),
        # TP car detected only at low conf (.2); an image with no detections
        img([(*big, .2, 0)], [(*big, 0)], group="seqB", camera="sideLeft"),
        img([], [(0, 0, 50, 50, 0)], group="seqB", camera="sideLeft"),
    ], n_classes=7)


def test_counts_and_rates_at_threshold(split):
    c = errors.counts(split, 0.25)
    assert c["images"] == 3
    assert c["gt"][[0, 1, 6]].tolist() == [3, 1, 1]
    assert c["miss"][[0, 1, 6]].tolist() == [2, 0, 1]          # conf .2 car and the 50 px car; the person
    assert c["confusion"][0, 0] == 1 and c["confusion"][1, 0] == 1
    assert c["det"][[0, 3]].tolist() == [2, 1] and c["false_det"].tolist() == [0, 0, 0, 1, 0, 0, 0]
    r = errors.rates(c)
    assert r["miss_rate"][0] == pytest.approx(2 / 3) and r["recall"][1] == 0 and r["miss_rate"][1] == 0
    assert r["precision"][0] == pytest.approx(0.5) and r["false_det_per_image"][3] == pytest.approx(1 / 3)
    # The 50x50 car is medium, the 100x100 cars large; the 10x10 person small.
    assert c["gt_by_size"][0].tolist() == [0, 1, 2] and c["miss_by_size"][0].tolist() == [0, 1, 1]
    assert c["miss_by_size"][6].tolist() == [1, 0, 0]
    # Lowering the threshold recovers the conf .2 car.
    assert errors.counts(split, 0.1)["miss"][0] == 1


def test_counts_on_image_subset(split):
    c = errors.counts(split, 0.1, split.image_group == split.groups.index("seqB"))
    assert c["images"] == 2 and c["gt"][0] == 2 and c["miss"][0] == 1 and c["det"].sum() == 1


def test_threshold_choice_and_count_error(split):
    grid = np.array([0.1, 0.25, 0.5, 0.95])
    t, curve = errors.choose_threshold(split, grid)
    assert len(curve) == 4 and curve[int(np.argmax(curve))] == curve.max() and t in grid
    ce = errors.count_error(split, 0.25)
    # car: image 1 predicts 2 vs 1 true, image 2 predicts 0 vs 1, image 3 0 vs 1
    assert ce["mean_abs"][0] == pytest.approx(1.0) and ce["mean_signed"][0] == pytest.approx(-1 / 3)


def test_bootstrap_resamples_groups(split):
    ci = errors.bootstrap(split, 0.25, reps=200, seed=0)
    lo, hi = ci["miss_rate"]
    assert lo[0] <= 2 / 3 <= hi[0]
    assert ci["miss_rate_by_size"].shape == (2, 7, 3)
