#!/usr/bin/env python3
"""Extract the 612 printed unnumbered N1 Unit 40 headings as review candidates."""
from __future__ import annotations

import json
import re
from pathlib import Path


INPUT = Path("data/ocr-paddle-full")
OUTPUT = Path("data/advanced-candidates.json")
POS_PATTERN = r"(?:名|副|形|他|自|連|连|感|叹|接|助|代|ト|文|书|書|面|接头|接尾|前缀|后缀)"
HEADER = re.compile(rf"[（(]({POS_PATTERN}[^）)]*)[）)]")
PITCH = re.compile(r"[⓪①②③④⑤⑥⑦⑧⑨⑩0-9・·-]+$")


def clean_head(text: str) -> str:
    return PITCH.sub("", text.strip()).strip()


def parse_header(text: str) -> tuple[str, str, str, str]:
    pos = HEADER.search(text)
    if not pos:
        raise ValueError(text)
    head = text[: pos.start()].strip()
    meaning = text[pos.end() :].strip()
    bracket = re.search(r"【([^】]+)】", head)
    reading_part = head[: bracket.start()] if bracket else head
    reading = clean_head(reading_part)
    written = bracket.group(1).strip() if bracket else ""
    if written and re.search(r"[ぁ-んァ-ヶ一-龯]", written) and not re.fullmatch(r"[A-Za-z .'-]+", written):
        word = written
    else:
        word = reading
    return word, reading, pos.group(1), meaning


def main() -> None:
    candidates = []
    for page in range(296, 307):
        doc = json.loads((INPUT / f"page-{page:04d}.json").read_text(encoding="utf-8"))
        for side_number, side in enumerate(doc["sides"]):
            current = None
            for row in side:
                text = str(row["text"]).strip()
                # The illustrated footer contains a proverb and the printed page
                # number.  They are not vocabulary continuations.
                footer_start = 430 if page == 306 else 1160
                if float(row["y"]) >= footer_start:
                    continue
                if HEADER.search(text):
                    if current:
                        candidates.append(current)
                    word, reading, pos, meaning = parse_header(text)
                    current = {
                        "source_number": len(candidates) + 1,
                        "section": "超纲词",
                        "unit": "第40单元",
                        "book_page": page - 7,
                        "pdf_page": page,
                        "source_side": "left" if side_number == 0 else "right",
                        "word": word,
                        "reading": reading,
                        "part_of_speech": pos,
                        "meaning_zh_candidate": meaning,
                        "has_original_sentence": False,
                        "sentence_ja_candidate": "",
                        "sentence_zh_candidate": "",
                        "source_bbox": [float(row[key]) for key in ("x", "y", "w", "h")],
                        "ocr_engine": doc["engine"],
                        "ocr_score_min": float(row["score"]),
                        "raw_lines": [text],
                        "verification_method": "pending",
                        "verification_note": "待与原页及第二OCR逐字段核对。",
                    }
                elif current:
                    if len(text) <= 2 or text in {"超纲词", "あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ", "さ", "し", "す", "せ", "そ", "た", "ち", "つ", "て", "と", "な", "に", "ぬ", "ね", "の", "は", "ひ", "ふ", "へ", "ほ", "ま", "み", "む", "め", "も", "や", "ゆ", "よ", "ら", "り", "る", "れ", "ろ", "わ"}:
                        continue
                    current["raw_lines"].append(text)
                    current["meaning_zh_candidate"] += text
                    current["ocr_score_min"] = min(current["ocr_score_min"], float(row["score"]))
                    x, y, w, h = (float(row[key]) for key in ("x", "y", "w", "h"))
                    bx, by, bw, bh = current["source_bbox"]
                    left, top = min(bx, x), min(by, y)
                    right, bottom = max(bx + bw, x + w), max(by + bh, y + h)
                    current["source_bbox"] = [left, top, right - left, bottom - top]
            if current:
                candidates.append(current)
    side_order = {"left": 0, "right": 1}
    candidates.sort(key=lambda row: (row["pdf_page"], side_order[row["source_side"]], row["source_bbox"][1]))
    if len(candidates) != 612:
        raise SystemExit(f"expected 612 advanced candidates, got {len(candidates)}")
    for number, row in enumerate(candidates, start=1):
        row["source_number"] = number
        row["id_number"] = 4214 + number
    OUTPUT.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(candidates)} advanced candidates")
    print(f"Minimum OCR score: {min(row['ocr_score_min'] for row in candidates):.4f}")


if __name__ == "__main__":
    main()
