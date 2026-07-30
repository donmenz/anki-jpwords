---
name: build-japanese-anki-apkg
description: Build, rebuild, download, audit, and safely clean up the complete JLPT N3 Anki APKG workflow in this repository, including staging temporary wordlist data, replaying translation corrections, validating all 3400 source-grounded entries, running GitHub Actions Edge TTS, verifying the final deck, and deleting repository wordlist data only after explicit user confirmation. Use when asked to generate, regenerate, publish, troubleshoot, download, validate, or clean up this project's N3 APKG workflow; do not use for general Anki advice or unrelated decks.
---

# Build Japanese Anki APKG

Deliver a complete, source-faithful N3 deck. Treat a sample deck, a successful TTS probe, or matching file counts as intermediate evidence rather than final delivery.

Before a full build or APKG audit, read [references/quality-gates.md](references/quality-gates.md).

## Establish the current state

1. Confirm that the current repository is `donmenz/anki-jpwords` or contains the expected files from the quality-gates reference.
2. Read `README.md` and any current `HANDOFF*.md` available in the workspace.
3. Inspect `git status -sb`, the active branch, the remote, and the latest commit before changing anything.
4. Preserve unrelated user changes. Never stage, overwrite, or discard them silently.
5. Treat GitHub `main` as the build-code truth. Expect the default repository tree to contain no complete wordlist data after a finished delivery.
6. If build data is present, treat `data/n3/wordlist_original.json` as immutable extracted source data and `data/n3/wordlist.json` as generated build data.

## Choose the smallest workflow

- For a new build in a clean repository, stage the user-provided source data in the temporary paths from the quality-gates reference before running any generator.
- For a translation correction, update `review/n3_translation_corrections.json`, replay corrections, validate the wordlist, and review the generated diff.
- For a template or TTS change, run or inspect the four-card sample path before authorizing a full build.
- For a full build with no code change, validate the current `main`, dispatch the full workflow, monitor it to completion, download the artifact, and validate it locally.
- For an existing successful run, skip generation and proceed to artifact download and final validation.
- For diagnosis only, inspect and report the failure cause. Do not implement or rerun unless the user requested a fix or completion.
- For cleanup after a completed build, require explicit user confirmation before deleting any repository data.

## Prepare source data

1. Place the user's extracted source at `data/n3/wordlist_original.json` and structured corrections at `review/n3_translation_corrections.json`. Use an empty JSON array for corrections when none exist.
2. Add corrections with the reviewed translation, reason, category, severity, and source.
3. Do not replace original translations or examples merely to hide a correction.
4. Never fabricate an example for a row whose source has no example. Keep it explicitly marked as source-missing.
5. Replay and validate:

```bash
python scripts/apply_translation_corrections.py
python scripts/validate_wordlist.py
```

6. Review changes to the corrected JSON, CSV, errata files, and any generated workbook. Confirm that mutable correction counts are internally consistent; do not assume the historical count is permanent.

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

## Remove repository wordlist data after confirmation

Treat cleanup as a separate destructive phase after successful delivery.

1. Show the user the delivered APKG path, checksum, validation result, and the exact tracked data paths proposed for deletion.
2. Ask for explicit confirmation that the APKG is accepted and the repository data may be removed. Do not infer confirmation from silence, a successful Action, or a prior request to generate the deck.
3. Until confirmation arrives, preserve the repository data so the build remains reproducible.
4. After confirmation, delete only tracked wordlist-bearing paths such as:
   - `data/n3/wordlist_original.json`
   - `data/n3/wordlist.json`
   - `data/n3/wordlist.csv`
   - `review/n3_translation_corrections.json`
   - `review/n3_translation_errata.csv`
   - wordlist workbooks under `artifacts/`
5. Preserve scripts, templates, the Skill, workflows, and validated files in the user's external delivery directory.
6. Review the deletion diff, commit it on a scoped branch, publish it through a PR, and merge only when authorized.
7. Verify the target branch no longer tracks wordlist-bearing files.
8. State that a normal deletion commit removes data from the current tree but not from Git history. Never rewrite history without separate explicit authorization after explaining clone, fork, tag, release, and force-push impact.

## Report completion

Lead with whether the complete deck is ready. Include:

- clickable APKG and workbook paths;
- note, card, and media counts;
- APKG size and SHA-256;
- voice and audio settings;
- source-example and source-missing counts;
- confirmed correction count, clearly described as confirmed rather than exhaustive;
- GitHub PR, merge commit, and full workflow URL when publication occurred;
- whether repository wordlist cleanup is pending confirmation or completed;
- any remaining real-device Anki import or interaction check.

State incomplete boundaries plainly. A structurally valid APKG is not proof that every translation has received exhaustive human review.
