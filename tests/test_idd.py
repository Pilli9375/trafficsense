"""IDD -> YOLO conversion on a tiny hand-made VOC tree (tmp_path; no real data needed)."""
import json

import pytest

from trafficsense.perception import idd

XML = """<annotation><size><width>{w}</width><height>{h}</height><depth>3</depth></size>{objs}</annotation>"""
OBJ = "<object><name>{}</name><bndbox><xmin>{}</xmin><ymax>{}</ymax><xmax>{}</xmax><ymin>{}</ymin></bndbox></object>"


def obj(name, x0, y0, x1, y1):
    return OBJ.format(name, x0, y1, x1, y0)  # IDD writes ymax before xmax


def make_tree(root, entries):
    """entries: {split: {id: (w, h, [objs])}}; writes XML, empty JPEG files and split lists."""
    for split, items in entries.items():
        for image_id, (w, h, objs) in items.items():
            for sub, ext, text in (("Annotations", "xml", XML.format(w=w, h=h, objs="".join(objs))),
                                   ("JPEGImages", "jpg", "")):
                p = root / sub / f"{image_id}.{ext}"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
        (root / f"{split}.txt").write_text("\n".join(items) + "\n")


def test_mapping_covers_our_classes_only():
    assert set(v for v in idd.IDD_TO_OURS.values() if v) == set(idd.CLASSES)
    for dropped in ("rider", "vehicle fallback", "animal", "traffic sign", "traffic light"):
        assert idd.IDD_TO_OURS[dropped] is None


def test_convert_objects_maps_normalises_clips_and_drops():
    objs = [("car", 100, 50, 300, 250), ("rider", 0, 0, 10, 10), ("person", -5, 900, 50, 1100),
            ("traffic light", 10, 20, 30, 20)]
    lines, stats = idd.convert_objects(1000, 1000, objs)
    assert lines == ["0 0.200000 0.150000 0.200000 0.200000",   # car
                     "6 0.025000 0.950000 0.050000 0.100000"]   # person, clipped to [0,900,50,1000]
    assert stats["clipped"] == 1
    assert stats["dropped_class:rider"] == 1 and stats["dropped_class:traffic light"] == 1
    assert stats["box:car"] == 1 and stats["box:person"] == 1


def test_degenerate_box_dropped():
    lines, stats = idd.convert_objects(100, 100, [("car", 10, 10, 10.5, 50)])
    assert lines == [] and stats["dropped_degenerate"] == 1


def test_unknown_class_raises():
    with pytest.raises(ValueError, match="Unknown IDD class"):
        idd.convert_objects(100, 100, [("spaceship", 0, 0, 10, 10)])


def test_holdout_is_per_group_seeded_and_by_sequence():
    ids = [f"frontFar/seq{s}/{f}" for s in range(20) for f in range(3)] + \
          [f"sideLeft/s{s}/{f}" for s in range(3) for f in range(2)]
    a = idd.holdout_sequences(ids, 0.1, 0)
    assert a == idd.holdout_sequences(list(reversed(ids)), 0.1, 0)
    assert sum(s.startswith("frontFar/") for s in a) == 2
    assert sum(s.startswith("sideLeft/") for s in a) == 1   # max(1, round(0.3))
    with pytest.raises(ValueError):
        idd.holdout_sequences(["mystery/x/1"], 0.1, 0)


def test_label_path_matches_ultralytics_rule():
    assert idd.label_path_for("/r/idd_yolo/images/frontFar/s/000702_r.jpg") == \
        "/r/idd_yolo/labels/frontFar/s/000702_r.txt"


def test_convert_end_to_end(tmp_path):
    src = tmp_path / "IDD_Detection"
    train = {f"frontFar/seq{s}/{f:04d}": (200, 100, [obj("car", 20, 10, 60, 50), obj("rider", 0, 0, 5, 5)])
             for s in range(10) for f in range(2)}
    train["frontFar/seq0/bg"] = (200, 100, [obj("animal", 0, 0, 50, 50)])
    val = {"sideLeft/v0/0001": (200, 100, [obj("bus", 0, 0, 200, 100)])}
    make_tree(src, {"train": train, "val": val})
    out = tmp_path / "idd_yolo"

    report = idd.convert(src, out, 0.1, 0)

    assert (out / "images").is_symlink() and (out / "images").resolve() == (src / "JPEGImages").resolve()
    s = report["splits"]
    assert s["val"]["sequences"] == 1 and s["train"]["sequences"] == 9
    assert s["train"]["images"] + s["val"]["images"] == 21
    assert s["test"]["boxes"]["bus"] == 1 and s["test"]["official_split"] == "val"
    assert s["train"]["dropped_by_class"]["rider"] + s["val"]["dropped_by_class"]["rider"] == 20
    lines = (out / "train.txt").read_text().splitlines() + (out / "val.txt").read_text().splitlines()
    assert all(line.startswith("./images/") and line.endswith(".jpg") for line in lines)
    bg = idd.label_path_for(str(out / "images" / "frontFar/seq0/bg.jpg"))
    assert open(bg).read() == ""   # all boxes dropped -> background image
    assert "names:\n  0: car\n" in (out / "data.yaml").read_text()
    assert json.loads((out / "conversion_report.json").read_text())["classes"] == list(idd.CLASSES)
    idd.convert(src, out, 0.1, 0)   # rerun is idempotent (existing symlink accepted)


def test_convert_with_resized_images_dir_retargets_link(tmp_path):
    src = tmp_path / "IDD_Detection"
    make_tree(src, {"train": {"frontFar/a/1": (10, 10, [obj("car", 0, 0, 5, 5)])}, "val": {"frontFar/b/1": (10, 10, [])}})
    resized = tmp_path / "IDD_640" / "JPEGImages"
    for image_id in ("frontFar/a/1", "frontFar/b/1"):
        (resized / f"{image_id}.jpg").parent.mkdir(parents=True, exist_ok=True)
        (resized / f"{image_id}.jpg").write_text("")
    out = tmp_path / "out"
    idd.convert(src, out, 0.1, 0)
    report = idd.convert(src, out, 0.1, 0, images_dir=resized)
    assert (out / "images").resolve() == resized.resolve() and report["images"] == str(resized.resolve())
    with pytest.raises(FileNotFoundError):
        idd.convert(src, out, 0.1, 0, images_dir=tmp_path / "nope")


def test_convert_refuses_foreign_images_dir(tmp_path):
    src = tmp_path / "IDD_Detection"
    make_tree(src, {"train": {"frontFar/a/1": (10, 10, [])}, "val": {"frontFar/b/1": (10, 10, [])}})
    out = tmp_path / "out"
    (out / "images").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        idd.convert(src, out, 0.1, 0)
