# Build Japanese Anki APKG Skill

这个仓库以可复用的 Codex / ChatGPT Skill 为核心，可把任意日语词书制作成带 Edge TTS 音频、经过结构验收的 Anki `.apkg`。词书名称、卡片数量、ID、牌组身份、音色和输出文件名都由本次构建的配置决定。

仓库平时只保存 Skill、脚本、三阶段听辨模板和 GitHub Actions，不长期保存词表、原书例句、翻译勘误、音频或 APKG。

## 使用 Skill

在包含本仓库的 Codex 任务中输入：

```text
$build-japanese-anki-apkg
```

ChatGPT 桌面端也可以在 **Skills** 侧栏找到 **Build Japanese Anki APKG**，或在聊天框使用 `@` 选择它。

Skill 文件位于 `.agents/skills/build-japanese-anki-apkg/`。

## 它会完成什么

1. 接收词书、例句与翻译修订，保留原始内容和人工修订的来源关系。
2. 为本次词书建立 `data/deck-config.json`，再生成并验证标准词表。
3. 先生成少量音频用于检查，再由 GitHub Actions 动态分片生成全量音频。
4. 构建并验证 APKG 的卡片数、字段、牌组身份及每张卡的三个媒体文件。
5. 将 APKG 和对应配置保存到仓库外的持久目录。
6. 等待用户实际导入确认；只有用户明确同意后，才删除仓库里的临时词表数据并提交清理改动。

任何原书没有例句的词条都会保留 `has_original_sentence: false`，卡片界面明确显示“原书未提供例句”；脚本不会为了填满字段而伪造句子。

## 临时构建数据

构建期间使用：

```text
data/deck-config.json
data/source.json
data/corrections.json
data/wordlist.json
data/wordlist.csv
data/errata.csv
data/wordlist.xlsx       # 可选
```

这些文件可以为了 GitHub Actions 构建而临时进入仓库，但不是长期内容。手动触发 Action 时缺少配置或词表会明确失败；清理 PR 中没有数据时，Action 只确认仓库已回到无词表状态。

普通删除提交只会从当前分支移除数据，历史提交仍可能含有旧版本。永久擦除 Git 历史必须单独评估并取得明确授权。

## 每本词书的配置

`data/deck-config.json` 是本次牌组的身份凭据。示例：

```json
{
  "source_title": "示例日语词书",
  "id_prefix": "sample",
  "id_width": 4,
  "expected_total": 1200,
  "expected_original_examples": 1080,
  "expected_unit_counts": {"上册": 600, "下册": 600},
  "model_id": 1889931025,
  "deck_id": 1889931026,
  "model_name": "示例日语词书 · 三阶段听辨",
  "deck_name": "日语词书::示例日语词书",
  "guid_prefix": "sample-wordbook-edge-tts-v1",
  "tag_prefix": "SampleWordbook",
  "output_filename": "示例日语词书-EdgeTTS.apkg",
  "artifact_name": "sample-wordbook-apkg",
  "voice": "ja-JP-NanamiNeural",
  "rate": "-10%",
  "volume": "+0%",
  "pitch": "+0Hz",
  "sample_rate_hz": 24000,
  "channels": 1,
  "bit_rate_kbps": 96
}
```

`expected_original_examples` 和 `expected_unit_counts` 可以省略；其余身份字段用于保证同一本词书重建时仍能稳定更新原卡片。

## 构建组件

- `.github/workflows/generate-apkg.yml`：样本音频和全量 APKG 工作流。
- `scripts/apply_translation_corrections.py`：重放结构化翻译修订。
- `scripts/validate_wordlist.py`：按词书配置验证词表。
- `scripts/generate_audio.py` / `scripts/validate_audio.py`：生成和逐个检查 MP3。
- `scripts/build_apkg.py` / `scripts/validate_apkg.py`：构建和验收最终牌组。
- `templates/`：三阶段听辨卡片模板。

每张卡固定引用 `word_x2`、`sentence_x1`、`sentence_x2` 三个 MP3；总卡片数、媒体数、分片数、牌组名和 Action 制品名全部动态计算。详细规则见 `.agents/skills/build-japanese-anki-apkg/references/quality-gates.md`。
