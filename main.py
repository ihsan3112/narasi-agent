# === Narasi-Agent: kirim daftar link berita ke Telegram ===
# - Baca RSS dari FEEDS default, atau dari utils/sources.yaml (jika ada)
# - Kirim ke Telegram (judul + link) dengan pemotongan aman < 4096 char
# - Dedup link/judul dan urutkan berdasarkan waktu terbit (jika tersedia)

import os
import time
import json
import requests
import feedparser
from pathlib import Path

try:
    import yaml  # optional (untuk baca utils/sources.yaml)
except Exception:
    yaml = None

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# FEEDS default (boleh kamu ubah/kurangi)
DEFAULT_FEEDS = [
    # Media umum kripto
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss",          # kadang parsial
    "https://blockworks.co/feed",           # RSS WordPress standar
    # Ekosistem (opsional)
    "https://solana.com/news/rss.xml",
    "https://blog.chain.link/feed/",
]

def now_utc_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def load_custom_feeds():
    """
    Jika ada utils/sources.yaml dan berisi:
      feeds:
        - https://example.com/rss
        - ...
    maka gunakan itu.
    """
    cfg_path = Path("utils") / "sources.yaml"
    if not cfg_path.exists() or yaml is None:
        return None
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        feeds = data.get("feeds") if isinstance(data, dict) else None
        if isinstance(feeds, list) and all(isinstance(u, str) for u in feeds):
            return feeds
    except Exception:
        pass
    return None

def chunk_text(text, limit=3900):
    """Bagi pesan panjang ke beberapa bagian (<4096, aman 3900)."""
    parts, cur = [], []
    length = 0
    for line in text.splitlines():
        add = len(line) + 1
        if length + add > limit and cur:
            parts.append("\n".join(cur))
            cur, length = [], 0
        cur.append(line)
        length += add
    if cur:
        parts.append("\n".join(cur))
    return parts

def send_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] BOT_TOKEN/CHAT_ID kosong, lewati kirim Telegram")
        return
    try:
        r = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=30,
        )
        r.raise_for_status()
        print("[OK] sendMessage:", r.json().get("result", {}).get("message_id"))
    except Exception as e:
        print("[ERR] sendMessage:", repr(e))
        try:
            print("Resp:", r.status_code, r.text)  # type: ignore
        except Exception:
            pass

def format_item(entry):
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    # tanggal publish kalau ada
    ts = 0
    try:
        if entry.get("published_parsed"):
            ts = int(time.mktime(entry["published_parsed"]))
        elif entry.get("updated_parsed"):
            ts = int(time.mktime(entry["updated_parsed"]))
    except Exception:
        ts = 0
    return {"title": title, "link": link, "ts": ts}

def fetch_all_links(feeds):
    items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:20]:  # ambil sebagian per feed
                it = format_item(e)
                # hanya yang ada judul & link
                if it["title"] and it["link"]:
                    items.append(it)
        except Exception as e:
            print(f"[WARN] Gagal fetch {url}: {e}")
    # dedup (utamakan unik link)
    seen = set()
    deduped = []
    for it in items:
        key = it["link"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    # urutkan baru -> lama berdasarkan ts (kalau ts=0 akan di belakang)
    deduped.sort(key=lambda x: x["ts"], reverse=True)
    return deduped

def build_messages(items, max_items=40):
    if not items:
        return ["Tidak ada artikel baru yang bisa diambil saat ini."]
    # batasi jumlah total agar pesan tidak kepanjangan
    items = items[:max_items]
    header = f"🔔 Narasi-agent update ({now_utc_iso()})\n"
    lines = []
    for it in items:
        lines.append(f"• {it['title']}\n{it['link']}")
    body = "\n\n".join(lines)
    parts = chunk_text(header + "\n" + body)
    return parts

def main():
    feeds = load_custom_feeds() or DEFAULT_FEEDS
    print("[INFO] Feeds yang dipakai:", json.dumps(feeds, indent=2))
    items = fetch_all_links(feeds)
    print(f"[INFO] Total items sesudah dedup: {len(items)}")
    messages = build_messages(items)
    for idx, msg in enumerate(messages, 1):
        print(f"[INFO] Kirim part {idx}/{len(messages)} (len={len(msg)})")
        send_message(msg)

if __name__ == "__main__":
    main()
