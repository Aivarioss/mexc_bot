# train_all_models.py
import os
import pandas as pd
import ccxt
from dotenv import load_dotenv
from modules.ai_trainer import train_ai_model
from datetime import datetime

# === Ielādē .env
load_dotenv()
api_key = os.getenv("MEXC_API_KEY")
api_secret = os.getenv("MEXC_API_SECRET")

exchange = ccxt.mexc({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})

DATA_DIR = "data/market_data"
MODEL_DIR = "models"
LOG_FILE = "logs/train_all_errors.log"
os.makedirs("logs", exist_ok=True)

files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
total = len(files)

print(f"📊 Atrasti {total} CSV faili. Sākam trenēšanu...\n")

for idx, file in enumerate(files, start=1):
    symbol = file.replace("USDT.csv", "/USDT")
    model_path = os.path.join(MODEL_DIR, file.replace(".csv", "_model.pkl"))

    print(f"[{idx}/{total}] ⏳ Pārbaude: {symbol}")

    # ✅ Skip already trained
    if os.path.exists(model_path):
        print(f"⏭️ {symbol} modelis jau eksistē. Izlaižam.")
        continue

    # 📁 Verificē CSV failu saturu
    csv_path = os.path.join(DATA_DIR, file)
    try:
        df = pd.read_csv(csv_path)
        if df.empty or "label" not in df.columns:
            print(f"⚠️ {symbol} — tukšs vai nederīgs fails.")
            continue
    except Exception as e:
        print(f"❌ Kļūda lasot {symbol} CSV: {e}")
        with open(LOG_FILE, "a", encoding="utf-8") as logf:
            logf.write(f"[{datetime.now()}] {symbol}: CSV read error — {e}\n")
        continue

    # 🧠 Trenē AI modeli
    print(f"🚀 Trenējam: {symbol}")
    try:
        train_ai_model(symbol, exchange)
    except Exception as e:
        print(f"❌ Kļūda trenējot {symbol}: {e}")
        with open(LOG_FILE, "a", encoding="utf-8") as logf:
            logf.write(f"[{datetime.now()}] {symbol}: Training error — {e}\n")
        continue

print("\n✅ Gatavs! Visi trenējamie faili apstrādāti.")
