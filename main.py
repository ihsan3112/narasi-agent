import os, datetime, logging
from pathlib import Path

import feedparser
import pandas as pd
import yaml
from dotenv import load_dotenv

# -------- SETUP --------
ROOT = Path(__file__).resolve().parent
(REPORTS := ROOT / "reports").mkdir(exist_ok=True)
(LOGS := ROOT / "logs").mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOGS / "narasi.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

LABELS = [
    "AI","DePIN","RWA","Gaming","Solana","Ethereum","L2/OP-Stack",
    "BTC L2","Restaking","Social/Creator Economy","DeFi Perp/DEX",
    "Interop/Bridges","Data/Oracle"
]

def load_sources():
    with open(ROOT / "sources.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def collect_rss(urls, limit=100):
    items = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:limit]:
                items.append({
                    "date": getattr(e, "published", ""),
                    "source": url,
                    "link": getattr(e, "link", ""),
                    "title": getattr(e, "title", ""),
                    "text": (getattr(e, "summary", "") or "")[:8000]
                })
        except Exception as ex:
            logging.exception(f"RSS error: {url}: {ex}")
    return items

def rule_labels(title_text: str):
    t = (title_text or "").lower()
    tags = []
    if any(k in t for k in ["solana","solana vm"," sol "]): tags.append("Solana")
    if any(k in t for k in ["optimism","op stack","base","arbitrum","l2"]): tags.append("L2/OP-Stack")
    if any(k in t for k in ["restaking","eigenlayer"]): tags.append("Restaking")
    if any(k in t for k in [" ai "," agent","artificial intelligence"," llm"]): tags.append("AI")
    if any(k in t for k in ["rwa","treasury","t-bill","tokenized bonds","us treasur"]): tags.append("RWA")
    if any(k in t for k in ["gaming","gamefi"]): tags.append("Gaming")
    if any(k in t for k in ["bridge","interoperab","interchain","wormhole","hyperlane","layerzero","l0"]): tags.append("Interop/Bridges")
    if any(k in t for k in ["oracle","data","indexer"]): tags.append("Data/Oracle")
    if any(k in t for k in ["perp","perpetual","dex","amm","liquidity","market maker"]): tags.append("DeFi Perp/DEX")
    if any(k in t for k in ["ethereum"," eth "]): tags.append("Ethereum")
    if any(k in t for k in ["btc l2","bitcoin l2","bitvm","runes","ordinals"]): tags.append("BTC L2")
    if any(k in t for k in ["creator","social","zora"]): tags.append("Social/Creator Economy")
    return tags or ["Uncategorized"]

def make_report(rows):
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    df = pd.DataFrame(rows)
    csv_path = REPORTS / f"{ts}-report.csv"
    txt_path = REPORTS / f"{ts}-summary.txt"
    df.to_csv(csv_path, index=False)

    # Ringkasan top labels
    lines = []
    if not df.empty:
        top = (df.explode("topic_tags")
                 .groupby("topic_tags")["link"]
                 .count().sort_values(ascending=False).head(7))
        lines.append("RINGKASAN NARASI (Top 7 by Frequency):")
        for tag, cnt in top.items():
            lines.append(f"- {tag}: {cnt} sumber")
        lines.append("")
        lines.append("Contoh kutipan:")
        for _, r in df.head(5).iterrows():
            title = str(r.get("title","")).strip()
            link = str(r.get("link","")).strip()
            lines.append(f"* {title} ({link})")
    else:
        lines.append("Tidak ada data dari RSS. Cek koneksi atau sumber RSS.")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return csv_path, txt_path

def main():
    load_dotenv()  # untuk BOT_TOKEN/CHAT_ID bila ada
    try:
        cfg = load_sources()
        rss_urls = cfg.get("rss", [])
        logging.info(f"Collecting from {len(rss_urls)} RSS feeds")
        docs = collect_rss(rss_urls)
        outputs = []
        for d in docs:
            tags = rule_labels((d.get("title","") + " " + d.get("text","")))
            outputs.append({
                "date": d.get("date",""), "source": d.get("source",""), "link": d.get("link",""),
                "entity": "", "entity_type": "fund_or_proj",
                "title": d.get("title",""), "quote": d.get("title",""),
                "chain": "multi", "topic_tags": tags,
                "sentiment": "neutral", "confidence": 0.55,
                "onchain_tx_usd": 0
            })
        csv_path, txt_path = make_report(outputs)
        print(f"[OK] CSV: {csv_path}")
        print(f"[OK] TXT: {txt_path}")
        # kirim ke Telegram kalau env tersedia
        try:
            from utils.telegram_notifier import send_message, send_file
            send_message("✅ Laporan narasi selesai.")
            send_file(str(csv_path), caption="CSV laporan")
            send_file(str(txt_path), caption="Ringkasan TXT")
        except Exception as te:
            logging.warning(f"Telegram warn: {te}")
    except Exception as ex:
        logging.exception(f"Fatal: {ex}")
        print("Terjadi error. Cek logs/narasi.log")

if __name__ == "__main__":
    main()

# --- Jadwal otomatis (cron contoh, 07:00 WIB) ---
# crontab -e
# 0 0 * * * /usr/bin/bash -lc 'cd /path/narasi-agent && source .venv/bin/activate && python main.py >> logs/cron.out 2>&1'
# (0 0 UTC ≈ 07:00 WIB)
