# 富邦學習知識庫

富邦人壽訓練、討論與教學錄音的私有連結網站：每份錄音有重點整理與完整逐字稿，首頁可全文搜尋、按分類與主題翻找。頁面設定 `noindex`，`robots.txt` 禁止收錄。

## 結構

- `index.html`：總站（條目列表、分類與主題標籤、全文搜尋）
- `events/<slug>/`：重點整理
- `transcripts/<slug>/`：完整逐字稿
- `entries/<slug>/edits.py`：章節、導讀、頁面文字；`clean*.py`：逐段校稿（已去識別化）
- `content/<slug>.json`：build 結果紀錄
- `search-index.js`、`search.js`：搜尋（沒有 JS 時正文照常顯示）
- `scripts/prepare_draft.py`、`scripts/build_site.py`

## 目前條目

| 日期 | 標題 | 分類 |
|---|---|---|
| 2026-10-08 | 新人問卷怎麼講 | 銷售流程 |
| 2026-10-06 | 重大傷病怎麼開議題 | 議題與話術 |

## 新增一份錄音

1. 本機轉錄（super-assistant 根目錄）：
   `WHISPER_LANGUAGE=zh WHISPER_MODEL_PATH=tools/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin scripts/transcribe_local.sh <audio> output/transcribe/<slug>`
2. 建 `entries/<slug>/source.json`（列出各段 whisper JSON），跑 `python3 scripts/prepare_draft.py <slug>`
3. 寫 `entries/<slug>/clean.py`（校稿）與 `edits.py`（META 含 `date`、`category`、`tags`）
4. `python3 scripts/build_site.py`

原始轉錄草稿 `entries/*/draft.json` 與 `source.json` 含未去識別化內容，不進版控，只存在本機。
