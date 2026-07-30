#!/usr/bin/env python3
"""Import-level structural validation for a complete Japanese wordbook APKG."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from deck_common import FIELDS, audio_names, expected_ids, load_config, load_wordlist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apkg", type=Path)
    parser.add_argument("--config", type=Path, default=Path("data/deck-config.json"))
    parser.add_argument("--input", type=Path, default=Path("data/wordlist.json"))
    args = parser.parse_args()

    config = load_config(args.config)
    rows = load_wordlist(args.input, config)
    expected_note_ids = expected_ids(config)
    expected_media = sorted(name for row in rows for name in audio_names(str(row["id"])))

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
        models_json, decks_json = connection.execute("select models, decks from col").fetchone()
        models = json.loads(models_json)
        decks = json.loads(decks_json)
        connection.close()

        model = models.get(str(config["model_id"]))
        deck = decks.get(str(config["deck_id"]))
        if not model or model.get("name") != config["model_name"]:
            raise ValueError("configured model identity is missing from the APKG")
        if [field["name"] for field in model["flds"]] != FIELDS:
            raise ValueError("APKG model fields differ from the configured contract")
        if not deck or deck.get("name") != config["deck_name"]:
            raise ValueError("configured deck identity is missing from the APKG")

        media_map = json.loads((directory / "media").read_text(encoding="utf-8"))
        media_names = sorted(media_map.values())
        missing_media = [key for key in media_map if not (directory / key).is_file()]
        if notes != len(rows) or cards != len(rows):
            raise ValueError(f"expected {len(rows)} notes/cards, got {notes}/{cards}")
        if ids != expected_note_ids:
            raise ValueError("note IDs are missing, duplicated, or out of order")
        if media_names != expected_media:
            raise ValueError("APKG media names differ from the expected three files per card")
        if missing_media:
            raise ValueError(f"APKG archive is missing media payloads: {missing_media[:10]}")
        print(f"PASS: {notes} notes, {cards} cards, {len(media_names)} media files")


if __name__ == "__main__":
    main()
