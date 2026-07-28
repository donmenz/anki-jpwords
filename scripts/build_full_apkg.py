#!/usr/bin/env python3
"""Build the complete 3,400-card clean-PDF N3 APKG from Edge TTS audio."""

from __future__ import annotations

import argparse
from pathlib import Path

import genanki

from n3_audio_common import (
    DECK_ID,
    DECK_NAME,
    FIELDS,
    MODEL_ID,
    MODEL_NAME,
    audio_names,
    load_wordlist,
    to_anki_fields,
)


def build_package(
    rows: list[dict[str, object]],
    audio_dir: Path,
    output: Path,
    root: Path,
) -> None:
    media_files = [audio_dir / name for row in rows for name in audio_names(str(row["id"]))]
    missing = [str(path) for path in media_files if not path.is_file() or path.stat().st_size <= 1000]
    if missing:
        raise ValueError(f"missing or invalid media: {missing[:10]}")

    model = genanki.Model(
        MODEL_ID,
        MODEL_NAME,
        fields=[{"name": field} for field in FIELDS],
        templates=[{
            "name": "三阶段听辨",
            "qfmt": (root / "templates/front.html").read_text(encoding="utf-8"),
            "afmt": (root / "templates/back.html").read_text(encoding="utf-8"),
        }],
        css=(root / "templates/style.css").read_text(encoding="utf-8"),
        sort_field_index=0,
    )
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    for row in rows:
        fields = to_anki_fields(row)
        tags = [
            "N3",
            "CleanPdfEdgeTTS",
            f"Unit{int(row['unit']):02d}",
            str(row["translation_status"]).replace(" ", "_"),
            "OriginalExample" if row["has_original_sentence"] else "NoOriginalExample",
        ]
        deck.add_note(genanki.Note(
            model=model,
            fields=[fields[field] for field in FIELDS],
            tags=tags,
            # Keep this edition separate from the earlier 3,256-card TTS deck
            # and from the publisher-audio deck in the same Anki profile.
            guid=genanki.guid_for("n3-clean-pdf-edge-tts-v1", str(row["id"])),
        ))

    output.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.media_files = [str(path) for path in media_files]
    package.write_to_file(str(output))
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/n3/wordlist.json"))
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("dist/无敌绿宝书-N3-3400词-EdgeTTS.apkg"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    rows = load_wordlist(args.input)
    build_package(rows, args.audio_dir, args.output, root)


if __name__ == "__main__":
    main()
