#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Narasi Agent - Minimal, robust, CI-friendly.
- Fetch crypto news from RSS feeds
- Classify into simple narratives by keywords
- Save CSV + TXT summary under reports/
- Optionally send a short message to Telegram if BOT_TOKEN & CHAT_ID are set
"""

from __future__ import annotations
import os
import sys
import json
import time
import datetime as dt
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Third-party (ringan & umum)
import feedparser
import requests

# ---------------------------
# Paths & timestamps
# ---------------------------
ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
LOGS = ROOT / "logs"
REPORTS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

UTC = dt.timezone.utc
now = dt.datetime.now(UTC)
stamp_day = now.strftime("%Y-%m-%d")
stamp_iso = now.isoformat(timespec="seconds")

# ---------------------------
# Config sumber RSS (fallback)
# ---------------------------
DEFAULT_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.theblock.co/rss",
    "https://cryptoslate.com/feed/",
    "https://decrypt.co/feed",
]

# Kalau ada sources.yaml (opsional), baca daftar feed dari sana (key: rss)
def load_feeds_from_sources() -> List[str]:
    src = ROOT / "sources.yaml"
    if not src.exists():
        return DEFAULT_FEEDS
    try:
        import yaml  # hanya jika ada
        data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
        feeds = data.get("rss", [])
        return [u for u in feeds if isinstance(u, str) and u.strip()] or DEFAULT_FEEDS
    except Exception:
        return DEFAULT_FEEDS


FEEDS = load_feeds_from_sources()

# ---------------------------
# Narasi / kategori sederhana
# ---------------------------
NARRATIVE_RULES: Dict[str, List[str]] = {
    "BTC L2 / Rollup": ["btc l2", "bitcoin l2", "bitvm", "rollkit", "stacks", "rootstock", "bvm"],
    "Restaking / AVS": ["restaking", "eigenlayer", "avs"],
    "AI x Crypto": ["ai", "artificial intelligence", "llm", "depin"],
    "DeFi / Perp/DEX": ["defi", "dex", "perp", "amm", "lending", "yield"],
    "Solana": ["solana", "sol", "saga", "jito"],
    "Ethereum / L2": ["ethereum", "eth", "optimism", "arbitrum", "base", "zksync", "scroll", "linea"],
    "Meme / Culture": ["meme", "pepe", "doge", "shib", "bonk"],
    "Airdrop / Points": ["airdrop", "points", "campaign", "quest", "galxe"],
    "Infra / Oracles": ["chainlink", "link", "oracle", "data feed"],
}

def classify(text: str) -> str:
    t = (text or "").lower()
    for label, keys in NARRATIVE_RULES.items():
        if any(k in t for k in keys):
            return label
    return "Uncategorized"

# ---------------------------
# Utils
# ---------------------------
def safe_get(d: dict, *keys, default=""):
    x = d
    for k in keys:
        x = x.get(k, {})
    return x if x else default

def parse_published(entry: dict) -> str:
    # feedparser sering berikan 'published_parsed' (time.struct_time)
    try:
        tt = entry.get("published_parsed") or entry.get("updated_parsed")
        if tt:
            return dt.datetime.fromtimestamp(time.mktime(tt), UTC).isoformat(timespec="seconds")
    except Exception:
        pass
    # fallback: string
    return (entry.get("published") or entry.get("updated") or stamp_iso)

def fetch_feed(url: str) -> List[Dict[str, Any]]:
    out = []
    try:
        fp = feedparser.parse(url)
        for e in fp.entries[:50]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            published = parse_published(e)
            summary = (e.get("summary") or e.get("description") or "").strip()
            source = (fp.feed.get("title") or url).strip()

            if not title or not link:
                continue

            out.append({
                "title": title,
                "link": link,
                "published": published,
                "source": source,
                "summary": summary,
            })
    except Exception as ex:
        (LOGS / f"fetch_error_{int(time.time())}.log").write_text(
            f"{url}\n{repr(ex)}\n", encoding="utf-8"
        )
    return out

# ---------------------------
# Main: fetch -> classify -> save
# ---------------------------
def main() -> Tuple[Path, Path]:
    all_rows: List[Dict[str, Any]] = []
    for u in FEEDS:
        all_rows.extend(fetch_feed(u))

    # de-dup by link
    seen = set()
    uniq = []
    for r in all_rows:
        if r["link"] in seen:
            continue
        seen.add(r["link"])
        r["narrative"] = classify(f"{r['title']} {r['summary']}")
        uniq.append(r)

    # sort newest first
    uniq.sort(key=lambda x: x.get("published", ""), reverse=True)

    # ---- WRITE CSV ----
    csv_path = REPORTS / f"{stamp_day}-report.csv"
    import csv
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["published_utc", "narrative", "title", "source", "link"])
        for r in uniq:
            w.writerow([r["published"], r["narrative"], r["title"], r["source"], r["link"]])

    # ---- WRITE TXT SUMMARY ----
    # hitung frekuensi narasi top
    from collections import Counter
    freq = Counter([r["narrative"] for r in uniq])
    top5 = freq.most_common(7)

    txt_path = REPORTS / f"{stamp_day}-summary.txt"
    with txt_path.open("w", encoding="utf-8") as f:
        f.write(f"RINGKASAN NARASI (Top by Frequency) - {stamp_iso}\n")
        for label, n in top5:
            f.write(f"- {label}: {n} sumber\n")
        f.write("\nContoh kutipan:\n")
        for r in uniq[:10]:
            f.write(f"• {r['title']} ({r['source']})\n  {r['link']}\n")

    print(f"[OK] CSV: {csv_path}")
    print(f"[OK] TXT: {txt_path}")
    return txt_path, csv_path

# ---------------------------
# Optional: Telegram ping (teks pendek)
# ---------------------------
def telegram_ping(message: str) -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "").strip()
    if not (token and chat_id):
        return  # silent if not configured

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=15)
        print("[OK] Telegram ping sent.")
    except Exception as ex:
        print(f"[WARN] Telegram ping failed: {ex}", file=sys.stderr)

# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    try:
        txt, csvf = main()
        telegram_ping(f"Narasi-agent selesai {stamp_iso} (UTC). File siap di /reports/ ✅")
        sys.exit(0)
    except Exception as e:
        (LOGS / "fatal.log").write_text(f"{stamp_iso}\n{repr(e)}\n", encoding="utf-8")
        print(f"[FATAL] {e}", file=sys.stderr)
        sys.exit(1)
