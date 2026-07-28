#!/usr/bin/env python3
"""Validate the complete clean-PDF N3 wordlist and reviewed corrections."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "n3"
WORDLIST = DATA_DIR / "wordlist.json"
ERRATA = ROOT / "review" / "n3_translation_corrections.json"
EXPECTED_TOTAL = 3400
EXPECTED_EXAMPLES = 3254
EXPECTED_ERRATA = 47
EXPECTED_UNIT_COUNTS = {
    1: 106, 2: 119, 3: 104, 4: 91, 5: 143, 6: 144, 7: 105, 8: 119,
    9: 86, 10: 110, 11: 84, 12: 97, 13: 95, 14: 92, 15: 103, 16: 101,
    17: 96, 18: 118, 19: 74, 20: 126, 21: 95, 22: 107, 23: 105,
    24: 106, 25: 83, 26: 106, 27: 96, 28: 112, 29: 106, 30: 130,
    31: 95, 32: 146,
}
REQUIRED_FIELDS = (
    "id",
    "unit",
    "word",
    "reading",
    "part_of_speech",
    "meaning_zh",
    "meaning_zh_original",
    "meaning_zh_reviewed",
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
        empty = [row["id"] for row in rows if not str(row.get(field, "")).strip()]
        assert not empty, f"empty {field}: {empty[:10]}"

    examples = [row for row in rows if row["has_original_sentence"]]
    supplements = [row for row in rows if not row["has_original_sentence"]]
    assert len(examples) == EXPECTED_EXAMPLES, len(examples)
    assert len(supplements) == EXPECTED_TOTAL - EXPECTED_EXAMPLES, len(supplements)
    assert all(int(row["unit"]) == 32 for row in supplements), "no-example rows must be Unit 32"
    for row in examples:
        for field in ("sentence_ja", "sentence_zh_original", "sentence_zh_reviewed"):
            assert str(row.get(field, "")).strip(), f"{row['id']} has empty {field}"
    contamination = [
        row["id"] for row in rows
        if "习题：" in str(row.get("sentence_ja", ""))
        or "解析：" in str(row.get("sentence_ja", ""))
        or "习题：" in str(row.get("sentence_zh_reviewed", ""))
    ]
    assert not contamination, f"exercise commentary remains: {contamination[:10]}"

    unit_counts = Counter(int(row["unit"]) for row in rows)
    assert dict(unit_counts) == EXPECTED_UNIT_COUNTS, dict(unit_counts)

    errata = load_json(ERRATA)
    assert len(errata) == EXPECTED_ERRATA, len(errata)
    assert len({row["id"] for row in errata}) == EXPECTED_ERRATA, "duplicate errata ids"
    corrected_ids = {row["id"] for row in rows if row["translation_status"] != "original_book" and row["translation_status"] != "no_example_in_source"}
    assert corrected_ids == {row["id"] for row in errata}, "wordlist corrections differ from errata"

    print(f"PASS: {len(rows)} continuous rows ({rows[0]['id']}–{rows[-1]['id']})")
    print(f"Original examples: {len(examples)}; Unit 32 supplements: {len(supplements)}")
    print("Translation status:", dict(Counter(row["translation_status"] for row in rows)))
    print("Unit counts:", dict(unit_counts))


if __name__ == "__main__":
    main()
