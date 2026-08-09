#!/usr/bin/env python3
"""Generate one resumable shard of full-deck Edge TTS audio."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path

import edge_tts

from n3_audio_common import audio_names, load_wordlist, select_shard


VOICE = "ja-JP-NanamiNeural"
RATE = "-10%"
VOLUME = "+0%"
PITCH = "+0Hz"
MIN_BYTES = 1000


async def run_process(*command: str) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(command)}\n{stderr.decode(errors='replace')}")


def valid_audio(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > MIN_BYTES


async def synthesize(text: str, output: Path, retries: int) -> None:
    if valid_audio(output):
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".edge.mp3")
    for attempt in range(1, retries + 1):
        try:
            temporary.unlink(missing_ok=True)
            communicator = edge_tts.Communicate(
                text=text,
                voice=VOICE,
                rate=RATE,
                volume=VOLUME,
                pitch=PITCH,
            )
            await communicator.save(str(temporary))
            normalized = output.with_suffix(".normalized.mp3")
            normalized.unlink(missing_ok=True)
            await run_process(
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(temporary),
                "-af", "loudnorm=I=-16:TP=-1.0:LRA=11",
                "-ar", "24000", "-ac", "1", "-b:a", "96k",
                str(normalized),
            )
            temporary.unlink(missing_ok=True)
            if not valid_audio(normalized):
                raise RuntimeError(f"normalized audio is unexpectedly small: {normalized}")
            os.replace(normalized, output)
            return
        except Exception:
            temporary.unlink(missing_ok=True)
            output.with_suffix(".normalized.mp3").unlink(missing_ok=True)
            if attempt == retries:
                raise
            await asyncio.sleep(min(3 * attempt, 15))


async def make_double(single: Path, output: Path) -> None:
    if valid_audio(output):
        return
    temporary = output.with_suffix(".concat.mp3")
    temporary.unlink(missing_ok=True)
    await run_process(
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(single),
        "-f", "lavfi", "-t", "0.700", "-i", "anullsrc=r=24000:cl=mono",
        "-filter_complex", "[0:a]asplit=2[first][second];[first][1:a][second]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ar", "24000", "-ac", "1", "-b:a", "96k",
        str(temporary),
    )
    if not valid_audio(temporary):
        raise RuntimeError(f"double audio is unexpectedly small: {temporary}")
    os.replace(temporary, output)


def word_audio_text(row: dict[str, object]) -> str:
    return str(row["reading"]).replace("・", "、").replace("／", "、")


async def generate_card(
    row: dict[str, object],
    output_dir: Path,
    work_dir: Path,
    retries: int,
    semaphore: asyncio.Semaphore,
) -> None:
    card_id = str(row["id"])
    word_x2_name, sentence_x1_name, sentence_x2_name = audio_names(card_id)
    word_x1 = work_dir / f"{card_id}_word_x1.mp3"
    word_x2 = output_dir / word_x2_name
    sentence_x1 = output_dir / sentence_x1_name
    sentence_x2 = output_dir / sentence_x2_name
    if all(valid_audio(path) for path in (word_x2, sentence_x1, sentence_x2)):
        print(f"cached {card_id}", flush=True)
        return
    async with semaphore:
        print(f"generate {card_id}", flush=True)
        if not valid_audio(word_x2):
            await synthesize(word_audio_text(row), word_x1, retries)
            await make_double(word_x1, word_x2)
        sentence_text = str(row.get("sentence_ja", "")).strip() or word_audio_text(row)
        await synthesize(sentence_text, sentence_x1, retries)
        await make_double(sentence_x1, sentence_x2)
        word_x1.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def async_main(args: argparse.Namespace) -> None:
    rows = load_wordlist(args.input)
    selected = select_shard(rows, args.shard_index, args.shard_count, args.limit)
    print(
        f"selected {len(selected)} cards: {selected[0]['id']}–{selected[-1]['id']} "
        f"(shard {args.shard_index + 1}/{args.shard_count})",
        flush=True,
    )
    if args.plan_only:
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = args.work_dir or args.output_dir.parent / f"work-shard-{args.shard_index:02d}"
    work_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(args.concurrency)
    await asyncio.gather(*(
        generate_card(row, args.output_dir, work_dir, args.retries, semaphore)
        for row in selected
    ))

    entries = []
    for row in selected:
        card_id = str(row["id"])
        files = []
        for name in audio_names(card_id):
            path = args.output_dir / name
            if not valid_audio(path):
                raise RuntimeError(f"missing or invalid audio: {path}")
            files.append({"name": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
        entries.append({"id": card_id, "files": files})
    manifest = {
        "version": 1,
        "voice": VOICE,
        "rate": RATE,
        "sample_rate_hz": 24000,
        "channels": 1,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "card_count": len(selected),
        "first_id": selected[0]["id"],
        "last_id": selected[-1]["id"],
        "entries": entries,
    }
    manifest_path = args.output_dir / f"audio_manifest_shard_{args.shard_index:02d}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.keep_work:
        shutil.rmtree(work_dir, ignore_errors=True)
    print(f"created {len(entries) * 3} audio files and {manifest_path.name}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/n3/wordlist.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/n3-audio"))
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
