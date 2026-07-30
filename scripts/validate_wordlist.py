#!/usr/bin/env python3
"""Validate a configuration-driven Japanese wordbook and its corrections."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from deck_common import load_config, load_wordlist


REQUIRED_REVIEW_FIELDS = (
    "meaning_zh_original",
    "meaning_zh_reviewed",
    "translation_status",
    "translation_note",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("data/deck-config.json"))
    parser.add_argument("--input", type=Path, default=Path("data/wordlist.json"))
    parser.add_argument("--corrections", type=Path, default=Path("data/corrections.json"))
    args = parser.parse_args()

    config = load_config(args.config)
    rows = load_wordlist(args.input, config)
    for field in REQUIRED_REVIEW_FIELDS:
        empty = [row["id"] for row in rows if not str(row.get(field, "")).strip()]
        if empty:
            raise ValueError(f"empty {field}: {empty[:10]}")

    examples = [row for row in rows if row["has_original_sentence"]]
    source_missing = [row for row in rows if not row["has_original_sentence"]]
    expected_examples = config.get("expected_original_examples")
    if expected_examples is not None and len(examples) != int(expected_examples):
        raise ValueError(f"expected {expected_examples} original examples, got {len(examples)}")
    for row in examples:
        if not str(row.get("sentence_ja", "")).strip():
            raise ValueError(f"{row['id']} has an empty Japanese source example")

    contamination = [
        row["id"] for row in rows
        if "习题：" in str(row.get("sentence_ja", ""))
        or "解析：" in str(row.get("sentence_ja", ""))
        or "习题：" in str(row.get("sentence_zh_reviewed", ""))
    ]
    if contamination:
        raise ValueError(f"exercise commentary remains: {contamination[:10]}")

    unit_counts = Counter(str(row.get("unit", "")) for row in rows)
    expected_unit_counts = config.get("expected_unit_counts")
    if expected_unit_counts is not None and dict(unit_counts) != expected_unit_counts:
        raise ValueError(f"unit counts differ: {dict(unit_counts)}")

    corrections = load_json(args.corrections)
    if not isinstance(corrections, list):
        raise ValueError("corrections must be a JSON array")
    correction_ids = [str(row.get("id", "")) for row in corrections]
    if len(set(correction_ids)) != len(correction_ids):
        raise ValueError("duplicate correction ids")
    word_ids = {str(row["id"]) for row in rows}
    unknown = sorted(set(correction_ids) - word_ids)
    if unknown:
        raise ValueError(f"unknown correction ids: {unknown[:10]}")
    unchanged_statuses = {"original_book", "no_example_in_source"}
    corrected_ids = {
        str(row["id"]) for row in rows
        if str(row["translation_status"]) not in unchanged_statuses
    }
    if corrected_ids != set(correction_ids):
        raise ValueError("wordlist corrections differ from structured corrections")

    print(f"PASS: {len(rows)} continuous rows ({rows[0]['id']}–{rows[-1]['id']})")
    print(f"Original examples: {len(examples)}; source-missing examples: {len(source_missing)}")
    print("Translation status:", dict(Counter(str(row["translation_status"]) for row in rows)))
    if expected_unit_counts is not None:
        print("Unit counts:", dict(unit_counts))


if __name__ == "__main__":
    main()
