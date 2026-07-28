# anki-jpwords · JLPT N3 3400 词

本仓库以清晰版《无敌绿宝书》PDF 为底稿，保存完整 N3 词表、原书例句、中文翻译勘误，以及通过 GitHub Actions 生成 Edge TTS 全量 Anki 卡组的流程。

## 当前数据

- 3400 个连续词条：`n3_0001` 至 `n3_3400`
- 32 个单元，单元数量与原书一致
- 3254 个原书例句及原书中译
- 第 32 单元 146 个补充词；原书没有提供例句
- 47 条已确认勘误：实质误译、词义修正、措辞优化及 7 条习题文本串入清理
- 最终卡组使用修订译文，同时保留原书中译供对照

主要文件：

- `data/n3/wordlist_original.json`：清晰 PDF 的原始提取结果
- `data/n3/wordlist.json`：应用勘误后的最终构建数据
- `data/n3/wordlist.csv`：可直接用表格软件打开的全量词表
- `review/n3_translation_corrections.json`：可重复应用的结构化修订
- `review/n3_translation_errata.csv`：47 条中文翻译勘误
- `artifacts/n3_wordlist_3400_with_errata.xlsx`：全量词表与勘误 Excel

重新应用修订并校验：

```bash
python scripts/apply_translation_corrections.py
python scripts/validate_wordlist.py
```

## GitHub Actions 生成全量 APKG

工作流名称为 **Generate Full N3 Audio**。拉取请求会自动生成 4 张样卡；正式全量构建需要在 `main` 手动触发：

1. 打开仓库的 **Actions** 页面。
2. 选择 **Generate Full N3 Audio**。
3. 点击 **Run workflow**，分支选 `main`。
4. `mode` 选择 `full` 后运行。
5. 完成后下载 `n3-0001-3400-edge-tts-apkg`。

音频参数：

- 声音：Microsoft Edge TTS `ja-JP-NanamiNeural`
- 语速：`-10%`（约 0.90×）
- 后处理：FFmpeg `loudnorm`，24 kHz、单声道、96 kbps
- 每张卡 3 个 MP3：单词两遍、例句一遍、例句两遍
- 第 32 单元没有原书例句，因此两个“例句”音频槽使用单词读音
- 全量共 10200 个 MP3，拆为 16 个可恢复分片，并行上限为 4

最终工作流会验证全部音频，再构建 `无敌绿宝书-N3-3400词-EdgeTTS.apkg`，并检查 3400 个笔记、3400 张卡片、连续 ID 和 10200 个媒体文件。

## 卡片模板

卡片沿用此前确定的三阶段听辨模板：

- 第一阶段只听音频
- 第二阶段显示原书日语例句
- 第三阶段显示大号假名、词头、中文释义及修订后的例句中译
- 点击词块或例句即可播放
- 长词保持单行显示
- 第 32 单元显示“原书未提供例句”，保留单词训练

本版使用独立的 Anki 模型、牌组 ID 与 GUID 前缀，可与早期 3256 词实验版及原书配音版共存，不会互相覆盖。

## 旧版 50 卡构建

早期 `n3_0125`–`n3_0174` 的 50 卡脚本仍保留作参考：

```bash
sudo apt-get install ffmpeg
python -m pip install -r requirements.txt
python scripts/build_apkg.py
python scripts/validate_apkg.py "dist/无敌绿宝书-N3-0125至0174.apkg"
```

源 PDF 和生成的 MP3 不提交到仓库；GitHub Actions 产物默认保留 14 天。
