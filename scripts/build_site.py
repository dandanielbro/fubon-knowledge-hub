#!/usr/bin/env python3
"""富邦知識庫：從 entries/<slug>/ 的 draft.json + edits.py 產生 static-first 網站。

每個條目一個資料夾：
  entries/<slug>/edits.py    META、PARTS、SECTIONS、OVERRIDES、DROP、REPLACEMENTS
  entries/<slug>/draft.json  whisper 草稿（含未去識別化內容，不進版控）

輸出：
  index.html                     總站：條目列表、主題標籤、全文搜尋
  events/<slug>/index.html       重點整理
  transcripts/<slug>/index.html  完整逐字稿
  content/<slug>.json            build 結果紀錄（已去識別化，頁面不讀）
  search-index.js                搜尋資料（用 <script> 載入，file:// 也能用）

正文不依賴 JS；JS 只做搜尋與標籤篩選。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = ROOT / "entries"
ROBOTS = '<meta name="robots" content="noindex,nofollow,noarchive">'
SITE_TITLE = "富邦學習知識庫"
SITE_LEAD = "富邦人壽的訓練、討論與教學錄音，整理成重點和逐字稿。可以用關鍵字搜尋全部內容，或按主題翻找。"
PRIVACY = "這個網站只有拿到網址的人看得到，頁面已設定不讓搜尋引擎收錄。客戶資料已去識別化。"


def fmt(value: float) -> str:
    total = int(value)
    return f"{total // 60:02d}:{total % 60:02d}"


def load_edits(entry: Path):
    """各條目都有 edits.py / clean*.py，模組名稱會撞，載入後清掉快取。"""
    before = set(sys.modules)
    sys.path.insert(0, str(entry))
    try:
        spec = importlib.util.spec_from_file_location(f"edits_{entry.name.replace('-', '_')}", entry / "edits.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(entry))
        for name in set(sys.modules) - before:
            if name.startswith(("clean", "edits")):
                del sys.modules[name]
    return module


def build_entry(entry: Path) -> dict:
    edits = load_edits(entry)
    draft = json.loads((entry / "draft.json").read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in draft}
    order = [p["id"] for p in draft]
    unknown = (set(edits.OVERRIDES) | set(edits.DROP)) - set(by_id)
    if unknown:
        raise SystemExit(f"{entry.name}: edits 指到不存在的段落：{sorted(unknown)}")
    raw = [pid for pid in order if pid not in edits.OVERRIDES and pid not in edits.DROP]
    if raw:
        print(f"  注意 {entry.name}: {len(raw)} 段沒有校稿，使用原始轉錄：{raw[:5]}…")

    parts = dict(edits.PARTS)
    multi = len(parts) > 1
    sections, covered = [], set()
    for idx, sec in enumerate(edits.SECTIONS, start=1):
        start_i, end_i = order.index(sec["from"]), order.index(sec["to"])
        rows = []
        for pid in order[start_i:end_i + 1]:
            covered.add(pid)
            if pid in edits.DROP:
                continue
            text = edits.OVERRIDES.get(pid, by_id[pid]["text"])
            for old, new in edits.REPLACEMENTS:
                text = text.replace(old, new)
            if text.strip():
                rows.append({"id": pid, "time": fmt(by_id[pid]["start"]), "text": text})
        first, last = by_id[sec["from"]], by_id[sec["to"]]
        prefix = f"{parts[first['part']]} " if multi else ""
        sections.append({
            "id": f"ch{idx:02d}",
            "index": f"{idx:02d}",
            "timeRange": f"{prefix}{fmt(first['start'])}–{fmt(last['end'])}",
            **{k: sec[k] for k in ("kicker", "title", "tag", "summary", "highlights")},
            "rows": rows,
        })
    missing = [pid for pid in order if pid not in covered]
    if missing:
        raise SystemExit(f"{entry.name}: 有段落沒有被任何章節涵蓋：{missing[:10]}…（共 {len(missing)}）")
    return {**edits.META, "sections": sections}


def e(value: object) -> str:
    return escape(str(value), quote=True)


def rich(text: str) -> str:
    """跳脫 HTML，再把 **粗體** 與換行轉成標記。"""
    html = e(text)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    return html.replace("\n", "<br>")


def plain(text: str) -> str:
    return text.replace("**", "")


def head(title: str, description: str, prefix: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {ROBOTS}
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <link rel="stylesheet" href="{prefix}styles.css">
</head>"""


def toc(data: dict) -> str:
    return "\n".join(
        f'<a class="toc-link" href="#{s["id"]}"><strong>{s["index"]} {e(s["title"])}</strong>'
        f'<span>{e(s["timeRange"])} · {e(s["tag"])}</span></a>'
        for s in data["sections"]
    )


