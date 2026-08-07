#!/usr/bin/env python3
"""Re-segment all advanced entries in global reading order across columns/pages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_advanced_candidates import HEADER, parse_header
from extract_numbered_candidates import group_text, groups, side_rows_paddle


def span(rows: list[dict], page: int, side: str) -> dict | None:
    if not rows:
        return None
    left = min(float(row["x"]) for row in rows)
    top = min(float(row["y"]) for row in rows)
    right = max(float(row["x"]) + float(row["w"]) for row in rows)
    bottom = max(float(row["y"]) + float(row["h"]) for row in rows)
    return {"pdf_page": page, "book_page": page - 7, "source_side": side, "bbox": [left, top, right - left, bottom - top]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markers", type=Path, default=Path("data/advanced-candidates.json"))
    parser.add_argument("--ocr", type=Path, default=Path("data/ocr-paddle-full"))
    parser.add_argument("--output", type=Path, default=Path("data/advanced-global-candidates.json"))
    args = parser.parse_args()
    markers = json.loads(args.markers.read_text(encoding="utf-8"))
    columns = []
    location = {}
    for page in range(296, 307):
        sides = side_rows_paddle(args.ocr / f"page-{page:04d}.json")
        for side_number, rows in enumerate(sides):
            side = "left" if side_number == 0 else "right"
            location[(page, side)] = len(columns)
            columns.append({"page": page, "side": side, "rows": rows})
    output = []
    for index, marker in enumerate(markers):
        start_column = location[(int(marker["pdf_page"]), marker["source_side"])]
        following = markers[index + 1] if index + 1 < len(markers) else None
        end_column = location[(int(following["pdf_page"]), following["source_side"])] if following else start_column
        evidence = []
        spans = []
        for column_index in range(start_column, end_column + 1):
            column = columns[column_index]
            lower = float(marker["source_bbox"][1]) - 12 if column_index == start_column else 0.0
            upper = float(following["source_bbox"][1]) - 5 if following and column_index == end_column else (430.0 if column["page"] == 306 else 1160.0)
            selected = [row for row in column["rows"] if lower <= float(row["y"]) < upper]
            part_span = span(selected, column["page"], column["side"])
            if part_span:
                spans.append(part_span)
            for raw in selected:
                row = dict(raw)
                row["_source_pdf_page"] = column["page"]
                row["_source_side"] = column["side"]
                row["y"] = float(row["y"]) + (column_index - start_column) * 2000.0
                evidence.append(row)
        line_groups = groups(evidence)
        header_index = next((i for i, group in enumerate(line_groups) if HEADER.search(group_text(group))), None)
        header_end_index = header_index
        if header_index is None:
            if not line_groups:
                raise SystemExit(f"advanced {marker['id_number']} has no OCR evidence")
            marker_y = float(marker["source_bbox"][1])
            header_index = min(
                range(len(line_groups)),
                key=lambda i: abs(
                    sum(float(row.get("y", 0)) for row in line_groups[i]) / len(line_groups[i])
                    - marker_y
                ),
            )
            header_end_index = header_index
            header_text = ""
            for end_index in range(header_index, min(len(line_groups), header_index + 3)):
                candidate = "".join(group_text(group) for group in line_groups[header_index : end_index + 1])
                if HEADER.search(candidate):
                    header_text = candidate
                    header_end_index = end_index
                    break
            if not header_text:
                header_text = str(marker.get("green_band", {}).get("vision_text", ""))
            if not HEADER.search(header_text):
                raise SystemExit(f"advanced {marker['id_number']} lost its header in both OCR passes")
        else:
            header_text = group_text(line_groups[header_index])
        word, reading, pos, meaning = parse_header(header_text)
        continuation = []
        for group in line_groups[int(header_end_index) + 1 :]:
            text = group_text(group).strip()
            if (
                not text
                or len(text) <= 1
                or "单元" in text
                or any(label in text for label in ("纲词", "必考词", "基础词"))
            ):
                continue
            continuation.append(text)
        meaning += "".join(continuation)
        primary_bbox = spans[0]["bbox"] if spans else marker["source_bbox"]
        output.append({
            **marker,
            "word": word,
            "reading": reading,
            "part_of_speech": pos,
            "meaning_zh_candidate": meaning,
            "source_bbox": primary_bbox,
            "source_spans": spans,
            "raw_lines": [header_text, *continuation],
            "ocr_score_min": min(float(row.get("score", 1.0)) for row in evidence),
        })
    if len(output) != 612:
        raise SystemExit(f"expected 612 entries, got {len(output)}")
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: rebuilt {len(output)} advanced entries in global reading order")
    print("Cross-column/page entries:", sum(len(row.get("source_spans", [])) > 1 for row in output))


if __name__ == "__main__":
    main()
