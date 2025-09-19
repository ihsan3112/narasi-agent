import os, requests


def _need():
    return os.getenv("BOT_TOKEN") and os.getenv("CHAT_ID")


def send_message(text: str):
    if not _need():
        return
    url = f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/sendMessage"
    r = requests.post(url, data={"chat_id": os.getenv('CHAT_ID'), "text": text})
    r.raise_for_status()


def send_file(path: str, caption: str = None):
    if not _need():
        return
    url = f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/sendDocument"
    with open(path, "rb") as f:
        r = requests.post(url, data={"chat_id": os.getenv('CHAT_ID'), "caption": caption or ""}, files={"document": f})
    r.raise_for_status()
