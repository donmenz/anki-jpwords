#!/usr/bin/env python3
"""Build a complete Japanese wordbook APKG from validated Edge TTS audio."""

from __future__ import annotations

import argparse
from pathlib import Path

import genanki

from deck_common import FIELDS, audio_names, load_config, load_wordlist, to_anki_fields


def safe_tag(value: object) -> str:
    return str(value).strip().replace(" ", "_")


def build_package(
    rows: list[dict[str, object]],
    config: dict[str, object],
    audio_dir: Path,
    output: Path,
    root: Path,
) -> None:
    media_files = [audio_dir / name for row in rows for name in audio_names(str(row["id"]))]
    missing = [str(path) for path in media_files if not path.is_file() or path.stat().st_size <= 1000]
    if missing:
        raise ValueError(f"missing or invalid media: {missing[:10]}")

    model = genanki.Model(
        int(config["model_id"]),
        str(config["model_name"]),
        fields=[{"name": field} for field in FIELDS],
        templates=[{
            "name": "三阶段听辨",
            "qfmt": (root / "templates/front.html").read_text(encoding="utf-8"),
            "afmt": (root / "templates/back.html").read_text(encoding="utf-8"),
        }],
        css=(root / "templates/style.css").read_text(encoding="utf-8"),
        sort_field_index=0,
    )
    deck = genanki.Deck(int(config["deck_id"]), str(config["deck_name"]))
    for row in rows:
        fields = to_anki_fields(row, config)
        tags = [
            safe_tag(config["tag_prefix"]),
            "EdgeTTS",
            safe_tag(row["translation_status"]),
            "OriginalExample" if row["has_original_sentence"] else "NoOriginalExample",
        ]
        if str(row.get("unit", "")).strip():
            tags.append(f"Unit_{safe_tag(row['unit'])}")
        deck.add_note(genanki.Note(
            model=model,
            fields=[fields[field] for field in FIELDS],
            tags=tags,
            guid=genanki.guid_for(str(config["guid_prefix"]), str(row["id"])),
        ))

    output.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.media_files = [str(path) for path in media_files]
    package.write_to_file(str(output))
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("data/deck-config.json"))
    parser.add_argument("--input", type=Path, default=Path("data/wordlist.json"))
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    config = load_config(args.config)
    rows = load_wordlist(args.input, config)
    output = args.output or Path("dist") / str(config["output_filename"])
    build_package(rows, config, args.audio_dir, output, root)


if __name__ == "__main__":
    main()
