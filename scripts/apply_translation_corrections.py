#!/usr/bin/env python3
"""Apply reviewed corrections to the clean-PDF N3 wordlist."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_SOURCE = Path("data/n3/wordlist_original.json")
DEFAULT_CORRECTIONS = Path("review/n3_translation_corrections.json")
DEFAULT_OUTPUT = Path("data/n3/wordlist.json")
DEFAULT_WORDLIST_CSV = Path("data/n3/wordlist.csv")
DEFAULT_ERRATA_CSV = Path("review/n3_translation_errata.csv")

WORDLIST_COLUMNS = [
    "id",
    "source_number",
    "level",
    "unit",
    "book_page",
    "pdf_page",
    "word",
    "reading",
    "part_of_speech",
    "meaning_zh_original",
    "meaning_zh_reviewed",
    "sentence_ja_original",
    "sentence_ja",
    "sentence_zh_original",
    "sentence_zh_reviewed",
    "translation_status",
    "correction_category",
    "translation_note",
    "has_original_sentence",
]

ERRATA_COLUMNS = [
    "id",
    "unit",
    "book_page",
    "word",
    "reading",
    "part_of_speech",
    "category",
    "severity",
    "meaning_zh_original",
    "meaning_zh_reviewed",
    "sentence_ja_original",
    "sentence_ja_reviewed",
    "sentence_zh_original",
    "sentence_zh_reviewed",
    "reason",
    "source",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_japanese_spacing(text: str) -> str:
    """Remove extraction-only whitespace from Japanese sentences."""
    return re.sub(r"\s+", "", text or "")


def status_for(category: str) -> str:
    if "提取" in category or "数据" in category:
        return "data_cleaned"
    if "措辞" in category:
        return "wording_refined"
    if "词义" in category:
        return "meaning_corrected"
    return "corrected"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--corrections", type=Path, default=DEFAULT_CORRECTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--wordlist-csv", type=Path, default=DEFAULT_WORDLIST_CSV)
    parser.add_argument("--errata-csv", type=Path, default=DEFAULT_ERRATA_CSV)
    args = parser.parse_args()

    source_rows = read_json(args.source)
    corrections = read_json(args.corrections)
    by_id = {item["id"]: item for item in corrections}

    if len(by_id) != len(corrections):
        raise SystemExit("duplicate correction ids")
    source_ids = {row["id"] for row in source_rows}
    unknown = sorted(set(by_id) - source_ids)
    if unknown:
        raise SystemExit(f"unknown correction ids: {unknown}")

    output_rows: list[dict] = []
    errata_rows: list[dict] = []
    for original in source_rows:
        row = dict(original)
        row["meaning_zh_original"] = original.get("meaning_zh", "")
        row["meaning_zh_reviewed"] = original.get("meaning_zh", "")
        row["sentence_ja_original"] = original.get("sentence_ja", "")
        row["sentence_ja"] = normalize_japanese_spacing(original.get("sentence_ja", ""))
        row["sentence_zh_reviewed"] = original.get("sentence_zh_original", "")
        row["correction_category"] = ""

        correction = by_id.get(row["id"])
        if correction:
            if correction.get("reviewed_meaning_zh"):
                row["meaning_zh_reviewed"] = correction["reviewed_meaning_zh"]
                row["meaning_zh"] = correction["reviewed_meaning_zh"]
            if correction.get("reviewed_sentence_ja"):
                row["sentence_ja"] = normalize_japanese_spacing(
                    correction["reviewed_sentence_ja"]
                )
            if correction.get("reviewed_sentence_zh"):
                row["sentence_zh_reviewed"] = correction["reviewed_sentence_zh"]
            row["translation_status"] = status_for(correction["category"])
            row["correction_category"] = correction["category"]
            row["translation_note"] = correction["reason"]

            errata_rows.append(
                {
                    "id": row["id"],
                    "unit": row["unit"],
                    "book_page": row["book_page"],
                    "word": row["word"],
                    "reading": row["reading"],
                    "part_of_speech": row["part_of_speech"],
                    "category": correction["category"],
                    "severity": correction["severity"],
                    "meaning_zh_original": row["meaning_zh_original"],
                    "meaning_zh_reviewed": row["meaning_zh_reviewed"],
                    "sentence_ja_original": row["sentence_ja_original"],
                    "sentence_ja_reviewed": row["sentence_ja"],
                    "sentence_zh_original": row["sentence_zh_original"],
                    "sentence_zh_reviewed": row["sentence_zh_reviewed"],
                    "reason": correction["reason"],
                    "source": correction["source"],
                }
            )
        elif row.get("has_original_sentence"):
            row["translation_status"] = "original_book"
            row["translation_note"] = "使用原书例句与原书中文译文。"
        else:
            row["translation_status"] = "no_example_in_source"
            row["translation_note"] = "原书补充词表未提供例句。"

        output_rows.append(row)

    if len(output_rows) != 3400:
        raise SystemExit(f"expected 3400 rows, got {len(output_rows)}")
    if [row["id"] for row in output_rows] != [f"n3_{i:04d}" for i in range(1, 3401)]:
        raise SystemExit("ids are not contiguous n3_0001..n3_3400")
    if any("习题" in row["sentence_ja"] or "解析" in row["sentence_ja"] for row in output_rows):
        raise SystemExit("exercise text remains in Japanese examples")
    contaminated_markers = ("习题：", "解析：", "选项1", "选项１")
    if any(
        any(marker in row["sentence_zh_reviewed"] for marker in contaminated_markers)
        for row in output_rows
    ):
        raise SystemExit("exercise commentary remains in reviewed Chinese translations")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(args.wordlist_csv, output_rows, WORDLIST_COLUMNS)
    write_csv(args.errata_csv, errata_rows, ERRATA_COLUMNS)

    print(
        json.dumps(
            {
                "rows": len(output_rows),
                "examples": sum(bool(row["sentence_ja"]) for row in output_rows),
                "errata": len(errata_rows),
                "categories": Counter(row["category"] for row in errata_rows),
                "statuses": Counter(row["translation_status"] for row in output_rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
