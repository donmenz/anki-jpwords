#!/usr/bin/env python3
"""Build the immutable, source-faithful N1 dataset from reconciled evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit(f"{path} must contain a JSON array")
    return value


def assert_verification_evidence(row: dict, field: str, detail: dict) -> None:
    method = str(detail.get("method", ""))
    if method in {"source_language_ocr_crosscheck", "source_language_ocr_cleanup_crosscheck"}:
        evidence = detail.get("evidence") or {}
        if not evidence.get("corroborating_engines"):
            raise SystemExit(
                f"row {row['id_number']} field {field} claims an OCR cross-check without independent exact corroboration"
            )
    if method == "observed_pair_jmdict_crosscheck":
        lexical = (detail.get("evidence") or {}).get("lexical") or {}
        selected = lexical.get("selected")
        if selected is None:
            pairs = detail.get("valid_pairs") or []
            selected = pairs[0] if pairs else None
        if not selected or (int(selected.get("pair_support", 0)) < 2 and int(selected.get("support", 0)) < 4):
            raise SystemExit(
                f"row {row['id_number']} field {field} lacks a strongly supported observed JMdict pair"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--numbered", type=Path, default=Path("data/numbered-reconciled.json"))
    parser.add_argument("--advanced", type=Path, default=Path("data/advanced-reconciled.json"))
    parser.add_argument("--config", type=Path, default=Path("data/deck-config.json"))
    parser.add_argument("--output", type=Path, default=Path("data/source.json"))
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    rows = sorted(load(args.numbered) + load(args.advanced), key=lambda row: int(row["id_number"]))
    expected_total = int(config["expected_total"])
    if [int(row["id_number"]) for row in rows] != list(range(1, expected_total + 1)):
        raise SystemExit("reconciled IDs are not continuous")

    output = []
    for row in rows:
        unresolved = list(row.get("requires_visual_review", []))
        if unresolved:
            raise SystemExit(f"row {row['id_number']} still requires review: {unresolved}")
        field_methods = {
            field: str(detail["method"])
            for field, detail in row["verification_fields"].items()
        }
        if any(method in {"needs_visual_review", "missing_all_candidates", "provisional_quality_choice"} for method in field_methods.values()):
            raise SystemExit(f"row {row['id_number']} still has an unresolved field method")
        for field, detail in row["verification_fields"].items():
            assert_verification_evidence(row, field, detail)
        visual_fields = sorted(field for field, method in field_methods.items() if method == "visual_page_review")
        verification_method = "visual_page_review" if visual_fields else "multi_ocr_source_crosscheck"
        has_example = row["section"] != "超纲词"
        sentence_ja = str(row.get("sentence_ja", "")) if has_example else ""
        sentence_zh = str(row.get("sentence_zh_original", "")) if has_example else ""
        output.append({
            "id": f"{config['id_prefix']}_{int(row['id_number']):0{int(config['id_width'])}d}",
            "source_number": int(row["source_number"]),
            "section": str(row["section"]),
            "unit": str(row["unit"]),
            "book_page": int(row["book_page"]),
            "pdf_page": int(row["pdf_page"]),
            "word": str(row["word"]),
            "reading": str(row["reading"]),
            "part_of_speech": str(row["part_of_speech"]),
            "meaning_zh": str(row["meaning_zh"]),
            "sentence_ja": sentence_ja,
            "sentence_zh_original": sentence_zh,
            "has_original_sentence": has_example,
            "source_bbox": row["source_bbox"],
            "source_spans": row.get("source_spans") or [{
                "pdf_page": int(row["pdf_page"]),
                "book_page": int(row["book_page"]),
                "source_side": str(row["source_side"]),
                "bbox": row["source_bbox"],
            }],
            "verification_method": verification_method,
            "verification_note": "; ".join(f"{field}={method}" for field, method in field_methods.items()),
            "field_verification": field_methods,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    visual_rows = sum(row["verification_method"] == "visual_page_review" for row in output)
    print(f"PASS: wrote {len(output)} rows; visual rows: {visual_rows}; crosschecked rows: {len(output) - visual_rows}")


if __name__ == "__main__":
    main()
