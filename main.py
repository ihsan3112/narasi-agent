# === Kirim ringkasan + daftar link ke Telegram ===
import os, requests, pandas as pd
from pathlib import Path

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def chunk_text(text, limit=3900):
    """Bagi pesan panjang jadi beberapa bagian agar < 4096 char (aman 3900)."""
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
    r = requests.post(f"{TELEGRAM_API}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True})
    try:
        r.raise_for_status()
    except Exception as e:
        print("[ERR] Telegram sendMessage:", e, r.text[:300])

def format_summary(summary_path: Path) -> str:
    ts = summary_path.stem.replace("-summary","")
    header = f"📰 Narasi Agent Report ({ts})"
    body = summary_path.read_text(encoding="utf-8").strip()
    # Ambil 15 baris pertama agar ringkas (opsional)
    short = "\n".join(body.splitlines()[:50])
    return f"{header}\n\n{short}"

def format_links(csv_path: Path, max_items=25) -> str:
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"⚠️ Gagal baca CSV: {e}"

    # Cari kolom kandidat
    title_col = next((c for c in df.columns if c.lower() in ["title","judul","headline","subject"]), None)
    url_col   = next((c for c in df.columns if c.lower() in ["url","link","href"]), None)
    src_col   = next((c for c in df.columns if c.lower() in ["source","sumber","site"]), None)

    if not url_col:
        return "⚠️ CSV tidak punya kolom URL."
    if not title_col:
        # fallback: pakai url sebagai judul kalau tak ada title
        df[ "title_fallback" ] = df[url_col]
        title_col = "title_fallback"

    lines = ["🔗 Berita terbaru:"]
    for i, row in df.head(max_items).iterrows():
        title = str(row[title_col]).strip()
        url   = str(row[url_col]).strip()
        src   = f" ({row[src_col]})" if src_col and not pd.isna(row[src_col]) else ""
        lines.append(f"{i+1}. {title}{src}\n   {url}")
    if len(df) > max_items:
        lines.append(f"\n…dan {len(df)-max_items} link lainnya (lihat CSV penuh).")
    return "\n".join(lines)

def send_summary_and_links():
    reports = Path("reports")
    if not reports.exists():
        print("[WARN] Folder reports/ belum ada, lewati kirim Telegram")
        return

    # Ambil file terbaru
    txts = sorted(reports.glob("*-summary.txt"))
    csvs = sorted(reports.glob("*-report.csv"))
    if txts:
        summary_msg = format_summary(txts[-1])
        for part in chunk_text(summary_msg):
            send_message(part)
    else:
        send_message("⚠️ Ringkasan belum tersedia.")

    if csvs:
        links_msg = format_links(csvs[-1], max_items=25)
        for part in chunk_text(links_msg):
            send_message(part)
    else:
        send_message("⚠️ Daftar link belum tersedia.")

# PANGGIL fungsi ini DI PALING AKHIR setelah laporan dibuat:
if __name__ == "__main__":
    # ... (kode kamu yang generate laporan)
    # pastikan bagian ini tetap terakhir:
    send_summary_and_links()
