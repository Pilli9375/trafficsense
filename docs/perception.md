# Perception: IDD Detection → YOLO

Phase 4a prepares a real, labelled Indian road dataset for the YOLOv8 detector. The
detector the project had before was trained on coloured rectangles, so everything here is
about the real data: what it is, how it is converted, and how we will check the result.

Sections 1–4 were written and committed **before** any conversion code existed
(pre-registration). Section 5 records what the conversion actually produced.

## 1. The dataset as found (verified 2026-10-22)

IDD Detection (India Driving Dataset, IIIT Hyderabad / Intel), extracted at
`/mnt/d/trafficsense/datasets/idd-detection/IDD_Detection` (24 GB). It stays on D; the repo
only points at it through the gitignored symlink `data/external/idd_detection`.

Layout: Pascal VOC. `JPEGImages/<camera>/<sequence>/<frame>.jpg`,
`Annotations/<camera>/<sequence>/<frame>.xml`, split lists `train.txt`, `val.txt`,
`test.txt` (one `<camera>/<sequence>/<frame>` id per line, no extension). Each XML has
`size` (width, height) and `object`s with `name` and `bndbox` (xmin, ymin, xmax, ymax in
pixels). There are no `difficult`/`truncated`/`occluded` flags.

| split | ids | images present | annotations present | sequences | image sizes (W×H) |
|---|---|---|---|---|---|
| train | 31,569 | 31,569 | 31,569 | 438 | 1920×1080: 26,989 · 1280×964: 3,431 · 1921×1080: 1,149 |
| val | 10,225 | 10,225 | 10,225 | 119 | 1920×1080: 8,535 · 1280×964: 1,065 · 1280×720: 421 · 1921×1080: 204 |
| test | 4,794 | 4,794 | **0** | 69 | (labels withheld by the dataset authors) |

- No id appears twice; no sequence is shared between splits.
- Every train/val annotation has at least one object.
- 1 zero-area box in train (a `traffic light`); 218 (train) and 45 (val) boxes extend past
  the image border.
- A random sample of 1,000 images (seed 0, all splits) was fully decoded with Pillow: 0
  corrupt, and the XML `size` matched the real image size in all of them (including the odd
  1921-wide frames).
- 71 images and 65 annotations on disk are in none of the split lists; they are not used.

Folder sizes: JPEGImages: highquality_16k 8.4 GB, sideRight 4.9 GB, sideLeft 4.1 GB,
frontNear 2.4 GB, frontFar 2.1 GB, rearNear 1.4 GB. `Annotations/rearFar` is an empty
folder and there is no `JPEGImages/rearFar`. That folder is not in any split list, so
nothing is missing.

Classes and box counts (from the XMLs, before any mapping):

| IDD class | train | val |
|---|---:|---:|
| motorcycle | 78,119 | 25,489 |
| rider | 73,108 | 24,518 |
| person | 70,319 | 18,078 |
| car | 65,676 | 24,844 |
| autorickshaw | 24,498 | 7,782 |
| truck | 20,759 | 7,078 |
| vehicle fallback | 14,992 | 6,089 |
| bus | 13,829 | 4,916 |
| traffic sign | 9,916 | 4,287 |
| animal | 4,764 | 1,460 |
| traffic light | 2,780 | 919 |
| bicycle | 2,573 | 569 |
| caravan | 125 | 11 |
| train | 47 | 13 |
| trailer | 11 | 7 |

## 2. Class mapping (pre-registered)

Our 7 classes, in this index order: `0 car, 1 motorcycle, 2 autorickshaw, 3 bus, 4 truck,
5 bicycle, 6 person`.

| IDD class | → ours | why |
|---|---|---|
| car, motorcycle, autorickshaw, bus, truck, bicycle, person | same name | one-to-one |
| rider | dropped | A rider sits on a motorcycle or bicycle that has its own box. Counting riders would double-count road users, and calling them `person` would turn every two-wheeler into a pedestrian. Leaving them unlabelled teaches the detector that `person` means a pedestrian, which is what the signal controller needs. |
| vehicle fallback | dropped | IDD's catch-all for vehicles that fit no class (tractors, handcarts, unclear shapes). Forcing it into any one of our classes would be a guess. **Side effect:** these regions become background, which slightly penalises the model for detecting them as e.g. truck. They are 6.8% of the vehicle boxes in train. We accept this rather than editing images. |
| caravan, trailer | dropped | 136 and 18 boxes in total: too few to learn, and neither is clearly a `truck`. |
| train | dropped | Not road traffic at a signal. |
| animal | dropped | Not a vehicle or pedestrian, and the simulator has no animal agents. Cattle on Indian roads are real, but they are outside this project's scope. |
| traffic sign, traffic light | dropped | Infrastructure, not road users. The controller already knows its own signal state. |

