#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apkg")
    args = parser.parse_args()
    apkg = Path(args.apkg)
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(apkg) as zf:
            zf.extractall(tmp)
        collection = Path(tmp) / "collection.anki2"
        con = sqlite3.connect(collection)
        notes = con.execute("select count(*) from notes").fetchone()[0]
        cards = con.execute("select count(*) from cards").fetchone()[0]
        ids = [row[0].split("\x1f", 1)[0] for row in con.execute("select flds from notes order by flds")]
        media_map = json.loads((Path(tmp) / "media").read_text(encoding="utf-8"))
        media_names = set(media_map.values())
        missing = [name for name in media_names if not (Path(tmp) / next(k for k, v in media_map.items() if v == name)).exists()]
        assert notes == 50, notes
        assert cards == 50, cards
        assert ids[0] == "n3_0125" and ids[-1] == "n3_0174", (ids[0], ids[-1])
        assert len(media_names) == 150, len(media_names)
        assert not missing, missing
        print(f"OK: {notes} notes, {cards} cards, {len(media_names)} media files")


if __name__ == "__main__":
    main()
