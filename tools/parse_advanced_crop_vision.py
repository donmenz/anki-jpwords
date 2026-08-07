#!/usr/bin/env python3
"""Parse isolated high-resolution Vision OCR crops for the 612 advanced entries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_numbered_candidates import group_text, groups, parse_header


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/advanced-candidates.json"))
    parser.add_argument("--crops", type=Path, default=Path("data/ocr-advanced-crops-vision"))
    parser.add_argument("--output", type=Path, default=Path("data/advanced-crop-candidates.json"))
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    output = []
    for row in source:
        card_id = int(row["id_number"])
        path = args.crops / f"entry-{card_id:04d}.json"
        if not path.is_file():
            if args.allow_partial:
                continue
            raise SystemExit(f"missing crop OCR: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        boxes = [dict(box) for box in document.get("ocr_boxes", [])]
        text = "".join(group_text(group) for group in groups(boxes, tolerance=10.0))
        parsed = parse_header(text)
        output.append({
            "id_number": card_id,
            "source_number": row["source_number"],
            "pdf_page": row["pdf_page"],
            "source_side": row["source_side"],
            "crop_vision": {
                **parsed,
                "source_bbox": row["source_bbox"],
                "raw_text": text,
                "raw_boxes": boxes,
                "ocr_engine": "Apple Vision isolated crop at 240 dpi",
            },
        })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: parsed {len(output)} advanced crop candidates")


if __name__ == "__main__":
    main()
