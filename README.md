# anki-jpwords · N3 归档版音频构建

This temporary build branch generates unit audio from the archived,
source-faithful 3,400-row vocabulary table.

## Current dataset

- 3,400 continuous rows: `n3_0001` through `n3_3400`
- 32 units
- 3,254 original-book examples
- 146 rows explicitly marked as having no example in the source
- Unit audio order: word twice, then example twice
- Source-missing example slots repeat the reading instead of inventing a sentence

Files:

- `data/n3/wordlist.json` — complete dataset
- `.github/workflows/generate-full-n3.yml` — validation, 16 audio shards,
  32 unit MP3 files, and one downloadable ZIP

The archived table retains original and reviewed Chinese text plus correction
status. It does not fill source-missing rows with generated Japanese examples.

## Validate the wordlist

No third-party package is required:

```bash
python scripts/validate_wordlist.py
```

The validator checks row count, continuous IDs, 32 unit counts, required fields,
source-example invariants, and source-missing invariants.

## Generate the complete audio deck on GitHub

The `Generate Full N3 Audio` workflow is deliberately manual for full runs.
It does not commit generated MP3 files to Git. Audio is split into 16 resumable
shards, with at most four shards running in parallel.

1. Open the repository's **Actions** tab.
2. Select **Generate Full N3 Audio**.
3. Choose **Run workflow** on `main`.
4. Run `sample` first (the default, eight cards).
5. After the sample artifact is checked, run again with mode `full`.
6. Download the `n3-3400-unit-audio-zip` artifact after all jobs finish.

Each card produces three 24 kHz mono MP3 files:

- word played twice
- sentence played once
- sentence played twice

The complete run validates all 10,200 card-level MP3 files, builds 32 unit MP3
files, and packages them as `N3-3400词-32单元音频.zip`. Successful shards are
cached, so a later rerun can reuse completed audio for the same wordlist.

Generated artifacts are retained for 14 days. The workflow uses Microsoft
Edge TTS (`ja-JP-NanamiNeural`, rate `-10%`) and therefore requires outbound
network access from the GitHub runner.

## Legacy 50-card Anki build

The earlier `n3_0125`–`n3_0174` build remains available for reference:

```bash
sudo apt-get install ffmpeg
python -m pip install -r requirements.txt
python scripts/build_apkg.py
python scripts/validate_apkg.py "dist/无敌绿宝书-N3-0125至0174.apkg"
```

The source PDF and generated audio are not stored in this repository.

## Data sources

- Source book pages: vocabulary, readings, parts of speech, meanings, and
  original examples
- Tatoeba downloads: <https://tatoeba.org/en/downloads>
- OpenCC: <https://github.com/BYVoid/OpenCC>
