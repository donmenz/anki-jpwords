#!/usr/bin/env python3
"""Align OCR marker/header positions to every printed source number."""
from __future__ import annotations

import json
from pathlib import Path

from extract_numbered_candidates import (
    POS,
    direct_number,
    side_rows_paddle,
    side_rows_vision,
)


SECTIONS = (
    ("必考词", 8, 208, 2809, 0),
    ("基础词", 209, 295, 1405, 2809),
)
VISION = Path("data/ocr-columns")
PADDLE = Path("data/ocr-paddle-full")
OUTPUT = Path("data/master-markers.json")


def cluster(items: list[dict], tolerance: float = 12.0) -> list[list[dict]]:
    output: list[list[dict]] = []
    for item in sorted(items, key=lambda row: row["y"]):
        if not output or item["y"] - sum(row["y"] for row in output[-1]) / len(output[-1]) > tolerance:
            output.append([item])
        else:
            output[-1].append(item)
    return output


def positions_for_section(start: int, end: int, total: int) -> list[dict]:
    positions = []
    for page in range(start, end + 1):
        engines = []
        vision_path = VISION / f"page-{page:04d}.json"
        paddle_path = PADDLE / f"page-{page:04d}.json"
        if vision_path.is_file():
            engines.append(("vision", side_rows_vision(vision_path)))
        if paddle_path.is_file():
            engines.append(("paddle", side_rows_paddle(paddle_path)))
        for side_number in (0, 1):
            number_items = []
            header_items = []
            for engine, sides in engines:
                for row in sides[side_number]:
                    text = str(row.get("text", "")).strip()
                    number = direct_number(row, total)
                    if number is not None:
                        number_items.append({"y": float(row["y"]), "engine": engine, "value": number, "text": text})
                    if POS.search(text):
                        header_items.append({"y": float(row["y"]), "engine": engine, "text": text})
            number_clusters = cluster(number_items)
            page_positions = []
            for group in number_clusters:
                page_positions.append({
                    "pdf_page": page,
                    "source_side": "left" if side_number == 0 else "right",
                    "y": sum(row["y"] for row in group) / len(group),
                    "observed_numbers": sorted({row["value"] for row in group}),
                    "number_observations": group,
                    "header_observations": [],
                    "position_source": "number",
                })
            for group in cluster(header_items):
                header_y = sum(row["y"] for row in group) / len(group)
                preceding = [position for position in page_positions if 5 <= header_y - position["y"] <= 65]
                if preceding:
                    nearest = min(preceding, key=lambda position: header_y - position["y"])
                    nearest["header_observations"].extend(group)
                else:
                    page_positions.append({
                        "pdf_page": page,
                        "source_side": "left" if side_number == 0 else "right",
                        "y": header_y - 16,
                        "observed_numbers": [],
                        "number_observations": [],
                        "header_observations": group,
                        "position_source": "header_only",
                    })
            positions.extend(sorted(page_positions, key=lambda row: row["y"]))
    return positions


def match_cost(position: dict, expected: int) -> int:
    values = position["observed_numbers"]
    if expected in values:
        return 0
    if not values:
        return 6
    distance = min(abs(value - expected) for value in values)
    return 2 + distance if distance <= 2 else 7


def align(positions: list[dict], expected_numbers: list[int]) -> tuple[list[dict], list[dict], list[int]]:
    total = len(expected_numbers)
    skip_position = 4
    # There are more physical position candidates than expected entries.  A
    # missing printed number should therefore attach to a header/neighbor
    # position rather than disappear as an unmapped source ID.
    skip_expected = 100
    previous = [number * skip_expected for number in range(total + 1)]
    traces = [bytearray(total + 1)]
    for index, position in enumerate(positions, start=1):
        current = [index * skip_position] + [0] * total
        trace = bytearray(total + 1)
        for expected in range(1, total + 1):
            source_number = expected_numbers[expected - 1]
            choices = (
                previous[expected - 1] + match_cost(position, source_number),
                previous[expected] + skip_position,
                current[expected - 1] + skip_expected,
            )
            operation = min(range(3), key=choices.__getitem__)
            current[expected] = choices[operation]
            trace[expected] = operation
        traces.append(trace)
        previous = current
    matched = []
    skipped_positions = []
    skipped_ids = []
    i, expected = len(positions), total
    while i or expected:
        operation = traces[i][expected] if i else 2
        if operation == 0:
            position = dict(positions[i - 1])
            source_number = expected_numbers[expected - 1]
            position["source_number"] = source_number
            position["alignment"] = "observed_exact" if source_number in position["observed_numbers"] else "position_inferred"
            matched.append(position)
            i -= 1
            expected -= 1
        elif operation == 1:
            skipped_positions.append(positions[i - 1])
            i -= 1
        else:
            skipped_ids.append(expected_numbers[expected - 1])
            expected -= 1
    matched.reverse()
    skipped_positions.reverse()
    skipped_ids.reverse()
    return matched, skipped_positions, skipped_ids


def main() -> None:
    output = []
    diagnostics = []
    for section, start, end, total, offset in SECTIONS:
        positions = positions_for_section(start, end, total)
        expected_numbers = list(range(1, total + 1))
        matched, skipped_positions, skipped_ids = align(positions, expected_numbers)
        for row in matched:
            row["section"] = section
            row["id_number"] = len(output) + 1
            output.append(row)
        diagnostic = {
            "section": section,
            "positions": len(positions),
            "expected": len(expected_numbers),
            "matched": len(matched),
            "observed_exact": sum(row["alignment"] == "observed_exact" for row in matched),
            "position_inferred": sum(row["alignment"] == "position_inferred" for row in matched),
            "skipped_positions": skipped_positions,
            "skipped_ids": skipped_ids,
        }
        diagnostics.append(diagnostic)
        print(section, {key: value if not isinstance(value, list) else len(value) for key, value in diagnostic.items()})
    if len(output) != 4214 or [row["id_number"] for row in output] != list(range(1, 4215)):
        raise SystemExit("master marker alignment is not complete and continuous")
    OUTPUT.write_text(json.dumps({"markers": output, "diagnostics": diagnostics}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: 4214 continuous numbered marker positions")


if __name__ == "__main__":
    main()
