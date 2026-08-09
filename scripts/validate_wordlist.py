#!/usr/bin/env python3
"""Validate the source-faithful 3,400-row N3 wordlist."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "n3"
WORDLIST = DATA_DIR / "wordlist.json"
EXPECTED_TOTAL = 3400
REQUIRED_FIELDS = (
    "id",
    "unit",
    "word",
    "reading",
    "part_of_speech",
    "meaning_zh",
    "translation_status",
    "translation_note",
    "has_original_sentence",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    rows = load_json(WORDLIST)
    expected_ids = [f"n3_{number:04d}" for number in range(1, EXPECTED_TOTAL + 1)]

    assert len(rows) == EXPECTED_TOTAL, f"expected {EXPECTED_TOTAL} rows, got {len(rows)}"
    assert [row["id"] for row in rows] == expected_ids, "IDs are missing, duplicated, or out of order"

    for field in REQUIRED_FIELDS:
        empty = [
            row["id"] for row in rows
            if field != "has_original_sentence" and not str(row.get(field, "")).strip()
        ]
        assert not empty, f"empty {field}: {empty[:10]}"

    invalid_flags = [row["id"] for row in rows if not isinstance(row.get("has_original_sentence"), bool)]
    assert not invalid_flags, f"invalid has_original_sentence: {invalid_flags[:10]}"
    missing_original = [
        row["id"] for row in rows
        if row["has_original_sentence"] and not str(row.get("sentence_ja", "")).strip()
    ]
    assert not missing_original, f"source examples missing Japanese text: {missing_original[:10]}"
    fabricated = [
        row["id"] for row in rows
        if not row["has_original_sentence"] and str(row.get("sentence_ja", "")).strip()
    ]
    assert not fabricated, f"source-missing rows contain generated text: {fabricated[:10]}"

    placeholders = [
        row["id"] for row in rows
        if "という言葉を覚えます" in str(row["sentence_ja"])
    ]
    assert not placeholders, f"placeholder examples remain: {placeholders[:10]}"

    print(f"PASS: {len(rows)} continuous rows ({rows[0]['id']}–{rows[-1]['id']})")
    print("Units:", dict(Counter(str(row["unit"]) for row in rows)))
    print("Translation status:", dict(Counter(row["translation_status"] for row in rows)))
    print("Original examples:", sum(bool(row["has_original_sentence"]) for row in rows))
    print("Source-missing examples:", sum(not bool(row["has_original_sentence"]) for row in rows))


if __name__ == "__main__":
    main()
