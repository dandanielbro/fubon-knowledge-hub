#!/usr/bin/env python3
"""把 whisper.cpp JSON 合併成帶穩定 id 的段落草稿，供人工校稿。

用法：python3 scripts/prepare_draft.py <entry-slug>
讀 entries/<slug>/source.json（列出音檔分段），輸出：
  entries/<slug>/draft.json  段落資料（id、part、start、end、text）；含未去識別化內容，不進版控
  entries/<slug>/draft.txt   校稿用純文字
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
MERGE_GAP = 2.0
MAX_CHARS = 160
END_PUNCT = "。？！?!…"


def fmt(value: float) -> str:
    total = int(value)
    return f"{total // 60:02d}:{total % 60:02d}"


def normalize(text: str) -> str:
    text = text.strip()
    return text.replace("?", "？").replace("!", "！").replace(",", "，").replace(" ", "")


def join(a: str, b: str) -> str:
    if not a:
        return b
    if a[-1] in END_PUNCT + "，、":
        return a + b
    return a + "，" + b


def load(path: Path, part: str) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    paragraphs: list[dict] = []
    for item in raw["transcription"]:
        text = normalize(item["text"])
        if not text:
            continue
        seg = {"start": item["offsets"]["from"] / 1000, "end": item["offsets"]["to"] / 1000, "text": text}
        last = paragraphs[-1] if paragraphs else None
        if last and seg["start"] - last["end"] <= MERGE_GAP and len(last["text"]) + len(seg["text"]) <= MAX_CHARS:
            last["text"] = join(last["text"], seg["text"])
            last["end"] = seg["end"]
        else:
            paragraphs.append(seg)
    for idx, para in enumerate(paragraphs, start=1):
        para["id"] = f"{part}-{idx:03d}"
        para["part"] = part
    return paragraphs


def main() -> None:
    entry = ROOT / "entries" / sys.argv[1]
    source = json.loads((entry / "source.json").read_text(encoding="utf-8"))
    out, lines = [], []
    for part in source["parts"]:
        paras = load(REPO / part["json"], part["key"])
        out.extend(paras)
        lines.append(f"##### {part['key']} {part['label']}")
        lines.extend(f"{p['id']} [{fmt(p['start'])}] {p['text']}" for p in paras)
    (entry / "draft.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (entry / "draft.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(out)} paragraphs")


if __name__ == "__main__":
    main()
