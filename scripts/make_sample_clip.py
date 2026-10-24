"""Make the Live Detection page's sample clip from IDD frames of OUR TEST split (official IDD val),
which the detector never saw in training or in choosing its threshold.

    python scripts/make_sample_clip.py

IDD is a set of sampled frames, not videos: a sequence's frames are every n-th frame of the
original recording. The clip uses the sequence in the test split with the longest run of evenly
spaced frames (checked here; the script stops if the configured sequence is not that one), and the
first `frames` frames of that run, played at `fps`. So the clip is a time-lapse of a dashcam
drive. Written to paths.dashboard_media (a symlink to D, not in git) with a JSON record of the
source frames.
"""
import collections
import hashlib
import json
import re
from pathlib import Path

import cv2

from trafficsense.config import load_config, resolve_path

FRAME = re.compile(r"^\d+$")


def evenly_spaced_runs(ids: list[str]) -> dict[str, tuple[int, int, list[int]]]:
    """Per camera/sequence: (most common frame step, longest run length, frames of that run)."""
    seqs = collections.defaultdict(list)
    for i in ids:
        cam, seq, fr = i.split("/")
        if FRAME.match(fr):
            seqs[f"{cam}/{seq}"].append(int(fr))
    out = {}
    for k, frames in seqs.items():
        frames.sort()
        diffs = [b - a for a, b in zip(frames, frames[1:])]
        if not diffs:
            continue
        step = collections.Counter(diffs).most_common(1)[0][0]
        best, start, cur, cur_start = 1, 0, 1, 0
        for j, d in enumerate(diffs):
            if d == step:
                cur += 1
            else:
                cur, cur_start = 1, j + 1
            if cur > best:
                best, start = cur, cur_start
        out[k] = (step, best, frames[start:start + best])
    return out


def main():
    cfg = load_config("configs/default.yaml")
    sc = cfg["dashboard"]["detection"]["sample_clip"]
    idd = resolve_path(cfg, "idd_root")
    test_ids = (idd / "val.txt").read_text().split()       # our test split = official val
    train_ids = set((idd / "train.txt").read_text().split())
    runs = evenly_spaced_runs(test_ids)
    longest = max(runs, key=lambda k: (runs[k][1], k))
    if longest != sc["sequence"]:
        raise SystemExit(f"Longest evenly spaced run in the test split is {longest}, config says {sc['sequence']}")
    step, length, frames = runs[longest]
    if length < sc["frames"]:
        raise SystemExit(f"{longest}: run has {length} frames, need {sc['frames']}")
    frames = frames[: sc["frames"]]
    width = int(sc["width"])
    out_dir = resolve_path(cfg, "dashboard_media")
    if not out_dir.is_dir():
        raise SystemExit(f"{out_dir} does not exist; create the symlink to D (configs/default.yaml, paths.dashboard_media)")
    src = []
    writer = None
    clip = out_dir / sc["file"]
    for fr in frames:
        name = f"{fr:07d}"
        fid = f"{longest}/{name}"
        if fid not in test_ids or fid in train_ids:
            raise SystemExit(f"{fid} is not (only) in the test split")
        img = cv2.imread(str(idd / "JPEGImages" / f"{fid}.jpg"))
        if img is None:
            raise SystemExit(f"Cannot read {fid}.jpg")
        h = round(img.shape[0] * width / img.shape[1] / 2) * 2
        img = cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA)
        if writer is None:
            writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), float(sc["fps"]), (width, h))
        writer.write(img)
        src.append(fid)
    writer.release()
    record = {
        "made_by": "scripts/make_sample_clip.py",
        "dataset": "IDD Detection, our test split (official val): never used for training or the threshold",
        "sequence": longest,
        "frame_step_in_recording": step,
        "longest_evenly_spaced_run": length,
        "frames": src,
        "fps": sc["fps"],
        "width": width,
        "clip": sc["file"],
        "clip_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
        "caveat": "IDD is filmed from a moving vehicle (dashcam), not from a pole-mounted junction camera",
    }
    (out_dir / (Path(sc["file"]).stem + ".json")).write_text(json.dumps(record, indent=1))
    print(f"{clip}: {len(src)} frames of {longest} (every {step}th recorded frame), {sc['fps']} fps")


if __name__ == "__main__":
    main()
