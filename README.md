# anki-jpwords · N3 0125-0174

This branch builds a 50-card Anki package for IDs `n3_0125` through `n3_0174`.

## Output

- Deck: `无敌绿宝书::N3（音量增强版）`
- Note type: `无敌绿宝书 · 三阶段听辨（音量增强版）`
- Voice: Microsoft Edge TTS `ja-JP-NanamiNeural`
- Rate: `-10%` (displayed as 0.90×)
- Audio per card:
  - word ×2
  - sentence ×1
  - sentence ×2
- APKG: `dist/无敌绿宝书-N3-0125至0174.apkg`

The model ID and deck ID match the existing 001-124 package, so importing this package appends the next 50 cards to the same note type/deck.

## Build locally

```bash
sudo apt-get install ffmpeg
python -m pip install -r requirements.txt
python scripts/build_apkg.py
python scripts/validate_apkg.py "dist/无敌绿宝书-N3-0125至0174.apkg"
```

## Card flow

1. The sentence audio plays twice without showing text.
2. Click blank space to reveal the Japanese sentence.
3. Click the sentence to replay it once.
4. Click blank space again to reveal the word, reading, part of speech, meaning and reviewed Chinese translation.

Only the transformed 50-card dataset and build code are included here; the source PDF is not stored in the repository.
