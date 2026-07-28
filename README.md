# anki-jpwords · JLPT N3

This repository contains a complete, reviewable JLPT N3 vocabulary dataset
recovered from 《无敌绿宝书》 and prepared for a later GitHub-based audio and
Anki build.

## Current dataset

- 3,256 continuous cards: `n3_0001` through `n3_3256`
- 31 units
- Every card has a headword, reading, part of speech, Chinese meaning,
  Japanese example sentence, and Chinese example translation
- Example provenance and review status are stored per card
- Audio has **not** been generated for the full dataset yet

Files:

- `data/n3/wordlist.json` — complete dataset
- `data/n3/batches/` — four non-overlapping GitHub-processing batches
- `data/n3/quality_summary.json` — source and review counts
- `artifacts/n3_wordlist_3256.xlsx` — filterable review workbook

## Review status

The dataset is structurally complete, but it is not represented as a fully
human-reviewed edition. The workbook and JSON retain two independent statuses:

- `review_status` for example sentences
- `lexical_review_status` for headword, reading, part of speech, and meaning

Current example sources:

- 1,968 Tatoeba Japanese-Chinese direct pairs
- 601 Tatoeba examples linked through the same English sentence
- 432 examples retained from the source book
- 255 generated fallback examples

Tatoeba indirect pairs, OCR-derived source examples, and generated examples
remain explicitly marked for review before full audio generation.

## Validate the wordlist

No third-party package is required:

```bash
python scripts/validate_wordlist.py
```

The validator checks row count, continuous IDs, required fields, placeholder
sentences, and the four batch boundaries.

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