Box cleaning: boxes are clipped to the image; a box with width or height below 1 px after
clipping is dropped. Counts of clipped and dropped boxes are written to the conversion
report. Images whose boxes are all dropped are kept as background images (negatives).

## 3. Splits (pre-registered)

The official test split has no public labels, so it cannot measure anything. Therefore:

| our split | source | role |
|---|---|---|
| **train** | official train minus the held-out sequences | training |
| **val** | 10% of the official-train **sequences**, chosen per camera group | early stopping, picking epochs and thresholds |
| **test** | official val (10,225 images, 119 sequences) | final numbers only; looked at once, after all choices are fixed |
| (unused) | official test | qualitative demos at most; no metrics |

The held-out val is chosen by **sequence**, not by frame. Consecutive frames of one drive
are near-duplicates, so a frame-level split would leak the same scenes into training and
make val scores look better than they are. Rule: for each camera group (`frontFar`,
`frontNear`, `highquality_16k`, `rearNear`, `sideLeft`, `sideRight`), sort its sequence
names and take `max(1, round(0.10 × n))` of them with `random.Random(0).sample`. The chosen
sequence list is written to the output folder.

## 4. Image size (pre-registered)

Training and evaluation at `imgsz=640`: YOLO letterboxes the long side to 640, so a
1920×1080 frame becomes 640×360 (3× downscale). This is what fits a GTX 1650 (section 6).
Cost: small, distant objects shrink a lot. A 30 px-tall far motorcycle becomes 10 px. We
will report recall by box size (COCO small/medium/large, measured at the 640 scale) so this
cost is visible rather than hidden in the mean.

Labels are written in YOLO format (`class cx cy w h`, normalised by the original image
size), so they are independent of the training size.

## 5. Conversion result

`python scripts/prepare_idd.py` (report: `outputs/perception/idd_conversion.json`, with the
git commit it ran at). Output in `data/external/idd_yolo/` (gitignored): `images` → symlink
to `JPEGImages` on D, `labels/` (159 MB, one `.txt` per image, same layout), `train.txt`,
`val.txt`, `test.txt` (`./images/...jpg` lines), `val_sequences.txt` and `data.yaml`. No
image was copied. After writing, the script reads every one of the 41,794 label files back
and compares it with a fresh conversion of its XML; all matched.

| our split | from | images | sequences | boxes kept | background images |
|---|---|---:|---:|---:|---:|
| train | official train | 28,384 | 393 | 247,051 | 1,203 |
| val | official train (held-out sequences) | 3,185 | 45 | 28,722 | 189 |
| test | official val | 10,225 | 119 | 88,755 | 382 |

Boxes per class after mapping:

| class | train | val | test |
|---|---:|---:|---:|
| car | 58,508 | 7,168 | 24,843 |
| motorcycle | 69,602 | 8,517 | 25,489 |
| autorickshaw | 21,793 | 2,705 | 7,782 |
| bus | 12,534 | 1,295 | 4,916 |
| truck | 18,645 | 2,114 | 7,078 |
| bicycle | 2,240 | 333 | 569 |
| person | 63,729 | 6,590 | 18,078 |

Dropped by the mapping (train / val / test): rider 65,981 / 7,127 / 24,518 · vehicle
fallback 13,450 / 1,542 / 6,089 · traffic sign 8,404 / 1,512 / 4,287 · animal 4,494 / 270 /
1,460 · traffic light 2,522 / 258 / 919 · caravan 115 / 10 / 11 · train 39 / 8 / 13 ·
trailer 11 / 0 / 7. Box cleaning: 155 / 15 / 39 boxes clipped to the image border; 1 box
dropped as degenerate (a zero-height `car` in test; the zero-area `traffic light` in train is
already dropped by class).

**bicycle is rare** (2,240 training boxes, about 0.9% of kept boxes, and only 569 in test).
Expect its per-class numbers to be the weakest and the noisiest.

Proof that the labels are real: `python scripts/render_idd_samples.py` draws the converted
labels (read back from `labels/`, not from the XML) on 16 random training images
(`outputs/perception/sample_grid.jpg`, seed 0) and on 3 of them at full resolution
(`alignment_*.jpg`). The images are not committed; the chosen image ids are in
`outputs/perception/sample_grid.json`.

What the check showed (seed 0): the boxes sit tightly on the cars, autorickshaws, buses,
motorcycles and pedestrians in all 16 tiles, and the class names are right. A motorcycle box
covers the bike and the lower half of its rider, which is how IDD draws them. Two tiles have
visible vehicles without boxes. In both, the XML has them as dropped classes: tile 2's
vehicle at the right edge is a `caravan`, and tile 6's trailer and the vehicle beside it are
`vehicle fallback`. This is the side effect described in section 2, now seen on real images,
and not a conversion error. Tile 15 has only a tiny far motorcycle and a person, which shows
how small distant objects get.

