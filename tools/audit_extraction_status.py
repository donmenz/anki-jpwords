#!/usr/bin/env python3
"""Report field-level extraction coverage without promoting candidates to source."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


FIELDS = ("word", "reading", "part_of_speech", "meaning_zh", "sentence_ja", "sentence_zh_original")


def normalized(value: object, field: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", "", text)
    if field in {"part_of_speech", "meaning_zh", "sentence_zh_original"}:
        text = text.translate(str.maketrans({"，": ",", "；": ";", "：": ":", "。": ".", "、": ",", "·": "・"}))
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--numbered", type=Path, default=Path("data/numbered-candidates.json"))
    parser.add_argument("--advanced", type=Path, default=Path("data/advanced-candidates.json"))
    parser.add_argument("--output", type=Path, default=Path("data/extraction-status.json"))
    args = parser.parse_args()
    numbered = json.loads(args.numbered.read_text(encoding="utf-8"))
    advanced = json.loads(args.advanced.read_text(encoding="utf-8"))
    structural = Counter(str(row["candidate_status"]) for row in numbered)
    field_counts: dict[str, Counter] = {field: Counter() for field in FIELDS}
    unresolved = []
    for row in numbered:
        row_issues = []
        vision, paddle = row.get("vision"), row.get("paddle")
        for field in FIELDS:
            left = normalized(vision.get(field, "") if vision else "", field)
            right = normalized(paddle.get(field, "") if paddle else "", field)
            if left and right and left == right:
                status = "dual_exact"
            elif left and right:
                status = "dual_disagree"
            elif left or right:
                status = "single_value"
            else:
                status = "missing"
            field_counts[field][status] += 1
            if status != "dual_exact":
                row_issues.append({"field": field, "status": status, "vision": left, "paddle": right})
        if row_issues:
            unresolved.append({
                "id_number": row["id_number"],
                "section": row["section"],
                "source_number": row["source_number"],
                "issues": row_issues,
            })
    advanced_pending = sum(str(row.get("verification_method")) == "pending" for row in advanced)
    report = {
        "expected_total": 4826,
        "numbered_expected": 4214,
        "advanced_expected": 612,
        "numbered_structural": dict(structural),
        "field_status": {field: dict(counts) for field, counts in field_counts.items()},
        "numbered_rows_with_unresolved_fields": len(unresolved),
        "advanced_pending_rows": advanced_pending,
        "ready_for_source_json": not unresolved and not advanced_pending and structural.get("missing", 0) == 0,
        "unresolved": unresolved,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "unresolved"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
