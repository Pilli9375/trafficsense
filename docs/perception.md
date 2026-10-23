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

## 6. Training plan

| setting | value | why |
|---|---|---|
| model | `yolov8n`, starting from the COCO-pretrained `yolov8n.pt` | 3.2 M parameters. `yolov8s` (11 M) would need batch ≤ 4 in FP32 on 4 GB and train about 3× slower. COCO already knows car/bus/truck/motorcycle/bicycle/person, and the 7-class head is trained fresh. |
| image size | 640 | section 4 |
| batch | 8 | Fits in 4 GB in FP32 with headroom. Try 16 in the probe (below) and keep it only if peak memory stays under ~3.5 GB. |
| AMP | **off** (`amp=False`) | GTX 16-series cards produce NaN losses under FP16 AMP. Ultralytics' own AMP check also disables it on the 1650. FP32 costs speed and memory, not accuracy. |
| epochs | 50, `patience=10` on our val mAP50-95 | Fine-tuning from COCO converges in tens of epochs. Early stopping uses our val split only. |
| workers | 8 | 12 logical CPUs. Fastest of 2/4/6/8 in every run (6.3). |
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

### 6.3 After the Defender exclusion (2026-10-22)

The user added a Windows Defender exclusion for `D:\trafficsense\datasets`. Everything was
then re-measured with `scripts/bench_image_io.py`, CPU only with the GPU hidden (GPU memory
stayed at 13 MiB throughout):

- **Raw reads:** whole files, N threads, a fresh random sample of 300 test-split images per
  row. These images were not read by anything earlier the same day.
- **Ultralytics loader:** our train split through `YOLODataset` with the training
  augmentations (mosaic etc., 640, batch 8). The rate is measured in steady state over 250
  batches = 2,000 images, after skipping the first 2 × workers batches, and each row has its
  own shuffle seed. Mosaic takes its 3 extra images from an in-memory buffer, so training
  opens about one file per image.

Three runs were made. Run 1 timed only 75 batches and included the warm-up, which overstates
the loader at high worker counts; the script was then fixed. Results:
`outputs/perception/io_bench_seed1.json` and `io_bench_seed2.json`. Run 1's JSON was
overwritten, and its result lines are kept in `io_bench_run1.log`.

| | run 1 | run 2 (seed 1) | run 3 (seed 2) |
|---|---:|---:|---:|
| Ultralytics' per-file "ping" | 5.4 ms | | |
| raw, 1 thread | 22.4 | 29.2 | 34.2 |
| raw, 2 threads | 34.7 | 43.4 | 52.9 |
| raw, 4 threads | 42.0 | 55.9 | 63.4 |
| raw, 8 threads | 44.5 | 55.6 | 72.1 |
| raw, 16 threads | 45.4 | 61.8 | 64.5 |
| **loader, workers = 2** | 35.5* | 38.4 | 48.9 |
| **loader, workers = 4** | 49.6* | 54.9 | 74.7 |
| **loader, workers = 6** | 52.6* | 63.1 | 85.4 |
| **loader, workers = 8** | 55.4* | 68.3 | 90.8 |
| raw, 8 threads, train images already read by the label scan | 51.9 | 73.5 | 102.8 |

