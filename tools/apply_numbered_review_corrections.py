#!/usr/bin/env python3
"""Replay every visually confirmed numbered correction into manual overrides."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overrides", type=Path, default=Path("data/manual-review-overrides.json"))
    parser.add_argument("--corrections", type=Path, default=Path("data/numbered-review-corrections.json"))
    args = parser.parse_args()

    merged = {
        int(row["id_number"]): dict(row)
        for row in json.loads(args.overrides.read_text(encoding="utf-8"))
    }
    corrections = json.loads(args.corrections.read_text(encoding="utf-8"))
    seen: set[int] = set()
    for correction in corrections:
        card_id = int(correction["id_number"])
        if card_id in seen:
            raise SystemExit(f"duplicate correction ID: {card_id}")
        seen.add(card_id)
        override = merged.setdefault(card_id, {"id_number": card_id})
        override["verification_method"] = "visual_page_review"
        override.update({key: value for key, value in correction.items() if key != "id_number"})

    args.overrides.write_text(
        json.dumps([merged[key] for key in sorted(merged)], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"PASS: applied {len(corrections)} unique visual corrections")


if __name__ == "__main__":
    main()
