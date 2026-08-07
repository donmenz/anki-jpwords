#!/usr/bin/env python3
"""Index numbered source entries from independent OCR outputs without merging their text."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SECTIONS = (
    ("必考词", 8, 208, 2809, 0),
    ("基础词", 209, 295, 1405, 2809),
)
NUMBER = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def vision_lines(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    midpoint = float(doc["image_width"]) / 2
    sides = ([], [])
    for box in doc.get("ocr_boxes", []):
        side = 0 if float(box.get("x", 0)) + float(box.get("w", 0)) / 2 < midpoint else 1
        sides[side].append(box)
    rows = []
    for side in sides:
        rows.extend(sorted(side, key=lambda item: (float(item.get("y", 0)), float(item.get("x", 0)))))
    return rows


def paddle_lines(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [row for side in doc.get("sides", []) for row in side]


def collect(folder: Path, loader, start: int, end: int, total: int) -> dict[int, dict]:
    entries: dict[int, dict] = {}
    last = 0
    active: int | None = None
    for page in range(start, end + 1):
        path = folder / f"page-{page:04d}.json"
        if not path.is_file():
            continue
        for row in loader(path):
            text = str(row.get("text", "")).strip()
            candidates = [int(value) for value in NUMBER.findall(text)]
            marker = next((value for value in candidates if last < value <= min(total, last + 30)), None)
            if marker is not None:
                last = marker
                active = marker
                entries[marker] = {"pdf_page": page, "evidence_rows": []}
            if active is not None:
                x, y, w, h = (float(row.get(key, 0)) for key in ("x", "y", "w", "h"))
                entries[active]["evidence_rows"].append({"pdf_page": page, "text": text, "bbox": [x, y, w, h]})
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision", type=Path, default=Path("data/ocr-columns"))
    parser.add_argument("--paddle", type=Path, default=Path("data/ocr-paddle-full"))
    parser.add_argument("--output", type=Path, default=Path("data/extraction-index.json"))
    args = parser.parse_args()
    output = []
    for section, start, end, total, offset in SECTIONS:
        vision = collect(args.vision, vision_lines, start, end, total)
        paddle = collect(args.paddle, paddle_lines, start, end, total)
        for source_number in range(1, total + 1):
            output.append({
                "id_number": len(output) + 1,
                "section": section,
                "source_number": source_number,
                "vision": vision.get(source_number),
                "paddle": paddle.get(source_number),
                "index_status": "dual" if source_number in vision and source_number in paddle else "single" if source_number in vision or source_number in paddle else "missing",
            })
        print(section, "vision", len(vision), "paddle", len(paddle), "dual", len(set(vision) & set(paddle)))
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = {status: sum(row["index_status"] == status for row in output) for status in ("dual", "single", "missing")}
    print("Index statuses:", statuses)


if __name__ == "__main__":
    main()
