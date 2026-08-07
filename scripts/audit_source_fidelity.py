#!/usr/bin/env python3
"""Fail closed unless every extracted row has complete, traceable source evidence."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from deck_common import expected_ids, load_config


REQUIRED = (
    "id", "source_number", "section", "unit", "book_page", "pdf_page",
    "word", "reading", "part_of_speech", "meaning_zh", "sentence_ja",
    "sentence_zh_original", "has_original_sentence", "source_bbox",
    "verification_method", "verification_note",
)
ALLOWED_VERIFICATION = {"multi_ocr_source_crosscheck", "visual_page_review"}
EXPECTED_SECTIONS = {"必考词": 2809, "基础词": 1405, "超纲词": 612}
FORBIDDEN_EXAMPLES = ("という言葉を覚えます", "习题：", "解析：")
UNRESOLVED_FIELD_METHODS = {"needs_visual_review", "missing_all_candidates", "provisional_quality_choice"}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("data/deck-config.json"))
    parser.add_argument("--input", type=Path, default=Path("data/source.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        fail("source must be a JSON array")
    if len(rows) != int(config["expected_total"]):
        fail(f"expected {config['expected_total']} rows, got {len(rows)}")
    ids = [str(row.get("id", "")) for row in rows]
    if ids != expected_ids(config):
        fail("IDs are not continuous and ordered")
    section_counts = Counter(str(row.get("section", "")) for row in rows)
    if dict(section_counts) != EXPECTED_SECTIONS:
        fail(f"section counts differ: {dict(section_counts)}")
    for row in rows:
        missing = [key for key in REQUIRED if key not in row]
        if missing:
            fail(f"{row.get('id', '<unknown>')} missing fields {missing}")
        empty = [
            key for key in REQUIRED
            if key not in {"sentence_ja", "sentence_zh_original", "has_original_sentence"}
            and not str(row.get(key, "")).strip()
        ]
        if empty:
            fail(f"{row['id']} empty fields {empty}")
        if not isinstance(row["has_original_sentence"], bool):
            fail(f"{row['id']} has_original_sentence is not a JSON boolean")
        if row["has_original_sentence"]:
            if not str(row["sentence_ja"]).strip() or not str(row["sentence_zh_original"]).strip():
                fail(f"{row['id']} source example is incomplete")
        elif str(row["sentence_ja"]).strip() or str(row["sentence_zh_original"]).strip():
            fail(f"{row['id']} marks no source example but contains example text")
        if str(row["verification_method"]) not in ALLOWED_VERIFICATION:
            fail(f"{row['id']} unresolved verification method {row['verification_method']!r}")
        field_verification = row.get("field_verification")
        if not isinstance(field_verification, dict) or not field_verification:
            fail(f"{row['id']} lacks field-level verification")
        unresolved = {field: method for field, method in field_verification.items() if method in UNRESOLVED_FIELD_METHODS}
        if unresolved:
            fail(f"{row['id']} has unresolved fields {unresolved}")
        bbox = row["source_bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4 or any(float(value) < 0 for value in bbox):
            fail(f"{row['id']} has an invalid source_bbox")
        combined = " ".join(str(row.get(key, "")) for key in ("sentence_ja", "sentence_zh_original"))
        if any(marker in combined for marker in FORBIDDEN_EXAMPLES):
            fail(f"{row['id']} contains fabricated or contaminated example text")
        if not re.search(r"[ぁ-んァ-ヶ一-龯]", str(row["word"]) + str(row["reading"])):
            fail(f"{row['id']} word/reading lacks Japanese text")
    examples = sum(bool(row["has_original_sentence"]) for row in rows)
    if examples != int(config["expected_original_examples"]):
        fail(f"expected {config['expected_original_examples']} source examples, got {examples}")
    required_numbers = [row["source_number"] for row in rows if row["section"] == "必考词"]
    if required_numbers != list(range(1, 2810)):
        fail("必考词 printed numbers are not exactly 1 through 2809")
    basic_numbers = [row["source_number"] for row in rows if row["section"] == "基础词"]
    expected_basic = list(range(1, 1406))
    if basic_numbers != expected_basic:
        fail("基础词 printed numbers are not exactly 1 through 1405")
    advanced_numbers = [row["source_number"] for row in rows if row["section"] == "超纲词"]
    if advanced_numbers != list(range(1, 613)):
        fail("超纲词 source order is not exactly 1 through 612")
    verification = Counter(str(row["verification_method"]) for row in rows)
    print(f"PASS: {len(rows)} source-faithful rows")
    print("Sections:", dict(section_counts))
    print(f"Source examples: {examples}; source-missing: {len(rows)-examples}")
    print("Verification:", dict(verification))


if __name__ == "__main__":
    main()
