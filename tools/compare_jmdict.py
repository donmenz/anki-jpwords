#!/usr/bin/env python3
"""Use JMdict only to flag likely OCR errors; never rewrite source fields."""
from __future__ import annotations

import argparse
import gzip
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def load_jmdict(path: Path) -> tuple[dict[str, set[str]], set[str]]:
    by_written: dict[str, set[str]] = defaultdict(set)
    readings: set[str] = set()
    with gzip.open(path, "rb") as handle:
        for _event, entry in ET.iterparse(handle, events=("end",)):
            if entry.tag != "entry":
                continue
            written = [node.text or "" for node in entry.findall("k_ele/keb")]
            entry_readings = [node.text or "" for node in entry.findall("r_ele/reb")]
            readings.update(entry_readings)
            for word in written:
                by_written[word].update(entry_readings)
            entry.clear()
    return dict(by_written), readings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jmdict", type=Path, default=Path("data/reference/JMdict_e.gz"))
    parser.add_argument("--input", type=Path, default=Path("data/advanced-candidates.json"))
    parser.add_argument("--output", type=Path, default=Path("data/advanced-jmdict-review.json"))
    args = parser.parse_args()
    by_written, readings = load_jmdict(args.jmdict)
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    review = []
    for row in rows:
        word = str(row["word"])
        reading = str(row["reading"])
        if word in by_written:
            expected = sorted(by_written[word])
            status = "exact" if reading in by_written[word] else "reading_mismatch"
        elif word in readings:
            expected = [word]
            status = "exact" if reading == word else "reading_mismatch"
        else:
            expected = []
            status = "headword_not_found"
        review.append({
            "id_number": row["id_number"],
            "pdf_page": row["pdf_page"],
            "source_side": row["source_side"],
            "word_candidate": word,
            "reading_candidate": reading,
            "jmdict_readings": expected,
            "status": status,
            "decision": "pending" if status != "exact" else "dictionary_crosscheck_only",
        })
    args.output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {status: sum(row["status"] == status for row in review) for status in ("exact", "reading_mismatch", "headword_not_found")}
    print(counts)


if __name__ == "__main__":
    main()
