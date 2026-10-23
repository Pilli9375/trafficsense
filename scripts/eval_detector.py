"""Evaluate the trained detector and build the camera error model (docs/perception.md section 7).

    python scripts/eval_detector.py --stage val    # our val split: choose the confidence threshold
    python scripts/eval_detector.py --stage test   # our test split (official IDD val): final numbers, once

Both stages run Ultralytics' validator once on the split with best.pt (conf 0.001, NMS IoU
0.7, imgsz from config). It gives mAP50 and mAP50-95; a subclass also keeps every image's
detections and ground truth from the same pass, which our own error statistics use
(trafficsense.perception.errors). The detections are saved on D next to the run, and a
later call reuses them instead of running the model again.

--stage val picks the threshold that maximises the mean F1 over the 7 classes on a grid of
0.01 steps and writes paths.perception_outputs/detector_val.json. --stage test refuses to
run until that file exists for the same best.pt (sha256), then writes detector_test.json
and the error model error_model.json.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from trafficsense.config import load_config, resolve_path
from trafficsense.experiment import git_info
from trafficsense.perception import detector, errors
from trafficsense.perception.idd import CLASSES

CONF, NMS_IOU, MATCH_IOU = 0.001, 0.7, 0.5
GRID = np.round(np.arange(0.01, 0.96, 0.01), 2)
BOOT_REPS, BOOT_SEED = 1000, 0
CAVEAT = ("IDD is filmed from a moving vehicle, not from a camera on a pole at an intersection. "
          "Viewpoint, distance and occlusion differ, so these rates are a measured proxy for an "
          "intersection camera, not its true error.")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_validator(weights: Path, data_yaml: Path, split: str, imgsz: int, save_dir: Path,
                  device: str | None = None) -> tuple[dict, list]:
    """Ultralytics validation; returns (metrics, per-image detections + ground truth in 640-copy pixels)."""
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionValidator
    from ultralytics.utils import ops

    captured: list[dict] = []

    class CapturingValidator(DetectionValidator):
        def update_metrics(self, preds, batch):
            super().update_metrics(preds, batch)
            for si, pred in enumerate(preds):
                pb = self._prepare_batch(si, batch)
                p = self.scale_preds(pred, pb)
                gt = ops.scale_boxes(pb["imgsz"], pb["bboxes"].clone(), pb["ori_shape"], ratio_pad=pb["ratio_pad"])
                captured.append({"im_file": pb["im_file"], "shape": tuple(int(x) for x in pb["ori_shape"]),
                                 "det_xyxy": p["bboxes"].cpu().numpy(), "det_conf": p["conf"].cpu().numpy(),
                                 "det_cls": p["cls"].cpu().numpy().astype(np.int64),
                                 "gt_xyxy": gt.cpu().numpy().reshape(-1, 4),
                                 "gt_cls": pb["cls"].cpu().numpy().astype(np.int64)})

    model = YOLO(str(weights))
    m = model.val(data=str(data_yaml), split=split, imgsz=imgsz, batch=16, conf=CONF, iou=NMS_IOU,
                  project=str(save_dir.parent), name=save_dir.name, exist_ok=True, plots=True,
                  validator=CapturingValidator, **({"device": device} if device else {}))
    per_class = {}
    for i, c in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        per_class[CLASSES[int(c)]] = {"mAP50": ap50, "mAP50_95": ap, "ultralytics_precision": p,
                                      "ultralytics_recall": r}
    metrics = {"mAP50": float(m.box.map50), "mAP50_95": float(m.box.map), "per_class": per_class,
               "images": len(captured), "note": "ultralytics_precision/recall are at the confidence Ultralytics "
               "picks on this same split (max mean F1); our operating point is chosen on our val split instead"}
    return metrics, captured


def save_preds(path: Path, images: list[dict]) -> None:
    lens = lambda k: np.array([len(im[k]) for im in images])
    cat = lambda k, w: np.concatenate([im[k].reshape(-1, *w) for im in images]) if images else np.zeros(0)
    np.savez_compressed(path, im_file=np.array([im["im_file"] for im in images]),
                        shape=np.array([im["shape"] for im in images]), n_det=lens("det_conf"), n_gt=lens("gt_cls"),
                        det_xyxy=cat("det_xyxy", (4,)), det_conf=cat("det_conf", ()), det_cls=cat("det_cls", ()),
                        gt_xyxy=cat("gt_xyxy", (4,)), gt_cls=cat("gt_cls", ()))


def load_preds(path: Path) -> list[dict]:
    z = np.load(path)
    od, og = np.concatenate([[0], np.cumsum(z["n_det"])]), np.concatenate([[0], np.cumsum(z["n_gt"])])
    return [{"im_file": str(f), "shape": tuple(z["shape"][i]),
             "det_xyxy": z["det_xyxy"][od[i]:od[i + 1]], "det_conf": z["det_conf"][od[i]:od[i + 1]],
             "det_cls": z["det_cls"][od[i]:od[i + 1]], "gt_xyxy": z["gt_xyxy"][og[i]:og[i + 1]],
             "gt_cls": z["gt_cls"][og[i]:og[i + 1]]} for i, f in enumerate(z["im_file"])]


def with_groups(images: list[dict]) -> list[dict]:
    """Sequence (camera/sequence) and camera group from the path .../images/<camera>/<sequence>/<frame>.jpg."""
    out = []
    for im in images:
        parts = Path(im["im_file"]).parts
        k = len(parts) - 1 - parts[::-1].index("images")
        out.append({**im, "camera": parts[k + 1], "group": f"{parts[k + 1]}/{parts[k + 2]}"})
    return out


def predictions(cfg, split: str, weights: Path, eval_dir: Path) -> tuple[dict, list]:
    """Run the validator once per split; later calls read the saved detections and metrics."""
    preds, mfile = eval_dir / f"{split}_preds.npz", eval_dir / f"{split}_ultralytics_metrics.json"
    if preds.is_file() and mfile.is_file():
        stored = json.loads(mfile.read_text())
        if stored["weights_sha256"] != detector.sha256(weights):
            raise RuntimeError(f"{preds} was made with other weights; move it away to re-evaluate")
        print(f"reusing saved {split} detections: {preds}")
        return stored["metrics"], load_preds(preds)
    data_yaml = resolve_path(cfg, "idd_yolo") / "data.yaml"
    metrics, images = run_validator(weights, data_yaml, split, int(cfg["perception"]["imgsz"]), eval_dir / split)
    save_preds(preds, images)
    mfile.write_text(json.dumps({"weights_sha256": detector.sha256(weights), "metrics": metrics,
                                 "timestamp": now()}, indent=2) + "\n")
    return metrics, images


def per_class(values: np.ndarray, digits: int = 4) -> dict:
    return {c: (None if np.isnan(v) else round(float(v), digits)) for c, v in zip(CLASSES, values)}


def with_ci(point: np.ndarray, ci: np.ndarray, digits: int = 4) -> dict:
    return {c: {"value": None if np.isnan(point[i]) else round(float(point[i]), digits),
                "ci95": [None if np.isnan(x) else round(float(x), digits) for x in ci[:, i]]}
            for i, c in enumerate(CLASSES)}


def error_stats(m: errors.Matched, thr: float) -> dict:
    c = errors.counts(m, thr)
    r = errors.rates(c)
    ci = errors.bootstrap(m, thr, BOOT_REPS, BOOT_SEED)
    k = len(CLASSES)
    conf = c["confusion"]
    with np.errstate(divide="ignore", invalid="ignore"):
        p_given_detected = conf / conf.sum(axis=1, keepdims=True)
        p_given_true = conf / c["gt"][:, None]
    by_size = {c_: {b: {"gt": int(c["gt_by_size"][i, j]),
                        "miss_rate": None if c["gt_by_size"][i, j] == 0 else round(float(r["miss_rate_by_size"][i, j]), 4),
                        "ci95": [None if np.isnan(x) else round(float(x), 4) for x in ci["miss_rate_by_size"][:, i, j]]}
                    for j, b in enumerate(errors.SIZE_BUCKETS)} for i, c_ in enumerate(CLASSES)}
    by_camera = {}
    for gi, cam in enumerate(m.cameras):
        cc = errors.counts(m, thr, m.image_camera == gi)
        rr = errors.rates(cc)
        by_camera[cam] = {"images": int(cc["images"]), "gt": per_class(cc["gt"], 0),
                          "miss_rate": per_class(rr["miss_rate"]),
                          "false_det_per_image": per_class(rr["false_det_per_image"])}
    ce = errors.count_error(m, thr)
    return {
        "images": int(c["images"]), "sequences": len(m.groups),
        "gt": per_class(c["gt"], 0), "detections": per_class(c["det"], 0),
        "true_positives": per_class(np.diag(conf), 0), "misses": per_class(c["miss"], 0),
        "false_detections": per_class(c["false_det"], 0),
        "miss_rate": with_ci(r["miss_rate"], ci["miss_rate"]),
        "recall": with_ci(r["recall"], ci["recall"]),
        "precision": with_ci(r["precision"], ci["precision"]),
        "false_det_per_image": with_ci(r["false_det_per_image"], ci["false_det_per_image"]),
        "miss_rate_by_size": by_size,
        "confusion_matrix": {"rows_true_cols_predicted": list(CLASSES),
                             "counts": conf.tolist(),
                             "p_pred_given_true_detected": [[round(float(x), 4) for x in row] for row in
                                                            np.nan_to_num(p_given_detected)],
                             "p_pred_given_true": [[round(float(x), 4) for x in row] for row in
                                                   np.nan_to_num(p_given_true)]},
        "count_error_per_image": {"mean_abs": per_class(ce["mean_abs"]), "mean_signed": per_class(ce["mean_signed"])},
        "by_camera": by_camera,
        "bootstrap": {"reps": BOOT_REPS, "seed": BOOT_SEED, "unit": "sequence", "interval": "2.5-97.5 percentile"},
        "_k": k,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stage", choices=("val", "test"), required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    out = resolve_path(cfg, "perception_outputs")
    train = json.loads((out / "detector_train.json").read_text())
    weights = Path(train["weights"]["best"]["path"])
    sha = detector.sha256(weights)
    if sha != train["weights"]["best"]["sha256"]:
        raise RuntimeError(f"{weights} does not match the sha256 in detector_train.json")
    eval_dir = Path(train["run_dir"]) / "eval"
    eval_dir.mkdir(exist_ok=True)
    git = git_info()
    common = {"weights": {"path": str(weights), "sha256": sha}, "conf_for_inference": CONF, "nms_iou": NMS_IOU,
              "match_iou": MATCH_IOU, "imgsz": int(cfg["perception"]["imgsz"]), "classes": list(CLASSES)}
    prov = lambda stage: {"script": f"scripts/eval_detector.py --stage {stage}", "git_commit": git["commit"],
                          "git_dirty": git["dirty"], "timestamp": now()}

    if args.stage == "val":
        metrics, images = predictions(cfg, "val", weights, eval_dir)
        m = errors.match_split(with_groups(images), len(CLASSES), MATCH_IOU)
        thr, curve = errors.choose_threshold(m, GRID)
        res = {"split": "val (our held-out official-train sequences)", **common, "ultralytics": metrics,
               "threshold": {"conf": thr, "rule": "max mean F1 over the 7 classes, grid 0.01-0.95 step 0.01",
                             "mean_f1": round(float(curve.max()), 4),
                             "f1_per_class": per_class(errors.f1_per_class(m, thr)),
                             "curve": {f"{t:.2f}": round(float(v), 4) for t, v in zip(GRID, curve)}},
               "provenance": prov("val")}
        (out / "detector_val.json").write_text(json.dumps(res, indent=2) + "\n")
        print(f"val mAP50 {metrics['mAP50']:.3f}, mAP50-95 {metrics['mAP50_95']:.3f}; "
              f"threshold {thr} (mean F1 {curve.max():.3f}); wrote {out / 'detector_val.json'}")
        return

    valf = out / "detector_val.json"
    if not valf.is_file():
        raise FileNotFoundError("Run --stage val first: the threshold must be fixed before the test split is used")
    val = json.loads(valf.read_text())
    if val["weights"]["sha256"] != sha:
        raise RuntimeError("detector_val.json was made with other weights")
    thr = float(val["threshold"]["conf"])
    metrics, images = predictions(cfg, "test", weights, eval_dir)
    m = errors.match_split(with_groups(images), len(CLASSES), MATCH_IOU)
    stats = error_stats(m, thr)
    stats.pop("_k")
    res = {"split": "test (official IDD val)", **common, "conf_threshold": thr,
           "threshold_source": "detector_val.json", "ultralytics": metrics, "errors": stats,
           "definitions": {
               "miss": "ground-truth box not matched by any kept detection (IoU >= 0.5, any class)",
               "confusion": "matched by a detection of another class; 1 - recall = miss rate + confusion rate",
               "false_detection": "kept detection not matched to any ground-truth box",
               "size": "COCO buckets on box area in the 640-long-side image: small < 32^2, medium < 96^2, large",
               "false detections by class": "per predicted class, per image"},
           "provenance": prov("test")}
    (out / "detector_test.json").write_text(json.dumps(res, indent=2) + "\n")

    model = {
        "description": "Camera error model for the simulator, measured once on our test split (official IDD val).",
        "caveat": CAVEAT,
        "use": ("Each object of class c in view is detected with p_detect[c] (by size bucket if the camera "
                "distance is modelled); a detected object is labelled j with p_label_given_detected[c][j]; "
                "false detections of class j are added as a Poisson count with mean "
                "false_det_per_image[j] per camera frame."),
        "classes": list(CLASSES), "conf_threshold": thr, "nms_iou": NMS_IOU, "match_iou": MATCH_IOU,
        "p_detect": {c: None if v["value"] is None else round(1 - v["value"], 4) for c, v in stats["miss_rate"].items()},
        "miss_rate": stats["miss_rate"],
        "miss_rate_by_size": stats["miss_rate_by_size"],
        "p_label_given_detected": dict(zip(CLASSES, (dict(zip(CLASSES, row)) for row in
                                                     stats["confusion_matrix"]["p_pred_given_true_detected"]))),
        "false_det_per_image": stats["false_det_per_image"],
        "precision": stats["precision"],
        "source": {"split": res["split"], "images": stats["images"], "sequences": stats["sequences"],
                   "weights": common["weights"], "train_summary": "outputs/perception/detector_train.json",
                   "metrics_file": "outputs/perception/detector_test.json"},
        "provenance": prov("test"),
    }
    (out / "error_model.json").write_text(json.dumps(model, indent=2) + "\n")
    print(f"test mAP50 {metrics['mAP50']:.3f}, mAP50-95 {metrics['mAP50_95']:.3f} at conf {thr}; "
          f"wrote {out / 'detector_test.json'} and {out / 'error_model.json'}")


if __name__ == "__main__":
    main()
