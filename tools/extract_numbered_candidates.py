#!/usr/bin/env python3
"""Create review candidates for the 4,214 numbered N1 entries from two OCR passes.

This deliberately writes candidates, not data/source.json.  Missing markers and
field disagreements remain explicit so the source-fidelity gate cannot be
bypassed accidentally.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SECTIONS = (
    ("必考词", 8, 208, 2809, 0),
    ("基础词", 209, 295, 1405, 2809),
)
UNIT_START_BOOK_PAGES = {
    1: 1, 2: 13, 3: 25, 4: 33, 5: 41, 6: 50, 7: 59,
    8: 68, 9: 76, 10: 84, 11: 92, 12: 100, 13: 108,
    14: 116, 15: 124, 16: 132, 17: 140, 18: 148, 19: 155,
    20: 162, 21: 169, 22: 176, 23: 183, 24: 189, 25: 196,
    26: 202, 27: 208, 28: 214, 29: 221, 30: 228, 31: 235,
    32: 241, 33: 247, 34: 253, 35: 259, 36: 265, 37: 271,
    38: 277, 39: 283, 40: 289,
}
NUMBER = re.compile(r"(?<!\d)(\d{4})(?!\d)")
POS = re.compile(r"[（(]((?:名|副|形|他|自|連|连|感|叹|接|助|代|ト|文|书|書|面|接头|接尾|前缀|后缀)[^）)]*)[）)]")
PITCH = re.compile(r"[⓪①②③④⑤⑥⑦⑧⑨⑩0-9・·\-@◎○]+$")
META_LABELS = {"近", "反", "析", "注", "参", "派", "慣", "惯", "辨", "辨析"}
EXAMPLE_LABEL_OCR = {"国", "図", "园", "園", "因", "回", "固", "圀", "囯"}


def unit_for_pdf_page(pdf_page: int) -> str:
    book_page = pdf_page - 7
    unit = max(number for number, start in UNIT_START_BOOK_PAGES.items() if start <= book_page)
    return f"第{unit}单元"


def side_rows_vision(path: Path) -> list[list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    midpoint = float(doc["image_width"]) / 2
    sides: list[list[dict]] = [[], []]
    for raw in doc.get("ocr_boxes", []):
        row = dict(raw)
        center = float(row.get("x", 0)) + float(row.get("w", 0)) / 2
        sides[0 if center < midpoint else 1].append(row)
    for side in sides:
        side.sort(key=lambda row: (float(row.get("y", 0)), float(row.get("x", 0))))
    return sides


def side_rows_paddle(path: Path) -> list[list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    sides = [[dict(row) for row in side] for side in doc.get("sides", [])]
    for side in sides:
        side.sort(key=lambda row: (float(row.get("y", 0)), float(row.get("x", 0))))
    return sides


def marker_number(row: dict, side_number: int, image_width: float, total: int) -> int | None:
    text = str(row.get("text", "")).strip()
    found = NUMBER.findall(text)
    if len(found) != 1:
        return None
    # Printed entry numbers sit at the right edge of each vocabulary column.
    x = float(row.get("x", 0))
    minimum_x = image_width * (0.39 if side_number == 0 else 0.83)
    if x < minimum_x:
        return None
    residue = NUMBER.sub("", text)
    if re.search(r"[A-Za-zぁ-んァ-ヶ一-龯]", residue):
        return None
    value = int(found[0])
    return value if 1 <= value <= total else None


def direct_number(row: dict, total: int) -> int | None:
    """Read an isolated four-digit marker even when OCR moved its x coordinate."""
    text = str(row.get("text", "")).strip()
    found = NUMBER.findall(text)
    if len(found) != 1:
        return None
    residue = NUMBER.sub("", text)
    if re.search(r"[A-Za-zぁ-んァ-ヶ一-龯]", residue):
        return None
    value = int(found[0])
    return value if 1 <= value <= total else None


def groups(rows: list[dict], tolerance: float = 5.0) -> list[list[dict]]:
    output: list[list[dict]] = []
    for row in sorted(rows, key=lambda item: (float(item.get("y", 0)), float(item.get("x", 0)))):
        if not output or abs(float(row.get("y", 0)) - sum(float(x.get("y", 0)) for x in output[-1]) / len(output[-1])) > tolerance:
            output.append([row])
        else:
            output[-1].append(row)
    for group in output:
        group.sort(key=lambda item: float(item.get("x", 0)))
    return output


def group_text(group: list[dict]) -> str:
    return "".join(str(row.get("text", "")).strip() for row in group)


def starts_new_entry(group: list[dict]) -> bool:
    text = group_text(group)
    return bool(POS.search(text) and ("【" in text or "［" in text or re.search(r"[ぁ-んァ-ヶ]", text)))


def looks_like_translation(group: list[dict]) -> bool:
    text = group_text(group).lstrip("/／!！1|｜・• ")
    if not text:
        return False
    if any(str(row.get("text", "")).lstrip().startswith(("/", "／")) for row in group):
        return True
    if re.search(r"[的了这那们对还没把从为个吗您他她它与并将该让时后里过于着]", text):
        return True
    cjk = len(re.findall(r"[一-龯]", text))
    kana = len(re.findall(r"[ぁ-んァ-ヶ]", text))
    return cjk >= 5 and kana == 0


def looks_like_misread_example_label(group: list[dict]) -> bool:
    """The grey 例 badge is commonly read as a box-shaped CJK character."""
    text = group_text(group).strip()
    if not text or text[0] not in EXAMPLE_LABEL_OCR:
        return False
    remainder = text[1:].lstrip()
    return len(remainder) >= 6 and bool(re.search(r"[ぁ-んァ-ヶ]", remainder))


def looks_like_ruby_group(group: list[dict]) -> bool:
    """Identify small furigana OCR lines so they do not leak into meanings."""
    text = group_text(group).strip()
    if not text or re.search(r"[（）()【】「」『』。！？!?/／,:：;；]", text):
        return False
    kana = len(re.findall(r"[ぁ-んァ-ヶー]", text))
    cjk = len(re.findall(r"[一-龯]", text))
    return kana >= 2 and cjk <= max(1, kana // 8)


def clean_reading(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    return PITCH.sub("", text).strip()


def split_inline_bilingual_rows(rows: list[dict]) -> list[dict]:
    """Split OCR rows where Japanese example and /Chinese translation merged."""
    output = []
    for raw in rows:
        text = str(raw.get("text", ""))
        match = re.search(r"[/／]", text)
        if not match or not re.search(r"[ぁ-んァ-ヶ]", text[: match.start()]):
            output.append(raw)
            continue
        japanese = dict(raw)
        japanese["text"] = text[: match.start()].rstrip()
        chinese = dict(raw)
        chinese["text"] = "/" + text[match.end() :].lstrip()
        chinese["y"] = float(raw.get("y", 0)) + 10.0
        output.extend((japanese, chinese))
    return output


def parse_header(text: str) -> dict[str, str]:
    normalized = text.replace("［", "【").replace("]", "】").replace("］", "】")
    pos = POS.search(normalized)
    before = normalized[: pos.start()].strip() if pos else normalized
    meaning = normalized[pos.end() :].strip() if pos else ""
    bracket = re.search(r"【([^】]+)】", before)
    reading_source = before[: bracket.start()] if bracket else before
    reading = clean_reading(reading_source)
    written = bracket.group(1).strip() if bracket else ""
    if written and re.search(r"[ぁ-んァ-ヶ一-龯]", written) and not re.fullmatch(r"[A-Za-z .'-]+", written):
        word = written
    else:
        word = reading
    return {
        "word": word,
        "reading": reading,
        "part_of_speech": pos.group(1) if pos else "",
        "meaning_zh": meaning,
    }


def parse_entry(
    rows: list[dict],
    marker: dict,
    page: int,
    side_number: int,
    example_y_hint: float | None = None,
    translation_y_hint: float | None = None,
) -> dict:
    body = [row for row in rows if row is not marker]
    body = split_inline_bilingual_rows(body)
    line_groups = groups(body)
    example_index = None
    example_method = None
    for index, group in enumerate(line_groups):
        texts = [str(row.get("text", "")).strip() for row in group]
        if any(text == "例" or text.startswith("例") for text in texts) or looks_like_misread_example_label(group):
            example_index = index
            example_method = "printed_or_misread_label"
            label_y = sum(float(row.get("y", 0)) for row in group) / len(group)
            if index and label_y - max(float(row.get("y", 0)) for row in line_groups[index - 1]) <= 15:
                prior_text = group_text(line_groups[index - 1])
                if re.search(r"[ぁ-んァ-ヶ]", prior_text) and not looks_like_ruby_group(line_groups[index - 1]):
                    example_index = index - 1
                    example_method = "printed_label_with_preceding_baseline"
            break
    if example_index is None and example_y_hint is not None and line_groups:
        candidates = [
            (
                abs(sum(float(row.get("y", 0)) for row in group) / len(group) - example_y_hint)
                + (100 if looks_like_ruby_group(group) else 0),
                index,
            )
            for index, group in enumerate(line_groups)
        ]
        distance, hinted_index = min(candidates)
        if distance <= 18:
            example_index = hinted_index
            example_method = "cross_ocr_position_hint"
    if example_index is None:
        for index, group in enumerate(line_groups):
            if not any(str(row.get("text", "")).lstrip().startswith(("/", "／")) for row in group):
                continue
            for prior in range(index - 1, -1, -1):
                text = group_text(line_groups[prior])
                if re.search(r"[ぁ-んァ-ヶ]", text) and re.search(r"[。！？!?]", text):
                    example_index = prior
                    example_method = "translation_backtrack"
                    break
            if example_index is not None:
                break
    slash_index = None
    if example_index is not None:
        for index in range(example_index + 1, len(line_groups)):
            group_y = sum(float(row.get("y", 0)) for row in line_groups[index]) / len(line_groups[index])
            hinted = (
                translation_y_hint is not None
                and abs(group_y - translation_y_hint) <= 18
                and not re.search(r"[ぁ-んァ-ヶ]", group_text(line_groups[index]))
            )
            if hinted or looks_like_translation(line_groups[index]):
                slash_index = index
                break

    if example_index is None:
        header_groups = line_groups
    else:
        example_y = min(float(row.get("y", 0)) for row in line_groups[example_index])
        header_groups = [
            group for group in line_groups[:example_index]
            if max(float(row.get("y", 0)) for row in group) <= example_y - 12
            and not looks_like_ruby_group(group)
        ]
    header_text = "".join(group_text(group) for group in header_groups)
    parsed = parse_header(header_text)

    sentence = ""
    translation = ""
    if example_index is not None:
        end = slash_index if slash_index is not None else len(line_groups)
        sentence_parts = []
        for group in line_groups[example_index:end]:
            if group is not line_groups[example_index] and looks_like_ruby_group(group):
                continue
            for row in group:
                # Main example glyphs are consistently 15-20 px high in both
                # OCR passes. Furigana and spurious illustration fragments are
                # 6-12 px high; concatenating them silently corrupts otherwise
                # plausible sentences (especially around numbers and kanji).
                if float(row.get("h", 0)) < 13.0:
                    continue
                text = str(row.get("text", "")).strip()
                if text == "例":
                    continue
                if text.startswith("例"):
                    text = text[1:].lstrip()
                elif text and text[0] in EXAMPLE_LABEL_OCR and looks_like_misread_example_label(group):
                    text = text[1:].lstrip()
                sentence_parts.append(text)
        sentence = "".join(sentence_parts)
    if slash_index is not None:
        translation_parts = []
        label_x_max = 110 if side_number == 0 else 480
        for group in line_groups[slash_index:]:
            texts = [str(row.get("text", "")).strip() for row in group]
            if group is not line_groups[slash_index] and starts_new_entry(group):
                break
            if any(text in META_LABELS or text.startswith(("习题", "解析")) for text in texts):
                break
            if group is not line_groups[slash_index] and any(
                text.startswith(tuple(META_LABELS)) or re.search(r"[ぁ-んァ-ヶ]", text)
                for text in texts
            ):
                break
            if group is not line_groups[slash_index] and any(float(row.get("x", 0)) < label_x_max and len(str(row.get("text", "")).strip()) <= 3 for row in group):
                break
            for text in texts:
                translation_parts.append(text.lstrip("/／!！1|｜・• "))
        translation = "".join(translation_parts)

    all_x = [float(row.get("x", 0)) for row in rows]
    all_y = [float(row.get("y", 0)) for row in rows]
    all_right = [float(row.get("x", 0)) + float(row.get("w", 0)) for row in rows]
    all_bottom = [float(row.get("y", 0)) + float(row.get("h", 0)) for row in rows]
    return {
        **parsed,
        "sentence_ja": sentence,
        "sentence_zh_original": translation,
        "pdf_page": page,
        "book_page": page - 7,
        "unit": unit_for_pdf_page(page),
        "source_side": "left" if side_number == 0 else "right",
        "source_bbox": [min(all_x), min(all_y), max(all_right) - min(all_x), max(all_bottom) - min(all_y)],
        "raw_rows": rows,
        "field_status": {
            "header_parsed": bool(parsed["word"] and parsed["reading"] and parsed["part_of_speech"] and parsed["meaning_zh"]),
            "example_found": example_index is not None,
            "translation_found": slash_index is not None and bool(translation),
        },
        "example_detection": example_method,
        "example_y": None if example_index is None else sum(float(row.get("y", 0)) for row in line_groups[example_index]) / len(line_groups[example_index]),
        "translation_y": None if slash_index is None else sum(float(row.get("y", 0)) for row in line_groups[slash_index]) / len(line_groups[slash_index]),
    }


def collect_engine(folder: Path, loader, start: int, end: int, total: int) -> dict[int, dict]:
    entries: dict[int, dict] = {}
    direct: dict[int, list[dict]] = {}
    last = 0
    for page in range(start, end + 1):
        path = folder / f"page-{page:04d}.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        image_width = float(doc["image_width"])
        for side_number, side in enumerate(loader(path)):
            all_markers: list[tuple[int, int, dict]] = []
            for index, row in enumerate(side):
                number = direct_number(row, total)
                if number is not None:
                    all_markers.append((index, number, row))
            for marker_index, (row_index, number, marker) in enumerate(all_markers):
                next_index = all_markers[marker_index + 1][0] if marker_index + 1 < len(all_markers) else len(side)
                candidate = parse_entry(side[row_index:next_index], marker, page, side_number)
                direct.setdefault(number, []).append(candidate)
            markers: list[tuple[int, int, dict]] = []
            for index, row in enumerate(side):
                number = marker_number(row, side_number, image_width, total)
                if number is not None and last < number <= min(total, last + 30):
                    markers.append((index, number, row))
                    last = number
            for marker_index, (row_index, number, marker) in enumerate(markers):
                next_index = markers[marker_index + 1][0] if marker_index + 1 < len(markers) else len(side)
                evidence = side[row_index:next_index]
                entries[number] = parse_entry(evidence, marker, page, side_number)
    def location(row: dict) -> tuple[int, int, float]:
        return (int(row["pdf_page"]), 0 if row["source_side"] == "left" else 1, float(row["source_bbox"][1]))

    for number in range(1, total + 1):
        if number in entries or number not in direct:
            continue
        previous = next((entries[value] for value in range(number - 1, 0, -1) if value in entries), None)
        following = next((entries[value] for value in range(number + 1, total + 1) if value in entries), None)
        lower = location(previous) if previous else (start, 0, 0.0)
        upper = location(following) if following else (end, 1, float("inf"))
        bounded = [candidate for candidate in direct[number] if lower < location(candidate) < upper]
        if len(bounded) == 1:
            entries[number] = bounded[0]
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision", type=Path, default=Path("data/ocr-columns"))
    parser.add_argument("--paddle", type=Path, default=Path("data/ocr-paddle-full"))
    parser.add_argument("--output", type=Path, default=Path("data/numbered-candidates.json"))
    args = parser.parse_args()
    output = []
    for section, start, end, total, offset in SECTIONS:
        vision = collect_engine(args.vision, side_rows_vision, start, end, total)
        paddle = collect_engine(args.paddle, side_rows_paddle, start, end, total)
        print(section, "vision", len(vision), "paddle", len(paddle), "combined", len(set(vision) | set(paddle)))
        for source_number in range(1, total + 1):
            output.append({
                "id_number": len(output) + 1,
                "section": section,
                "source_number": source_number,
                "vision": vision.get(source_number),
                "paddle": paddle.get(source_number),
                "candidate_status": "dual" if source_number in vision and source_number in paddle else "single" if source_number in vision or source_number in paddle else "missing",
                "verification_method": "pending",
            })
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {status: sum(row["candidate_status"] == status for row in output) for status in ("dual", "single", "missing")}
    print("Candidate statuses:", counts)


if __name__ == "__main__":
    main()
