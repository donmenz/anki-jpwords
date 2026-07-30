# Japanese Wordbook APKG Quality Gates

Read this reference before starting a full build, auditing a downloaded APKG, or changing the data contract.

## Repository-at-rest policy

The finished repository contains the Skill, scripts, templates, and workflow, but no complete wordlist, example-sentence dataset, correction dataset, wordlist workbook, generated audio, or APKG.

Build data may be committed temporarily so GitHub Actions can read it. After the final APKG and matching configuration are validated and copied to durable storage, keep the temporary files until the user explicitly confirms acceptance. Remove them only in a separate reviewed commit.

An ordinary Git deletion removes files from the current tree, not from historical commits. History rewriting is a separate high-impact operation that requires separate explicit authorization.

## Temporary build files

- `data/deck-config.json`: identity, expected counts, audio settings, and output names for one wordbook edition.
- `data/source.json`: immutable source extraction.
- `data/corrections.json`: replayable human corrections.
- `data/wordlist.json`: corrected APKG input.
- `data/wordlist.csv`: reviewable full table.
- `data/errata.csv`: human-readable correction table.
- `data/wordlist.xlsx`: optional review workbook.
- `templates/front.html`, `templates/back.html`, `templates/style.css`: three-stage listening card.
- `.github/workflows/generate-apkg.yml`: sample-audio and full-package workflow.

These paths are temporary inputs or derived data, not permanent repository content. Do not revive older OCR output or fallback examples as authoritative material.

## Configuration invariants

Require `source_title`, `id_prefix`, `id_width`, `expected_total`, model/deck IDs and names, GUID/tag prefixes, output filename, and artifact name. The ID prefix must be safe for media filenames; the artifact name must be safe for GitHub Actions.

The voice defaults to `ja-JP-NanamiNeural`, rate to `-10%`, sample rate to 24000 Hz, one channel, and 96 kbps, but every value is configuration-driven. Optional `expected_original_examples` and `expected_unit_counts` strengthen source-specific validation without making the Skill depend on one book's structure.

Keep the configuration with the delivered APKG. Reuse its identity values when rebuilding the same edition so Anki can update stable notes rather than create an accidental duplicate deck.

## Wordlist invariants

- Row count equals `expected_total`.
- IDs are continuous from one through `expected_total`, using the configured prefix and width.
- Every row has a word, reading, Chinese meaning, translation status, translation note, and a real JSON boolean `has_original_sentence`.
- A source-example row has a non-empty Japanese sentence.
- A source-missing row may occur in any unit and keeps the sentence empty; the card UI states that the original book supplied no example.
- Original and reviewed Chinese translations remain separate fields.
- Exercise commentary such as `习题：` or `解析：` does not leak into example fields.
- The set of corrected row IDs exactly matches `data/corrections.json`.
- Optional source-example and per-unit totals match the configuration when supplied.
- Never synthesize a sentence merely to satisfy a non-empty-field check.

Correction totals and status counts may grow as review continues. Derive them from the current structured corrections and wordlist.

## Anki contract

- Model ID, deck ID, names, and GUID seed come from the configuration.
- One note and one card are produced for every validated row.
- Seventeen fields are defined by `scripts/deck_common.py`; the second field is the source title rather than a proficiency label.
- Every card has three media references: `word_x2`, `sentence_x1`, and `sentence_x2`.
- Expected media count is `expected_total × 3`.
- Tags contain the configured book prefix, translation status, example provenance, and an optional unit tag.

## Audio contract

- Edge voice, rate, pitch, volume, sample rate, channels, and bit rate come from the configuration.
- FFmpeg applies `loudnorm=I=-16:TP=-1.0:LRA=11`.
- Word audio plays the reading twice with 0.7 seconds of silence between repetitions.
- Sentence audio plays the source Japanese sentence once and twice.
- When the source has no example, sentence slots reuse the word reading while data and UI continue to mark the example as missing.
- Full generation uses up to 16 non-empty resumable shards, bounded parallelism, and five synthesis retries.

Edge TTS is an online dependency. A transient missing-audio response is a failure to retry or diagnose, not permission to create placeholder media.

## GitHub workflow contract

- Workflow file: `.github/workflows/generate-apkg.yml`.
- Pull requests exercise a small audio sample when temporary wordlist data exists.
- Full builds run from the default branch with `mode=full`.
- Shard count is the smaller of 16 and the configured card count.
- Media, manifest, filename, and artifact expectations are calculated from the configuration.
- The final artifact includes both the APKG and its `deck-config.json`.
- GitHub artifact retention is finite; keep a validated copy in durable storage.

## Minimum final evidence

Require all of the following before reporting completion:

1. `scripts/validate_wordlist.py` passes on the exact build input and configuration.
2. Every planned audio shard succeeds.
3. The package job confirms the configured card count times three MP3 files and one manifest per shard.
4. `scripts/validate_apkg.py` confirms note/card count, identity, fields, IDs, and exact media names.
5. The final file has a recorded byte size and SHA-256.
6. Representative MP3 files match the configured sample rate and channel count.
7. Representative corrected entries retain original and reviewed text plus the correction reason.
8. A source-missing row, when present, retains its explicit status and does not present generated text as an original example.
9. The delivered copy has the same checksum as the downloaded validated artifact.
10. The exact configuration used to build the APKG is saved beside it.

Manual import and interaction checks in the user's actual Anki client remain a separate experience-level acceptance step; report them as pending until performed.

## Cleanup evidence after user confirmation

Require all of the following before reporting repository cleanup complete:

1. The user explicitly confirmed acceptance of the delivered APKG and authorized repository-data deletion.
2. The exact deletion list was shown before removal.
3. The APKG and its configuration remain in durable storage outside the repository.
4. The staged diff or final commit shows only intended data removal and related maintenance changes.
5. The target branch no longer tracks temporary build files under `data/` or other output directories.
6. Scripts, templates, workflows, and `.agents/skills/build-japanese-anki-apkg/` remain present.
7. The user is told that historical commits still retain prior data unless a separately authorized history rewrite is performed.
