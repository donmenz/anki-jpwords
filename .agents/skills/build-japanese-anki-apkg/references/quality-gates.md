# N3 APKG Quality Gates

Read this reference before starting a full build, auditing a downloaded APKG, or changing the data contract.

## Repository-at-rest policy

The default finished repository contains the Skill, scripts, templates, and workflow, but no complete wordlist, example-sentence dataset, correction dataset, wordlist workbook, generated audio, or APKG.

During a build, wordlist-bearing files may be temporarily committed so GitHub Actions can read them. After the final APKG is validated and copied to durable storage, keep those files until the user explicitly confirms acceptance. Then remove them in a separate reviewed commit.

An ordinary Git deletion removes files from the current tree, not from historical commits. Treat history rewriting as a separate high-impact operation requiring separate explicit authorization.

## Temporary build files

- `data/n3/wordlist_original.json`: immutable clean-PDF extraction.
- `data/n3/wordlist.json`: corrected build input generated from the original plus structured corrections.
- `data/n3/wordlist.csv`: reviewable full table.
- `review/n3_translation_corrections.json`: replayable correction source.
- `review/n3_translation_errata.csv`: human-readable correction table.
- `artifacts/*.xlsx`: optional generated wordlist and errata workbooks.
- `templates/front.html`, `templates/back.html`, `templates/style.css`: three-stage listening card.
- `.github/workflows/generate-full-n3.yml`: sample and full Edge TTS workflow.

These paths are inputs and derived data during a build, not permanent repository content. The old 3256-card OCR data and its template fallback examples are not authoritative. Do not revive or publish them as the final deck.

## Stable data invariants

- Exactly 3400 rows with continuous IDs `n3_0001` through `n3_3400`.
- Exactly 32 units with the per-unit counts enforced by `scripts/validate_wordlist.py`.
- Exactly 3254 source examples.
- Exactly 146 Unit 32 supplement words without source examples.
- No source-missing row outside Unit 32.
- No exercise commentary such as `习题：` or `解析：` embedded in Japanese example fields.
- Preserve original and reviewed Chinese translations as separate fields.
- Never synthesize a sentence merely to satisfy a non-empty-field check.

Correction totals and status counts may grow as human review continues. Derive them from the current structured corrections and wordlist rather than hardcoding the historical total.

## Stable Anki contract

- Model ID: `1889930925`.
- Deck ID: `1889930926`.
- Deck name: `无敌绿宝书::N3（清晰PDF·Edge TTS版）`.
- GUID seed prefix: `n3-clean-pdf-edge-tts-v1`.
- One note and one card per word: 3400 notes and 3400 cards.
- Seventeen fields as defined by `scripts/n3_audio_common.py`.
- Three media references per card: `word_x2`, `sentence_x1`, and `sentence_x2`.
- Total media files: 10200.

Keep the model, deck, GUID seed, and row IDs stable for rebuilds of this edition. Change them only when the user explicitly wants a separate edition that must not update existing notes.

## Stable audio contract

- Voice: Microsoft Edge TTS `ja-JP-NanamiNeural`.
- Rate: `-10%`.
- Pitch and Edge volume: unchanged defaults.
- Post-processing: FFmpeg `loudnorm=I=-16:TP=-1.0:LRA=11`.
- Output: MP3, 24000 Hz, mono, 96000 bit/s.
- Word audio: reading twice, with 0.7 seconds of silence between repetitions.
- Sentence audio: source Japanese sentence once and twice.
- Source-missing rows: sentence slots reuse the word reading, while the data and card UI continue to say that the source supplied no example.
- Full generation: 16 resumable shards, bounded parallelism, five retries per synthesis request.

Edge TTS is an online dependency. A transient missing-audio response is a failure to retry or diagnose, not permission to create placeholder media.

## GitHub workflow contract

- Workflow name: `Generate Full N3 Audio`.
- Pull requests exercise a four-card sample path.
- Full builds must run on `main` with `mode=full`.
- Full artifact: `n3-0001-3400-edge-tts-apkg`.
- Final filename: `无敌绿宝书-N3-3400词-EdgeTTS.apkg`.
- GitHub artifact retention is finite; keep a validated copy in the durable delivery directory.

## Minimum final evidence

Require all of the following before reporting completion:

1. `scripts/validate_wordlist.py` passes on the exact build input.
2. All 16 audio shards succeed.
3. The package job confirms exactly 10200 MP3 files before packaging.
4. `scripts/validate_full_apkg.py` reports 3400 notes, 3400 cards, and 10200 media files.
5. The final file has a recorded byte size and SHA-256.
6. Representative MP3 files parse as 24 kHz mono MP3.
7. Representative corrected entries retain both original and reviewed translations plus the correction reason.
8. A Unit 32 source-missing row retains its explicit status and does not present generated text as an original example.
9. The delivered copy has the same checksum as the downloaded validated artifact.

Manual import and interaction checks in the user's actual Anki client remain a separate experience-level acceptance step; report them as pending until performed.

## Cleanup evidence after user confirmation

Require all of the following before reporting repository cleanup complete:

1. The user explicitly confirmed acceptance of the delivered APKG and authorized repository-data deletion.
2. The exact deletion list was shown before removal.
3. The APKG and any user-requested workbook remain in durable storage outside the repository.
4. `git diff --cached --name-status` or the final commit shows only the intended data removal and related documentation/workflow updates.
5. The target branch no longer tracks files under `data/`, `review/`, or wordlist-bearing files under `artifacts/`.
6. Scripts, templates, workflows, and `.agents/skills/build-japanese-anki-apkg/` remain present.
7. The user is told that historical commits still retain prior data unless a separately authorized history rewrite is performed.
