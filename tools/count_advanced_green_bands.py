#!/usr/bin/env python3
"""Count green advanced-word headword baselines independently of OCR text."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from extract_numbered_candidates import POS, side_rows_vision


def bands_for_side(image: np.ndarray, left: int, right: int, footer_start: int) -> list[dict]:
    blue, green, red = cv2.split(image)
    mask = (
        (green.astype(np.int16) > red.astype(np.int16) + 15)
        & (green.astype(np.int16) > blue.astype(np.int16) + 15)
        & (green > 70)
    )
    mask = mask[:, left:right]
    row_counts = mask.sum(axis=1)
    output = []
    start = None
    for y, count in enumerate(row_counts):
        active = int(count) >= 3
        if active and start is None:
            start = y
        if start is not None and (not active or y == len(row_counts) - 1):
            end = y
            block = mask[start:end]
            total = int(block.sum())
            if 40 <= start < footer_start and end - start >= 3 and total > 10:
                ys, xs = np.where(block)
                if len(xs):
                    width = int(xs.max() - xs.min() + 1)
                    fill = total / max(1, (end - start) * width)
                    output.append({
                        "y": start,
                        "bottom": end,
                        "green_pixels": total,
                        "green_width": width,
                        "fill": round(fill, 4),
                    })
            start = None
    merged = []
    for band in output:
        if merged and band["y"] - merged[-1]["bottom"] <= 8:
            previous = merged[-1]
            previous["bottom"] = band["bottom"]
            previous["green_pixels"] += band["green_pixels"]
            previous["green_width"] = max(previous["green_width"], band["green_width"])
            previous["fill"] = round(
                previous["green_pixels"]
                / max(1, (previous["bottom"] - previous["y"]) * previous["green_width"]),
                4,
            )
        else:
            merged.append(band)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--start", type=int, default=296)
    parser.add_argument("--end", type=int, default=306)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--vision", type=Path, default=Path("data/ocr-columns"))
    parser.add_argument("--markers-output", type=Path)
    args = parser.parse_args()
    report = []
    markers = []
    with tempfile.TemporaryDirectory(prefix="n1-advanced-green-") as temp_dir:
        temp = Path(temp_dir)
        for page in range(args.start, args.end + 1):
            target = temp / f"page-{page:04d}"
            subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "120", "-png", "-singlefile", str(args.pdf), str(target)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            image = cv2.imread(str(target.with_suffix(".png")))
            height, width = image.shape[:2]
            footer_start = 430 if page == 306 else 1160
            sides = [
                bands_for_side(image, 50, width // 2 - 20, footer_start),
                bands_for_side(image, width // 2 + 20, width - 50, footer_start),
            ]
            vision_sides = side_rows_vision(args.vision / f"page-{page:04d}.json")
            for side_number, side_bands in enumerate(sides):
                for band in side_bands:
                    nearby = [
                        row for row in vision_sides[side_number]
                        if band["y"] - 8
                        <= float(row.get("y", 0)) + float(row.get("h", 0)) / 2
                        <= band["bottom"] + 8
                    ]
                    text = "".join(str(row.get("text", "")) for row in nearby)
                    is_entry = bool(
                        POS.search(text)
                        or (
                            any(character in text for character in ("（", "("))
                            and any("ぁ" <= character <= "ヿ" for character in text)
                        )
                        or (
                            "【" in text
                            and any("ぁ" <= character <= "ヿ" for character in text)
                        )
                    )
                    band["vision_text"] = text
                    band["classification"] = "entry" if is_entry else "decoration"
                    if is_entry:
                        x_values = [float(row.get("x", 0)) for row in nearby]
                        right_values = [
                            float(row.get("x", 0)) + float(row.get("w", 0)) for row in nearby
                        ]
                        x = min(x_values) if x_values else (50 if side_number == 0 else width // 2 + 20)
                        right = max(right_values) if right_values else (width // 2 - 20 if side_number == 0 else width - 50)
                        markers.append({
                            "section": "超纲词",
                            "unit": "第40单元",
                            "pdf_page": page,
                            "book_page": page - 7,
                            "source_side": "left" if side_number == 0 else "right",
                            "source_bbox": [x, float(band["y"]), max(20.0, right - x), float(band["bottom"] - band["y"])],
                            "green_band": band,
                            "verification_method": "green_headword_band_plus_vision_text",
                        })
            report.append({"pdf_page": page, "width": width, "height": height, "sides": sides})
            print(page, [len(side) for side in sides], sum(map(len, sides)))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("raw green bands:", sum(len(side) for page in report for side in page["sides"]))
    if len(markers) != 612:
        raise SystemExit(f"expected 612 unique green entry markers, got {len(markers)}")
    for number, marker in enumerate(markers, start=1):
        marker["source_number"] = number
        marker["id_number"] = 4214 + number
    if args.markers_output:
        args.markers_output.parent.mkdir(parents=True, exist_ok=True)
        args.markers_output.write_text(json.dumps(markers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: 612 unique green entry markers")


if __name__ == "__main__":
    main()
