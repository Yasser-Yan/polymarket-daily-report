#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import statistics
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://gamma-api.polymarket.com/markets"
ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")


def get_json(url: str, params: dict) -> list[dict]:
    req = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "polymarket-daily-report"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
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
        return "结算时间待确认"
    try:
        end = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "结算时间待确认"
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    days = math.ceil((end - now.astimezone(timezone.utc)).total_seconds() / 86400)
    if days < 0:
        return "已到期/待结算"
    if days == 0:
        return "今天结算"
    if days < 365:
        return f"{days}天后结算"
    return f"{days // 365}年+后结算"


def normalize(item: dict) -> dict:
    q = str(item.get("question") or item.get("title") or "").strip()
    outcomes = [str(x) for x in parse_list(item.get("outcomes"))]
    prices = [num(x) for x in parse_list(item.get("outcomePrices"))]
    if not q or not prices:
        return {}
    pairs = [(outcomes[i] if i < len(outcomes) else f"Outcome {i + 1}", prices[i]) for i in range(len(prices))]
    pairs = [(name, price) for name, price in pairs if 0 <= price <= 1]
    if not pairs:
        return {}
    top_name, top_price = max(pairs, key=lambda x: x[1])
    slug = str(item.get("slug") or "")
    return {
        "question": q,
        "slug": slug,
        "url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com/markets",
        "category": category(item),
        "volume": num(item.get("volumeNum") or item.get("volume") or item.get("volume24hr")),
        "liquidity": num(item.get("liquidityNum") or item.get("liquidity")),
        "end": str(item.get("endDate") or ""),
        "outcome": top_name,
        "price": top_price,
    }


def rows(markets: list[dict], now: datetime) -> str:
    out = []
    for i, m in enumerate(markets[:12], 1):
        rank = "rank-1" if i == 1 else "rank-2" if i == 2 else "rank-3" if i == 3 else "rank-other"
        prob = "high" if m["price"] >= 0.66 else "medium" if m["price"] >= 0.34 else "low"
        out.append(f"""
        <tr>
          <td><span class="rank {rank}">{i}</span></td>
          <td><a class="market-link" href="{html.escape(m['url'])}" target="_blank" rel="noopener"><strong>{html.escape(m['question'])}</strong></a><br><span class="muted">{html.escape(days_until(m['end'], now))}</span></td>
          <td><span class="tag {tag_class(m['category'])}">{html.escape(m['category'])}</span></td>
          <td>{html.escape(m['outcome'])}</td>
          <td><div class="prob-wrap"><span>{pct(m['price'])}</span><div class="prob-bar"><div class="prob-bar-fill {prob}" style="width:{m['price'] * 100:.0f}%"></div></div></div></td>
          <td class="vol-text">{money(m['volume'])}</td>
          <td>{money(m['liquidity'])}</td>
        </tr>""")
    return "\n".join(out)


def theme_cards(markets: list[dict]) -> str:
    volume = Counter()
    for m in markets:
        volume[m["category"]] += m["volume"]
    cards = []
    for cat, vol in volume.most_common(6):
        examples = [m["question"] for m in markets if m["category"] == cat][:2]
        cards.append(f"""
      <div class="theme-card">
        <div class="theme-top"><h3>{html.escape(cat)}</h3><span>{money(vol)}</span></div>
        <p>{html.escape(" / ".join(examples))}</p>
      </div>""")
    return "\n".join(cards)


def insights(markets: list[dict]) -> str:
    total = sum(m["volume"] for m in markets)
    cat_count = Counter(m["category"] for m in markets)
    cat_volume = Counter()
    for m in markets:
        cat_volume[m["category"]] += m["volume"]
    hot_cat, hot_vol = cat_volume.most_common(1)[0]
    most_cat, most_n = cat_count.most_common(1)[0]
    median = statistics.median(m["price"] for m in markets)
    mood = "更偏共识" if median >= 0.6 else "分歧较高" if median <= 0.45 else "中性分布"
    items = [
        ("green", "成交集中度", f"本次样本总成交量约 {money(total)}，成交额最高主题是 {html.escape(hot_cat)}（{money(hot_vol)}）。"),
        ("yellow", "市场结构", f"{html.escape(most_cat)} 类市场数量最多，共 {most_n} 个。"),
        ("blue", "概率情绪", f"领先结果的中位概率为 {pct(median)}，整体呈现{mood}。"),
    ]
    return "\n".join(f'<div class="insight"><span class="insight-dot {c}"></span><div><strong>{t}</strong><p>{b}</p></div></div>' for c, t, b in items)


