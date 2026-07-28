#!/usr/bin/env python3
"""Import-level structural validation for the complete N3 APKG."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from n3_audio_common import EXPECTED_TOTAL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apkg", type=Path)
    args = parser.parse_args()
    expected_ids = [f"n3_{number:04d}" for number in range(1, EXPECTED_TOTAL + 1)]

    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        with zipfile.ZipFile(args.apkg) as archive:
            archive.extractall(directory)
        collection = directory / "collection.anki2"
        if not collection.is_file():
            raise ValueError("collection.anki2 is missing")
        connection = sqlite3.connect(collection)
        notes = connection.execute("select count(*) from notes").fetchone()[0]
        cards = connection.execute("select count(*) from cards").fetchone()[0]
        ids = sorted(row[0].split("\x1f", 1)[0] for row in connection.execute("select flds from notes"))
        connection.close()
        media_map = json.loads((directory / "media").read_text(encoding="utf-8"))
        media_names = list(media_map.values())
        missing_media = [key for key in media_map if not (directory / key).is_file()]

        assert notes == EXPECTED_TOTAL, notes
        assert cards == EXPECTED_TOTAL, cards
        assert ids == expected_ids, "note IDs are missing, duplicated, or out of order"
        assert len(media_names) == EXPECTED_TOTAL * 3, len(media_names)
        assert len(set(media_names)) == len(media_names), "duplicate media names"
        assert not missing_media, missing_media[:10]
        print(f"PASS: {notes} notes, {cards} cards, {len(media_names)} media files")


if __name__ == "__main__":
    main()
