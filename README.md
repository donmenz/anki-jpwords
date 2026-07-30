# Build Japanese Anki APKG Skill

这个仓库以可复用的 Codex / ChatGPT Skill 为核心，指导代理把经过校验的日语词表转换为带 Edge TTS 音频的 Anki `.apkg`，监控 GitHub Actions 全量构建，下载并验收成品，并在用户确认交付后清理仓库中的词表数据。

仓库默认只保存：

- Skill 工作流与质量门槛；
- APKG、音频和数据校验脚本；
- 三阶段听辨卡片模板；
- GitHub Actions 构建流程。

仓库默认不保存完整词表、原书例句、翻译勘误、生成音频或 APKG 成品。

## 使用 Skill

在包含本仓库的 Codex 任务中输入：

```text
$build-japanese-anki-apkg
```

ChatGPT 桌面端也可以在 **Skills** 侧栏找到 **Build Japanese Anki APKG**，或在聊天框使用 `@` 选择它。

Skill 文件位于：

```text
.agents/skills/build-japanese-anki-apkg/
├── SKILL.md
├── agents/openai.yaml
└── references/quality-gates.md
```

## Skill 覆盖的流程

1. 接收并核对用户提供的词表、原书例句和翻译修订。
2. 保留原始数据与修订数据的来源关系，禁止用模板句冒充原书例句。
3. 在构建期间将数据临时放入约定目录。
4. 重放修订并验证完整词表。
5. 先通过样卡检查模板与 TTS。
6. 在 GitHub Actions 中分片生成全量 Edge TTS 音频并构建 APKG。
7. 下载 APKG，验证卡片、媒体、字段、代表性勘误和音频编码。
8. 将验收后的 APKG 保存到用户指定的持久化目录。
9. 等待用户明确确认成品可用。
10. 仅在用户确认后，从仓库当前分支删除词表、勘误和含词条的工作簿，并提交清理改动。

## 临时数据约定

构建期间使用以下路径：

```text
data/n3/wordlist_original.json
data/n3/wordlist.json
data/n3/wordlist.csv
review/n3_translation_corrections.json
review/n3_translation_errata.csv
artifacts/*.xlsx
```

这些文件可以为了 GitHub Actions 构建而临时进入仓库，但不是仓库的长期内容。构建脚本不会在数据缺失时伪造默认词条；手动触发全量 Action 而没有 `data/n3/wordlist.json` 会明确失败。清理 PR 删除数据时，Action 只报告仓库已回到无词表状态，不会尝试生成样卡。

普通删除提交只会把数据从当前 `main` 文件树移除，历史提交仍可能包含旧版本。如果需要从 Git 历史永久擦除，必须单独评估影响并取得用户明确授权后再进行历史重写。

## 保留的构建组件

- `.github/workflows/generate-full-n3.yml`：样卡和全量 Edge TTS/APKG 工作流。
- `scripts/apply_translation_corrections.py`：重放结构化翻译修订。
- `scripts/validate_wordlist.py`：验证完整 N3 数据。
- `scripts/generate_n3_audio.py`：生成可恢复音频分片。
- `scripts/validate_n3_audio.py`：逐个检查 MP3。
- `scripts/build_full_apkg.py`：构建全量 APKG。
- `scripts/validate_full_apkg.py`：验证最终牌组。
- `templates/`：三阶段听辨卡片模板。

## 当前 N3 构建契约

- 3400 个连续 ID：`n3_0001`–`n3_3400`
- 3254 条原书例句
- 第 32 单元 146 个原书无例句补充词
- 3400 个笔记、3400 张卡片
- 每张卡 3 个 MP3，共 10200 个媒体文件
- Edge TTS：`ja-JP-NanamiNeural`，语速 `-10%`
- 输出：24 kHz、单声道、96 kbps MP3
- 正式 Action 制品：`n3-0001-3400-edge-tts-apkg`

详细的身份、音频与验收规则以 `.agents/skills/build-japanese-anki-apkg/references/quality-gates.md` 为准。
