#!/usr/bin/env python3
"""Render selected source.json entries for final visual text review."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int):
    for path in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--input", type=Path, default=Path("data/source.json"))
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/n1-source-review"))
    parser.add_argument("--ids", required=True, help="Comma-separated final card numbers")
    parser.add_argument("--field", required=True)
    parser.add_argument("--per-sheet", type=int, default=6)
    parser.add_argument("--dpi", type=int, default=240)
    args = parser.parse_args()
    selected_ids = [int(value) for value in args.ids.split(",")]
    all_rows = json.loads(args.input.read_text(encoding="utf-8"))
    by_id = {int(str(row["id"]).rsplit("_", 1)[1]): row for row in all_rows}
    rows = [by_id[value] for value in selected_ids]
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="n1-source-review-") as temp_dir:
        temp = Path(temp_dir)
        pages: OrderedDict[int, Image.Image] = OrderedDict()
        crops = []
        scale = args.dpi / 120
        font = load_font(22)
        for final_id, row in zip(selected_ids, rows):
            page = int(row["pdf_page"])
            if page not in pages:
                target = temp / f"page-{page:04d}"
                subprocess.run(
                    ["pdftoppm", "-f", str(page), "-l", str(page), "-jpeg", "-r", str(args.dpi), "-singlefile", str(args.pdf), str(target)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                pages[page] = Image.open(target.with_suffix(".jpg")).convert("RGB")
                while len(pages) > 2:
                    _, old = pages.popitem(last=False)
                    old.close()
            source = pages[page]
            x, y, width, height = [float(value) for value in row["source_bbox"]]
            box = (
                max(0, int((x - 12) * scale)), max(0, int((y - 10) * scale)),
                min(source.width, int((x + width + 12) * scale)), min(source.height, int((y + height + 10) * scale)),
            )
            crop = source.crop(box)
            value = str(row.get(args.field, ""))
            label = f"ID {final_id} | PDF {page} | {args.field}\nOCR: {value}"
            labeled = Image.new("RGB", (max(900, crop.width), crop.height + 72), "white")
            labeled.paste(crop, (0, 72))
            ImageDraw.Draw(labeled).multiline_text((8, 6), label, fill="black", font=font, spacing=2)
            crops.append(labeled)
        for start in range(0, len(crops), args.per_sheet):
            batch = crops[start:start + args.per_sheet]
            sheet = Image.new("RGB", (max(image.width for image in batch), sum(image.height for image in batch) + 8 * (len(batch) - 1)), "#dddddd")
            y = 0
            for review in batch:
                sheet.paste(review, (0, y))
                y += review.height + 8
            sheet.save(args.output / f"sheet-{start // args.per_sheet + 1:02d}.png")
    print(f"PASS: rendered {len(rows)} rows")


if __name__ == "__main__":
    main()