def render(markets: list[dict], now: datetime) -> str:
    top = markets[:12]
    total_volume = sum(m["volume"] for m in top)
    total_liquidity = sum(m["liquidity"] for m in top)
    avg_price = sum(m["price"] for m in top) / len(top)
    display_date = now.strftime("%Y年%m月%d日 %H:%M")
    title_date = now.strftime("%Y年%m月%d日")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Polymarket 预测市场日报 | {title_date}</title>
<style>
:root{{--bg-primary:#0a0e17;--bg-secondary:#111827;--bg-card:#161d2b;--bg-card-hover:#1c2538;--border:#1e2d45;--text-primary:#e2e8f0;--text-secondary:#94a3b8;--text-muted:#64748b;--accent-green:#22c55e;--accent-red:#ef4444;--accent-blue:#3b82f6;--accent-yellow:#eab308;--accent-purple:#a855f7;--accent-cyan:#06b6d4;--accent-orange:#f97316;--gradient-header:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);--gradient-green:linear-gradient(90deg,#22c55e,#16a34a);--gradient-blue:linear-gradient(90deg,#3b82f6,#2563eb);--shadow:0 4px 24px rgba(0,0,0,.3)}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg-primary);color:var(--text-primary);line-height:1.6;min-height:100vh}}a{{color:inherit;text-decoration:none}}.container{{max-width:1180px;margin:0 auto;padding:0 20px}}header{{background:var(--gradient-header);border-bottom:1px solid var(--border);padding:24px 0 30px;margin-bottom:30px}}.topbar{{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}}.logo{{font-size:22px;font-weight:700;color:var(--accent-blue);display:flex;align-items:center;gap:10px}}.logo-icon{{width:36px;height:36px;background:var(--accent-blue);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff}}.header-date{{color:var(--text-secondary);font-size:14px}}.status{{display:inline-flex;align-items:center;gap:8px;margin-top:18px;padding:8px 12px;border-radius:999px;background:rgba(34,197,94,.15);color:var(--accent-green);font-size:13px}}.live-dot{{width:8px;height:8px;background:var(--accent-green);border-radius:50%;animation:pulse 2s infinite}}@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.45}}}}.hero{{margin-top:22px;display:grid;gap:10px}}.hero h1{{font-size:clamp(28px,4vw,44px);line-height:1.1;letter-spacing:0}}.hero p{{max-width:760px;color:var(--text-secondary);font-size:15px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:34px}}.stat-card,.theme-card,.panel{{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:18px;transition:.2s ease}}.stat-card:hover,.theme-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow)}}.stat-label{{font-size:12px;color:var(--text-muted);margin-bottom:6px;text-transform:uppercase}}.stat-value{{font-size:26px;font-weight:750}}.green{{color:var(--accent-green)}}.blue{{color:var(--accent-blue)}}.purple{{color:var(--accent-purple)}}.cyan{{color:var(--accent-cyan)}}section{{margin-bottom:34px}}.section-title{{font-size:20px;font-weight:720;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid var(--border)}}.table-wrap{{overflow-x:auto;border-radius:12px;border:1px solid var(--border)}}table{{width:100%;border-collapse:collapse;background:var(--bg-card);min-width:900px}}thead th{{background:var(--bg-secondary);padding:14px 16px;text-align:left;font-size:12px;color:var(--text-muted);text-transform:uppercase;border-bottom:1px solid var(--border)}}tbody td{{padding:14px 16px;border-bottom:1px solid var(--border);font-size:14px;vertical-align:middle}}tbody tr:hover{{background:var(--bg-card-hover)}}.rank{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-weight:700;font-size:13px}}.rank-1{{background:rgba(234,179,8,.2);color:var(--accent-yellow)}}.rank-2{{background:rgba(148,163,184,.2);color:var(--text-secondary)}}.rank-3{{background:rgba(249,115,22,.2);color:var(--accent-orange)}}.rank-other{{background:rgba(148,163,184,.1);color:var(--text-muted)}}.market-link:hover{{color:var(--accent-blue)}}.muted{{font-size:12px;color:var(--text-muted)}}.tag{{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600}}.tag-sports{{background:rgba(34,197,94,.15);color:var(--accent-green)}}.tag-politics{{background:rgba(239,68,68,.15);color:var(--accent-red)}}.tag-finance{{background:rgba(59,130,246,.15);color:var(--accent-blue)}}.tag-crypto{{background:rgba(249,115,22,.15);color:var(--accent-orange)}}.tag-other{{background:rgba(148,163,184,.12);color:var(--text-secondary)}}.prob-wrap{{display:grid;gap:6px;min-width:120px}}.prob-bar{{height:8px;background:rgba(148,163,184,.18);border-radius:999px;overflow:hidden}}.prob-bar-fill{{height:100%;border-radius:999px}}.prob-bar-fill.high{{background:var(--gradient-green)}}.prob-bar-fill.medium{{background:var(--gradient-blue)}}.prob-bar-fill.low{{background:linear-gradient(90deg,var(--accent-yellow),var(--accent-orange))}}.vol-text{{font-weight:700}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.theme-top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}}.theme-top h3{{font-size:17px}}.theme-top span{{color:var(--accent-green);font-weight:700}}.theme-card p{{color:var(--text-secondary);font-size:13px}}.insight{{display:flex;gap:12px;padding:14px 0;border-bottom:1px solid var(--border)}}.insight:last-child{{border-bottom:0}}.insight-dot{{width:10px;height:10px;border-radius:50%;margin-top:7px;flex:0 0 auto}}.insight-dot.green{{background:var(--accent-green)}}.insight-dot.yellow{{background:var(--accent-yellow)}}.insight-dot.blue{{background:var(--accent-blue)}}.insight p{{color:var(--text-secondary);font-size:14px;margin-top:4px}}footer{{text-align:center;padding:30px 20px;color:var(--text-muted);font-size:12px;border-top:1px solid var(--border);margin-top:34px}}@media(max-width:900px){{.stats,.grid{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:640px){{.container{{padding:0 14px}}.stats,.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><div class="container"><div class="topbar"><div class="logo"><span class="logo-icon">P</span><span>Polymarket 预测市场日报</span></div><div class="header-date">北京时间 {display_date}</div></div><span class="status"><span class="live-dot"></span>每日自动更新</span><div class="hero"><h1>今日预测市场热度扫描</h1><p>按 Polymarket 活跃市场成交量自动生成，聚焦高流动性问题、当前主流概率和市场主题变化。</p></div></div></header>
<main class="container"><div class="stats"><div class="stat-card"><div class="stat-label">样本市场</div><div class="stat-value blue">{len(top)}</div></div><div class="stat-card"><div class="stat-label">头部成交量</div><div class="stat-value green">{money(total_volume)}</div></div><div class="stat-card"><div class="stat-label">头部流动性</div><div class="stat-value cyan">{money(total_liquidity)}</div></div><div class="stat-card"><div class="stat-label">平均领先概率</div><div class="stat-value purple">{pct(avg_price)}</div></div></div>
<section><h2 class="section-title">Top Markets</h2><div class="table-wrap"><table><thead><tr><th>#</th><th>市场</th><th>类别</th><th>领先结果</th><th>概率</th><th>成交量</th><th>流动性</th></tr></thead><tbody>{rows(top, now)}</tbody></table></div></section>
<section><h2 class="section-title">主题热度</h2><div class="grid">{theme_cards(markets)}</div></section>
<section><h2 class="section-title">今日观察</h2><div class="panel">{insights(markets)}</div></section></main>
<footer>数据来源：Polymarket Gamma API。页面由 GitHub Actions 每天自动生成。市场价格和成交量可能存在延迟，仅供研究参考。</footer></body></html>
"""


def main() -> None:
    raw = get_json(API, {"active": "true", "closed": "false", "archived": "false", "limit": 100, "order": "volume", "ascending": "false"})
    markets = [m for m in (normalize(x) for x in raw) if m]
    markets.sort(key=lambda x: x["volume"], reverse=True)
    if not markets:
        raise SystemExit("No markets returned")
    now = datetime.now(TZ)
    (ROOT / "index.html").write_text(render(markets, now), encoding="utf-8", newline="\n")
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "latest.json").write_text(json.dumps({"generated_at": now.isoformat(), "markets": markets[:50]}, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
