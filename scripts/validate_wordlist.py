#!/usr/bin/env python3
"""Validate the complete N3 wordlist and its four processing batches."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "n3"
WORDLIST = DATA_DIR / "wordlist.json"
BATCH_DIR = DATA_DIR / "batches"
EXPECTED_TOTAL = 3256
REQUIRED_FIELDS = (
    "id",
    "unit",
    "word",
    "reading",
    "part_of_speech",
    "meaning_zh",
    "sentence_ja",
    "sentence_zh_reviewed",
    "example_source",
    "review_status",
    "lexical_review_status",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    rows = load_json(WORDLIST)
    expected_ids = [f"n3_{number:04d}" for number in range(1, EXPECTED_TOTAL + 1)]

    assert len(rows) == EXPECTED_TOTAL, f"expected {EXPECTED_TOTAL} rows, got {len(rows)}"
    assert [row["id"] for row in rows] == expected_ids, "IDs are missing, duplicated, or out of order"

    for field in REQUIRED_FIELDS:
        empty = [row["id"] for row in rows if not str(row.get(field, "")).strip()]
        assert not empty, f"empty {field}: {empty[:10]}"

    placeholders = [
        row["id"] for row in rows
        if "という言葉を覚えます" in str(row["sentence_ja"])
    ]
    assert not placeholders, f"placeholder examples remain: {placeholders[:10]}"

    batch_paths = sorted(BATCH_DIR.glob("batch_*.json"))
    assert len(batch_paths) == 4, f"expected four batches, got {len(batch_paths)}"
    merged = [row for path in batch_paths for row in load_json(path)]
    assert [row["id"] for row in merged] == expected_ids, "batches do not exactly reproduce the wordlist"

    print(f"PASS: {len(rows)} continuous rows ({rows[0]['id']}–{rows[-1]['id']})")
    print("Example sources:", dict(Counter(row["example_source"] for row in rows)))
    print("Example review:", dict(Counter(row["review_status"] for row in rows)))
    print("Lexical review:", dict(Counter(row["lexical_review_status"] for row in rows)))
    for path in batch_paths:
        batch = load_json(path)
        print(f"{path.name}: {len(batch)} rows ({batch[0]['id']}–{batch[-1]['id']})")


if __name__ == "__main__":
    main()