(images/s; * = run 1's biased loader timing.)

What this shows:

- **The exclusion helped a lot.** Per-file latency fell from ~51 ms to ~5 ms (Ultralytics'
  own probe). One thread now reads 22-34 img/s against 8.8 before, and 8 threads 44-72
  against 20-23. Defender was most of the ~50 ms.
- **Parallel workers hide much of the remaining latency.** Going from 2 to 4 workers adds the
  most (+40-50%), and 6 → 8 still adds 5-8%. Use **workers = 8**: the CPU has 12 logical
  cores, which leaves room for the main training process.
- **The numbers drift upward from run to run, by up to 30-60%,** even for images never read
  before. The likely causes are the Windows file cache filling with this dataset (images
  already read come back 15-40% faster than unread ones in each run) and varying load from
  the other session. The cause is not pinned down, so the planning number is the **low end:
  ~55-70 img/s with 8 workers**. Later epochs may run faster if Windows keeps the 3.8 GB
  cached; WSL can take up to 12 GB of the 16 GB, so that is not guaranteed.
- The one-time label scan of the 28,384 training images took 410 s. Its cache
  (`labels/frontFar/BLR-2018-03-22_17-39-26_2_frontFar.cache`) now exists, so later runs only
  check file sizes (~2 min).

### 6.3.1 New training-time estimate

With 8 workers the loader supplies ~55-90 img/s. FP32 yolov8n at 640 on the GTX 1650 is
assumed to run at ~45 img/s, an **estimate** to be measured. So **the GPU is now expected
to be the limit, not the disk.**

| case | train epoch (28,384 imgs) | + val (3,185, no augmentation) | 50 epochs |
|---|---|---|---|
| GPU at 45 img/s (expected limit) | ~10.5 min | ~1 min | **~9.5 h** |
| if the GPU proves faster, disk at the low end, ~55 img/s | ~8.6 min | ~1 min | ~8 h |
| previous estimate, before the exclusion (6.2) | ~21 min | 2-3 min | ~20 h |

Early stopping (`patience=10`) can end it sooner. The 1-epoch probe on 10% of train will
replace the assumed GPU speed with a measured one; if the GPU turns out faster than the disk,
the disk row applies.

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

### 6.5 Probe (2026-10-23)

`python scripts/train_detector.py --probe [--batch 16]`: 1 epoch on a random 10% of our train
split (2,838 images, `random.Random(0)`, list saved in the probe folder), then validation on
our full val split. Ultralytics' own `fraction=0.1` was not used: it takes the first 10% of
the sorted list, which is all `frontFar`. Mosaic was kept on (`close_mosaic=0`); with
`epochs=1` the default would switch it off from the start, unlike the first 40 epochs of the
real run. Per batch, the script times the wait for data and the GPU work separately
(with `torch.cuda.synchronize`), and stops on any non-finite loss. It also stops if
Ultralytics halves the batch after a CUDA out-of-memory error. Results:
`outputs/perception/detector_probe_b8.json`, `detector_probe_b16.json` (commit `d32f1e6`,
clean tree); run folders on D under `runs/detector/`.

| | batch 8 | batch 16 |
|---|---:|---:|
| training speed, steady state (img/s) | **31.7** | 20.9 |
| GPU work only (img/s) | 31.9 | 21.0 |
| share of time waiting for data | 0.5% | 0.1% |
| peak VRAM, PyTorch allocated / reserved (MiB) | 1,781 / 1,972 | 3,518 / **4,928** |
| peak memory used, nvidia-smi (MiB) | 2,313 | 3,927 |
| non-finite losses | 0 | 0 |
| validation + checkpoint save (s) | 87 | 112 |

What this shows:

- **The GPU is now the limit, not the disk.** The loader kept up (0.5% waiting), and GPU
  utilisation was 85-92% during training. FP32 yolov8n trains at **~32 img/s** on the GTX
  1650, slower than the 45 img/s assumed in 6.3.1.
- **AMP off is stable:** no NaN or Inf in any batch at either size.
- **Batch 16 is rejected.** The rule, set before running it: use 16 only if it is at least
  10% faster, keeps peak VRAM under ~3.6 GB and keeps the loss finite. It was 34% *slower*,
  and PyTorch reserved 4.9 GB, more than the card has. On Windows the driver then spills
  into shared system memory over PCIe, which is the likely cause of the slowdown. The full
  run therefore keeps the pre-registered **batch 8**.
- **The batch size does not change the optimisation much either way.** Ultralytics
  accumulates gradients up to its nominal batch `nbs=64` (8 batches of 8, or 4 of 16) and
  scales weight decay to match, so each optimiser step sees 64 images. With
  `optimizer=auto` it picks the optimiser from the number of steps,
  `ceil(28,384 / 64) × 50 = 22,200 > 10,000`, which gives MuSGD with lr 0.01 for both batch
  sizes. (The 1-epoch probes have only 444 steps and so used AdamW; the optimiser step runs
  once per 64 images, so this hardly affects the speed measured.)

**Estimate for the full run** (extrapolated from the batch 8 probe, not measured): 28,384 /
31.7 img/s = 14.9 min training + 1.5 min validation per epoch, **~13.6 h for 50 epochs**,
less if early stopping (`patience=10`) ends it sooner.

### 6.6 Full run

`python scripts/train_detector.py --full`, detached, logging to
`/mnt/d/trafficsense/runs/logs/full.log`. The run folder is
`/mnt/d/trafficsense/runs/detector/yolov8n_idd/`. Running the same command again resumes
from `weights/last.pt` after an interruption, or does nothing if the run has finished. Each
start or resume is logged with its git commit in `segments.jsonl`.

It ran in one go (no resume) from commit `7636966` (clean tree), 2026-10-23 11:28 to 00:42:
all 50 epochs, at 29.5-31.6 img/s per epoch with no non-finite loss and batch 8 throughout.
Early stopping did not trigger: val mAP50-95 was still rising by about 0.0001 per epoch at
the end, so the model is close to converged at this size and resolution. Weights are not in
git; their paths and sha256 are in `outputs/perception/detector_train.json` and in the table
of section 8.1.

Bookkeeping fix: after the last epoch Ultralytics validates `best.pt` once more and fires the
end-of-epoch callback again. The first version of our monitor logged that as an "epoch 51"
carrying epoch 50's timings. `train_log.jsonl` keeps that record as written;
`--summarize` rebuilt the summary using Ultralytics' `results.csv` (50 rows) as the epoch
count, and the monitor now logs this call as `final_eval` (commit `cf0639f`).

## 7. Measuring the detector's errors for the camera-error experiment (plan)

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
   - miss rate_c = misses_c / GT_c. (Clarified when implementing: a box matched by a
     detection of another class is a confusion, not a miss, so 1 − recall = miss rate +
     confusion rate. The error model below needs exactly this split.)
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

## 8. Detector results

`python scripts/eval_detector.py --stage val`, then `--stage test`; tables generated by
`python scripts/make_perception_results.py` (check: `--check`). Each stage ran Ultralytics'
validator once with `best.pt` (conf 0.001, NMS IoU 0.7, imgsz 640) and saved every
detection to `runs/detector/yolov8n_idd/eval/` on D; mAP and our error statistics come from
that same pass. The threshold was chosen on our val split and committed (`876076d`)
before the test split was evaluated. Files: `outputs/perception/detector_train.json`,
`detector_val.json`, `detector_test.json`, `error_model.json`.

### 8.1 Training

<!-- BEGIN:detector_train -->
|  | value |
|---|---:|
| epochs run (of 50) | 50 |
| stopped early | no |
| best epoch (our val fitness) | 49 |
| training time | 13.3 h |
| val mAP50 / mAP50-95 at the best epoch | 0.602 / 0.403 |
| best.pt | `/mnt/d/trafficsense/runs/detector/yolov8n_idd/weights/best.pt` |
| best.pt sha256 | `af7f77cc14d5fec51ac54cdb9d17bdb9108f75eed3eab37e223462dd8e3a683d` |
| pretrained yolov8n.pt sha256 | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
<!-- END:detector_train -->

### 8.2 Operating point (our val split)

<!-- BEGIN:detector_threshold -->
|  | value |
|---|---:|
| confidence threshold (chosen on our val split) | 0.3 |
| mean F1 over 7 classes at that threshold (val) | 0.620 |
| val mAP50 / mAP50-95 (Ultralytics, best.pt) | 0.602 / 0.403 |
<!-- END:detector_threshold -->

The mean-F1 curve is flat between 0.28 and 0.32, so the exact choice matters little.

### 8.3 Test split (official IDD val), per class

mAP from Ultralytics; precision, recall, miss rate and false detections from our matching at
the operating point, with 95% intervals from 1,000 bootstrap resamples of whole sequences.

<!-- BEGIN:detector_test_classes -->
Test split: 10,225 images, 119 sequences; operating point conf ≥ 0.3, NMS IoU 0.7, match IoU 0.5.

| class | GT boxes | mAP50 | mAP50-95 | precision | recall | miss rate | false det. / image |
|---|---:|---:|---:|---:|---:|---:|---:|
| car | 24843 | 0.637 | 0.442 | 83.9% (82.3%–85.4%) | 54.9% (50.7%–58.9%) | 43.2% (38.8%–47.3%) | 0.222 (0.156–0.305) |
| motorcycle | 25489 | 0.630 | 0.373 | 81.9% (81.0%–82.9%) | 56.2% (53.3%–60.3%) | 43.4% (39.2%–46.3%) | 0.271 (0.208–0.340) |
| autorickshaw | 7782 | 0.652 | 0.461 | 82.0% (79.8%–83.6%) | 56.0% (51.1%–60.1%) | 40.2% (36.6%–44.2%) | 0.070 (0.043–0.101) |
| bus | 4915 | 0.664 | 0.502 | 82.3% (76.8%–86.4%) | 56.9% (47.0%–65.9%) | 36.8% (29.2%–44.2%) | 0.039 (0.025–0.056) |
| truck | 7077 | 0.576 | 0.412 | 72.9% (69.0%–76.4%) | 48.3% (42.6%–54.7%) | 46.3% (39.9%–52.2%) | 0.079 (0.059–0.098) |
| bicycle | 569 | 0.339 | 0.193 | 61.0% (52.1%–68.6%) | 24.8% (19.8%–31.1%) | 55.4% (47.2%–61.7%) | 0.006 (0.004–0.008) |
| person | 18078 | 0.444 | 0.241 | 79.1% (77.5%–80.5%) | 35.5% (30.9%–40.9%) | 63.6% (58.2%–68.2%) | 0.149 (0.116–0.181) |
| **all** | 88753 | **0.563** | **0.375** |  |  |  |  |
<!-- END:detector_test_classes -->

### 8.4 Miss rate by object size (box area in the 640-wide image)

<!-- BEGIN:detector_test_sizes -->
| class | small miss rate (GT) | medium miss rate (GT) | large miss rate (GT) |
|---|---:|---:|---:|
| car | 65.4% (15,489) | 9.1% (6,065) | 1.3% (3,289) |
| motorcycle | 59.0% (17,565) | 10.1% (6,250) | 3.8% (1,674) |
| autorickshaw | 63.6% (4,646) | 7.8% (2,106) | 1.1% (1,030) |
| bus | 70.8% (2,199) | 19.2% (1,141) | 2.1% (1,575) |
| truck | 73.0% (3,712) | 22.4% (1,820) | 10.2% (1,545) |
| bicycle | 71.9% (334) | 33.8% (198) | 21.6% (37) |
| person | 75.7% (14,180) | 20.7% (3,288) | 12.0% (610) |
<!-- END:detector_test_sizes -->

### 8.5 Confusion matrix (counts at the operating point)

Rows: true class; columns: predicted class for matched boxes, then unmatched ground truth
(missed). Last row: detections matched to nothing.

<!-- BEGIN:detector_test_confusion -->
| true ↓ / predicted → | car | motorcycle | autorickshaw | bus | truck | bicycle | person | missed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| car | 13,629 | 150 | 83 | 74 | 86 | 0 | 89 | 10,732 |
| motorcycle | 32 | 14,332 | 5 | 0 | 4 | 20 | 46 | 11,050 |
| autorickshaw | 91 | 14 | 4,361 | 9 | 175 | 0 | 1 | 3,131 |
| bus | 84 | 2 | 13 | 2,798 | 204 | 6 | 0 | 1,808 |
| truck | 123 | 4 | 137 | 116 | 3,421 | 0 | 1 | 3,275 |
| bicycle | 0 | 75 | 0 | 0 | 0 | 141 | 38 | 315 |
| person | 6 | 155 | 6 | 0 | 0 | 2 | 6,414 | 11,495 |
| false detection | 2,273 | 2,768 | 713 | 403 | 806 | 62 | 1,521 |  |
<!-- END:detector_test_confusion -->

### 8.6 Count error per image and miss rate by camera group

<!-- BEGIN:detector_test_counts -->
| class | mean abs. count error / image | mean signed (pred − true) |
|---|---:|---:|
| car | 1.002 | -0.842 |
| motorcycle | 0.952 | -0.781 |
| autorickshaw | 0.324 | -0.241 |
| bus | 0.222 | -0.148 |
| truck | 0.364 | -0.233 |
| bicycle | 0.047 | -0.033 |
| person | 1.085 | -0.975 |
<!-- END:detector_test_counts -->

<!-- BEGIN:detector_test_cameras -->
| camera group | images | GT boxes | small share | median box area (px) | car miss | motorcycle miss | autorickshaw miss | bus miss | truck miss | bicycle miss | person miss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| frontFar | 1,065 | 1,644 | 68% | 434 | 31% | 36% | 19% | 29% | 18% | 78% | 51% |
| frontNear | 1,605 | 7,032 | 56% | 674 | 27% | 34% | 39% | 14% | 18% | 39% | 50% |
| highquality_16k | 3,633 | 64,381 | 74% | 259 | 49% | 49% | 44% | 47% | 54% | 60% | 72% |
| rearNear | 421 | 1,943 | 39% | 2,112 | 24% | 29% | 20% | 11% | 32% | 47% | 44% |
| sideLeft | 1,548 | 5,825 | 39% | 1,904 | 30% | 25% | 24% | 25% | 45% | 58% | 46% |
| sideRight | 1,953 | 7,928 | 33% | 2,751 | 20% | 27% | 19% | 19% | 25% | 54% | 46% |
<!-- END:detector_test_cameras -->

### 8.7 Camera error model

`outputs/perception/error_model.json`: per class `p_detect` = 1 − miss rate (overall and by
size), the label probabilities given detection (the rows of 8.5, normalised), and the
false detections per image as a Poisson mean.

<!-- BEGIN:detector_error_model -->
| class | p_detect | false det. / image (Poisson mean) |
|---|---:|---:|
| car | 0.568 | 0.222 |
| motorcycle | 0.567 | 0.271 |
| autorickshaw | 0.598 | 0.070 |
| bus | 0.632 | 0.039 |
| truck | 0.537 | 0.079 |
| bicycle | 0.446 | 0.006 |
| person | 0.364 | 0.149 |
<!-- END:detector_error_model -->

### 8.8 What the numbers show

- **Most misses are small objects.** Small boxes (under 32×32 px at 640, i.e. under about
  96×96 px in a 1920-wide original) are the majority of the ground truth for every class
  except bus (45%), and the detector misses 59-76% of them, against 1-22% of large boxes
  (8.4). This is the cost of training and running at 640 named in section 4. For the
  simulator it means `p_detect` depends strongly on how far the camera sees; the overall
  rate is a mixture dominated by distant objects.
- **The detector undercounts.** The signed count error is negative for every class (8.6):
  it misses more than it invents. False detections are rare per image compared with misses.
- **Confusions are few and plausible:** bicycle is often labelled motorcycle, and bus,
  truck and autorickshaw are confused with each other and with car (8.5). bicycle is also
  the weakest class overall, as expected from its 2,240 training boxes (section 5).
- **person has the highest miss rate.** Pedestrians are mostly small; part of the gap may
  also come from dropping `rider` (section 2): riders look like people but are unlabelled, so
  the model is taught not to fire on person-shaped regions on two-wheelers.
- **Test is a little lower than val** (mAP50-95 0.375 vs 0.403). The test split is a
  different set of drives (official val), while our val split comes from the same
  collection as training; some drop is expected.
- **One camera group dominates the test numbers.** `highquality_16k` is 36% of the test
  images but 73% of the boxes, and its boxes are the smallest (median area ~260 px², about
  16×16 px at 640; 74% small). It also has the highest miss rates (8.6). The side and rear
  cameras see closer, larger objects (median 1,900-2,750 px²) and are missed far less. The
  overall per-class rates therefore mostly describe crowded scenes with distant objects;
  the size breakdown (8.4) is the better basis for a camera at a known distance.

**Caveat:** IDD is filmed from a moving vehicle, not from a camera on a pole at an
intersection. Viewpoint, distance and occlusion differ, so these rates are a measured proxy
for an intersection camera, not its true error.

