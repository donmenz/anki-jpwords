#!/usr/bin/env python3
"""Reconcile the 612 printed source entries that intentionally have no examples."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from audit_numbered_lexical_fields import clean, valid_pair
from compare_jmdict import load_jmdict
from reconcile_numbered_candidates import choose_part_of_speech, choose_source_language_field


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paddle", type=Path, default=Path("data/advanced-global-candidates.json"))
    parser.add_argument("--vision", type=Path, default=Path("data/advanced-vision-candidates.json"))
    parser.add_argument("--crop", type=Path, default=Path("data/advanced-crop-candidates.json"))
    parser.add_argument("--jmdict", type=Path, default=Path("data/reference/JMdict_e.gz"))
    parser.add_argument("--overrides", type=Path, default=Path("data/manual-review-overrides.json"))
    parser.add_argument("--output", type=Path, default=Path("data/advanced-reconciled.json"))
    args = parser.parse_args()
    by_written, readings = load_jmdict(args.jmdict)
    paddle = json.loads(args.paddle.read_text(encoding="utf-8"))
    vision = {int(row["id_number"]): row["vision_full"] for row in json.loads(args.vision.read_text(encoding="utf-8"))}
    crops = {int(row["id_number"]): row["crop_vision"] for row in json.loads(args.crop.read_text(encoding="utf-8"))}
    overrides = {}
    for override in json.loads(args.overrides.read_text(encoding="utf-8")):
        overrides.setdefault(int(override["id_number"]), {}).update(override)
    output = []
    methods = {field: Counter() for field in ("word_reading", "part_of_speech", "meaning_zh")}
    for row in paddle:
        card_id = int(row["id_number"])
        engines = {
            "paddle_full": {
                "word": row["word"],
                "reading": row["reading"],
                "part_of_speech": row["part_of_speech"],
                "meaning_zh": row["meaning_zh_candidate"],
            },
            "vision_full": vision[card_id],
            "vision_crop": crops[card_id],
        }
        observed = {
            name: {"word": clean(engine.get("word", "")), "reading": clean(engine.get("reading", ""))}
            for name, engine in engines.items()
        }
        words = {value["word"] for value in observed.values() if value["word"]}
        source_readings = {value["reading"] for value in observed.values() if value["reading"]}
        pairs = []
        for word in words:
            for reading in source_readings:
                if valid_pair(word, reading, by_written, readings):
                    support = sum(value["word"] == word for value in observed.values()) + sum(value["reading"] == reading for value in observed.values())
                    pairs.append({"word": word, "reading": reading, "support": support})
        pairs.sort(key=lambda item: (item["support"], len(item["word"])), reverse=True)
        if card_id in overrides and "word" in overrides[card_id] and "reading" in overrides[card_id]:
            word, reading = overrides[card_id]["word"], overrides[card_id]["reading"]
            lexical_method = "visual_page_review"
        elif pairs and pairs[0]["support"] >= 4 and (len(pairs) == 1 or pairs[0]["support"] > pairs[1]["support"]):
            word, reading = pairs[0]["word"], pairs[0]["reading"]
            lexical_method = "observed_pair_jmdict_crosscheck"
        else:
            word, reading = clean(row["word"]), clean(row["reading"])
            lexical_method = "needs_visual_review"
        pos, pos_method, pos_evidence = choose_part_of_speech(engines)
        if card_id in overrides and "part_of_speech" in overrides[card_id]:
            pos = overrides[card_id]["part_of_speech"]
            pos_method = "visual_page_review"
            pos_evidence = {"override": overrides[card_id]}
        if card_id in overrides and "meaning_zh" in overrides[card_id]:
            meaning = overrides[card_id]["meaning_zh"]
            meaning_method = "visual_page_review"
            meaning_evidence = {"override": overrides[card_id]}
        else:
            meaning, meaning_method, meaning_evidence = choose_source_language_field(engines, "meaning_zh")
        methods["word_reading"][lexical_method] += 1
        methods["part_of_speech"][pos_method] += 1
        methods["meaning_zh"][meaning_method] += 1
        verification = {
            "word_reading": {"method": lexical_method, "observed": observed, "valid_pairs": pairs},
            "part_of_speech": {"method": pos_method, "evidence": pos_evidence},
            "meaning_zh": {"method": meaning_method, "evidence": meaning_evidence, "candidates": {name: engine.get("meaning_zh", "") for name, engine in engines.items()}},
        }
        output.append({
            "id_number": card_id,
            "section": "超纲词",
            "source_number": row["source_number"],
            "word": word,
            "reading": reading,
            "part_of_speech": pos,
            "meaning_zh": meaning,
            "sentence_ja": "",
            "sentence_zh_original": "",
            "has_original_sentence": False,
            "pdf_page": row["pdf_page"],
            "book_page": row["book_page"],
            "unit": row["unit"],
            "source_side": row["source_side"],
            "source_bbox": row["source_bbox"],
            "source_spans": row.get("source_spans", []),
            "verification_fields": verification,
            "requires_visual_review": [field for field, detail in verification.items() if detail["method"] in {"needs_visual_review", "provisional_quality_choice", "missing_all_candidates"}],
        })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({field: dict(counts) for field, counts in methods.items()}, ensure_ascii=False, indent=2))
    print("rows requiring visual review:", sum(bool(row["requires_visual_review"]) for row in output))


if __name__ == "__main__":
    main()
