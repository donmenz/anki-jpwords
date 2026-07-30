---
name: build-japanese-anki-apkg
description: Turn any Japanese vocabulary book into a source-faithful, audio-enabled Anki APKG. Use when asked to extract or stage a Japanese wordbook, preserve original examples and translation corrections, configure stable deck identity, generate and validate Edge TTS audio, run or troubleshoot the GitHub Actions build, download and audit the completed APKG, or remove temporary repository wordlist data after explicit user acceptance. Do not use for general Anki advice or unrelated decks.
---

# Build Japanese Anki APKG

Deliver a complete, source-faithful deck for the user's chosen Japanese wordbook. Treat a sample, a successful speech probe, or matching file counts as intermediate evidence rather than final delivery.

Before a full build or APKG audit, read [references/quality-gates.md](references/quality-gates.md).

## Establish the current state

1. Confirm that the repository contains this Skill and the scripts named in the quality-gates reference.
2. Read `README.md` and any current `HANDOFF*.md` in the workspace.
3. Inspect the Git status, active branch, remote, and latest commit before changing anything.
4. Preserve unrelated user changes. Never stage, overwrite, or discard them silently.
5. Treat the default branch as the build-code truth. Expect a finished repository tree to contain no wordlist data.
6. If build data is present, treat `data/source.json` as immutable extracted source data and `data/wordlist.json` as generated build data.

## Configure this wordbook

Create `data/deck-config.json` for every new wordbook. Set:

- source title and a filesystem-safe ID prefix;
- numeric ID width and exact expected row count;
- stable model ID, deck ID, model name, deck name, GUID prefix, and tag prefix;
- APKG filename and GitHub artifact name;
- voice, rate, volume, pitch, sample rate, channel count, and bit rate;
- optionally, expected source-example count and per-unit counts.

Keep this configuration stable when rebuilding the same edition. Choose new identity values only when the user wants a separate edition rather than updates to existing notes.

## Prepare source data

1. Place the user's extracted source at `data/source.json` and structured corrections at `data/corrections.json`. Use an empty JSON array when there are no corrections.
2. Keep each correction replayable with its reviewed text, reason, category, severity, and source when known.
3. Never overwrite original translations or examples merely to hide a correction.
4. Never fabricate an example for a row whose source has no example. Set `has_original_sentence` to `false` and keep the example fields empty.
5. Build and validate the reviewed input:

```bash
python scripts/apply_translation_corrections.py
python scripts/validate_wordlist.py
```

6. Review the generated JSON, CSV, errata table, and any optional workbook. Derive correction totals from current data instead of assuming a historical number.

Stop before audio generation if validation fails or source provenance is unresolved.

## Validate a change before full generation

For a code, template, data, or voice change:

1. Run the wordlist validator on the exact build input.
2. Generate a small audio selection with `scripts/generate_audio.py` and validate it with `scripts/validate_audio.py`.
3. Inspect the manifest for voice, rate, ID range, and media count.
4. Probe representative MP3 files and inspect the three-stage card template.
5. If GitHub publication is in scope, publish through a scoped branch and pull request. The pull-request workflow should exercise the sample path.

Do not call a sample artifact the complete deck.

## Run the full GitHub workflow

1. Confirm the intended code and temporary data are present on the default branch.
2. Dispatch `.github/workflows/generate-apkg.yml` with `mode=full`.
3. Record the run URL and ID, then monitor every dynamic audio shard and the package job until completion.
4. Treat an unchanged running state as normal. On failure, inspect the failed job logs and fix only the demonstrated cause.
5. Never substitute fabricated audio or weaken validation to force a green run.

## Download and audit the final artifact

1. Read `artifact_name` and `output_filename` from `data/deck-config.json` and download that artifact from the successful run.
2. Validate the package:

```bash
python scripts/validate_apkg.py --config path/to/deck-config.json --input path/to/wordlist.json "path/to/output.apkg"
shasum -a 256 "path/to/output.apkg"
```

3. Confirm model and deck identity, fields, stable IDs, note/card count, and exactly three expected media names per card.
4. Inspect representative corrected entries and a source-missing entry when present. Keep reviewed text, original text, status, and correction reason distinguishable.
5. Probe representative word and sentence MP3 files.
6. Copy both the validated APKG and its exact `deck-config.json` to the user's durable delivery directory, then verify the copied checksum.

## Remove repository wordlist data after confirmation

Treat cleanup as a separate destructive phase after successful delivery.

1. Show the user the delivered APKG path, checksum, validation result, saved configuration path, and exact tracked paths proposed for deletion.
2. Ask for explicit confirmation that the APKG is accepted and repository data may be removed. Do not infer confirmation from silence, an Action success, or the earlier request to generate the deck.
3. Until confirmation arrives, preserve repository data so the build remains reproducible.
4. After confirmation, delete only tracked temporary build files such as:
   - `data/deck-config.json` after its delivered copy is verified
   - `data/source.json`
   - `data/corrections.json`
   - `data/wordlist.json`
   - `data/wordlist.csv`
   - `data/errata.csv`
   - `data/wordlist.xlsx`
5. Preserve scripts, templates, the Skill, workflows, and the APKG plus configuration in external durable storage.
6. Review the deletion diff, commit it on a scoped branch, publish it through a pull request, and merge only when authorized.
7. Verify the target branch no longer tracks wordlist-bearing files.
8. Explain that an ordinary deletion removes current-tree data but not historical commits. Never rewrite history without separate explicit authorization after describing its impact.

## Report completion

Lead with whether the complete deck is ready. Include:

- clickable APKG and saved configuration paths;
- note, card, source-example, source-missing, and media counts;
- APKG size and SHA-256;
- configured voice and audio settings;
- confirmed correction count, described as confirmed rather than exhaustive;
- GitHub pull request, merge commit, and workflow URL when publication occurred;
- whether repository cleanup is awaiting confirmation or complete;
- any remaining real-device Anki import and interaction check.

State incomplete boundaries plainly. Structural validation does not prove that every translation received exhaustive human review.