Provenance note: the report records commit `51a2b5e` with `git_dirty: true`. The dirty files
were another session's uncommitted LLM-client changes (`src/trafficsense/llm/`,
`control/llm.py`, and the `llm_hosted` block of `configs/default.yaml`), none of which the
conversion imports or reads. The conversion code is exactly as committed in `51a2b5e`, and a
first run before that commit produced identical counts.

## 6. Training plan (not run yet)

| setting | value | why |
|---|---|---|
| model | `yolov8n`, starting from the COCO-pretrained `yolov8n.pt` | 3.2 M parameters. `yolov8s` (11 M) would need batch ≤ 4 in FP32 on 4 GB and train about 3× slower. COCO already knows car/bus/truck/motorcycle/bicycle/person, and the 7-class head is trained fresh. |
| image size | 640 | section 4 |
| batch | 8 | Fits in 4 GB in FP32 with headroom. Try 16 in the probe (below) and keep it only if peak memory stays under ~3.5 GB. |
| AMP | **off** (`amp=False`) | GTX 16-series cards produce NaN losses under FP16 AMP. Ultralytics' own AMP check also disables it on the 1650. FP32 costs speed and memory, not accuracy. |
| epochs | 50, `patience=10` on our val mAP50-95 | Fine-tuning from COCO converges in tens of epochs. Early stopping uses our val split only. |
| workers | 8 | 12 logical CPUs. Reading is the limit (6.2), and more parallel readers help a little. |
| cache | off | RAM caching needs about 28,384 × 640×360×3 B ≈ 20 GB; WSL has 11 GB. |
| other | defaults (SGD/auto, mosaic, `close_mosaic=10`), `seed=0`, `deterministic=True` | No tuning before a first baseline exists. |

**The bottleneck is reading images from D, not the GPU.** D is a 5400 rpm laptop HDD
(Seagate ST1000LM035) reached from WSL over the 9p bridge. Measured on 2026-10-22, with
another session using the machine: 7.3 MB/s ≈ 14 img/s with 4 or 8 threads in random order,
9.8 MB/s ≈ 18 img/s sequential. Full-size frames average 520 KB. Many small files read
faster: the 41,794 XMLs took about 2 min with 32 threads, ≈ 350 files/s.

### 6.1 Resized copy (done, 2026-10-22)

`python scripts/resize_idd.py` wrote every image of our three splits (41,794) to
`/mnt/d/trafficsense/datasets/idd-detection/IDD_Detection_640/JPEGImages`, with the same
layout. The repo reaches it through the gitignored symlink `data/external/idd_detection_640`
(`paths.idd_resized`).

