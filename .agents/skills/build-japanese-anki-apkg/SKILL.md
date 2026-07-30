---
name: build-japanese-anki-apkg
description: Build, rebuild, download, or audit the complete JLPT N3 Anki APKG in this repository, including replaying translation corrections, validating all 3400 source-grounded entries, running and monitoring the GitHub Actions Edge TTS pipeline, and verifying the final deck and audio. Use when asked to generate, regenerate, publish, troubleshoot, download, or validate this project's N3 APKG or full audio workflow; do not use for general Anki advice or unrelated decks.
---

# Build Japanese Anki APKG

Deliver a complete, source-faithful N3 deck. Treat a sample deck, a successful TTS probe, or matching file counts as intermediate evidence rather than final delivery.

Before a full build or APKG audit, read [references/quality-gates.md](references/quality-gates.md).

## Establish the current state

1. Confirm that the current repository is `donmenz/anki-jpwords` or contains the expected files from the quality-gates reference.
2. Read `README.md` and any current `HANDOFF*.md` available in the workspace.
3. Inspect `git status -sb`, the active branch, the remote, and the latest commit before changing anything.
4. Preserve unrelated user changes. Never stage, overwrite, or discard them silently.
5. Treat GitHub `main` as the build-code truth. Treat `data/n3/wordlist_original.json` as immutable extracted source data and `data/n3/wordlist.json` as generated build data.

## Choose the smallest workflow

- For a translation correction, update `review/n3_translation_corrections.json`, replay corrections, validate the wordlist, and review the generated diff.
- For a template or TTS change, run or inspect the four-card sample path before authorizing a full build.
- For a full build with no code change, validate the current `main`, dispatch the full workflow, monitor it to completion, download the artifact, and validate it locally.
- For an existing successful run, skip generation and proceed to artifact download and final validation.
- For diagnosis only, inspect and report the failure cause. Do not implement or rerun unless the user requested a fix or completion.

## Prepare source data

1. Add structured corrections to `review/n3_translation_corrections.json`; include the reviewed translation, reason, category, severity, and source.
2. Do not replace original translations or examples merely to hide a correction.
3. Never fabricate an example for a row whose source has no example. Keep it explicitly marked as source-missing.
4. Replay and validate:

```bash
python scripts/apply_translation_corrections.py
python scripts/validate_wordlist.py
```

5. Review changes to the corrected JSON, CSV, errata files, and workbook. Confirm that mutable correction counts are internally consistent; do not assume the historical count is permanent.

Stop before audio generation if wordlist validation fails or source provenance is unresolved.

## Validate a change before full generation

For a code, template, or TTS change:

1. Publish the scoped change through a branch and pull request when the user authorized GitHub publication.
2. Let the pull-request workflow build its four-card sample.
3. Confirm that the sample job succeeds and inspect its manifest for the intended voice, rate, ID range, and media count.
4. Probe representative MP3 files with `ffprobe` and confirm the required encoding.
5. Inspect the sample APKG with the repository validator.

Do not call a sample artifact the full deck.

## Run the full GitHub workflow

1. Confirm that the intended change is present on GitHub `main`.
2. Dispatch the `Generate Full N3 Audio` workflow on `main` with `mode=full`.
3. Record the run URL and ID.
4. Monitor the run until every audio shard and `build-package` completes. Provide concise progress updates during long runs.
5. Treat an unchanged running state as normal. Do not stop monitoring merely because generation is slow.
6. On failure, inspect the failed job logs. Fix only the demonstrated cause, validate the change, publish it through the normal GitHub flow, and rerun when completion was requested.
7. Never bypass external-disclosure policy, substitute fabricated audio, or weaken validation to force a green run.

## Download and audit the final artifact

1. Download artifact `n3-0001-3400-edge-tts-apkg` from the successful full run to a writable output directory.
2. Run:

```bash
python scripts/validate_full_apkg.py "path/to/无敌绿宝书-N3-3400词-EdgeTTS.apkg"
shasum -a 256 "path/to/无敌绿宝书-N3-3400词-EdgeTTS.apkg"
```

3. Inspect the APKG database and media mapping to confirm the model, deck, fields, stable IDs, expected note/card counts, and expected media count.
4. Inspect representative corrected entries and one source-missing entry. Confirm that reviewed translations, original translations, status, and notes remain distinguishable.
5. Probe representative word, sentence, and source-missing fallback MP3 files with `ffprobe`.
6. Copy the validated APKG and current workbook to the user's durable delivery directory only when that destination is in scope. Verify the copied checksum.

## Report completion

Lead with whether the complete deck is ready. Include:

- clickable APKG and workbook paths;
- note, card, and media counts;
- APKG size and SHA-256;
- voice and audio settings;
- source-example and source-missing counts;
- confirmed correction count, clearly described as confirmed rather than exhaustive;
- GitHub PR, merge commit, and full workflow URL when publication occurred;
- any remaining real-device Anki import or interaction check.

State incomplete boundaries plainly. A structurally valid APKG is not proof that every translation has received exhaustive human review.
