#!/usr/bin/env python3
"""Extract a second advanced-word candidate from full-page Vision OCR using Paddle boxes."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from extract_numbered_candidates import clean_reading, group_text, groups, side_rows_vision


POS = re.compile(r"[（(]((?:名|副|形|他|自|連|连|感|叹|接|助|代|ト|文|书|書|面|接头|接尾|前缀|后缀)[^）)]*)[）)]")


def parse(text: str) -> dict[str, str]:
    pos = POS.search(text)
    before = text[: pos.start()].strip() if pos else text
    meaning = text[pos.end() :].strip() if pos else ""
    bracket = re.search(r"[【\[!！]([^】\]]+)[】\]]", before)
    reading_source = before[: bracket.start()] if bracket else before
    reading = clean_reading(reading_source)
    written = bracket.group(1).strip() if bracket else ""
    word = written if written and re.search(r"[ぁ-んァ-ヶ一-龯]", written) else reading
    return {"word": word, "reading": reading, "part_of_speech": pos.group(1) if pos else "", "meaning_zh": meaning}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/advanced-candidates.json"))
    parser.add_argument("--vision", type=Path, default=Path("data/ocr-columns"))
    parser.add_argument("--output", type=Path, default=Path("data/advanced-vision-candidates.json"))
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    cache = {}
    output = []
    for row in source:
        page = int(row["pdf_page"])
        if page not in cache:
            cache[page] = side_rows_vision(args.vision / f"page-{page:04d}.json")
        side_number = 0 if row["source_side"] == "left" else 1
        x, y, width, height = [float(value) for value in row["source_bbox"]]
        selected = []
        for box in cache[page][side_number]:
            center_x = float(box.get("x", 0)) + float(box.get("w", 0)) / 2
            center_y = float(box.get("y", 0)) + float(box.get("h", 0)) / 2
            if x - 12 <= center_x <= x + width + 12 and y - 8 <= center_y <= y + height + 8:
                selected.append(box)
        text = "".join(group_text(group) for group in groups(selected, tolerance=5.0))
        output.append({
            "id_number": row["id_number"],
            "source_number": row["source_number"],
            "pdf_page": page,
            "source_side": row["source_side"],
            "vision_full": {**parse(text), "raw_text": text, "raw_boxes": selected, "source_bbox": row["source_bbox"]},
        })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: parsed {len(output)} full-page Vision advanced candidates")


if __name__ == "__main__":
    main()
