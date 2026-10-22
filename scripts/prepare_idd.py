"""Convert IDD Detection to YOLO labels (docs/perception.md, sections 2-4 and 5).

    python scripts/prepare_idd.py [--config configs/default.yaml]

Reads the dataset through paths.idd_root, writes labels, image lists and data.yaml to
paths.idd_yolo (no image copies), then re-reads every label file and checks it against the
XML it came from. The conversion report, with provenance, also goes to
paths.perception_outputs/idd_conversion.json.
"""
import argparse
import json
from datetime import datetime, timezone

from trafficsense.config import load_config, resolve_path
from trafficsense.experiment import git_info
from trafficsense.perception import idd


def verify(idd_root, out_dir, splits) -> int:
    """Re-read each label and compare with a fresh conversion of its XML. Returns files checked."""
    n = 0
    for ids in splits.values():
        for image_id in ids:
            w, h, objs = idd.parse_voc(idd_root / "Annotations" / f"{image_id}.xml")
            expected, _ = idd.convert_objects(w, h, objs)
            lbl = idd.label_path_for(str(out_dir / "images" / f"{image_id}.jpg"))
            with open(lbl) as f:
                got = f.read().splitlines()
            if got != expected:
                raise RuntimeError(f"Label mismatch for {image_id}: {lbl}")
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    idd_root = resolve_path(cfg, "idd_root")
    if not idd_root.exists():
        raise FileNotFoundError(f"{idd_root} not found. Create the symlink to the extracted dataset: "
                                f"ln -s <...>/IDD_Detection {idd_root}")
    out_dir = resolve_path(cfg, "idd_yolo")
    pcfg = cfg["perception"]
    git = git_info()

    report = idd.convert(idd_root, out_dir, float(pcfg["val_fraction"]), int(pcfg["split_seed"]))
    splits, _ = idd.our_splits(idd_root.resolve(), float(pcfg["val_fraction"]), int(pcfg["split_seed"]))
    report["verified_label_files"] = verify(idd_root.resolve(), out_dir, splits)
    report["provenance"] = {"script": "scripts/prepare_idd.py", "git_commit": git["commit"],
                            "git_dirty": git["dirty"],
                            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    (out_dir / "conversion_report.json").write_text(json.dumps(report, indent=2) + "\n")
    outputs = resolve_path(cfg, "perception_outputs")
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "idd_conversion.json").write_text(json.dumps(report, indent=2) + "\n")
    for split, s in report["splits"].items():
        print(f"{split}: {s['images']} images, {s['sequences']} sequences, {s['boxes_total']} boxes "
              f"({s['background_images']} background images)")
    print(f"verified {report['verified_label_files']} label files; data.yaml: {out_dir / 'data.yaml'}")


if __name__ == "__main__":
    main()
