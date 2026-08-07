#!/usr/bin/env python3
"""Freeze visually reviewed fields from a fixed numbered reconciliation snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/numbered-reconciled.json"))
    parser.add_argument("--overrides", type=Path, default=Path("data/manual-review-overrides.json"))
    parser.add_argument("--corrections", type=Path, default=Path("data/numbered-review-corrections.json"))
    parser.add_argument("--from-sheet", type=int, required=True)
    parser.add_argument("--to-sheet", type=int, required=True)
    parser.add_argument("--per-sheet", type=int, default=6)
    args = parser.parse_args()

    review_rows = [
        row
        for row in json.loads(args.input.read_text(encoding="utf-8"))
        if row.get("requires_visual_review")
    ]
    start = (args.from_sheet - 1) * args.per_sheet
    end = min(args.to_sheet * args.per_sheet, len(review_rows))
    if start < 0 or start >= len(review_rows) or end <= start:
        raise SystemExit("invalid sheet range")

    merged = {
        int(row["id_number"]): dict(row)
        for row in json.loads(args.overrides.read_text(encoding="utf-8"))
    }
    corrections = {
        int(row["id_number"]): row
        for row in json.loads(args.corrections.read_text(encoding="utf-8"))
    }
    reviewed_ids = []
    for row in review_rows[start:end]:
        card_id = int(row["id_number"])
        override = merged.setdefault(card_id, {"id_number": card_id})
        override["verification_method"] = "visual_page_review"
        for field in row["requires_visual_review"]:
            if field == "word_reading":
                override["word"] = row["word"]
                override["reading"] = row["reading"]
            elif field != "source_alignment":
                override[field] = row[field]
        if card_id in corrections:
            override.update({key: value for key, value in corrections[card_id].items() if key != "id_number"})
        reviewed_ids.append(card_id)

    args.overrides.write_text(
        json.dumps([merged[key] for key in sorted(merged)], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"PASS: sheets {args.from_sheet}-{args.to_sheet}, "
        f"rows {len(reviewed_ids)}, IDs {reviewed_ids[0]}-{reviewed_ids[-1]}"
    )


if __name__ == "__main__":
    main()
