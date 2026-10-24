"""Live Detection: run the IDD-trained YOLOv8n on a video and show what it sees.

Weights: paths.detector_runs/detector/<perception.train.run_name>/weights/best.pt (as
scripts/train_detector.py), checked against the sha256 of the weights that were evaluated
(outputs/perception/detector_test.json). Confidence threshold: the operating point frozen on our
validation split (detector_val.json). Device: the GPU if CUDA is available and at least
dashboard.detection.min_free_vram_mib MiB are free (the LLM and YOLO cannot share this GPU), else CPU.

Before a run the page shows the clip itself (first frame and a filmstrip). Everything shown after a
run is measured now, on this machine; nothing is written to outputs/. Counts are detections per
frame, not unique vehicles (no tracking).
"""
from __future__ import annotations

import base64
import hashlib
import tempfile
import time
from pathlib import Path

import numpy as np
import streamlit as st

from trafficsense.dashboard import data, theme, ui

DET_TEST = "outputs/perception/detector_test.json"
DET_VAL = "outputs/perception/detector_val.json"
FILMSTRIP = 8


def weights_rel(cfg: dict) -> str:
    return f"{data.config_path('detector_runs')}/detector/{cfg['perception']['train']['run_name']}/weights/best.pt"


@st.cache_data(show_spinner=False)
def file_sha256(p: str, mtime: float) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pick_device(min_free_mib: int, force_cpu: bool) -> tuple[str, str, str]:
    """(device, short label, explanation)."""
    if force_cpu:
        return "cpu", "CPU", "chosen on the page"
    import torch
    if not torch.cuda.is_available():
        return "cpu", "CPU", "no CUDA device"
    free, total = torch.cuda.mem_get_info()
    free_mib, total_mib = free / 2**20, total / 2**20
    name = torch.cuda.get_device_name(0)
    if free_mib < min_free_mib:
        return "cpu", "CPU", f"{name} has only {free_mib:.0f} of {total_mib:.0f} MiB free; is an LLM loaded?"
    return "cuda:0", "GPU", f"{name}, {free_mib:.0f} of {total_mib:.0f} MiB free"


@st.cache_resource(show_spinner="Loading best.pt…")
def load_model(path: str, device: str):
    from ultralytics import YOLO
    m = YOLO(path)
    m.to(device)
    return m


