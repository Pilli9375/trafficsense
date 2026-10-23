"""Generate the detector result tables of docs/perception.md from the evaluation files.

    python scripts/make_perception_results.py            # update the tables in docs/perception.md
    python scripts/make_perception_results.py --check    # exit 1 if a table is out of date

Inputs (paths.perception_outputs): detector_train.json, detector_val.json, detector_test.json,
error_model.json. Each table sits between <!-- BEGIN:name --> and <!-- END:name --> markers.
Intervals are the 95% sequence-bootstrap intervals stored in detector_test.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root, resolve_path

DOC = Path("docs/perception.md")
SIZES = ("small", "medium", "large")


def pct(v, digits=1):
    return "–" if v is None else f"{100 * v:.{digits}f}%"


def with_ci(d, fmt=pct):
    lo, hi = d["ci95"]
    return "–" if d["value"] is None else f"{fmt(d['value'])} ({fmt(lo)}–{fmt(hi)})"


def num(v, digits=3):
    return "–" if v is None else f"{v:.{digits}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def tables(train, val, test, model) -> dict[str, str]:
    t = {}
    best = train["weights"]["best"]
    t["detector_train"] = table(["", "value"], [
        ["epochs run (of 50)", train["epochs_run"]],
        ["stopped early", "yes" if train["stopped_early"] else "no"],
        ["best epoch (our val fitness)", train["best_epoch"]],
        ["training time", f"{train['train_hours']:.1f} h"],
        ["val mAP50 / mAP50-95 at the best epoch",
         f"{train['best_val_metrics']['metrics/mAP50(B)']:.3f} / {train['best_val_metrics']['metrics/mAP50-95(B)']:.3f}"],
        ["best.pt", f"`{best['path']}`"],
        ["best.pt sha256", f"`{best['sha256']}`"],
        ["pretrained yolov8n.pt sha256", f"`{train['pretrained']['sha256']}`"],
    ])
    th = val["threshold"]
    t["detector_threshold"] = table(["", "value"], [
        ["confidence threshold (chosen on our val split)", th["conf"]],
        ["mean F1 over 7 classes at that threshold (val)", num(th["mean_f1"])],
        ["val mAP50 / mAP50-95 (Ultralytics, best.pt)",
         f"{val['ultralytics']['mAP50']:.3f} / {val['ultralytics']['mAP50_95']:.3f}"],
    ])
    e, u = test["errors"], test["ultralytics"]
    classes = test["classes"]
    rows = [[c, e["gt"][c], num(u["per_class"].get(c, {}).get("mAP50")), num(u["per_class"].get(c, {}).get("mAP50_95")),
             with_ci(e["precision"][c]), with_ci(e["recall"][c]), with_ci(e["miss_rate"][c]),
             with_ci(e["false_det_per_image"][c], lambda v: f"{v:.3f}")] for c in classes]
    rows.append(["**all**", sum(e["gt"].values()), f"**{u['mAP50']:.3f}**", f"**{u['mAP50_95']:.3f}**", "", "", "", ""])
    t["detector_test_classes"] = (
        f"Test split: {e['images']:,} images, {e['sequences']} sequences; operating point conf ≥ "
        f"{test['conf_threshold']}, NMS IoU {test['nms_iou']}, match IoU {test['match_iou']}.\n\n" +
        table(["class", "GT boxes", "mAP50", "mAP50-95", "precision", "recall", "miss rate", "false det. / image"], rows))
    ms = e["miss_rate_by_size"]
    t["detector_test_sizes"] = table(
        ["class"] + [f"{s} miss rate (GT)" for s in SIZES],
        [[c] + [f"{pct(ms[c][s]['miss_rate'])} ({ms[c][s]['gt']:,})" for s in SIZES] for c in classes])
    cm = e["confusion_matrix"]["counts"]
    t["detector_test_confusion"] = table(
        ["true ↓ / predicted →"] + classes + ["missed"],
        [[c] + [f"{x:,}" for x in cm[i]] + [f"{e['misses'][c]:,}"] for i, c in enumerate(classes)]
        + [["false detection"] + [f"{e['false_detections'][c]:,}" for c in classes] + [""]])
    ce = e["count_error_per_image"]
    t["detector_test_counts"] = table(
        ["class", "mean abs. count error / image", "mean signed (pred − true)"],
        [[c, num(ce["mean_abs"][c]), num(ce["mean_signed"][c])] for c in classes])
    cams = e["by_camera"]
    t["detector_test_cameras"] = table(
        ["camera group", "images", "GT boxes", "small share", "median box area (px)"] + [f"{c} miss" for c in classes],
        [[cam, f"{v['images']:,}", f"{v['gt_total']:,}", pct(v["gt_small_share"], 0), f"{v['gt_median_area_px']:,.0f}"]
         + [pct(v["miss_rate"][c], 0) for c in classes] for cam, v in cams.items()])
    t["detector_error_model"] = table(
        ["class", "p_detect", "false det. / image (Poisson mean)"],
        [[c, num(model["p_detect"][c]), num(model["false_det_per_image"][c]["value"])] for c in classes])
    return t


def render(doc: str, tabs: dict[str, str]) -> str:
    for name, body in tabs.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(doc):
            raise KeyError(f"Marker for table {name!r} missing in {DOC}")
        doc = pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = resolve_path(load_config(args.config), "perception_outputs")
    files = {k: json.loads((out / f).read_text()) for k, f in
             (("train", "detector_train.json"), ("val", "detector_val.json"), ("test", "detector_test.json"),
              ("model", "error_model.json"))}
    tabs = tables(**files)
    doc_path = repo_root() / DOC
    doc = doc_path.read_text()
    new = render(doc, tabs)
    if args.check:
        ok = new == doc
        print(f"{DOC} matches the evaluation files" if ok else f"{DOC} out of date; run scripts/make_perception_results.py")
        sys.exit(0 if ok else 1)
    doc_path.write_text(new)
    print(f"updated {len(tabs)} tables in {DOC}")


if __name__ == "__main__":
    main()
