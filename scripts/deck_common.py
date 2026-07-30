#!/usr/bin/env python3
"""Shared configuration, validation, and field mapping for a Japanese wordbook."""

from __future__ import annotations

import json
import re
from pathlib import Path


AUDIO_SUFFIXES = ("word_x2", "sentence_x1", "sentence_x2")
FIELDS = [
    "ID",
    "SourceTitle",
    "Unit",
    "BookPage",
    "PdfPage",
    "Word",
    "Reading",
    "PartOfSpeech",
    "MeaningZh",
    "SentenceJa",
    "SentenceZhReviewed",
    "SentenceZhOriginal",
    "TranslationStatus",
    "TranslationNote",
    "WordAudioX2",
    "SentenceAudioX1",
    "SentenceAudioX2",
]
REQUIRED_CONFIG_FIELDS = (
    "source_title",
    "id_prefix",
    "id_width",
    "expected_total",
    "model_id",
    "deck_id",
    "model_name",
    "deck_name",
    "guid_prefix",
    "tag_prefix",
    "output_filename",
    "artifact_name",
)
REQUIRED_WORD_FIELDS = (
    "id",
    "word",
    "reading",
    "meaning_zh",
    "translation_status",
    "translation_note",
    "has_original_sentence",
)
CONFIG_DEFAULTS = {
    "voice": "ja-JP-NanamiNeural",
    "rate": "-10%",
    "volume": "+0%",
    "pitch": "+0Hz",
    "sample_rate_hz": 24000,
    "channels": 1,
    "bit_rate_kbps": 96,
}


def load_config(path: Path) -> dict[str, object]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("deck config must be a JSON object")
    config = {**CONFIG_DEFAULTS, **config}
    missing = [field for field in REQUIRED_CONFIG_FIELDS if not str(config.get(field, "")).strip()]
    if missing:
        raise ValueError(f"deck config has empty fields: {missing}")
    prefix = str(config["id_prefix"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
        raise ValueError("id_prefix may contain only letters, digits, hyphens, and underscores")
    for field in ("id_width", "expected_total", "model_id", "deck_id", "sample_rate_hz", "channels", "bit_rate_kbps"):
        value = int(config[field])
        if value < 1:
            raise ValueError(f"{field} must be a positive integer")
        config[field] = value
    if int(config["id_width"]) < len(str(config["expected_total"])):
        raise ValueError("id_width is too small for expected_total")
    if not str(config["output_filename"]).endswith(".apkg") or Path(str(config["output_filename"])).name != str(config["output_filename"]):
        raise ValueError("output_filename must be a plain .apkg filename")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", str(config["artifact_name"])):
        raise ValueError("artifact_name may contain only letters, digits, periods, hyphens, and underscores")
    expected_unit_counts = config.get("expected_unit_counts")
    if expected_unit_counts is not None:
        if not isinstance(expected_unit_counts, dict) or not expected_unit_counts:
            raise ValueError("expected_unit_counts must be a non-empty object when supplied")
        config["expected_unit_counts"] = {
            str(key): int(value) for key, value in expected_unit_counts.items()
        }
        if any(value < 1 for value in config["expected_unit_counts"].values()):
            raise ValueError("expected_unit_counts values must be positive integers")
    if config.get("expected_original_examples") is not None:
        config["expected_original_examples"] = int(config["expected_original_examples"])
        if not 0 <= config["expected_original_examples"] <= config["expected_total"]:
            raise ValueError("expected_original_examples is outside the valid range")
    return config


def expected_ids(config: dict[str, object]) -> list[str]:
    prefix = str(config["id_prefix"])
    width = int(config["id_width"])
    total = int(config["expected_total"])
    return [f"{prefix}_{number:0{width}d}" for number in range(1, total + 1)]


def load_wordlist(path: Path, config: dict[str, object]) -> list[dict[str, object]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("wordlist must be a JSON array")
    expected = expected_ids(config)
    if len(rows) != len(expected):
        raise ValueError(f"expected {len(expected)} rows, got {len(rows)}")
    actual_ids = [str(row.get("id", "")) for row in rows]
    if actual_ids != expected:
        raise ValueError(f"IDs must be continuous from {expected[0]} through {expected[-1]}")
    for row in rows:
        missing = [field for field in REQUIRED_WORD_FIELDS if field not in row]
        if missing:
            raise ValueError(f"{row.get('id', '<unknown>')} is missing fields: {missing}")
        empty = [
            field for field in REQUIRED_WORD_FIELDS
            if field != "has_original_sentence" and not str(row.get(field, "")).strip()
        ]
        if empty:
            raise ValueError(f"{row.get('id', '<unknown>')} has empty fields: {empty}")
        if not isinstance(row["has_original_sentence"], bool):
            raise ValueError(f"{row['id']} has_original_sentence must be a JSON boolean")
        if row["has_original_sentence"] and not str(row.get("sentence_ja", "")).strip():
            raise ValueError(f"{row['id']} has no Japanese source example")
        if "习题：" in str(row.get("sentence_ja", "")) or "解析：" in str(row.get("sentence_ja", "")):
            raise ValueError(f"{row['id']} still contains exercise commentary")
    return rows


def select_shard(
    rows: list[dict[str, object]],
    shard_index: int,
    shard_count: int,
    limit: int | None = None,
) -> list[dict[str, object]]:
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be between 0 and shard_count - 1")
    start = len(rows) * shard_index // shard_count
    end = len(rows) * (shard_index + 1) // shard_count
    selected = rows[start:end]
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        selected = selected[:limit]
    if not selected:
        raise ValueError("selected shard is empty")
    return selected


def audio_names(card_id: str) -> tuple[str, str, str]:
    return tuple(f"{card_id}_{suffix}.mp3" for suffix in AUDIO_SUFFIXES)  # type: ignore[return-value]


def word_audio_text(row: dict[str, object]) -> str:
    return str(row["reading"]).replace("・", "、").replace("／", "、")


def sentence_audio_text(row: dict[str, object]) -> str:
    sentence = str(row.get("sentence_ja", "")).strip()
    return sentence or word_audio_text(row)


def to_anki_fields(row: dict[str, object], config: dict[str, object]) -> dict[str, str]:
    card_id = str(row["id"])
    word_x2, sentence_x1, sentence_x2 = audio_names(card_id)
    return {
        "ID": card_id,
        "SourceTitle": str(config["source_title"]),
        "Unit": str(row.get("unit", "")),
        "BookPage": str(row.get("book_page", "")),
        "PdfPage": str(row.get("pdf_page", "")),
        "Word": str(row["word"]),
        "Reading": str(row["reading"]),
        "PartOfSpeech": str(row.get("part_of_speech", "")),
        "MeaningZh": str(row["meaning_zh"]),
        "SentenceJa": str(row.get("sentence_ja", "")),
        "SentenceZhReviewed": str(row.get("sentence_zh_reviewed", "")),
        "SentenceZhOriginal": str(row.get("sentence_zh_original", "")),
        "TranslationStatus": str(row["translation_status"]),
        "TranslationNote": str(row["translation_note"]),
        "WordAudioX2": f"[sound:{word_x2}]",
        "SentenceAudioX1": f"[sound:{sentence_x1}]",
        "SentenceAudioX2": f"[sound:{sentence_x2}]",
    }