def _jpeg(frame: np.ndarray, width: int, quality: int) -> tuple[str, float]:
    """JPEG data URL of the frame resized to `width`, and the scale factor used."""
    import cv2
    scale = width / frame.shape[1]
    img = cv2.resize(frame, (width, int(round(frame.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("OpenCV could not encode a frame as JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii"), scale


@st.cache_data(show_spinner=False, max_entries=4)
def clip_preview(path: str, mtime: float) -> tuple[str, list[str], int]:
    """The clip's first frame (large) and FILMSTRIP evenly spaced thumbnails, read from the file."""
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV cannot read the video {path}")
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    want = sorted({int(round(i * (n - 1) / (FILMSTRIP - 1))) for i in range(FILMSTRIP)}) if n > 1 else [0]
    first, thumbs, i = None, [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i == 0:
            first = _jpeg(frame, 1280, 84)[0]
        if i in want:
            thumbs.append(_jpeg(frame, 240, 72)[0])
        i += 1
    cap.release()
    if first is None:
        raise RuntimeError(f"No frame could be read from {path}")
    return first, thumbs, i


def run_detection(video: str, model, device: str, conf: float, iou: float, imgsz: int, max_frames: int,
                  status) -> dict:
    import cv2
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV cannot read the video {video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n = min(max_frames, n_total) if n_total > 0 else max_frames
    width = 960 if n <= 120 else 640         # keeps the page's payload small for long uploads
    frames, boxes, infer_ms = [], [], []
    prog = status.progress(0.0, text="Running the detector…")
    t_start = time.perf_counter()
    for i in range(n):
        ok, frame = cap.read()
        if not ok:
            break
        res = model.predict(frame, conf=conf, iou=iou, imgsz=imgsz, device=device, verbose=False)[0]
        infer_ms.append(res.speed["preprocess"] + res.speed["inference"] + res.speed["postprocess"])
        url, sc = _jpeg(frame, width, 82)
        b = res.boxes
        xyxy = (b.xyxy.cpu().numpy() * sc).round(1).tolist()
        frames.append(url)
        boxes.append([[*xy, int(c), round(float(p), 3)] for xy, c, p in
                      zip(xyxy, b.cls.cpu().numpy().astype(int).tolist(), b.conf.cpu().numpy().tolist())])
        if i % 5 == 0 or i == n - 1:
            prog.progress((i + 1) / n, text=f"Frame {i + 1} of {n} on {device}")
    cap.release()
    total = time.perf_counter() - t_start
    prog.empty()
    if not frames:
        raise RuntimeError("No frame could be read from the video")
    h = int(round(width * frame.shape[0] / frame.shape[1]))
    names = [model.names[k] for k in sorted(model.names)]
    present = [c for c in names if any(names[bx[4]] == c for fb in boxes for bx in fb)]
    return {"frames": frames, "boxes": boxes, "w": width, "h": h, "classes": names, "present": present,
            "fps": src_fps if src_fps and src_fps > 0 else 4.0,
            "stats": {"detector_fps": 1000 / float(np.mean(infer_ms)), "latency_ms_mean": float(np.mean(infer_ms)),
                      "latency_ms_p95": float(np.percentile(infer_ms, 95)), "e2e_fps": len(frames) / total,
                      "n_total": n_total}}


def preview_html(first: str, thumbs: list[str], caption: str) -> str:
    strip = "".join(f'<img src="{t}" alt="" loading="lazy">' for t in thumbs)
    return (f'<div class="ts-prev"><div class="ts-prev-stage"><img src="{first}" alt="First frame of the sample clip">'
            f'<div class="ts-prev-cap">{caption}</div><div class="ts-prev-play">Press <b>Run detector</b> to run '
            f'YOLOv8n on this clip</div></div><div class="ts-strip">{strip}</div></div>')


def render() -> None:
    ui.page_header("Perception", "Live Detection",
                   "YOLOv8n trained on the India Driving Dataset, run frame by frame on a video, on this machine.",
                   ["dashcam proxy", "no tracking", "measured now"])
    try:
        cfg = data.config()
        dcfg = cfg["dashboard"]["detection"]
        test = data.read_json(DET_TEST, "Run scripts/eval_detector.py --stage test.")
        val = data.read_json(DET_VAL, "Run scripts/eval_detector.py --stage val.")
        wrel = weights_rel(cfg)
        wpath = data.path(wrel)
        if not wpath.is_file():
            raise data.MissingData(wrel, "Train the detector (scripts/train_detector.py) or create the "
                                         "data/external/detector_runs symlink (configs/default.yaml).")
        media = data.config_path("dashboard_media")
        clip_rel = f"{media}/{dcfg['sample_clip']['file']}"
        meta_rel = f"{media}/{Path(dcfg['sample_clip']['file']).stem}.json"
        clip_meta = data.read_json(meta_rel, "Make it with `python scripts/make_sample_clip.py`.")
    except data.MissingData as e:
        ui.missing(e)
        return
    sha = file_sha256(str(wpath), wpath.stat().st_mtime)
    if sha != test["weights"]["sha256"]:
        st.error(f"`{wrel}` is not the evaluated model: its sha256 differs from the one in `{DET_TEST}`. "
                 "Results shown elsewhere are for the evaluated weights.")
        return

    left, right = st.columns([1, 2.65], gap="medium")
    with left:
        with st.container(key="panel-det"):
            src = st.segmented_control("Video", ["Sample clip", "Upload"], default="Sample clip", key="det_src") or "Sample clip"
            up = None
            if src == "Upload":
                up = st.file_uploader("Video file", type=["mp4", "avi", "mov", "mkv"], key="det_upload")
            conf = st.slider("Confidence threshold", 0.05, 0.95, float(val["threshold"]["conf"]), 0.05,
                             help="Default: the operating point chosen on our validation split.")
            max_frames = st.number_input("Max frames", 1, 10 * int(dcfg["max_frames"]), int(dcfg["max_frames"]))
            force_cpu = st.toggle("Force CPU", value=False)
            go_btn = st.button("Run detector", type="primary", width="stretch", icon=":material/play_arrow:",
                               disabled=src == "Upload" and up is None)
        chips = "".join(f'<span class="ts-cls"><span class="ts-dot" style="background:{theme.CLASS_COLOURS[c]}"></span>'
                        f'{ui.esc(c)}</span>' for c in test["classes"])
        ui.html(ui.card(
            ui.card_header("Model", None, [DET_TEST, DET_VAL])
            + f'<div class="ts-kv"><span>Weights</span><code title="{ui.esc(wrel)}">best.pt</code></div>'
            + f'<div class="ts-kv"><span>sha256</span><span class="ok">{ui.icon("check", 14)} matches the evaluated weights</span></div>'
            + f'<div class="ts-kv"><span>Test mAP50</span><b>{test["ultralytics"]["mAP50"]:.3f}</b></div>'
            + f'<div class="ts-kv"><span>Default threshold</span><b>{val["threshold"]["conf"]}</b></div>'
            + f'<div class="ts-classes">{chips}</div>'))

    with right:
        status = st.empty()
        if go_btn:
            device, dev_short, why = pick_device(int(dcfg["min_free_vram_mib"]), force_cpu)
            model = load_model(str(wpath), device)
            if src == "Sample clip":
                video, label = str(data.path(clip_rel)), "IDD test-split sample"
                if not Path(video).is_file():
                    ui.missing(data.MissingData(clip_rel, "Make it with `python scripts/make_sample_clip.py`."))
                    return
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=Path(up.name).suffix, delete=False)
                tmp.write(up.getbuffer())
                tmp.close()
                video, label = tmp.name, up.name
            try:
                res = run_detection(video, model, device, conf, float(test["nms_iou"]), int(test["imgsz"]),
                                    int(max_frames), status.container())
            finally:
                if up is not None:
                    Path(video).unlink(missing_ok=True)
            res["label"] = label
            res["stats"].update(device_short=dev_short, device_detail=why)
            res["colours"] = {c: theme.CLASS_COLOURS[c] for c in res["classes"] if c in theme.CLASS_COLOURS}
            st.session_state["det_result"] = res
        res = st.session_state.get("det_result")
        if res:
            player = ui.component("trafficsense_detection_player", "pl-host", "player.css", "player.js")
            player(data=res, key="det_player", height="content")
        else:
            if src == "Sample clip":
                p = data.path(clip_rel)
                if not p.is_file():
                    ui.missing(data.MissingData(clip_rel, "Make it with `python scripts/make_sample_clip.py`."))
                    return
                first, thumbs, n = clip_preview(str(p), p.stat().st_mtime)
                cap = (f'<span class="ts-pill">Sample · IDD test split</span><span class="ts-pill">'
                       f'{data.derived(len(clip_meta["frames"]))} frames · {clip_meta["fps"]} fps</span>')
                ui.html(preview_html(first, thumbs, cap))
                ui.html(f'<div class="ts-prev-src">{ui.source_chip(meta_rel, align="left")}</div>')
            else:
                ui.html('<div class="ts-prev ts-prev-empty"><div>Choose a video file on the left, then press '
                        '<b>Run detector</b>.</div></div>')

    ui.why(
        "<p><b>Dashcam caveat.</b> IDD is filmed from a moving vehicle, not from a camera on a pole at a junction; "
        "viewpoint, distance and occlusion differ. The sample clip is IDD's sampled frames played in order "
        f"(every {clip_meta['frame_step_in_recording']}th recorded frame), so it is a time-lapse.</p>"
        "<p><b>Counts.</b> Boxes per frame; there is no tracking, so one vehicle is counted in every frame it "
        "appears in.</p>"
        "<p><b>Speed.</b> Detector speed is pre-processing, inference and NMS per frame, as Ultralytics reports it; "
        "end to end adds reading the video and encoding the frames for this page. Both are measured on this "
        "machine when you press Run and are not stored. The GPU is used only if enough of its memory is free "
        "(an LLM loaded by Ollama takes most of the 4 GB).</p>")
