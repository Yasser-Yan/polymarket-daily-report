#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://gamma-api.polymarket.com/markets"
TRANSLATE_API = "https://translate.googleapis.com/translate_a/single"
ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")
DATA_DIR = ROOT / "data"
TRANSLATION_CACHE = DATA_DIR / "translations.json"

ZH = {
    "settle_unknown": "\u7ed3\u7b97\u65f6\u95f4\u5f85\u786e\u8ba4",
    "settled": "\u5df2\u5230\u671f/\u5f85\u7ed3\u7b97",
    "settle_today": "\u4eca\u5929\u7ed3\u7b97",
    "days_later": "\u5929\u540e\u7ed3\u7b97",
    "years_later": "\u5e74+\u540e\u7ed3\u7b97",
    "report": "Polymarket \u9884\u6d4b\u5e02\u573a\u65e5\u62a5",
    "beijing_time": "\u5317\u4eac\u65f6\u95f4",
    "auto_update": "\u6bcf\u65e5\u81ea\u52a8\u66f4\u65b0",
    "hero_title": "\u4eca\u65e5\u9884\u6d4b\u5e02\u573a\u70ed\u5ea6\u626b\u63cf",
    "hero_desc": "\u6293\u53d6 Polymarket \u6d3b\u8dc3\u5e02\u573a\u6570\u636e\uff0c\u5c06\u82f1\u6587\u6807\u9898\u548c\u9009\u9879\u7ffb\u8bd1\u6210\u4e2d\u6587\uff0c\u5e76\u6309\u6210\u4ea4\u91cf\u751f\u6210\u6bcf\u65e5\u62a5\u544a\u3002",
    "sample_markets": "\u6837\u672c\u5e02\u573a",
    "top_volume": "\u5934\u90e8\u6210\u4ea4\u91cf",
    "top_liquidity": "\u5934\u90e8\u6d41\u52a8\u6027",
    "avg_probability": "\u5e73\u5747\u9886\u5148\u6982\u7387",
    "market": "\u5e02\u573a",
    "category": "\u7c7b\u522b",
    "leading_outcome": "\u9886\u5148\u7ed3\u679c",
    "probability": "\u6982\u7387",
    "volume": "\u6210\u4ea4\u91cf",
    "liquidity": "\u6d41\u52a8\u6027",
    "theme_heat": "\u4e3b\u9898\u70ed\u5ea6",
    "today_notes": "\u4eca\u65e5\u89c2\u5bdf",
    "footer": "\u6570\u636e\u6765\u6e90\uff1aPolymarket Gamma API\u3002\u82f1\u6587\u5e02\u573a\u6807\u9898\u4f1a\u5728\u751f\u6210\u65f6\u81ea\u52a8\u7ffb\u8bd1\u4e3a\u4e2d\u6587\u3002\u5e02\u573a\u4ef7\u683c\u548c\u6210\u4ea4\u91cf\u53ef\u80fd\u5b58\u5728\u5ef6\u8fdf\uff0c\u4ec5\u4f9b\u7814\u7a76\u53c2\u8003\u3002",
    "concentration": "\u6210\u4ea4\u96c6\u4e2d\u5ea6",
    "structure": "\u5e02\u573a\u7ed3\u6784",
    "sentiment": "\u6982\u7387\u60c5\u7eea",
    "consensus": "\u66f4\u504f\u5171\u8bc6",
    "divergent": "\u5206\u6b67\u8f83\u9ad8",
    "neutral": "\u4e2d\u6027\u5206\u5e03",
    "total_volume_prefix": "\u672c\u6b21\u6837\u672c\u603b\u6210\u4ea4\u91cf\u7ea6",
    "hot_theme": "\u6210\u4ea4\u989d\u6700\u9ad8\u4e3b\u9898\u662f",
    "most_count_prefix": "\u7c7b\u5e02\u573a\u6570\u91cf\u6700\u591a\uff0c\u5171",
    "unit_market": "\u4e2a",
    "median_prefix": "\u9886\u5148\u7ed3\u679c\u7684\u4e2d\u4f4d\u6982\u7387\u4e3a",
    "overall": "\u6574\u4f53\u5448\u73b0",
    "original": "\u539f\u6587",
}

