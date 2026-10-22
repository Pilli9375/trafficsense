"""Draw converted YOLO boxes on random IDD images: proof the labels are real and line up.

    python scripts/render_idd_samples.py [--split train] [--n 16] [--seed 0] [--full 3]

Reads the image list and label files under paths.idd_yolo, i.e. the converted labels, not
the original XML. Writes paths.perception_outputs/sample_grid.jpg (n images in a grid) and
--full images at their original resolution (alignment_<k>.jpg) for a close look.
"""
import argparse
import json
import math
import random

from PIL import Image, ImageDraw, ImageFont

from trafficsense.config import load_config, resolve_path
from trafficsense.perception import idd

COLORS = {"car": (0, 170, 255), "motorcycle": (255, 60, 60), "autorickshaw": (255, 210, 0),
          "bus": (0, 210, 90), "truck": (255, 140, 0), "bicycle": (200, 80, 255), "person": (255, 255, 255)}


def draw(image_path: str, scale: float, font) -> tuple[Image.Image, int]:
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    if scale != 1:
        im = im.resize((round(w * scale), round(h * scale)), Image.BILINEAR)
    d = ImageDraw.Draw(im)
    with open(idd.label_path_for(image_path)) as f:
        rows = [line.split() for line in f if line.strip()]
    for c, cx, cy, bw, bh in rows:
        name = idd.CLASSES[int(c)]
        cx, cy, bw, bh = float(cx) * w * scale, float(cy) * h * scale, float(bw) * w * scale, float(bh) * h * scale
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        d.rectangle(box, outline=COLORS[name], width=2)
        left, top, right, bottom = font.getbbox(name)
        y = max(0, box[1] - (bottom - top) - 2)
        d.rectangle((box[0], y, box[0] + right - left + 2, y + bottom - top + 2), fill=COLORS[name])
        d.text((box[0] + 1 - left, y + 1 - top), name, fill=(0, 0, 0), font=font)
    return im, len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--split", default="train", choices=["train", "val", "test"])
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--full", type=int, default=3, help="also save this many full-resolution images")
    args = ap.parse_args()
    cfg = load_config(args.config)
    yolo = resolve_path(cfg, "idd_yolo")
    out = resolve_path(cfg, "perception_outputs")
    out.mkdir(parents=True, exist_ok=True)

    lines = (yolo / f"{args.split}.txt").read_text().splitlines()
    picks = random.Random(args.seed).sample(lines, args.n)
    paths = [str(yolo / p[2:]) if p.startswith("./") else p for p in picks]

    tile_w, cols = 640, 4
    rows = math.ceil(args.n / cols)
    tiles = []
    font = ImageFont.load_default(size=13)
    for p in paths:
        with Image.open(p) as im:
            scale = tile_w / im.size[0]
        tiles.append(draw(p, scale, font)[0])
    tile_h = max(t.size[1] for t in tiles)
    grid = Image.new("RGB", (cols * tile_w, rows * tile_h), (30, 30, 30))
    for k, t in enumerate(tiles):
        grid.paste(t, ((k % cols) * tile_w, (k // cols) * tile_h))
    grid.save(out / "sample_grid.jpg", quality=88)

    big_font = ImageFont.load_default(size=22)
    for k, p in enumerate(paths[:args.full]):
        draw(p, 1.0, big_font)[0].save(out / f"alignment_{k}.jpg", quality=90)
    (out / "sample_grid.json").write_text(json.dumps(
        {"split": args.split, "seed": args.seed, "images": [p[len("./images/"):] for p in picks],
         "alignment_images": [p[len("./images/"):] for p in picks[:args.full]]}, indent=2) + "\n")
    print(f"wrote {out / 'sample_grid.jpg'} and {args.full} alignment images")


if __name__ == "__main__":
    main()
