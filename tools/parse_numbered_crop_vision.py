#!/usr/bin/env python3
"""Parse isolated high-resolution Vision OCR crops into a third field candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_numbered_candidates import direct_number, parse_entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/numbered-candidates.json"))
    parser.add_argument("--crops", type=Path, default=Path("data/ocr-numbered-crops-vision"))
    parser.add_argument("--output", type=Path, default=Path("data/numbered-crop-candidates.json"))
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    numbered = json.loads(args.input.read_text(encoding="utf-8"))
    output = []
    for row in numbered:
        card_id = int(row["id_number"])
        path = args.crops / f"entry-{card_id:04d}.json"
        if not path.is_file():
            if args.allow_partial:
                continue
            raise SystemExit(f"missing crop OCR: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        evidence = []
        for part_index, part in enumerate(document["parts"]):
            boxes = [dict(box) for box in part["ocr"].get("ocr_boxes", [])]
            boxes.sort(key=lambda item: (float(item.get("y", 0)), float(item.get("x", 0))))
            for box in boxes:
                box["y"] = float(box.get("y", 0)) + part_index * 2000.0
                box["_source_part"] = part_index
                evidence.append(box)
        reference = row["paddle"] or row["vision"]
        page = int(reference["pdf_page"])
        total = 2809 if row["section"] == "必考词" else 1405
        numeric_rows = [box for box in evidence if direct_number(box, total) is not None]
        source_number = int(row["source_number"])
        exact_rows = [box for box in numeric_rows if direct_number(box, total) == source_number]
        marker = exact_rows[0] if exact_rows else numeric_rows[0] if numeric_rows else {}
        parsed = parse_entry(evidence, marker, page, 0)
        parsed["source_side"] = reference["source_side"]
        parsed["source_bbox"] = reference["source_bbox"]
        parsed["source_spans"] = reference.get("source_spans", [])
        parsed["ocr_engine"] = "Apple Vision isolated crop at 240 dpi"
        output.append({
            "id_number": card_id,
            "section": row["section"],
            "source_number": row["source_number"],
            "crop_vision": parsed,
        })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: parsed {len(output)} isolated crop candidates")


if __name__ == "__main__":
    main()