CATEGORY_ZH = {
    "Sports": "\u4f53\u80b2",
    "Politics": "\u653f\u6cbb",
    "Finance": "\u91d1\u878d",
    "Crypto": "\u52a0\u5bc6",
    "Economics": "\u7ecf\u6d4e",
    "Culture": "\u6587\u5316",
    "Tech": "\u79d1\u6280",
    "Other": "\u5176\u4ed6",
}


def get_json(url: str, params: dict, timeout: int = 30):
    req = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "polymarket-daily-report"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def num(value) -> float:
    try:
        out = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return out if math.isfinite(out) else 0.0


def money(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def category(item: dict) -> str:
    raw = str(item.get("category") or item.get("groupItemTitle") or "").strip()
    if raw:
        return raw.title()
    q = str(item.get("question") or "").lower()
    if any(x in q for x in ["bitcoin", "btc", "ethereum", "crypto", "solana"]):
        return "Crypto"
    if any(x in q for x in ["election", "president", "senate", "trump"]):
        return "Politics"
    if any(x in q for x in ["fed", "rate", "inflation", "stock", "nasdaq"]):
        return "Finance"
    if any(x in q for x in ["nba", "nfl", "world cup", "champions"]):
        return "Sports"
    return "Other"


def load_cache() -> dict[str, str]:
    if not TRANSLATION_CACHE.exists():
        return {}
    try:
        data = json.loads(TRANSLATION_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(cache: dict[str, str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    TRANSLATION_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def translate_text(text: str, cache: dict[str, str]) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        return ""
    key = "zh-CN|" + text
    if key in cache:
        return cache[key]
    try:
        data = get_json(TRANSLATE_API, {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text}, timeout=20)
        translated = "".join(part[0] for part in data[0] if part and part[0]).strip()
    except Exception:
        translated = text
    cache[key] = translated or text
    time.sleep(0.08)
    return cache[key]


def category_zh(cat: str, cache: dict[str, str]) -> str:
    return CATEGORY_ZH.get(cat, translate_text(cat, cache))


def tag_class(cat: str) -> str:
    c = cat.lower()
    if "sport" in c:
        return "tag-sports"
    if "politic" in c or "election" in c:
        return "tag-politics"
    if "crypto" in c:
        return "tag-crypto"
    if "finance" in c or "econom" in c:
        return "tag-finance"
    return "tag-other"


def days_until(value: str, now: datetime) -> str:
    if not value:
        return ZH["settle_unknown"]
    try:
        end = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ZH["settle_unknown"]
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    days = math.ceil((end - now.astimezone(timezone.utc)).total_seconds() / 86400)
    if days < 0:
        return ZH["settled"]
    if days == 0:
        return ZH["settle_today"]
    if days < 365:
        return f"{days}{ZH['days_later']}"
    return f"{days // 365}{ZH['years_later']}"


def normalize(item: dict) -> dict:
    question = str(item.get("question") or item.get("title") or "").strip()
    outcomes = [str(x) for x in parse_list(item.get("outcomes"))]
    prices = [num(x) for x in parse_list(item.get("outcomePrices"))]
    if not question or not prices:
        return {}
    pairs = [(outcomes[i] if i < len(outcomes) else f"Outcome {i + 1}", prices[i]) for i in range(len(prices))]
    pairs = [(name, price) for name, price in pairs if 0 <= price <= 1]
    if not pairs:
        return {}
    top_name, top_price = max(pairs, key=lambda x: x[1])
    slug = str(item.get("slug") or "")
    return {
        "question": question,
        "question_zh": "",
        "slug": slug,
        "url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com/markets",
        "category": category(item),
        "category_zh": "",
        "volume": num(item.get("volumeNum") or item.get("volume") or item.get("volume24hr")),
        "liquidity": num(item.get("liquidityNum") or item.get("liquidity")),
        "end": str(item.get("endDate") or ""),
        "outcome": top_name,
        "outcome_zh": "",
        "price": top_price,
    }


def add_translations(markets: list[dict]) -> None:
    cache = load_cache()
    for market in markets[:50]:
        market["question_zh"] = translate_text(market["question"], cache)
        market["outcome_zh"] = translate_text(market["outcome"], cache)
        market["category_zh"] = category_zh(market["category"], cache)
    for market in markets[50:]:
        market["question_zh"] = market["question"]
        market["outcome_zh"] = market["outcome"]
        market["category_zh"] = category_zh(market["category"], cache)
    save_cache(cache)


def rows(markets: list[dict], now: datetime) -> str:
    out = []
    for i, m in enumerate(markets[:12], 1):
        rank = "rank-1" if i == 1 else "rank-2" if i == 2 else "rank-3" if i == 3 else "rank-other"
        prob = "high" if m["price"] >= 0.66 else "medium" if m["price"] >= 0.34 else "low"
        out.append(f"""
        <tr>
          <td><span class="rank {rank}">{i}</span></td>
          <td>
            <a class="market-link" href="{html.escape(m['url'])}" target="_blank" rel="noopener"><strong>{html.escape(m['question_zh'])}</strong></a>
            <br><span class="muted">{ZH['original']}: {html.escape(m['question'])}</span>
            <br><span class="muted">{html.escape(days_until(m['end'], now))}</span>
          </td>
          <td><span class="tag {tag_class(m['category'])}">{html.escape(m['category_zh'])}</span></td>
          <td>{html.escape(m['outcome_zh'])}</td>
          <td><div class="prob-wrap"><span>{pct(m['price'])}</span><div class="prob-bar"><div class="prob-bar-fill {prob}" style="width:{m['price'] * 100:.0f}%"></div></div></div></td>
          <td class="vol-text">{money(m['volume'])}</td>
          <td>{money(m['liquidity'])}</td>
        </tr>""")
    return "\n".join(out)


def theme_cards(markets: list[dict]) -> str:
    volume = Counter()
    for market in markets:
        volume[market["category_zh"]] += market["volume"]
    cards = []
    for cat, vol in volume.most_common(6):
        examples = [m["question_zh"] for m in markets if m["category_zh"] == cat][:2]
        cards.append(f"""
      <div class="theme-card">
        <div class="theme-top"><h3>{html.escape(cat)}</h3><span>{money(vol)}</span></div>
        <p>{html.escape(' / '.join(examples))}</p>
      </div>""")
    return "\n".join(cards)


def insights(markets: list[dict]) -> str:
    total = sum(m["volume"] for m in markets)
    cat_count = Counter(m["category_zh"] for m in markets)
    cat_volume = Counter()
    for market in markets:
        cat_volume[market["category_zh"]] += market["volume"]
    hot_cat, hot_vol = cat_volume.most_common(1)[0]
    most_cat, most_n = cat_count.most_common(1)[0]
    median = statistics.median(m["price"] for m in markets)
    mood = ZH["consensus"] if median >= 0.6 else ZH["divergent"] if median <= 0.45 else ZH["neutral"]
    items = [
        ("green", ZH["concentration"], f"{ZH['total_volume_prefix']} {money(total)}\uff0c{ZH['hot_theme']} {html.escape(hot_cat)}\uff08{money(hot_vol)}\uff09\u3002"),
        ("yellow", ZH["structure"], f"{html.escape(most_cat)} {ZH['most_count_prefix']} {most_n} {ZH['unit_market']}\u3002"),
        ("blue", ZH["sentiment"], f"{ZH['median_prefix']} {pct(median)}\uff0c{ZH['overall']}{mood}\u3002"),
    ]
    return "\n".join(f'<div class="insight"><span class="insight-dot {c}"></span><div><strong>{t}</strong><p>{b}</p></div></div>' for c, t, b in items)


def render(markets: list[dict], now: datetime) -> str:
    top = markets[:12]
    total_volume = sum(m["volume"] for m in top)
    total_liquidity = sum(m["liquidity"] for m in top)
    avg_price = sum(m["price"] for m in top) / len(top)
    display_date = now.strftime(f"%Y{chr(24180)}%m{chr(26376)}%d{chr(26085)} %H:%M")
    title_date = now.strftime(f"%Y{chr(24180)}%m{chr(26376)}%d{chr(26085)}")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{ZH['report']} | {title_date}</title>
<style>
:root{{--bg-primary:#0a0e17;--bg-secondary:#111827;--bg-card:#161d2b;--bg-card-hover:#1c2538;--border:#1e2d45;--text-primary:#e2e8f0;--text-secondary:#94a3b8;--text-muted:#64748b;--accent-green:#22c55e;--accent-red:#ef4444;--accent-blue:#3b82f6;--accent-yellow:#eab308;--accent-purple:#a855f7;--accent-cyan:#06b6d4;--accent-orange:#f97316;--gradient-header:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);--gradient-green:linear-gradient(90deg,#22c55e,#16a34a);--gradient-blue:linear-gradient(90deg,#3b82f6,#2563eb);--shadow:0 4px 24px rgba(0,0,0,.3)}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg-primary);color:var(--text-primary);line-height:1.6;min-height:100vh}}a{{color:inherit;text-decoration:none}}.container{{max-width:1180px;margin:0 auto;padding:0 20px}}header{{background:var(--gradient-header);border-bottom:1px solid var(--border);padding:24px 0 30px;margin-bottom:30px}}.topbar{{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}}.logo{{font-size:22px;font-weight:700;color:var(--accent-blue);display:flex;align-items:center;gap:10px}}.logo-icon{{width:36px;height:36px;background:var(--accent-blue);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff}}.header-date{{color:var(--text-secondary);font-size:14px}}.status{{display:inline-flex;align-items:center;gap:8px;margin-top:18px;padding:8px 12px;border-radius:999px;background:rgba(34,197,94,.15);color:var(--accent-green);font-size:13px}}.live-dot{{width:8px;height:8px;background:var(--accent-green);border-radius:50%;animation:pulse 2s infinite}}@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.45}}}}.hero{{margin-top:22px;display:grid;gap:10px}}.hero h1{{font-size:clamp(28px,4vw,44px);line-height:1.1;letter-spacing:0}}.hero p{{max-width:760px;color:var(--text-secondary);font-size:15px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:34px}}.stat-card,.theme-card,.panel{{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:18px;transition:.2s ease}}.stat-card:hover,.theme-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow)}}.stat-label{{font-size:12px;color:var(--text-muted);margin-bottom:6px;text-transform:uppercase}}.stat-value{{font-size:26px;font-weight:750}}.green{{color:var(--accent-green)}}.blue{{color:var(--accent-blue)}}.purple{{color:var(--accent-purple)}}.cyan{{color:var(--accent-cyan)}}section{{margin-bottom:34px}}.section-title{{font-size:20px;font-weight:720;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid var(--border)}}.table-wrap{{overflow-x:auto;border-radius:12px;border:1px solid var(--border)}}table{{width:100%;border-collapse:collapse;background:var(--bg-card);min-width:900px}}thead th{{background:var(--bg-secondary);padding:14px 16px;text-align:left;font-size:12px;color:var(--text-muted);text-transform:uppercase;border-bottom:1px solid var(--border)}}tbody td{{padding:14px 16px;border-bottom:1px solid var(--border);font-size:14px;vertical-align:middle}}tbody tr:hover{{background:var(--bg-card-hover)}}.rank{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-weight:700;font-size:13px}}.rank-1{{background:rgba(234,179,8,.2);color:var(--accent-yellow)}}.rank-2{{background:rgba(148,163,184,.2);color:var(--text-secondary)}}.rank-3{{background:rgba(249,115,22,.2);color:var(--accent-orange)}}.rank-other{{background:rgba(148,163,184,.1);color:var(--text-muted)}}.market-link:hover{{color:var(--accent-blue)}}.muted{{font-size:12px;color:var(--text-muted)}}.tag{{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600}}.tag-sports{{background:rgba(34,197,94,.15);color:var(--accent-green)}}.tag-politics{{background:rgba(239,68,68,.15);color:var(--accent-red)}}.tag-finance{{background:rgba(59,130,246,.15);color:var(--accent-blue)}}.tag-crypto{{background:rgba(249,115,22,.15);color:var(--accent-orange)}}.tag-other{{background:rgba(148,163,184,.12);color:var(--text-secondary)}}.prob-wrap{{display:grid;gap:6px;min-width:120px}}.prob-bar{{height:8px;background:rgba(148,163,184,.18);border-radius:999px;overflow:hidden}}.prob-bar-fill{{height:100%;border-radius:999px}}.prob-bar-fill.high{{background:var(--gradient-green)}}.prob-bar-fill.medium{{background:var(--gradient-blue)}}.prob-bar-fill.low{{background:linear-gradient(90deg,var(--accent-yellow),var(--accent-orange))}}.vol-text{{font-weight:700}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.theme-top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}}.theme-top h3{{font-size:17px}}.theme-top span{{color:var(--accent-green);font-weight:700}}.theme-card p{{color:var(--text-secondary);font-size:13px}}.insight{{display:flex;gap:12px;padding:14px 0;border-bottom:1px solid var(--border)}}.insight:last-child{{border-bottom:0}}.insight-dot{{width:10px;height:10px;border-radius:50%;margin-top:7px;flex:0 0 auto}}.insight-dot.green{{background:var(--accent-green)}}.insight-dot.yellow{{background:var(--accent-yellow)}}.insight-dot.blue{{background:var(--accent-blue)}}.insight p{{color:var(--text-secondary);font-size:14px;margin-top:4px}}footer{{text-align:center;padding:30px 20px;color:var(--text-muted);font-size:12px;border-top:1px solid var(--border);margin-top:34px}}@media(max-width:900px){{.stats,.grid{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:640px){{.container{{padding:0 14px}}.stats,.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><div class="container"><div class="topbar"><div class="logo"><span class="logo-icon">P</span><span>{ZH['report']}</span></div><div class="header-date">{ZH['beijing_time']} {display_date}</div></div><span class="status"><span class="live-dot"></span>{ZH['auto_update']}</span><div class="hero"><h1>{ZH['hero_title']}</h1><p>{ZH['hero_desc']}</p></div></div></header>
<main class="container"><div class="stats"><div class="stat-card"><div class="stat-label">{ZH['sample_markets']}</div><div class="stat-value blue">{len(top)}</div></div><div class="stat-card"><div class="stat-label">{ZH['top_volume']}</div><div class="stat-value green">{money(total_volume)}</div></div><div class="stat-card"><div class="stat-label">{ZH['top_liquidity']}</div><div class="stat-value cyan">{money(total_liquidity)}</div></div><div class="stat-card"><div class="stat-label">{ZH['avg_probability']}</div><div class="stat-value purple">{pct(avg_price)}</div></div></div>
<section><h2 class="section-title">Top Markets</h2><div class="table-wrap"><table><thead><tr><th>#</th><th>{ZH['market']}</th><th>{ZH['category']}</th><th>{ZH['leading_outcome']}</th><th>{ZH['probability']}</th><th>{ZH['volume']}</th><th>{ZH['liquidity']}</th></tr></thead><tbody>{rows(top, now)}</tbody></table></div></section>
<section><h2 class="section-title">{ZH['theme_heat']}</h2><div class="grid">{theme_cards(markets)}</div></section>
<section><h2 class="section-title">{ZH['today_notes']}</h2><div class="panel">{insights(markets)}</div></section></main>
<footer>{ZH['footer']}</footer></body></html>
"""


def main() -> None:
    raw = get_json(API, {"active": "true", "closed": "false", "archived": "false", "limit": 100, "order": "volume", "ascending": "false"})
    markets = [m for m in (normalize(x) for x in raw) if m]
    markets.sort(key=lambda x: x["volume"], reverse=True)
    if not markets:
        raise SystemExit("No markets returned")
    add_translations(markets)
    now = datetime.now(TZ)
    (ROOT / "index.html").write_text(render(markets, now), encoding="utf-8", newline="\n")
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "latest.json").write_text(json.dumps({"generated_at": now.isoformat(), "markets": markets[:50]}, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