def render_cheatsheet(sheet: dict) -> str:
    cols = sheet["columns"]
    header = "".join(f"<th scope=\"col\">{e(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(
            (f'<th scope="row">{rich(cell)}</th>' if i == 0 else f'<td data-label="{e(cols[i])}">{rich(cell)}</td>')
            for i, cell in enumerate(row)
        ) + "</tr>"
        for row in sheet["rows"]
    )
    return f"""<section class="card panel" id="cheatsheet">
      <p class="eyebrow">Cheat Sheet</p>
      <h2>{e(sheet["title"])}</h2>
      <p class="note">{e(sheet["note"])}</p>
      <div class="table-wrap"><table class="sheet"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>
    </section>"""


def render_summary(data: dict) -> str:
    slug = data["slug"]
    overview = "".join(f"<li>{rich(i)}</li>" for i in data["overview"])
    notes = "".join(f"<li>{rich(i)}</li>" for i in data["sourceNotes"])
    target = f"../../transcripts/{slug}/"
    cheatsheet = render_cheatsheet(data["cheatsheet"]) if data.get("cheatsheet") else ""
    chapters = []
    for s in data["sections"]:
        hl = "".join(f"<li>{rich(i)}</li>" for i in s["highlights"])
        chapters.append(f"""<article class="card chapter" id="{s["id"]}">
  <header class="chapter-head">
    <span class="chapter-index">{s["index"]}</span>
    <div>
      <p class="eyebrow">{e(s["kicker"])}</p>
      <h2>{e(s["title"])}</h2>
      <p class="chips"><span>{e(s["timeRange"])}</span><span>{e(s["tag"])}</span></p>
    </div>
  </header>
  <div class="chapter-body">
    <p class="chapter-summary">{rich(s["summary"])}</p>
    <div class="keypoints"><p class="label">重點</p><ul>{hl}</ul></div>
    <a class="button" href="{target}#{s["id"]}">看本章逐字稿</a>
  </div>
</article>""")
    return f"""{head("重點整理｜" + data["title"], data["subtitle"], "../../")}
<body>
  <header class="hero">
    <div class="shell">
      <a class="back" href="../../">← 回知識庫</a>
      <p class="eyebrow">{e(data["eyebrow"])}</p>
      <h1>{e(data["title"])}</h1>
      <p class="lead">{e(data["subtitle"])}</p>
      <p class="chips">{"".join(f"<span>{e(c)}</span>" for c in data["chips"])}</p>
      <div class="actions"><a class="button primary" href="{target}">查看完整逐字稿</a></div>
    </div>
  </header>
  <main class="shell stack">
    <section class="card panel">
      <p class="eyebrow">Overview</p>
      <h2>這段錄音在講什麼</h2>
      <ul class="overview">{overview}</ul>
    </section>
    {cheatsheet}
    <nav class="card panel" id="toc" aria-label="章節導讀">
      <h2>章節導讀</h2>
      <p class="note">點章節標題會跳到下方整理；每章的「看本章逐字稿」會跳到完整逐字稿的同一章。</p>
      <div class="toc-list">{toc(data)}</div>
    </nav>
    {"".join(chapters)}
    <section class="card panel">
      <p class="eyebrow">Source</p>
      <h2>整理說明</h2>
      <ul class="plain">{notes}</ul>
    </section>
  </main>
  <a class="to-top" href="#toc">目錄</a>
  <footer class="footer">{e(SITE_TITLE)} · 私有連結 · 未開放搜尋引擎收錄</footer>
</body>
</html>
"""


def render_transcript(data: dict) -> str:
    target = f"../../events/{data['slug']}/"
    chapters = []
    for s in data["sections"]:
        rows = "".join(
            f'<div class="row" id="{r["id"]}"><time>{e(r["time"])}</time><p>{rich(r["text"])}</p></div>'
            for r in s["rows"]
        )
        chapters.append(f"""<article class="card tchapter" id="{s["id"]}">
  <header class="tchapter-head">
    <div>
      <p class="eyebrow">{e(s["timeRange"])} · {e(s["tag"])}</p>
      <h2>{s["index"]} {e(s["title"])}</h2>
    </div>
    <a class="button small" href="{target}#{s["id"]}">本章重點</a>
  </header>
  <div class="rows">{rows}</div>
</article>""")
    return f"""{head("完整逐字稿｜" + data["title"], data["subtitle"], "../../")}
<body>
  <main class="shell transcript-page">
    <a class="back" href="../../">← 回知識庫</a>
    <p class="eyebrow">{e(data["eyebrow"])} · Full Transcript</p>
    <h1>{e(data["title"])}｜完整逐字稿</h1>
    <p class="lead">{e(data["transcriptLead"])}</p>
    <div class="actions"><a class="button primary" href="{target}">查看重點整理</a></div>
    <nav class="card panel" id="toc" aria-label="逐字稿目錄">
      <h2>逐字稿目錄</h2>
      <div class="toc-list">{toc(data)}</div>
    </nav>
    {"".join(chapters)}
  </main>
  <a class="to-top" href="#toc">目錄</a>
  <footer class="footer">{e(SITE_TITLE)} · 私有連結 · 未開放搜尋引擎收錄</footer>
</body>
</html>
"""


