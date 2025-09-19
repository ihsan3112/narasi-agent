# Narasi Agent (Hedge Fund / VC Narrative Tracker)

Proyek Python sederhana untuk mengambil berita via RSS (tanpa API), memberi label narasi dasar,
lalu menyimpan laporan ke folder `reports/` dalam format CSV & TXT. Opsional: kirim ke Telegram.

## Cara jalan cepat (lokal)
```bash
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows (PowerShell)
# .venv\\Scripts\\Activate.ps1

pip install -r requirements.txt
python main.py
```

Output:
- `reports/YYYY-MM-DD-report.csv`
- `reports/YYYY-MM-DD-summary.txt`

## Kirim ke Telegram (opsional)
1. Buat bot via @BotFather → ambil `BOT_TOKEN`
2. Dapatkan `CHAT_ID` via `getUpdates` setelah chat bot sekali
3. Buat file `.env`:
```
BOT_TOKEN=123:abc...
CHAT_ID=123456789
```
4. Jalankan lagi `python main.py`

## Jadwal otomatis (cron contoh, 07:00 WIB ≈ 00:00 UTC di GitHub Actions)
Lihat instruksi di komentar bagian bawah `main.py`.
