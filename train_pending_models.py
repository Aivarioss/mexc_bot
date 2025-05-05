import os
import sys
import json
import time
import ccxt
import pandas as pd
from dotenv import load_dotenv
from modules.ai_trainer import train_ai_model
from config.settings import is_test_mode
from utils.summary import log_test_event, log_event

# === UTF-8 SUPPORT TERMINĀLIM (Windows fix)
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# === INIT
load_dotenv()
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_API_SECRET"),
    'enableRateLimit': True
})

PENDING_FILE = "data/pending_training.json"
DATA_DIR = "data/market_data"
LOG_FILE = "logs/train_errors.log"
os.makedirs("logs", exist_ok=True)

# === Ielādē pending simbolus
if not os.path.exists(PENDING_FILE):
    print("⚠️  Nav faila 'pending_training.json'.")
    exit()

with open(PENDING_FILE, 'r', encoding='utf-8') as f:
    try:
        pending = json.load(f)
    except json.JSONDecodeError:
        print("❌ Kļūda lasot pending JSON – iespējams bojāts fails.")
        exit()

if not pending:
    print("✅ Nav tokenu, ko apmācīt.")
    exit()

print(f"📊 Apmācīsim {len(pending)} tokenus...\n")

trained = []

for symbol in pending:
    try:
        safe_name = symbol.replace("/", "").replace(":", "")
        csv_path = os.path.join(DATA_DIR, f"{safe_name}.csv")

        if not os.path.exists(csv_path):
            print(f"⛔️ Trūkst CSV fails: {csv_path}")
            continue

        df = pd.read_csv(csv_path)

        if df.empty:
            print(f"⚠️  Tukšs fails: {csv_path}")
            continue
        
            print(f"🧠 Trenējam AI modeli: {symbol}")

        train_ai_model(symbol, exchange)
        trained.append(symbol)

        # === Logging
        if is_test_mode():
            log_test_event("test_train", symbol=symbol)
        else:
            log_event("train", symbol=symbol)

        time.sleep(1.5)

    except Exception as e:
        print(f"❌ Kļūda trenējot {symbol}: {e}")
        with open(LOG_FILE, "a", encoding="utf-8") as logf:
            logf.write(f"{symbol}: {str(e)}\n")

# === Atjauno pending sarakstu
remaining = [s for s in pending if s not in trained]
with open(PENDING_FILE, "w", encoding="utf-8") as f:
    json.dump(remaining, f, indent=2, ensure_ascii=False)

print(f"\n✅ Apmācīti {len(trained)} tokeni. Atlikuši: {len(remaining)}")
