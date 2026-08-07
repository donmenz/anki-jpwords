#!/usr/bin/env python3
"""Segment both OCR passes with the continuous master marker index."""
from __future__ import annotations

import json
from pathlib import Path

from extract_numbered_candidates import (
    direct_number,
    parse_entry,
    side_rows_paddle,
    side_rows_vision,
)


MASTER = Path("data/master-markers.json")
VISION = Path("data/ocr-columns")
PADDLE = Path("data/ocr-paddle-full")
OUTPUT = Path("data/numbered-candidates.json")


def load_columns(folder: Path, loader) -> tuple[list[dict], dict[tuple[int, str], int]]:
    """Load numbered pages in human reading order: left, right, next page."""
    columns = []
    location_index = {}
    for page in range(8, 296):
        path = folder / f"page-{page:04d}.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        midpoint = float(doc["image_width"]) / 2
        for side_number, rows in enumerate(loader(path)):
            source_side = "left" if side_number == 0 else "right"
            location_index[(page, source_side)] = len(columns)
            columns.append({
                "page": page,
                "side_number": side_number,
                "source_side": source_side,
                "midpoint": midpoint,
                "rows": rows,
            })
    return columns, location_index


def source_span(rows: list[dict], page: int, source_side: str) -> dict | None:
    if not rows:
        return None
    left = min(float(row.get("x", 0)) for row in rows)
    top = min(float(row.get("y", 0)) for row in rows)
    right = max(float(row.get("x", 0)) + float(row.get("w", 0)) for row in rows)
    bottom = max(float(row.get("y", 0)) + float(row.get("h", 0)) for row in rows)
    return {
        "pdf_page": page,
        "book_page": page - 7,
        "source_side": source_side,
        "bbox": [left, top, right - left, bottom - top],
    }


def normalized_rows(rows: list[dict], column: dict, sequence_offset: float) -> list[dict]:
    """Keep real coordinates while giving the parser one monotonic local column."""
    output = []
    x_offset = column["midpoint"] if column["side_number"] else 0.0
    for raw in rows:
        row = dict(raw)
        row["_source_pdf_page"] = column["page"]
        row["_source_side"] = column["source_side"]
        row["_source_x"] = float(raw.get("x", 0))
        row["_source_y"] = float(raw.get("y", 0))
        row["x"] = float(raw.get("x", 0)) - x_offset
        row["y"] = float(raw.get("y", 0)) + sequence_offset
        output.append(row)
    return output


def is_page_decoration(row: dict, continuation_column: bool) -> bool:
    text = str(row.get("text", "")).strip()
    if any(label in text for label in ("必考词", "必考詞", "必考司", "基础词", "基礎詞", "单元", "単元")):
        return True
    return continuation_column and float(row.get("y", 0)) < 100 and bool(text) and text.isdigit()


def add_master_metadata(parsed: dict, marker: dict, spans: list[dict]) -> dict:
    parsed["pdf_page"] = int(marker["pdf_page"])
    parsed["book_page"] = int(marker["pdf_page"]) - 7
    parsed["source_side"] = str(marker["source_side"])
    parsed["source_spans"] = spans
    if spans:
        parsed["source_bbox"] = spans[0]["bbox"]
    parsed["coordinate_space"] = "column_local_sequence"
    parsed["master_marker_y"] = marker["y"]
    parsed["master_alignment"] = marker["alignment"]
    parsed["master_observed_numbers"] = marker["observed_numbers"]
    return parsed


