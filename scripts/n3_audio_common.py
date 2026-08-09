#!/usr/bin/env python3
"""Shared validation and field mapping for the full N3 audio pipeline."""

from __future__ import annotations

import json
from pathlib import Path


EXPECTED_TOTAL = 3400
AUDIO_SUFFIXES = ("word_x2", "sentence_x1", "sentence_x2")
MODEL_ID = 1889930905
DECK_ID = 1889930906
MODEL_NAME = "无敌绿宝书 · 三阶段听辨（音量增强版）"
DECK_NAME = "无敌绿宝书::N3（音量增强版）"
FIELDS = [
    "ID",
    "Level",
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
REQUIRED_SOURCE_FIELDS = (
    "id",
    "unit",
    "word",
    "reading",
    "part_of_speech",
    "meaning_zh",
    "has_original_sentence",
    "translation_status",
    "translation_note",
)


def load_wordlist(path: Path) -> list[dict[str, object]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("wordlist must be a JSON array")
    if len(rows) != EXPECTED_TOTAL:
        raise ValueError(f"expected {EXPECTED_TOTAL} rows, got {len(rows)}")
    expected_ids = [f"n3_{number:04d}" for number in range(1, EXPECTED_TOTAL + 1)]
    actual_ids = [str(row.get("id", "")) for row in rows]
    if actual_ids != expected_ids:
        raise ValueError("IDs must be continuous from n3_0001 through n3_3400")
    for row in rows:
        missing = [
            field for field in REQUIRED_SOURCE_FIELDS
            if field != "has_original_sentence" and not str(row.get(field, "")).strip()
        ]
        if missing:
            raise ValueError(f"{row.get('id', '<unknown>')} has empty fields: {missing}")
        if not isinstance(row.get("has_original_sentence"), bool):
            raise ValueError(f"{row.get('id', '<unknown>')} has invalid has_original_sentence")
        sentence = str(row.get("sentence_ja", "")).strip()
        if row["has_original_sentence"] and not sentence:
            raise ValueError(f"{row['id']} is missing its original Japanese sentence")
        if not row["has_original_sentence"] and sentence:
            raise ValueError(f"{row['id']} must keep its source-missing sentence empty")
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


def to_anki_fields(row: dict[str, object]) -> dict[str, str]:
    card_id = str(row["id"])
    word_x2, sentence_x1, sentence_x2 = audio_names(card_id)
    return {
        "ID": card_id,
        "Level": str(row["level"]),
        "Unit": str(row["unit"]),
        "BookPage": str(row["book_page"]),
        "PdfPage": str(row["pdf_page"]),
        "Word": str(row["word"]),
        "Reading": str(row["reading"]),
        "PartOfSpeech": str(row["part_of_speech"]),
        "MeaningZh": str(row["meaning_zh"]),
        "SentenceJa": str(row["sentence_ja"]),
        "SentenceZhReviewed": str(row["sentence_zh_reviewed"]),
        "SentenceZhOriginal": str(row["sentence_zh_original"]),
        "TranslationStatus": str(row["translation_status"]),
        "TranslationNote": str(row["translation_note"]),
        "WordAudioX2": f"[sound:{word_x2}]",
        "SentenceAudioX1": f"[sound:{sentence_x1}]",
        "SentenceAudioX2": f"[sound:{sentence_x2}]",
    }
