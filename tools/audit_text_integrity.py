#!/usr/bin/env python3
"""Flag text-level OCR contamination that structural audits cannot detect."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


TEXT_FIELDS = ("word", "reading", "part_of_speech", "meaning_zh", "sentence_ja", "sentence_zh_original")
BRACKET_PAIRS = (("（", "）"), ("「", "」"), ("『", "』"), ("【", "】"), ("(", ")"), ("[", "]"))
SOURCE_LABELS = re.compile(r"(?:习题|習題|解析|近义|反义|例句)\s*[：:]")
RUBY_FRAGMENT = re.compile(r"(?:[ぁ-ん]{1,3}\s+){2,}[ぁ-ん]{1,3}")
BAD_SYMBOLS = set("�□■◆◇▶▷◀◁▯▮▬│┃┆┇┊┋┌┐└┘├┤┬┴┼")


def issue(bucket: dict[str, list[dict[str, object]]], kind: str, row: dict[str, object], field: str) -> None:
    bucket[kind].append({"id": row["id"], "field": field, "text": row.get(field, "")})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/source.json"))
    parser.add_argument("--output", type=Path, default=Path("data/text-integrity-audit.json"))
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    findings: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        for field in TEXT_FIELDS:
            text = str(row.get(field, ""))
            if any(unicodedata.category(ch) in {"Cc", "Cs", "Co"} for ch in text):
                issue(findings, "control_or_private_unicode", row, field)
            if any(ch in BAD_SYMBOLS for ch in text):
                issue(findings, "ocr_box_or_replacement_symbol", row, field)
            if text != text.strip() or "\n" in text or "\r" in text or "\t" in text or "  " in text:
                issue(findings, "unexpected_whitespace", row, field)
            if SOURCE_LABELS.search(text):
                issue(findings, "source_label_contamination", row, field)
            if RUBY_FRAGMENT.search(text):
                issue(findings, "possible_ruby_contamination", row, field)
            for left, right in BRACKET_PAIRS:
                if text.count(left) != text.count(right):
                    issue(findings, "unbalanced_brackets", row, field)
                    break
        ja = str(row.get("sentence_ja", ""))
        zh = str(row.get("sentence_zh_original", ""))
        if ja and not re.search(r"[。！？!?]$", ja):
            issue(findings, "japanese_sentence_no_terminal", row, "sentence_ja")
        if zh and not re.search(r"(?:[。！？!?][”’\"』」]?|……)$", zh):
            issue(findings, "chinese_sentence_no_terminal", row, "sentence_zh_original")
        if re.search(r"[A-Za-z]", ja) and row.get("verification_method") != "visual_page_review":
            issue(findings, "uncorroborated_ascii_in_japanese", row, "sentence_ja")
        if re.search(r"[ぁ-んァ-ヶ]", zh):
            issue(findings, "kana_in_chinese", row, "sentence_zh_original")
        if re.search(r"\d{5,}", ja + zh):
            issue(findings, "long_digit_run", row, "sentence_ja" if re.search(r"\d{5,}", ja) else "sentence_zh_original")
    report = {kind: values for kind, values in sorted(findings.items())}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({kind: len(values) for kind, values in report.items()}, ensure_ascii=False, indent=2))
    if any(kind in report for kind in ("control_or_private_unicode", "ocr_box_or_replacement_symbol", "source_label_contamination")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
