import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def escape_markdown(text):
    escape_chars = r"\_*[]()~`>#+-=|{}.!<>"
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram BOT_TOKEN vai CHAT_ID nav ielādēts.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print(f"⚠️ Telegram kļūda: {response.status_code}")
        else:
            print("📩 Telegram ziņa nosūtīta.")
    except Exception as e:
        print(f"⚠️ Telegram kļūda: {e}")
        
def sanitize_text(text):
    return text.encode('utf-16', 'surrogatepass').decode('utf-16')
        
def send_reply(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN vai CHAT_ID nav ielādēts.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    escaped_text = escape_markdown(text)  # <-- TE APSTRĀDĀ
    data = {
        "chat_id": CHAT_ID,
        "text": escaped_text,
        "parse_mode": "MarkdownV2"  # <-- Uzlabo uz MarkdownV2
    }

    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print(f"⚠️ Telegram kļūda: {response.status_code} → {response.text}")
        else:
            print("📩 Telegram ziņa nosūtīta (MarkdownV2).")
    except Exception as e:
        print(f"⚠️ Neizdevās nosūtīt Telegram ziņu: {e}")
