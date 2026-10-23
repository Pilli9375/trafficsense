"""Detector error statistics for the camera-error model (docs/perception.md section 7).

Input: per image, the detections (xyxy, conf, class) at a low confidence threshold and the
ground-truth boxes, all in the pixels of the image the detector saw (our 640 copies).

Matching, once per image and independent of the operating threshold: detections in order of
falling confidence, each matched to the unmatched ground-truth box with the highest IoU,
if that IoU is >= 0.5, ignoring class. Because matching is greedy in confidence order,
raising the threshold only drops the tail: a ground-truth box is detected at threshold t
exactly when its matched detection has conf >= t. So matching is done once and every
threshold is evaluated from the stored matches.

At a threshold, per ground-truth box: matched with the same class = true positive; matched
with another class = confusion; unmatched = miss. Per detection: unmatched = false
detection. miss rate = misses / GT, so 1 - recall = miss rate + confusion rate.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

SIZE_BUCKETS = ("small", "medium", "large")   # COCO: area < 32^2, < 96^2, >= 96^2 pixels


def box_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU matrix between xyxy boxes a (N, 4) and b (M, 4)."""
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.prod(np.clip(br - tl, 0, None), axis=2)
    area_a = np.prod(a[:, 2:] - a[:, :2], axis=1)
    area_b = np.prod(b[:, 2:] - b[:, :2], axis=1)
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9)


def size_bucket(xyxy: np.ndarray) -> np.ndarray:
    """0 small, 1 medium, 2 large, from box area in pixels."""
    area = np.prod(xyxy[:, 2:] - xyxy[:, :2], axis=1)
    return np.digitize(area, [32 ** 2, 96 ** 2])


