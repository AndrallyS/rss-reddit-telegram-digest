"""Build a static HTML dashboard from the latest digest outputs."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_ranking_config
from app.utils import clean_text, parse_datetime, truncate_text

SITE_DIR = PROJECT_ROOT / "site"
OUTPUT_DIR = PROJECT_ROOT / "output"

CATEGORY_META = {
    "games": {"label": "Gaming", "emoji": "🎮", "accent": "#f97316"},
    "gamedev": {"label": "Game Dev & Tools", "emoji": "🛠️", "accent": "#7c3aed"},
    "ai": {"label": "Inteligência Artificial", "emoji": "🤖", "accent": "#06b6d4"},
    "finance": {"label": "Brasil & Mercado", "emoji": "🟢", "accent": "#16a34a"},
    "tech": {"label": "Tech & Segurança", "emoji": "⚡", "accent": "#0f766e"},
    "reddit": {"label": "Radar Reddit", "emoji": "🔥", "accent": "#dc2626"},
    "rss": {"label": "Cobertura Editorial", "emoji": "📰", "accent": "#2563eb"},
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "from",
    "this",
    "into",
    "after",
    "over",
    "under",
    "your",
    "about",
    "mais",
    "para",
    "with",
    "have",
    "will",
    "just",
    "what",
    "when",
    "where",
    "como",
    "that",
    "they",
    "their",
    "still",
}


def _load_json(path: Path) -> list[dict] | dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _category_items(items: list[dict], category: str, limit: int) -> list[dict]:
    return [item for item in items if item.get("category") == category][:limit]


def _is_reddit_primary(item: dict) -> bool:
    return "reddit.com" in str(item.get("canonical_url", "")).lower()


def _item_source_label(item: dict) -> str:
    if _is_reddit_primary(item):
        subreddit = item.get("raw_metadata", {}).get("reddit", {}).get("subreddit")
        return f"REDDIT /r/{subreddit}" if subreddit else "REDDIT"
    return str(item.get("source_name") or "Unknown").upper()


def _item_keywords(item: dict, limit: int = 4) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]{4,}", str(item.get("title") or "").lower())
    seen: list[str] = []
    for word in words:
        if word in STOPWORDS or word in seen:
            continue
        seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def _keyword_trends(items: list[dict], limit: int = 8) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for item in items:
        words = re.findall(r"[A-Za-zÀ-ÿ0-9]{4,}", str(item.get("title") or "").lower())
        for word in words:
            if word in STOPWORDS:
                continue
            counter[word] += 1
    return counter.most_common(limit)


def _top_sources(items: list[dict], limit: int = 6) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for item in items:
        reddit_meta = item.get("raw_metadata", {}).get("reddit", {})
        subreddit = reddit_meta.get("subreddit")
        if subreddit:
            counter[f"/r/{subreddit}"] += 1
        else:
            counter[str(item.get("source_name") or "Unknown")] += 1
    return counter.most_common(limit)


def _format_dt(value: str | None) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return "Sem data"
    return parsed.astimezone().strftime("%d/%m %H:%M")


def _score_line(item: dict) -> str:
    signals = item.get("score_signals", {})
    reddit_score = signals.get("reddit_score", 0)
    ranking_score = signals.get("ranking_score", 0.0)
    comments = signals.get("num_comments", 0)
    return f"👍 {reddit_score} · 💬 {comments} · ⭐ {ranking_score:.1f}"


def _card(item: dict, index: int, category: str) -> str:
    meta = CATEGORY_META[category]
    summary = truncate_text(clean_text(str(item.get("summary") or "")), 180)
    source_label = html.escape(_item_source_label(item))
    title = html.escape(str(item.get("title") or "Untitled"))
    url = html.escape(str(item.get("canonical_url") or "#"))
    published = html.escape(_format_dt(item.get("published_at")))
    keywords = "".join(
        f'<span class="tag">{html.escape(keyword)}</span>' for keyword in _item_keywords(item)
    )
    original = html.escape(truncate_text(str(item.get("title") or ""), 70))
    discussion_url = item.get("discussion_url")
    discussion = (
        f'<a class="discussion-link" href="{html.escape(str(discussion_url))}" target="_blank" rel="noreferrer">Discussão no Reddit</a>'
        if discussion_url
        else ""
    )
    return f"""
    <article class="card">
      <div class="card-rank" style="background:{meta['accent']}">#{index}</div>
      <div class="card-top">
        <span class="source-pill">{source_label}</span>
        <span class="published">{published}</span>
      </div>
      <h3><a href="{url}" target="_blank" rel="noreferrer">{title}</a></h3>
      <p class="original">Original: {original}</p>
      <p class="score-line">{html.escape(_score_line(item))}</p>
      <div class="tags">{keywords}</div>
      <div class="links">
        <a href="{url}" target="_blank" rel="noreferrer">Ler artigo completo</a>
        {discussion}
      </div>
      <p class="summary">{html.escape(summary)}</p>
    </article>
    """


def _section(items: list[dict], category: str, limit: int) -> str:
    selected = _category_items(items, category, limit)
    if not selected:
        return ""
    meta = CATEGORY_META[category]
    cards = "\n".join(_card(item, index, category) for index, item in enumerate(selected, start=1))
    return f"""
    <section class="category-block">
      <div class="section-head">
        <h2>{meta['emoji']} {html.escape(meta['label'])}</h2>
        <span class="badge" style="background:{meta['accent']}">{len(selected)} destaques</span>
      </div>
      <div class="cards">{cards}</div>
    </section>
    """


def build_site() -> Path:
    ranked_items = _load_json(OUTPUT_DIR / "ranked_items.json")
    report = _load_json(OUTPUT_DIR / "last_run_report.json")
    ranking_config = load_ranking_config(PROJECT_ROOT)
    if not isinstance(ranked_items, list):
        raise RuntimeError("ranked_items.json is not a list")
    if not isinstance(report, dict):
        raise RuntimeError("last_run_report.json is not a dict")

    generated_at = parse_datetime(report.get("started_at"))
    generated_label = (
        generated_at.astimezone().strftime("%d de %B de %Y · %H:%M %Z")
        if generated_at
        else "Sem timestamp"
    )
    item_count = report.get("filtered_recently_sent_items") or report.get("deduped_items") or len(ranked_items)
    reddit_items = report.get("reddit_items", 0)

    top_sources = "".join(
        f'<span class="mini-chip">{html.escape(name)} ×{count}</span>'
        for name, count in _top_sources(ranked_items)
    )
    top_keywords = "".join(
        f'<span class="mini-chip">{html.escape(word)} ×{count}</span>'
        for word, count in _keyword_trends(ranked_items)
    )
    tabs = "".join(
        f'<span class="tab" style="border-color:{CATEGORY_META[key]["accent"]};color:{CATEGORY_META[key]["accent"]};">{CATEGORY_META[key]["emoji"]} {CATEGORY_META[key]["label"]}</span>'
        for key in ("games", "gamedev", "ai", "tech", "finance")
    )

    sections = "".join(
        _section(ranked_items, category, ranking_config.section_limits.get(category, 5))
        for category in ("games", "gamedev", "ai", "tech", "finance", "reddit")
    )

    html_output = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Briefing</title>
  <style>
    :root {{
      --bg: #eef2f7;
      --ink: #10203a;
      --muted: #6b7b95;
      --line: #d8e1ee;
      --card: #ffffff;
      --hero: #1d365b;
      --shadow: 0 18px 40px rgba(16, 32, 58, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: var(--bg);
      color: var(--ink);
    }}
    a {{ color: #2563eb; text-decoration: none; }}
    .hero {{
      background: linear-gradient(180deg, #1d365b 0%, #203b61 100%);
      color: #fff;
      padding: 40px 24px 56px;
      text-align: center;
    }}
    .eyebrow {{
      letter-spacing: 0.25em;
      text-transform: uppercase;
      font-size: 12px;
      opacity: 0.5;
    }}
    .hero h1 {{
      margin: 16px 0 10px;
      font-size: clamp(34px, 6vw, 56px);
    }}
    .hero p {{
      margin: 0;
      color: #d9e4f6;
      font-family: "Segoe UI", sans-serif;
    }}
    .tabs {{
      margin-top: 26px;
      display: flex;
      gap: 10px;
      justify-content: center;
      flex-wrap: wrap;
    }}
    .tab {{
      border: 1px solid;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      font-family: "Segoe UI", sans-serif;
      font-size: 14px;
    }}
    .shell {{
      width: min(980px, calc(100% - 32px));
      margin: -28px auto 48px;
    }}
    .trend-box {{
      background: rgba(255,255,255,0.9);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    .trend-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 24px;
    }}
    .trend-box h2 {{
      margin-top: 0;
      font-size: 28px;
    }}
    .mini-label {{
      display: block;
      margin-bottom: 10px;
      color: #8aa0c3;
      font: 600 12px/1.2 "Segoe UI", sans-serif;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .mini-chip {{
      display: inline-block;
      margin: 0 8px 8px 0;
      padding: 6px 10px;
      border-radius: 10px;
      background: #fff;
      border: 1px solid var(--line);
      font: 500 14px/1.2 "Segoe UI", sans-serif;
      color: var(--muted);
    }}
    .category-block {{
      margin-top: 36px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      border-bottom: 3px solid #f97316;
      padding-bottom: 10px;
      margin-bottom: 16px;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 40px;
    }}
    .badge {{
      color: #fff;
      border-radius: 999px;
      padding: 7px 12px;
      font: 700 13px/1 "Segoe UI", sans-serif;
      white-space: nowrap;
    }}
    .cards {{
      display: grid;
      gap: 16px;
    }}
    .card {{
      position: relative;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px 22px 20px 22px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .card-rank {{
      position: absolute;
      left: 14px;
      top: 10px;
      color: #fff;
      font: 700 12px/1 "Segoe UI", sans-serif;
      border-radius: 999px;
      padding: 7px 8px;
    }}
    .card-top {{
      margin-top: 14px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      font-family: "Segoe UI", sans-serif;
    }}
    .source-pill {{
      display: inline-block;
      background: #0f766e;
      color: #fff;
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .published {{
      color: #7b8db0;
      font-size: 14px;
      white-space: nowrap;
    }}
    .card h3 {{
      margin: 12px 0 8px;
      font-size: 24px;
      line-height: 1.28;
    }}
    .original, .summary {{
      margin: 6px 0;
      color: #8896b2;
      font: italic 16px/1.5 Georgia, serif;
    }}
    .score-line {{
      color: #5d6c84;
      font: 600 14px/1.2 "Segoe UI", sans-serif;
    }}
    .tags {{
      margin-top: 10px;
    }}
    .tag {{
      display: inline-block;
      margin: 0 8px 8px 0;
      padding: 6px 9px;
      border-radius: 6px;
      background: #fff4c5;
      color: #8a6112;
      font: 600 12px/1.2 "Segoe UI", sans-serif;
    }}
    .links {{
      margin-top: 14px;
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      font: 600 15px/1.2 "Segoe UI", sans-serif;
    }}
    .discussion-link {{
      color: #b91c1c;
    }}
    @media (max-width: 760px) {{
      .section-head h2 {{ font-size: 32px; }}
      .card h3 {{ font-size: 20px; }}
      .card-top {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="eyebrow">Daily Briefing · Auto-generated</div>
    <h1>🔦 Games · Dev · AI · Tech</h1>
    <p>{html.escape(generated_label)} · {item_count} destaques · Reddit items: {reddit_items}</p>
    <div class="tabs">{tabs}</div>
  </header>
  <main class="shell">
    <section class="trend-box">
      <h2>📈 Últimos 3 dias — tendências</h2>
      <div class="trend-grid">
        <div>
          <span class="mini-label">Top sources / subreddits</span>
          {top_sources}
        </div>
        <div>
          <span class="mini-label">Keywords em alta</span>
          {top_keywords}
        </div>
      </div>
    </section>
    {sections}
  </main>
</body>
</html>
"""
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(html_output, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    return SITE_DIR / "index.html"


def main() -> int:
    output_path = build_site()
    print(f"Browser briefing generated at: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
