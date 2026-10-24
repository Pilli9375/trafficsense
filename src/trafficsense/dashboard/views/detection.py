"""Live Detection: run the IDD-trained YOLOv8n on a video and show what it sees.

Weights: paths.detector_runs/detector/<perception.train.run_name>/weights/best.pt (as
scripts/train_detector.py), checked against the sha256 of the weights that were evaluated
(outputs/perception/detector_test.json). Confidence threshold: the operating point frozen on our
validation split (detector_val.json). Device: the GPU if CUDA is available and at least
dashboard.detection.min_free_vram_mib MiB are free (the LLM and YOLO cannot share this GPU), else CPU.

Everything shown after a run is measured now, on this machine; nothing is written to outputs/.
Counts are detections per frame, not unique vehicles (no tracking).
"""
from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trafficsense.dashboard import data, theme, ui

DET_TEST = "outputs/perception/detector_test.json"
DET_VAL = "outputs/perception/detector_val.json"


def weights_rel(cfg: dict) -> str:
    return f"{data.config_path('detector_runs')}/detector/{cfg['perception']['train']['run_name']}/weights/best.pt"


@st.cache_data(show_spinner=False)
def file_sha256(p: str, mtime: float) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pick_device(min_free_mib: int, force_cpu: bool) -> tuple[str, str]:
    if force_cpu:
        return "cpu", "CPU (chosen)"
    import torch
    if not torch.cuda.is_available():
        return "cpu", "CPU (no CUDA device)"
    free, total = torch.cuda.mem_get_info()
    free_mib, total_mib = free / 2**20, total / 2**20
    name = torch.cuda.get_device_name(0)
    if free_mib < min_free_mib:
        return "cpu", f"CPU ({name} has only {free_mib:.0f} of {total_mib:.0f} MiB free; is an LLM loaded?)"
    return "cuda:0", f"GPU: {name} ({free_mib:.0f} of {total_mib:.0f} MiB free)"


@st.cache_resource(show_spinner="Loading best.pt…")
def load_model(path: str, device: str):
    from ultralytics import YOLO
    m = YOLO(path)
    m.to(device)
    return m


