#!/usr/bin/env python3
"""Validate every MP3 in a generated Japanese wordbook audio selection."""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from deck_common import audio_names, load_config, load_wordlist, select_shard


def probe(path: Path) -> tuple[str, int, int, float]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels:format=duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    duration = float(payload["format"]["duration"])
    return path.name, int(stream["sample_rate"]), int(stream["channels"]), duration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("data/deck-config.json"))
    parser.add_argument("--input", type=Path, default=Path("data/wordlist.json"))
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    config = load_config(args.config)
    rows = load_wordlist(args.input, config)
    selected = select_shard(rows, args.shard_index, args.shard_count, args.limit)
    expected = [name for row in selected for name in audio_names(str(row["id"]))]
    actual = sorted(path.name for path in args.audio_dir.glob("*.mp3"))
    if sorted(expected) != actual:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValueError(f"audio filename mismatch; missing={missing[:10]}, extra={extra[:10]}")
    too_small = [name for name in expected if (args.audio_dir / name).stat().st_size <= 1000]
    if too_small:
        raise ValueError(f"audio files are unexpectedly small: {too_small[:10]}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        metadata = list(pool.map(probe, (args.audio_dir / name for name in expected)))
    invalid = [
        item for item in metadata
        if item[1] != int(config["sample_rate_hz"])
        or item[2] != int(config["channels"])
        or item[3] <= 0.2
    ]
    if invalid:
        raise ValueError(f"invalid audio metadata: {invalid[:10]}")
    print(
        f"PASS: {len(selected)} cards, {len(expected)} MP3 files, "
        f"{config['sample_rate_hz']} Hz, {config['channels']} channel(s) "
        f"({selected[0]['id']}–{selected[-1]['id']})"
    )


if __name__ == "__main__":
    main()
