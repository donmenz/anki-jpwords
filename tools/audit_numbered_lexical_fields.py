#!/usr/bin/env python3
"""Cross-check observed numbered headword/reading candidates against JMdict."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from compare_jmdict import load_jmdict


KANA = re.compile(r"^[ぁ-んァ-ヶー・]+$")


def clean(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = text.replace("<", "く").replace("|", "").replace("@", "")
    text = re.sub(r"^[.。…・·:：0-9]+", "", text)
    text = re.sub(r"[⓪①②③④⑤⑥⑦⑧⑨⑩0-9◎○Oo]+$", "", text)
    return text.strip(" []［］【】()（）・:：")


def valid_pair(word: str, reading: str, by_written: dict[str, set[str]], readings: set[str]) -> bool:
    if reading in by_written.get(word, set()):
        return True
    if KANA.fullmatch(word) and word == reading and reading in readings:
        return True
    variants = [part for part in re.split(r"[・·]", word) if part]
    return len(variants) > 1 and all(
        reading in by_written.get(part, set()) or (KANA.fullmatch(part) and part == reading)
        for part in variants
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--numbered", type=Path, default=Path("data/numbered-candidates.json"))
    parser.add_argument("--crop", type=Path, default=Path("data/numbered-crop-candidates.json"))
    parser.add_argument("--jmdict", type=Path, default=Path("data/reference/JMdict_e.gz"))
    parser.add_argument("--output", type=Path, default=Path("data/numbered-lexical-review.json"))
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    by_written, readings = load_jmdict(args.jmdict)
    numbered = json.loads(args.numbered.read_text(encoding="utf-8"))
    crops = {int(row["id_number"]): row["crop_vision"] for row in json.loads(args.crop.read_text(encoding="utf-8"))}
    output = []
    statuses = Counter()
    for row in numbered:
        card_id = int(row["id_number"])
        if card_id not in crops and not args.allow_partial:
            raise SystemExit(f"missing crop candidate for {card_id}")
        engines = {
            "vision_full": row["vision"],
            "paddle_full": row["paddle"],
        }
        if card_id in crops:
            engines["vision_crop"] = crops[card_id]
        observed = {
            name: {"word": clean((value or {}).get("word")), "reading": clean((value or {}).get("reading"))}
            for name, value in engines.items()
        }
        words = {value["word"] for value in observed.values() if value["word"]}
        source_readings = {value["reading"] for value in observed.values() if value["reading"]}
        valid_pairs = []
        for word in words:
            for reading in source_readings:
                valid = valid_pair(word, reading, by_written, readings)
                if valid:
                    support = sum(value["word"] == word for value in observed.values()) + sum(value["reading"] == reading for value in observed.values())
                    pair_support = sum(value == {"word": word, "reading": reading} for value in observed.values())
                    valid_pairs.append({"word": word, "reading": reading, "support": support, "pair_support": pair_support})
        valid_pairs.sort(key=lambda pair: (pair["pair_support"], pair["support"], len(pair["word"])), reverse=True)
        if not valid_pairs:
            status = "no_observed_jmdict_pair"
            selected = None
        elif (
            valid_pairs[0]["pair_support"] >= 2 or valid_pairs[0]["support"] >= 4
        ) and (
            len(valid_pairs) == 1
            or (valid_pairs[0]["pair_support"], valid_pairs[0]["support"])
            > (valid_pairs[1]["pair_support"], valid_pairs[1]["support"])
        ):
            status = "unique_best_observed_jmdict_pair"
            selected = valid_pairs[0]
        elif valid_pairs:
            status = "weakly_supported_observed_jmdict_pair"
            selected = None
        else:
            status = "ambiguous_observed_jmdict_pairs"
            selected = None
        statuses[status] += 1
        output.append({
            "id_number": card_id,
            "section": row["section"],
            "source_number": row["source_number"],
            "observed": observed,
            "valid_observed_pairs": valid_pairs,
            "selected": selected,
            "status": status,
        })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(dict(statuses))


if __name__ == "__main__":
    main()
