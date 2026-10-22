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