def greedy_match(det_xyxy: np.ndarray, det_conf: np.ndarray, gt_xyxy: np.ndarray,
                 iou_thr: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Class-agnostic greedy matching. Returns (gt index per detection or -1, det index per GT or -1)."""
    det_gt = np.full(len(det_xyxy), -1, dtype=np.int64)
    gt_det = np.full(len(gt_xyxy), -1, dtype=np.int64)
    if len(det_xyxy) == 0 or len(gt_xyxy) == 0:
        return det_gt, gt_det
    iou = box_iou(det_xyxy, gt_xyxy)
    for d in np.argsort(-det_conf, kind="stable"):
        cand = np.where(gt_det < 0, iou[d], -1.0)
        g = int(np.argmax(cand))
        if cand[g] >= iou_thr:
            det_gt[d], gt_det[g] = g, d
    return det_gt, gt_det


@dataclass
class Matched:
    """All images of a split, flattened, with their matches (built by `match_split`)."""
    n_classes: int
    image_group: np.ndarray          # per image: index into `groups` (sequence, for the bootstrap)
    groups: list[str]
    image_camera: np.ndarray         # per image: index into `cameras`
    cameras: list[str]
    det_image: np.ndarray = field(repr=False)
    det_cls: np.ndarray = field(repr=False)
    det_conf: np.ndarray = field(repr=False)
    det_matched: np.ndarray = field(repr=False)   # bool: matched to some GT (at the matching threshold)
    det_size: np.ndarray = field(repr=False)
    gt_image: np.ndarray = field(repr=False)
    gt_cls: np.ndarray = field(repr=False)
    gt_size: np.ndarray = field(repr=False)
    gt_match_conf: np.ndarray = field(repr=False)  # conf of the matched detection, -1 if none
    gt_match_cls: np.ndarray = field(repr=False)   # class of the matched detection, -1 if none

    @property
    def n_images(self) -> int:
        return len(self.image_group)


def match_split(images: list[dict], n_classes: int, iou_thr: float = 0.5) -> Matched:
    """images: dicts with group, camera, det_xyxy, det_conf, det_cls, gt_xyxy, gt_cls (numpy arrays)."""
    groups = sorted({im["group"] for im in images})
    cameras = sorted({im["camera"] for im in images})
    gi, ci = {g: i for i, g in enumerate(groups)}, {c: i for i, c in enumerate(cameras)}
    cols: dict[str, list] = {k: [] for k in ("det_image", "det_cls", "det_conf", "det_matched", "det_size",
                                            "gt_image", "gt_cls", "gt_size", "gt_match_conf", "gt_match_cls")}
    for i, im in enumerate(images):
        det_gt, gt_det = greedy_match(im["det_xyxy"], im["det_conf"], im["gt_xyxy"], iou_thr)
        nd, ng = len(im["det_conf"]), len(im["gt_cls"])
        cols["det_image"].append(np.full(nd, i))
        cols["det_cls"].append(im["det_cls"].astype(np.int64))
        cols["det_conf"].append(im["det_conf"].astype(np.float64))
        cols["det_matched"].append(det_gt >= 0)
        cols["det_size"].append(size_bucket(im["det_xyxy"]) if nd else np.zeros(0, np.int64))
        cols["gt_image"].append(np.full(ng, i))
        cols["gt_cls"].append(im["gt_cls"].astype(np.int64))
        cols["gt_size"].append(size_bucket(im["gt_xyxy"]) if ng else np.zeros(0, np.int64))
        hit = gt_det >= 0
        cols["gt_match_conf"].append(np.where(hit, im["det_conf"][np.maximum(gt_det, 0)] if nd else -1.0, -1.0))
        cols["gt_match_cls"].append(np.where(hit, im["det_cls"][np.maximum(gt_det, 0)] if nd else -1, -1)
                                    .astype(np.int64))
    arr = {k: np.concatenate(v) if v else np.zeros(0) for k, v in cols.items()}
    return Matched(n_classes, np.array([gi[im["group"]] for im in images]), groups,
                   np.array([ci[im["camera"]] for im in images]), cameras, **arr)


def counts(m: Matched, thr: float, image_mask: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Raw counts at threshold `thr`, optionally restricted to a subset of images."""
    k = m.n_classes
    gsel = np.ones(len(m.gt_cls), bool) if image_mask is None else image_mask[m.gt_image]
    dsel = m.det_conf >= thr
    if image_mask is not None:
        dsel &= image_mask[m.det_image]
    detected = gsel & (m.gt_match_conf >= thr)
    conf_mat = np.zeros((k, k), np.int64)
    np.add.at(conf_mat, (m.gt_cls[detected], m.gt_match_cls[detected]), 1)
    fp = dsel & ~m.det_matched
    gt_size = np.zeros((k, 3), np.int64)
    miss_size = np.zeros((k, 3), np.int64)
    np.add.at(gt_size, (m.gt_cls[gsel], m.gt_size[gsel]), 1)
    missed = gsel & ~detected
    np.add.at(miss_size, (m.gt_cls[missed], m.gt_size[missed]), 1)
    return {
        "images": np.int64(m.n_images if image_mask is None else image_mask.sum()),
        "gt": np.bincount(m.gt_cls[gsel], minlength=k),
        "miss": np.bincount(m.gt_cls[missed], minlength=k),
        "confusion": conf_mat,                                   # rows true class, cols predicted
        "det": np.bincount(m.det_cls[dsel], minlength=k),
        "false_det": np.bincount(m.det_cls[fp], minlength=k),
        "gt_by_size": gt_size, "miss_by_size": miss_size,
    }


def rates(c: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Per-class rates from `counts` (NaN where the denominator is 0)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        tp = np.diag(c["confusion"])
        return {
            "miss_rate": c["miss"] / c["gt"],
            "recall": tp / c["gt"],
            "precision": tp / c["det"],
            "false_det_per_image": c["false_det"] / c["images"],
            "miss_rate_by_size": c["miss_by_size"] / c["gt_by_size"],
        }


def f1_per_class(m: Matched, thr: float) -> np.ndarray:
    c = counts(m, thr)
    tp = np.diag(c["confusion"])
    fp, fn = c["det"] - tp, c["gt"] - tp
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(2 * tp + fp + fn > 0, 2 * tp / (2 * tp + fp + fn), 0.0)


def choose_threshold(m: Matched, grid: np.ndarray) -> tuple[float, np.ndarray]:
    """Threshold on `grid` that maximises the mean F1 over classes (first one on ties); and the curve."""
    curve = np.array([f1_per_class(m, float(t)).mean() for t in grid])
    return float(grid[int(np.argmax(curve))]), curve


def count_error(m: Matched, thr: float) -> dict[str, np.ndarray]:
    """Per class, over images: mean |detected count - true count| and mean signed error."""
    k, n = m.n_classes, m.n_images
    pred = np.zeros((n, k), np.int64)
    true = np.zeros((n, k), np.int64)
    d = m.det_conf >= thr
    np.add.at(pred, (m.det_image[d], m.det_cls[d]), 1)
    np.add.at(true, (m.gt_image, m.gt_cls), 1)
    return {"mean_abs": np.abs(pred - true).mean(axis=0), "mean_signed": (pred - true).mean(axis=0)}


def bootstrap(m: Matched, thr: float, reps: int = 1000, seed: int = 0) -> dict[str, np.ndarray]:
    """95% percentile intervals of the per-class rates, resampling whole groups (sequences)."""
    per_group = [counts(m, thr, m.image_group == g) for g in range(len(m.groups))]
    keys = ("images", "gt", "miss", "confusion", "det", "false_det", "gt_by_size", "miss_by_size")
    stacked = {key: np.stack([pg[key] for pg in per_group]) for key in keys}
    rng = np.random.default_rng(seed)
    draws: dict[str, list] = {}
    for _ in range(reps):
        pick = rng.integers(0, len(per_group), len(per_group))
        r = rates({key: stacked[key][pick].sum(axis=0) for key in keys})
        for key, v in r.items():
            draws.setdefault(key, []).append(v)
    with warnings.catch_warnings():   # classes or size buckets absent from a split stay NaN
        warnings.simplefilter("ignore", RuntimeWarning)
        return {key: np.nanpercentile(np.stack(v), [2.5, 97.5], axis=0) for key, v in draws.items()}