def annotate(frame: np.ndarray, boxes, names: dict) -> np.ndarray:
    import cv2
    out = frame.copy()
    for (x1, y1, x2, y2), c, conf in boxes:
        name = names[c]
        h = theme.CLASS_COLOURS[name].lstrip("#")
        bgr = (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))
        p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
        cv2.rectangle(out, p1, p2, bgr, max(2, out.shape[1] // 500), cv2.LINE_AA)
        label = f"{name} {conf:.2f}"
        fs = max(0.5, out.shape[1] / 1280 * 0.75)     # readable after the frame is shown at ~960 px
        th_ = max(1, round(fs * 2))
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, th_)
        cv2.rectangle(out, (p1[0], p1[1] - th - 8), (p1[0] + tw + 8, p1[1]), bgr, -1)
        cv2.putText(out, label, (p1[0] + 4, p1[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), th_, cv2.LINE_AA)
    return out


def run_detection(video: str, model, device: str, conf: float, iou: float, imgsz: int, max_frames: int) -> dict:
    import cv2
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV cannot read the video {video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    names = model.names
    frames, counts, infer_ms, wall_ms = [], [], [], []
    prog = st.progress(0.0, text="Running the detector…")
    live = st.empty()
    t_start = time.perf_counter()
    n = min(max_frames, n_total) if n_total > 0 else max_frames
    for i in range(n):
        ok, frame = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        res = model.predict(frame, conf=conf, iou=iou, imgsz=imgsz, device=device, verbose=False)[0]
        wall_ms.append(1000 * (time.perf_counter() - t0))
        infer_ms.append(res.speed["preprocess"] + res.speed["inference"] + res.speed["postprocess"])
        b = res.boxes
        boxes = list(zip(b.xyxy.cpu().numpy().tolist(), b.cls.cpu().numpy().astype(int).tolist(),
                         b.conf.cpu().numpy().tolist()))
        c = {names[k]: 0 for k in names}
        for _, k, _ in boxes:
            c[names[k]] += 1
        counts.append(c)
        img = annotate(frame, boxes, names)
        scale = 960 / img.shape[1]
        img = cv2.resize(img, (960, int(img.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frames.append(jpg.tobytes())
        if i % 5 == 0 or i == n - 1:
            live.image(jpg.tobytes(), caption=f"frame {i + 1} of {n}", width="stretch")
            prog.progress((i + 1) / n, text=f"Frame {i + 1} of {n} on {device}")
    cap.release()
    total = time.perf_counter() - t_start
    prog.empty()
    live.empty()
    if not frames:
        raise RuntimeError("No frame could be read from the video")
    return {"frames": frames, "counts": counts, "infer_ms": infer_ms, "wall_ms": wall_ms, "total_s": total,
            "src_fps": src_fps, "n_total": n_total, "device": device, "classes": [names[k] for k in names]}


def show_results(res: dict, source_label: str) -> None:
    n = len(res["frames"])
    model_fps = 1000 / np.mean(res["infer_ms"])
    e2e_fps = n / res["total_s"]
    kpis = [("Frames processed", f"{n}", "", f"of {res['n_total']} in the video" if res["n_total"] > 0 else ""),
            ("Detector speed", f"{model_fps:.1f}", "FPS", "pre-process + inference + NMS, mean per frame"),
            ("End to end", f"{e2e_fps:.1f}", "FPS", "incl. decoding, drawing and the page"),
            ("Device", "GPU" if res["device"].startswith("cuda") else "CPU", "", source_label)]
    for col, (t, v, u, s) in zip(st.columns(4, gap="small"), kpis):
        col.markdown(ui.kpi_card(t, v, u, ui.esc(s)), unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 1], gap="medium")
    with c1:
        k = st.slider("Frame", 1, n, 1, key="det_frame")
        st.image(res["frames"][k - 1], width="stretch")
    with c2:
        st.markdown("##### Detections per frame, one panel per class")
        df = pd.DataFrame(res["counts"])
        present = [c for c in res["classes"] if df[c].sum() > 0]
        fig = make_subplots(rows=len(present), cols=1, shared_xaxes=True, vertical_spacing=0.035)
        for i, c in enumerate(present, start=1):
            fig.add_trace(go.Scatter(x=np.arange(1, n + 1), y=df[c], mode="lines", name=c,
                                     line=dict(color=theme.CLASS_COLOURS[c], width=2, shape="hv"),
                                     hovertemplate="frame %{x}: %{y}<extra>" + c + "</extra>"), row=i, col=1)
            fig.update_yaxes(title_text=c, title_font=dict(size=11), rangemode="tozero", nticks=3, tickformat="d", row=i, col=1)
        fig.add_vline(x=k, line=dict(color=theme.TEXT_3, width=1, dash="dot"))
        fig.update_xaxes(title_text="frame", row=len(present), col=1)
        fig.update_layout(showlegend=False, height=70 + 72 * len(present), margin=dict(l=8, r=8, t=8, b=8))
        st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG)
        tot = df.sum().astype(int)
        st.dataframe(pd.DataFrame({"class": tot.index, "boxes, all frames": tot.values,
                                   "mean per frame": [f"{v:.2f}" for v in df.mean().values]}),
                     hide_index=True, width="stretch")
        st.caption("Measured now on this machine; not stored. Counts are boxes per frame, not unique vehicles.")


def render() -> None:
    ui.header("Live Detection", "What the camera model sees",
              "YOLOv8n trained on the India Driving Dataset, run frame by frame on a video. Upload your own "
              "clip or use the bundled sample from our test split.")
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
        clip_meta = data.read_json(f"{media}/{Path(dcfg['sample_clip']['file']).stem}.json",
                                   "Make it with `python scripts/make_sample_clip.py`.")
    except data.MissingData as e:
        ui.missing(e)
        return
    sha = file_sha256(str(wpath), wpath.stat().st_mtime)
    if sha != test["weights"]["sha256"]:
        st.error(f"`{wrel}` is not the evaluated model: its sha256 differs from the one in `{DET_TEST}`. "
                 "Results shown elsewhere are for the evaluated weights.")
        return

    ui.note("<p><b>Dashcam caveat.</b> IDD is filmed from a moving vehicle, not from a camera on a pole at a "
            "junction; viewpoint, distance and occlusion differ. The sample clip is IDD's sampled frames played in "
            f"order (every {clip_meta['frame_step_in_recording']}th recorded frame), so it is a time-lapse. "
            "Counts are per frame; there is no tracking, so one vehicle is counted in every frame it appears in.</p>",
            tags=[("dashcam proxy", "warn"), ("no tracking", "warn")])

    left, right = st.columns([1, 2.2], gap="medium")
    with left:
        src = st.radio("Video", ["Sample clip (IDD test split)", "Upload a video"], key="det_src")
        up = None
        if src == "Upload a video":
            up = st.file_uploader("Video file", type=["mp4", "avi", "mov", "mkv"], key="det_upload")
        conf = st.slider("Confidence threshold", 0.05, 0.95, float(val["threshold"]["conf"]), 0.05,
                         help="Default: the operating point chosen on our validation split.")
        force_cpu = st.toggle("Force CPU", value=False)
        max_frames = st.number_input("Max frames", 1, 10 * int(dcfg["max_frames"]), int(dcfg["max_frames"]))
        go_btn = st.button("Run detector", type="primary", width="stretch",
                           disabled=src == "Upload a video" and up is None)
    with right:
        st.markdown(f"**Model** `{wrel}`  \nsha256 matches the evaluated weights "
                    f"(test mAP50 {test['ultralytics']['mAP50']:.3f}). Classes: {', '.join(test['classes'])}.")
        if src.startswith("Sample"):
            st.markdown(f"**Sample** `{clip_meta['sequence']}` · {len(clip_meta['frames'])} frames · "
                        f"{clip_meta['fps']} fps · {clip_meta['dataset']}.")
        ui.caption_source(DET_TEST, DET_VAL)

    if go_btn:
        device, why = pick_device(int(dcfg["min_free_vram_mib"]), force_cpu)
        st.info(f"Running on {why}.", icon=":material/memory:")
        model = load_model(str(wpath), device)
        if src.startswith("Sample"):
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
            res = run_detection(video, model, device, conf, float(test["nms_iou"]), int(test["imgsz"]), int(max_frames))
        finally:
            if up is not None:
                Path(video).unlink(missing_ok=True)
        res["label"] = label
        st.session_state["det_result"] = res
    res = st.session_state.get("det_result")
    if res:
        show_results(res, res["label"])