def render_home(entries: list[dict]) -> str:
    categories = sorted({d["category"] for d in entries})
    tags: dict[str, int] = {}
    for d in entries:
        for t in d["tags"]:
            tags[t] = tags.get(t, 0) + 1
    cards = []
    for d in entries:
        slug = d["slug"]
        chapters = "".join(
            f'<li><a href="events/{slug}/#{s["id"]}">{s["index"]} {e(s["title"])}</a></li>'
            for s in d["sections"]
        )
        cards.append(f"""<article class="card entry" data-category="{e(d["category"])}">
  <p class="eyebrow">{e(d["date"])} · {e(d["category"])}</p>
  <h2><a href="events/{slug}/">{e(d["title"])}</a></h2>
  <p class="entry-sub">{e(d["subtitle"])}</p>
  <p class="chips tags">{"".join(f"<span>{e(t)}</span>" for t in d["tags"])}</p>
  <div class="actions">
    <a class="button primary small" href="events/{slug}/">重點整理</a>
    <a class="button small" href="transcripts/{slug}/">完整逐字稿</a>
  </div>
  <details class="entry-chapters"><summary>章節（{len(d["sections"])}）</summary><ol>{chapters}</ol></details>
</article>""")
    tag_buttons = "".join(
        f'<button type="button" class="tag" data-q="{e(t)}">{e(t)}<span>{n}</span></button>'
        for t, n in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    cat_buttons = "".join(f'<button type="button" class="tag" data-cat="{e(c)}">{e(c)}</button>' for c in categories)
    return f"""{head(SITE_TITLE, SITE_LEAD, "")}
<body>
  <header class="hero">
    <div class="shell">
      <p class="eyebrow">Fubon Life · 個人學習整理</p>
      <h1>{SITE_TITLE}</h1>
      <p class="lead">{SITE_LEAD}</p>
      <p class="note">{PRIVACY}</p>
    </div>
  </header>
  <main class="shell stack">
    <section class="card panel search-panel" id="search" hidden>
      <label class="search-label" for="q">搜尋全部重點與逐字稿</label>
      <input id="q" type="search" placeholder="例如：保單健診、競爭者、標靶藥、轉介紹" autocomplete="off">
      <div class="filters">
        <p class="label">分類</p><div class="tag-row">{cat_buttons}</div>
        <p class="label">主題</p><div class="tag-row">{tag_buttons}</div>
      </div>
      <p class="note" id="status" aria-live="polite"></p>
      <ol class="results" id="results"></ol>
    </section>
    <section id="entries" class="stack-tight">
      <h2 class="section-title">全部條目（{len(entries)}）</h2>
      {"".join(cards)}
    </section>
  </main>
  <footer class="footer">{SITE_TITLE} · 私有連結 · 未開放搜尋引擎收錄</footer>
  <script src="search-index.js"></script>
  <script src="search.js"></script>
</body>
</html>
"""


def search_index(entries: list[dict]) -> list[dict]:
    docs = []
    for d in entries:
        base = {"entry": d["title"], "date": d["date"], "slug": d["slug"], "category": d["category"]}
        for s in d["sections"]:
            docs.append({**base, "kind": "重點", "chapter": f'{s["index"]} {s["title"]}',
                         "href": f'events/{d["slug"]}/#{s["id"]}',
                         "text": plain(" ".join([s["title"], s["tag"], s["summary"], *s["highlights"]]))})
            for r in s["rows"]:
                docs.append({**base, "kind": "逐字稿", "chapter": f'{s["index"]} {s["title"]}', "time": r["time"],
                             "href": f'transcripts/{d["slug"]}/#{r["id"]}', "text": plain(r["text"])})
        if d.get("cheatsheet"):
            for row in d["cheatsheet"]["rows"]:
                docs.append({**base, "kind": "速查", "chapter": plain(row[0]),
                             "href": f'events/{d["slug"]}/#cheatsheet', "text": plain(" ".join(row))})
    return docs


def main() -> None:
    entries = []
    for entry in sorted(p for p in ENTRIES.iterdir() if (p / "edits.py").exists()):
        data = build_entry(entry)
        slug = data["slug"]
        for kind, render in (("events", render_summary), ("transcripts", render_transcript)):
            out = ROOT / kind / slug
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(render(data), encoding="utf-8")
        (ROOT / "content").mkdir(exist_ok=True)
        (ROOT / "content" / f"{slug}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        rows = sum(len(s["rows"]) for s in data["sections"])
        print(f"built {slug}: {len(data['sections'])} chapters, {rows} rows")
        entries.append(data)
    entries.sort(key=lambda d: d["date"], reverse=True)
    (ROOT / "index.html").write_text(render_home(entries), encoding="utf-8")
    (ROOT / "search-index.js").write_text(
        "window.SEARCH_INDEX = " + json.dumps(search_index(entries), ensure_ascii=False) + ";\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    main()
