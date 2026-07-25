#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import edge_tts
import genanki

VOICE = "ja-JP-NanamiNeural"
RATE = "-10%"
VOLUME = "+0%"
PITCH = "+0Hz"
MODEL_ID = 1889930905
DECK_ID = 1889930906
MODEL_NAME = "无敌绿宝书 · 三阶段听辨（音量增强版）"
DECK_NAME = "无敌绿宝书::N3（音量增强版）"
FIELDS = [
    "ID", "Level", "Unit", "BookPage", "PdfPage", "Word", "Reading",
    "PartOfSpeech", "MeaningZh", "SentenceJa", "SentenceZhReviewed",
    "SentenceZhOriginal", "TranslationStatus", "TranslationNote",
    "WordAudioX2", "SentenceAudioX1", "SentenceAudioX2",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


async def synthesize(text: str, output: Path, retries: int = 4) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 1000:
        return
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            tmp = output.with_suffix(".edge.mp3")
            tmp.unlink(missing_ok=True)
            communicate = edge_tts.Communicate(
                text=text,
                voice=VOICE,
                rate=RATE,
                volume=VOLUME,
                pitch=PITCH,
            )
            await communicate.save(str(tmp))
            run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(tmp), "-af", "loudnorm=I=-16:TP=-1.0:LRA=11",
                "-ar", "24000", "-ac", "1", "-b:a", "96k", str(output),
            ])
            tmp.unlink(missing_ok=True)
            if output.stat().st_size <= 1000:
                raise RuntimeError(f"Audio output is unexpectedly small: {output}")
            return
        except Exception as exc:  # pragma: no cover - network retries
            last_error = exc
            print(f"TTS attempt {attempt}/{retries} failed for {output.name}: {exc}", file=sys.stderr)
            output.unlink(missing_ok=True)
            await asyncio.sleep(min(3 * attempt, 10))
    raise RuntimeError(f"TTS failed after {retries} attempts: {output}") from last_error


def make_double(single: Path, output: Path, work_dir: Path) -> None:
    silence = work_dir / "silence_0700ms.wav"
    if not silence.exists():
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.700",
            "-c:a", "pcm_s16le", str(silence),
        ])
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(single), "-i", str(silence), "-i", str(single),
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "24000", "-ac", "1", "-b:a", "96k", str(output),
    ])


def audio_text_for_word(row: dict[str, str]) -> str:
    # Use the reading to avoid kanji ambiguity. A Japanese comma gives a natural pause
    # between alternative forms such as ゼミ・ゼミナール.
    return row["Reading"].replace("・", "、")


async def build_audio(rows: list[dict[str, str]], media_dir: Path, work_dir: Path) -> list[Path]:
    media_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    media_files: list[Path] = []
    for index, row in enumerate(rows, start=1):
        card_id = row["ID"]
        print(f"[{index:02d}/{len(rows)}] audio: {card_id}", flush=True)
        word_x1 = work_dir / f"{card_id}_word_x1.mp3"
        word_x2 = media_dir / f"{card_id}_word_x2.mp3"
        sentence_x1 = media_dir / f"{card_id}_sentence_x1.mp3"
        sentence_x2 = media_dir / f"{card_id}_sentence_x2.mp3"
        await synthesize(audio_text_for_word(row), word_x1)
        await synthesize(row["SentenceJa"], sentence_x1)
        make_double(word_x1, word_x2, work_dir)
        make_double(sentence_x1, sentence_x2, work_dir)
        media_files.extend([word_x2, sentence_x1, sentence_x2])
    return media_files


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 50:
        raise ValueError(f"Expected exactly 50 rows, got {len(rows)}")
    expected = [f"n3_{i:04d}" for i in range(125, 175)]
    actual = [row["ID"] for row in rows]
    if actual != expected:
        raise ValueError("IDs must be continuous from n3_0125 through n3_0174")
    for row in rows:
        missing = [field for field in FIELDS if not row.get(field)]
        if missing:
            raise ValueError(f"{row['ID']} has empty required fields: {missing}")
    return rows


def build_package(
    rows: list[dict[str, str]],
    media_files: list[Path],
    front: str,
    back: str,
    css: str,
    output: Path,
) -> None:
    model = genanki.Model(
        MODEL_ID,
        MODEL_NAME,
        fields=[{"name": field} for field in FIELDS],
        templates=[{"name": "三阶段听辨", "qfmt": front, "afmt": back}],
        css=css,
        sort_field_index=0,
    )
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    for row in rows:
        note = genanki.Note(
            model=model,
            fields=[row[field] for field in FIELDS],
            tags=row.get("Tags", "").split(),
            guid=genanki.guid_for(row["ID"]),
        )
        deck.add_note(note)
    output.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.media_files = [str(path) for path in media_files]
    package.write_to_file(str(output))
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/n3_0125_0174.csv")
    parser.add_argument("--output", default="dist/无敌绿宝书-N3-0125至0174.apkg")
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    csv_path = root / args.csv
    output = root / args.output
    media_dir = root / "build" / "media"
    work_dir = root / "build" / "work"
    rows = read_rows(csv_path)
    front = (root / "templates" / "front.html").read_text(encoding="utf-8")
    back = (root / "templates" / "back.html").read_text(encoding="utf-8")
    css = (root / "templates" / "style.css").read_text(encoding="utf-8")
    media_files = asyncio.run(build_audio(rows, media_dir, work_dir))
    build_package(rows, media_files, front, back, css, output)
    if not args.keep_work:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
