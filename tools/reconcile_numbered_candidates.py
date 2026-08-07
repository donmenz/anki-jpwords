#!/usr/bin/env python3
"""Select conservative numbered-field candidates and expose every remaining review item."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


FIELDS = ("part_of_speech", "meaning_zh", "sentence_ja", "sentence_zh_original")
META_CONTAMINATION = ("习题：", "解析：", "近)", "近）", "辨析", "可題", "阿題", "対題")
NON_JAPANESE = set("这们为还没从个吗您她它并将该让时后过于说请对发仅较则无别办现绘续简门问间开关")
SOURCE_MARKERS = ("习题", "解析", "必考词", "基础词", "考词", "单元", "単元")
SENTENCE_END_RE = re.compile(r"[。！？!?][」』”’》〉）)\]]?$")
TERMINAL_RE = re.compile(r"[。！？!?][」』”’》〉）)\]]?")


def normalized(value: object, field: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", "", text)
    if field != "sentence_ja":
        text = text.translate(str.maketrans({"，": ",", "；": ";", "：": ":", "、": ",", "·": "・", "。": ".", "？": "?", "！": "!"}))
    return text


def quality_penalty(value: str, field: str) -> int:
    penalty = 0
    if not value:
        return 10000
    penalty += sum(value.count(marker) * 200 for marker in META_CONTAMINATION)
    penalty += len(re.findall(r"[|@<>]", value)) * 30
    if field == "sentence_ja":
        penalty += sum(character in NON_JAPANESE for character in value) * 30
        penalty += len(re.findall(r"[A-Za-z0-9]", value)) * 12
        penalty += len(re.findall(r"[/／]", value)) * 50
        if not re.search(r"[。！？!?]$", value):
            penalty += 12
    else:
        penalty += len(re.findall(r"[ぁ-んァ-ヶ]", value)) * 30
        penalty += len(re.findall(r"[/／]", value)) * 20
        if field == "sentence_zh_original" and not re.search(r"[。！？!?]$", value):
            penalty += 3
    return penalty


def align_to_reference(reference: str, candidate: str) -> tuple[list[str | None], list[str]]:
    """Levenshtein-align one OCR string to a reference and retain insert slots."""
    n, m = len(reference), len(candidate)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        cost[i][0] = i
    for j in range(m + 1):
        cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
                cost[i - 1][j - 1] + (reference[i - 1] != candidate[j - 1]),
            )
    aligned: list[str | None] = [None] * n
    inserts = [""] * (n + 1)
    i, j = n, m
    operations = []
    while i or j:
        if i and j and cost[i][j] == cost[i - 1][j - 1] + (reference[i - 1] != candidate[j - 1]):
            operations.append(("pair", i - 1, candidate[j - 1]))
            i -= 1
            j -= 1
        elif i and cost[i][j] == cost[i - 1][j] + 1:
            operations.append(("delete", i - 1, None))
            i -= 1
        else:
            operations.append(("insert", i, candidate[j - 1]))
            j -= 1
    for operation, position, character in reversed(operations):
        if operation == "pair":
            aligned[position] = character
        elif operation == "insert":
            inserts[position] += str(character)
    return aligned, inserts


def character_consensus(values: dict[str, str], preferred: str) -> tuple[str, int]:
    names = list(values)
    reference_name = min(
        names,
        key=lambda name: sum(1 - SequenceMatcher(None, values[name], values[other]).ratio() for other in names if other != name),
    )
    reference = values[reference_name]
    aligned = {}
    inserted = {}
    for name, value in values.items():
        if name == reference_name:
            aligned[name] = list(reference)
            inserted[name] = [""] * (len(reference) + 1)
        else:
            aligned[name], inserted[name] = align_to_reference(reference, value)
    unresolved = 0
    output = []
    for position in range(len(reference) + 1):
        insertion_values = [inserted[name][position] for name in names]
        insertion_counts = Counter(insertion_values)
        insertion, support = insertion_counts.most_common(1)[0]
        if support < 2:
            unresolved += 1
            insertion = inserted[preferred][position]
        output.append(insertion)
        if position == len(reference):
            continue
        character_values = [aligned[name][position] for name in names]
        character_counts = Counter(character_values)
        character, support = character_counts.most_common(1)[0]
        if support < 2:
            unresolved += 1
            character = aligned[preferred][position]
        if character is not None:
            output.append(character)
    return "".join(output), unresolved


def choose_field(candidates: dict[str, str], field: str) -> tuple[str, str, dict]:
    values = {name: value.strip() for name, value in candidates.items() if value and value.strip()}
    if not values:
        return "", "missing_all_candidates", {"support": [], "penalties": {}}
    normalized_values = {name: normalized(value, field) for name, value in values.items()}
    groups: dict[str, list[str]] = {}
    for name, value in normalized_values.items():
        groups.setdefault(value, []).append(name)
    best_group = max(groups.values(), key=len) if groups else []
    if len(best_group) >= 2:
        preferred = "paddle_full" if "paddle_full" in best_group else "vision_crop" if "vision_crop" in best_group else best_group[0]
        method = "three_ocr_exact" if len(best_group) == 3 else "three_ocr_majority"
        return values[preferred], method, {"support": best_group, "penalties": {name: quality_penalty(value, field) for name, value in values.items()}}

    penalties = {name: quality_penalty(value, field) for name, value in values.items()}
    minimum = min(penalties.values())
    finalists = [name for name, penalty in penalties.items() if penalty == minimum]
    if len(finalists) > 1:
        similarity = {
            name: sum(SequenceMatcher(None, normalized_values[name], normalized_values[other]).ratio() for other in values if other != name)
            for name in finalists
        }
        best_similarity = max(similarity.values())
        finalists = [name for name in finalists if similarity[name] == best_similarity]
    for preferred in ("paddle_full", "vision_crop", "vision_full"):
        if preferred in finalists:
            consensus, unresolved = character_consensus(values, preferred)
            method = "three_ocr_character_consensus" if unresolved == 0 else "provisional_quality_choice"
            return consensus, method, {"support": [preferred], "penalties": penalties, "unresolved_character_slots": unresolved}
    raise AssertionError("no field candidate selected")


def choose_part_of_speech(engines: dict[str, dict]) -> tuple[str, str, dict]:
    """The source labels are Chinese; Paddle preserves 形动/接续/连语 reliably."""
    candidates = {name: str(engine.get("part_of_speech", "")) for name, engine in engines.items()}
    paddle = candidates.get("paddle_full", "").strip()
    if not paddle:
        return "", "missing_all_candidates", {"candidates": candidates}
    value = paddle.translate(str.maketrans({"·": "・", "•": "・", ".": "・", ":": "・", " ": ""}))
    value = value.replace("他ー", "他一").replace("自廿", "自サ").replace("他自サ", "自他サ")
    corroborating = [
        name for name, candidate in candidates.items()
        if name != "paddle_full"
        and normalized(candidate.translate(str.maketrans({"·": "・", "•": "・", ".": "・", ":": "・", " ": ""})), "part_of_speech")
        == normalized(value, "part_of_speech")
    ]
    method = "source_language_ocr_crosscheck" if corroborating else "needs_visual_review"
    return value, method, {
        "candidates": candidates,
        "normalizations": "separator and obvious glyph repair",
        "corroborating_engines": corroborating,
    }


def paddle_review_reasons(value: str, field: str) -> list[str]:
    """Flag only source-language OCR values that need a source-page decision."""
    reasons = []
    if not value.strip():
        return ["empty"]
    if any(marker in value for marker in SOURCE_MARKERS):
        reasons.append("page_metadata")
    if re.search(r"[|@<>]", value):
        reasons.append("ocr_symbols")
    if field == "meaning_zh":
        if re.search(r"[ぁ-んァ-ヶ]", value):
            reasons.append("kana_in_chinese_meaning")
        if re.search(r"[A-Za-z0-9=,;()\\~\[\]]", value):
            reasons.append("ascii_in_chinese_meaning")
    elif field == "sentence_ja":
        if any(character in NON_JAPANESE for character in value):
            reasons.append("simplified_chinese_in_japanese")
        if re.search(r"[\[\]§+=\\:;,]", value):
            reasons.append("ocr_symbols_in_japanese_sentence")
        if re.search(r"[A-Za-z]|\s", value):
            reasons.append("ascii_or_whitespace_in_japanese_sentence")
        if re.search(r"^(?:\[?例\]?|じかん|こ\s*uぎ)", value):
            reasons.append("source_label_or_ruby_in_japanese_sentence")
        if not SENTENCE_END_RE.search(value):
            reasons.append("missing_sentence_ending")
    elif field == "sentence_zh_original":
        if re.search(r"[ぁ-んァ-ヶ]", value):
            reasons.append("kana_in_chinese_translation")
        if re.search(r"[A-Za-z]", value):
            reasons.append("ascii_in_chinese_translation")
        if re.search(r"[\[\]§=+\\]", value):
            reasons.append("ocr_symbols_in_chinese_translation")
        if not SENTENCE_END_RE.search(value):
            reasons.append("missing_sentence_ending")
    return reasons


def trim_trailing_ocr_noise(value: str) -> tuple[str, str]:
    """Remove text after the final printed sentence terminator."""
    text = value.strip()
    endings = list(TERMINAL_RE.finditer(text))
    if endings and endings[-1].end() < len(text):
        return text[: endings[-1].end()], text[endings[-1].end() :]
    return text, ""


def choose_source_language_field(engines: dict[str, dict], field: str) -> tuple[str, str, dict]:
    """Prefer Paddle for Chinese/Japanese body text; Vision is corroboration only."""
    candidates = {name: str(engine.get(field, "")) for name, engine in engines.items()}
    paddle = candidates.get("paddle_full", "").strip()
    original_reasons = paddle_review_reasons(paddle, field)
    removed_suffix = ""
    if field in {"sentence_ja", "sentence_zh_original"} and original_reasons:
        paddle, removed_suffix = trim_trailing_ocr_noise(paddle)
    reasons = paddle_review_reasons(paddle, field)
    corroborating = []
    if original_reasons and not reasons:
        target = normalized(paddle, field)
        for name in ("vision_crop", "vision_full"):
            candidate, _ = trim_trailing_ocr_noise(candidates.get(name, ""))
            if target and normalized(candidate, field) == target:
                corroborating.append(name)
        if not corroborating:
            reasons.append("cleaned_value_not_exactly_corroborated")
    if field in {"sentence_ja", "sentence_zh_original"} and not reasons:
        vision_full, _ = trim_trailing_ocr_noise(candidates.get("vision_full", ""))
        vision_crop, _ = trim_trailing_ocr_noise(candidates.get("vision_crop", ""))
        if field in {"sentence_ja", "sentence_zh_original"}:
            paddle_numbers = re.findall(r"\d+(?:\.\d+)?", paddle)
            vision_numbers = [
                re.findall(r"\d+(?:\.\d+)?", candidate)
                for candidate in (vision_full, vision_crop)
            ]
            if paddle_numbers and paddle_numbers not in vision_numbers:
                reasons.append("numeric_content_not_corroborated")
        if (
            normalized(vision_full, field)
            and normalized(vision_full, field) == normalized(vision_crop, field)
            and normalized(vision_full, field) != normalized(paddle, field)
        ):
            reasons.append("vision_pair_contradicts_paddle")
    if not reasons:
        target = normalized(paddle, field)
        for name in ("vision_crop", "vision_full"):
            candidate = candidates.get(name, "")
            if field in {"sentence_ja", "sentence_zh_original"}:
                candidate, _ = trim_trailing_ocr_noise(candidate)
            if target and normalized(candidate, field) == target and name not in corroborating:
                corroborating.append(name)
        if not corroborating:
            reasons.append("no_independent_exact_corroboration")
    evidence = {
        "candidates": candidates,
        "review_reasons": reasons,
        "original_review_reasons": original_reasons,
        "canonical_engine": "paddle_full",
        "removed_suffix": removed_suffix,
        "corroborating_engines": corroborating,
    }
    if reasons:
        return paddle, "needs_visual_review", evidence
    method = "source_language_ocr_cleanup_crosscheck" if removed_suffix else "source_language_ocr_crosscheck"
    return paddle, method, evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--numbered", type=Path, default=Path("data/numbered-candidates.json"))
    parser.add_argument("--crop", type=Path, default=Path("data/numbered-crop-candidates.json"))
    parser.add_argument("--lexical", type=Path, default=Path("data/numbered-lexical-review.json"))
    parser.add_argument("--overrides", type=Path, default=Path("data/manual-review-overrides.json"))
    parser.add_argument("--output", type=Path, default=Path("data/numbered-reconciled.json"))
    args = parser.parse_args()
    numbered = json.loads(args.numbered.read_text(encoding="utf-8"))
    crops = {int(row["id_number"]): row["crop_vision"] for row in json.loads(args.crop.read_text(encoding="utf-8"))}
    lexical = {int(row["id_number"]): row for row in json.loads(args.lexical.read_text(encoding="utf-8"))}
    overrides = {}
    for override in json.loads(args.overrides.read_text(encoding="utf-8")):
        overrides.setdefault(int(override["id_number"]), {}).update(override)
    output = []
    field_methods = {field: Counter() for field in ("word_reading", *FIELDS)}
    for row in numbered:
        card_id = int(row["id_number"])
        engines = {"vision_full": row["vision"] or {}, "paddle_full": row["paddle"] or {}}
        if card_id in crops:
            engines["vision_crop"] = crops[card_id]
        selected_pair = lexical[card_id].get("selected")
        if card_id in overrides and "word" in overrides[card_id] and "reading" in overrides[card_id]:
            word = overrides[card_id]["word"]
            reading = overrides[card_id]["reading"]
            lexical_method = "visual_page_review"
        elif selected_pair:
            word = selected_pair["word"]
            reading = selected_pair["reading"]
            lexical_method = "observed_pair_jmdict_crosscheck"
        else:
            word = engines["paddle_full"].get("word", "") or engines["vision_full"].get("word", "")
            reading = engines["paddle_full"].get("reading", "") or engines["vision_full"].get("reading", "")
            lexical_method = "needs_visual_review"
        field_methods["word_reading"][lexical_method] += 1
        selected = {"word": word, "reading": reading}
        verification_fields = {"word_reading": {"method": lexical_method, "evidence": {"lexical": lexical[card_id], "override": overrides.get(card_id)}}}
        for field in FIELDS:
            if card_id in overrides and field in overrides[card_id]:
                value = overrides[card_id][field]
                method = "visual_page_review"
                evidence = {"override": overrides[card_id]}
            elif field == "part_of_speech":
                if card_id in overrides and "part_of_speech" in overrides[card_id]:
                    value = overrides[card_id]["part_of_speech"]
                    method = "visual_page_review"
                    evidence = {"override": overrides[card_id]}
                else:
                    value, method, evidence = choose_part_of_speech(engines)
            else:
                value, method, evidence = choose_source_language_field(engines, field)
            selected[field] = value
            verification_fields[field] = {"method": method, "evidence": evidence, "candidates": {name: engine.get(field, "") for name, engine in engines.items()}}
            field_methods[field][method] += 1
        if row.get("master_alignment") == "position_inferred":
            alignment_verified = bool(overrides.get(card_id, {}).get("source_alignment_verified"))
            verification_fields["source_alignment"] = {
                "method": "visual_page_review" if alignment_verified else "needs_visual_review",
                "evidence": {
                    "master_alignment": row["master_alignment"],
                    "override": overrides.get(card_id),
                },
            }
        reference = row["paddle"] or row["vision"]
        output.append({
            "id_number": card_id,
            "section": row["section"],
            "source_number": row["source_number"],
            **(
                {"source_number_printed": overrides[card_id]["source_number_printed"]}
                if card_id in overrides and "source_number_printed" in overrides[card_id]
                else {}
            ),
            **selected,
            "pdf_page": reference["pdf_page"],
            "book_page": reference["book_page"],
            "unit": reference["unit"],
            "source_side": reference["source_side"],
            "source_bbox": reference["source_bbox"],
            "source_spans": reference.get("source_spans", []),
            "verification_fields": verification_fields,
            "requires_visual_review": [field for field, detail in verification_fields.items() if detail["method"] in {"needs_visual_review", "provisional_quality_choice", "missing_all_candidates"}],
        })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({field: dict(counts) for field, counts in field_methods.items()}, ensure_ascii=False, indent=2))
    print("rows requiring visual review:", sum(bool(row["requires_visual_review"]) for row in output))


if __name__ == "__main__":
    main()