| setting | value |
|---|---|
| size | long side 640 (= `imgsz`), aspect kept, never upscaled: 1920×1080 → 640×360, 1280×964 → 640×482, 1280×720 → 640×360 |
| filter | Pillow `BOX` (area averaging, like OpenCV's `INTER_AREA`, which Ultralytics uses to shrink) |
| JPEG | quality 95, no EXIF |
| result | 41,794 images, 3.81 GB (≈ 91 KB/img), about 1.6 h on the HDD |
| check | every output re-opened and its size compared with the expected size: all correct |

The originals in `IDD_Detection/` are untouched. The settings are `perception.resize` in
`configs/default.yaml`, and the manifest (with provenance, commit `b2fd6ac`) is at
`outputs/perception/idd_resize.json`. `perception.images: resized` makes `prepare_idd.py`
point `data/external/idd_yolo/images` at this copy. The labels did not change: they are
normalised, and the regenerated report has the same counts as section 5.

Ultralytics' own loader was run on our val split on the CPU, with the GPU hidden
(`CUDA_VISIBLE_DEVICES=""`). It found all 3,185 images and their labels, 7 classes, at sizes
640×360 and 640×482. It also drops **exact duplicate boxes**: IDD has 4 boxes annotated
twice with identical coordinates (1 car in train, 1 person in val, 1 truck and 1 bus in
test). We keep the labels 1:1 with IDD; Ultralytics ignores the duplicates in training and
in validation.

### 6.2 Image reading speed: the resize helped less than expected

Measured after the resize, 600 random training images per run:

| source | threads | img/s |
|---|---|---|
| full-size originals (≈ 520 KB) | 4-8 | 14 |
| resized copy (≈ 91 KB) | 1 | 8.8 |
| resized copy | 8 | 20-23 |
| resized copy | 32 | 26 |
| resized copy, sequential in folder order | 1 | 19 |

Ultralytics measured the same thing independently: "ping 51 ms" per file. The limit is a
fixed **~50 ms cost per file opened** on D (laptop HDD seeks, plus WSL's 9p bridge to
Windows, plus probably Windows Defender's on-access scan, which is on). It is not the number
of bytes. The plan above assumed ~350 files/s from how fast the XMLs read; that was wrong for
images. The resize still gives ~1.5× faster reads and much less JPEG decoding.

### 6.3 Revised time estimate

Training will read ~20-25 img/s, which is less than the GPU can process (assumed ~45 img/s
in FP32, still to be measured), so reading is the limit:

- one epoch: 28,384 train images at ~22 img/s ≈ 21 min, plus val (3,185 images) ≈ 2-3 min
  → **~24 min per epoch**
- 50 epochs ≈ **20 h**, fewer if early stopping fires

The probe measures the real number. Ways to go faster, all for the user to decide and none
done:

1. A Defender exclusion for `D:\trafficsense\datasets` (admin), then re-measure. Free if
   Defender is a large part of the 50 ms.
2. Copy the 3.8 GB resized set into the WSL disk (SSD). It would be fast, but that disk lives
   on C, which now has 8.4 GB free.
3. Accept ~20 h. The run is resumable (`resume=True`), so it can be split over nights.

### 6.4 Software (installed 2026-10-22)

`.venv` now has `torch 2.14.1+cu126`, `torchvision 0.29.1+cu126` and `ultralytics 8.4.183`
(with `opencv-python 5.0.0`). Torch's requirements also upgraded `setuptools` 59.6 → 78.1.
CUDA 12.6 runs on driver 576.88 (which supports up to 12.9). The build's architecture list
includes `sm_75`, the GTX 1650, and `torch.cuda.is_available()` is True. No CUDA context was
created and nothing ran on the GPU. pip ran with `--no-cache-dir`, its temporary files went
to D, and the pip cache was purged afterwards.

Disk cost: `.venv` grew from 196 MB to 6.9 GB, mostly NVIDIA CUDA libraries. That is more
than the 3-4 GB estimated above. Windows C free space went from 16,701 MiB to 8,454 MiB
during this step; other activity on the machine accounts for the ~1.4 GB not explained by
the venv. The WSL disk image (`ext4.vhdx`) is now 13.2 GB. It does not shrink by itself when
files are deleted.

### 6.5 Next: probe, then the full run (waiting for the GPU)

Probe: 1 epoch on `fraction=0.1` of train, `amp=False`, batch 8 (then 16 if memory allows),
`workers=8`. It measures img/s, peak VRAM and whether the loss stays finite. Then the
50-epoch run, with nothing else on the GPU (no Ollama).

## 7. Measuring the detector's errors for the camera-error experiment (proposal)

The simulation experiment will feed the controller vehicle counts that are wrong in the way
a real detector is wrong. Its error parameters will be measured on **our test split**
(official val, never used for training or choices), once, with the final model.

1. **Operating point.** Pick one confidence threshold on our **val** split: the one that
   maximises mean F1 over the 7 classes. Freeze it before touching test. NMS IoU 0.7
   (Ultralytics default).
2. **Matching.** Per image, sort detections by confidence and greedily match each to the
   unmatched ground-truth box with the highest IoU ≥ 0.5, ignoring class. Then:
   - matched, same class → true positive
   - matched, other class → **confusion** (counted in a 7×7 confusion matrix)
   - unmatched detection → **false detection**
   - unmatched ground truth → **miss**
3. **Per-class numbers** (with 95% bootstrap intervals, resampling whole *sequences* so
   correlated frames don't make the intervals look tighter than they are):
   - miss rate_c = misses_c / GT_c (1 − recall)
   - false detections per image, per predicted class, and precision_c
   - confusion probabilities P(predicted j | true c)
   - split by box size (small / medium / large at the 640 scale) and by camera group, since
     far objects are where detectors fail
   - per-image count error |predicted count − true count| per class, because the controller
     consumes counts, not boxes
4. **Error model for the simulator.** Each vehicle of class c in a camera's view is detected
   with probability 1 − miss rate_c. A detected vehicle is labelled j with the measured
   confusion probabilities. False detections are added per approach per decision step as a
   Poisson count with the measured per-image rate. The parameters are written to
   `outputs/perception/error_model.json` with provenance and loaded from there, never typed
   into code.

**Caveat, stated wherever this is used:** IDD is filmed from a moving vehicle, not from a
camera on a pole at an intersection. Viewpoint, distance and occlusion differ, so these rates
are a measured proxy for an intersection camera, not its true error. The size-bucket split is
there so the experiment can at least vary how far the camera sees.
