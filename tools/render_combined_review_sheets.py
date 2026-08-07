#!/usr/bin/env python3
"""Render every unresolved field beside its exact source-book crop."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import textwrap
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int):
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


def spans(row: dict) -> list[dict]:
    return row.get("source_spans") or [{
        "pdf_page": row["pdf_page"],
        "source_side": row.get("source_side", ""),
        "bbox": row["source_bbox"],
    }]


def wrapped_label(row: dict, width: int = 58) -> str:
    unresolved = row["requires_visual_review"]
    lines = [f"ID {row['id_number']} | PDF {row['pdf_page']} | {','.join(unresolved)}"]
    for field in unresolved:
        if field == "word_reading":
            value = f"{row.get('word', '')} | {row.get('reading', '')}"
        else:
            value = str(row.get(field, ""))
        chunks = textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False) or [""]
        lines.append(f"{field}: {chunks[0]}")
        lines.extend(f"  {chunk}" for chunk in chunks[1:])
    return "\n".join(lines)


def save_sheet(batch: list[Image.Image], path: Path) -> None:
    sheet = Image.new(
        "RGB",
        (max(card.width for card in batch), sum(card.height for card in batch) + 8 * (len(batch) - 1)),
        "#dddddd",
    )
    y = 0
    for card in batch:
        sheet.paste(card, (0, y))
        y += card.height + 8
    sheet.save(path)
    sheet.close()
    for card in batch:
        card.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--input", type=Path, default=Path("data/numbered-reconciled.json"))
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/n1-numbered-review"))
    parser.add_argument("--per-sheet", type=int, default=6)
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument(
        "--ids",
        help="Optional comma-separated id_number filter for focused review sheets",
    )
    args = parser.parse_args()
    selected_ids = (
        {int(value) for value in args.ids.split(",") if value.strip()}
        if args.ids
        else None
    )
    rows = [
        row for row in json.loads(args.input.read_text(encoding="utf-8"))
        if (row.get("requires_visual_review") or selected_ids is not None)
        and (selected_ids is None or int(row["id_number"]) in selected_ids)
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    scale = args.dpi / 120
    font = load_font(21)
    with tempfile.TemporaryDirectory(prefix="n1-combined-review-") as temp_dir:
        temp = Path(temp_dir)
        pages: OrderedDict[int, Image.Image] = OrderedDict()
        batch = []
        sheet_number = 0
        for row in rows:
            parts = []
            for span in spans(row):
                page = int(span["pdf_page"])
                if page not in pages:
                    target = temp / f"page-{page:04d}"
                    subprocess.run(
                        [
                            "pdftoppm", "-f", str(page), "-l", str(page), "-jpeg",
                            "-r", str(args.dpi), "-singlefile", str(args.pdf), str(target),
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    pages[page] = Image.open(target.with_suffix(".jpg")).convert("RGB")
                    while len(pages) > 2:
                        _, old = pages.popitem(last=False)
                        old.close()
                else:
                    pages.move_to_end(page)
                x, y, width, height = [float(value) for value in span["bbox"]]
                source = pages[page]
                box = (
                    max(0, int((x - 10) * scale)),
                    max(0, int((y - 7) * scale)),
                    min(source.width, int((x + width + 10) * scale)),
                    min(source.height, int((y + height + 7) * scale)),
                )
                parts.append(source.crop(box))
            crop_width = max(part.width for part in parts)
            crop_height = sum(part.height for part in parts) + 4 * (len(parts) - 1)
            crop = Image.new("RGB", (crop_width, crop_height), "white")
            y = 0
            for part in parts:
                crop.paste(part, (0, y))
                y += part.height + 4
            label = wrapped_label(row)
            label_box = ImageDraw.Draw(Image.new("RGB", (1, 1))).multiline_textbbox(
                (0, 0), label, font=font, spacing=3
            )
            label_height = label_box[3] - label_box[1] + 16
            card = Image.new("RGB", (max(1100, crop.width), label_height + crop.height), "white")
            ImageDraw.Draw(card).multiline_text((8, 6), label, fill="black", font=font, spacing=3)
            card.paste(crop, (0, label_height))
            crop.close()
            for part in parts:
                part.close()
            batch.append(card)
            if len(batch) == args.per_sheet:
                sheet_number += 1
                save_sheet(batch, args.output / f"sheet-{sheet_number:04d}.png")
                batch = []
        if batch:
            sheet_number += 1
            save_sheet(batch, args.output / f"sheet-{sheet_number:04d}.png")
    print(f"PASS: rendered {len(rows)} rows into {(len(rows) + args.per_sheet - 1) // args.per_sheet} sheets")


if __name__ == "__main__":
    main()