def extract_engine(markers: list[dict], folder: Path, loader) -> dict[int, dict]:
    columns, location_index = load_columns(folder, loader)
    output = {}
    for index, marker in enumerate(markers):
        page = int(marker["pdf_page"])
        source_side = str(marker["source_side"])
        if (page, source_side) not in location_index:
            continue
        start_column = location_index[(page, source_side)]
        next_marker = markers[index + 1] if index + 1 < len(markers) else None
        end_column = (
            location_index.get((int(next_marker["pdf_page"]), str(next_marker["source_side"])), start_column)
            if next_marker is not None else start_column
        )
        evidence = []
        spans = []
        for column_index in range(start_column, end_column + 1):
            column = columns[column_index]
            lower = float(marker["y"]) - 10 if column_index == start_column else 0.0
            upper = (
                float(next_marker["y"]) - 6
                if next_marker is not None and column_index == end_column else 1165.0
            )
            selected = [
                row for row in column["rows"]
                if lower <= float(row.get("y", 0)) < upper
                and not is_page_decoration(row, column_index > start_column)
            ]
            span = source_span(selected, column["page"], column["source_side"])
            if span:
                spans.append(span)
            evidence.extend(normalized_rows(selected, column, (column_index - start_column) * 2000.0))
        if not evidence:
            continue
        printed_total = 2809 if page <= 208 else 1405
        numeric_rows = [row for row in evidence if direct_number(row, printed_total) is not None]
        marker_row = min(
            numeric_rows,
            key=lambda row: abs(float(row.get("y", 0)) - float(marker["y"])),
        ) if numeric_rows else {}
        parsed = parse_entry(evidence, marker_row, page, 0)
        output[int(marker["id_number"])] = add_master_metadata(parsed, marker, spans)
    return output


def reparse_with_hints(parsed: dict, example_y_hint: float | None, translation_y_hint: float | None) -> dict:
    evidence = parsed["raw_rows"]
    page = int(parsed["pdf_page"])
    side_number = 0
    printed_total = 2809 if page <= 208 else 1405
    numeric_rows = [row for row in evidence if direct_number(row, printed_total) is not None]
    marker_row = min(numeric_rows, key=lambda row: abs(float(row.get("y", 0)) - float(parsed["master_marker_y"]))) if numeric_rows else {}
    reparsed = parse_entry(
        evidence,
        marker_row,
        page,
        side_number,
        example_y_hint=example_y_hint,
        translation_y_hint=translation_y_hint,
    )
    for key in (
        "pdf_page", "book_page", "source_side", "source_bbox", "source_spans",
        "coordinate_space", "master_marker_y", "master_alignment", "master_observed_numbers",
    ):
        reparsed[key] = parsed[key]
    return reparsed


def main() -> None:
    markers = json.loads(MASTER.read_text(encoding="utf-8"))["markers"]
    vision = extract_engine(markers, VISION, side_rows_vision)
    paddle = extract_engine(markers, PADDLE, side_rows_paddle)
    for id_number in range(1, 4215):
        left, right = vision.get(id_number), paddle.get(id_number)
        if left is None or right is None:
            continue
        left_needs_hint = (
            left["example_y"] is None
            or left.get("example_detection") == "translation_backtrack"
            or len(str(left.get("sentence_ja", ""))) * 2 < len(str(right.get("sentence_ja", "")))
        )
        right_needs_hint = (
            right["example_y"] is None
            or right.get("example_detection") == "translation_backtrack"
            or len(str(right.get("sentence_ja", ""))) * 2 < len(str(left.get("sentence_ja", "")))
        )
        if left_needs_hint and right["example_y"] is not None:
            left = reparse_with_hints(left, right["example_y"], right["translation_y"])
            vision[id_number] = left
        if right_needs_hint and left["example_y"] is not None:
            right = reparse_with_hints(right, left["example_y"], left["translation_y"])
            paddle[id_number] = right
        if left["translation_y"] is None and right["translation_y"] is not None:
            vision[id_number] = reparse_with_hints(left, left["example_y"], right["translation_y"])
        if right["translation_y"] is None and left["translation_y"] is not None:
            paddle[id_number] = reparse_with_hints(right, right["example_y"], left["translation_y"])
    rows = []
    for marker in markers:
        id_number = int(marker["id_number"])
        rows.append({
            "id_number": id_number,
            "section": marker["section"],
            "source_number": marker["source_number"],
            "vision": vision.get(id_number),
            "paddle": paddle.get(id_number),
            "candidate_status": "dual" if id_number in vision and id_number in paddle else "single" if id_number in vision or id_number in paddle else "missing",
            "verification_method": "pending",
            "master_alignment": marker["alignment"],
        })
    if len(rows) != 4214 or [row["id_number"] for row in rows] != list(range(1, 4215)):
        raise SystemExit("numbered candidate IDs are not complete and continuous")
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = {status: sum(row["candidate_status"] == status for row in rows) for status in ("dual", "single", "missing")}
    print("Candidate statuses:", statuses)
    print("Position-inferred markers:", sum(row["master_alignment"] == "position_inferred" for row in rows))


if __name__ == "__main__":
    main()
