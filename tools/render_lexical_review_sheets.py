#!/usr/bin/env python3
"""Render compact source-page sheets for unresolved numbered headword/reading review."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def row_spans(row: dict) -> list[dict]:
    spans = row.get("source_spans") or []
    if spans:
        return spans
    return [{
        "pdf_page": row["pdf_page"],
        "source_side": row.get("source_side", ""),
        "bbox": row["source_bbox"],
    }]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--input", type=Path, default=Path("data/numbered-reconciled.json"))
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/n1-lexical-sheets"))
    parser.add_argument("--per-sheet", type=int, default=8)
    parser.add_argument("--field", default="word_reading")
    parser.add_argument("--method")
    parser.add_argument("--dpi", type=int, default=240)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = [row for row in json.loads(args.input.read_text(encoding="utf-8")) if args.field in row["requires_visual_review"]]
    if args.method:
        rows = [row for row in rows if row["verification_fields"][args.field]["method"] == args.method]
    with tempfile.TemporaryDirectory(prefix="n1-lexical-pages-") as temp_dir:
        temp = Path(temp_dir)
        rendered: OrderedDict[int, Image.Image] = OrderedDict()
        crops = []
        scale = args.dpi / 120
        font = load_font(22)
        for row in rows:
            parts = []
            for span in row_spans(row):
                page = int(span["pdf_page"])
                if page not in rendered:
                    target = temp / f"page-{page:04d}"
                    subprocess.run(
                        ["pdftoppm", "-f", str(page), "-l", str(page), "-jpeg", "-r", str(args.dpi), "-singlefile", str(args.pdf), str(target)],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    rendered[page] = Image.open(target.with_suffix(".jpg")).convert("RGB")
                    while len(rendered) > 2:
                        _, old_image = rendered.popitem(last=False)
                        old_image.close()
                else:
                    rendered.move_to_end(page)
                x, y, width, height = [float(value) for value in span["bbox"]]
                source = rendered[page]
                box = (
                    max(0, int((x - 8) * scale)),
                    max(0, int((y - 5) * scale)),
                    min(source.width, int((x + width + 8) * scale)),
                    min(source.height, int((y + height + 5) * scale)),
                )
                parts.append(source.crop(box))
            crop_width = max(part.width for part in parts)
            crop_height = sum(part.height for part in parts) + 4 * (len(parts) - 1)
            crop = Image.new("RGB", (crop_width, crop_height), "white")
            part_y = 0
            for part in parts:
                crop.paste(part, (0, part_y))
                part_y += part.height + 4
            reasons = row["verification_fields"][args.field].get("evidence", {}).get("review_reasons", [])
            selected = (
                f"{row.get('word', '')} | {row.get('reading', '')}"
                if args.field == "word_reading"
                else row.get(args.field, "")
            )
            label = f"ID {row['id_number']} | PDF {row['pdf_page']} | {args.field} | {','.join(reasons)}\nOCR: {selected}"
            label_height = 72
            labeled = Image.new("RGB", (max(900, crop.width), crop.height + label_height), "white")
            labeled.paste(crop, (0, label_height))
            ImageDraw.Draw(labeled).multiline_text((8, 6), label, fill="black", font=font, spacing=2)
            crops.append(labeled)
        for start in range(0, len(crops), args.per_sheet):
            batch = crops[start : start + args.per_sheet]
            width = max(image.width for image in batch)
            height = sum(image.height for image in batch) + 8 * (len(batch) - 1)
            sheet = Image.new("RGB", (width, height), "#dddddd")
            y = 0
            for image in batch:
                sheet.paste(image, (0, y))
                y += image.height + 8
            sheet.save(args.output / f"sheet-{start // args.per_sheet + 1:02d}.png")
    print(f"PASS: rendered {len(rows)} lexical rows into {(len(rows) + args.per_sheet - 1) // args.per_sheet} sheets")


if __name__ == "__main__":
    main()
