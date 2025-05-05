# label_candidates.py
import csv
import os
import ccxt
import sys
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

load_dotenv()

exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_API_SECRET"),
    'enableRateLimit': True
})

INPUT_FILE = "data/candidate_tokens.csv"
OUTPUT_FILE = "data/labeled_candidates.csv"
PENDING_FILE = "data/pending_training.json"

FIELDNAMES = [
    "timestamp", "symbol", "price", "rsi", "macd", "macd_signal",
    "volume", "avg_volume", "safety_score", "strategy",
    "ai_confidence", "reject_reason", "profit_after_6h", "label"
]

def label_candidates():
    labeled = []
    already_labeled = set()

    # === Ielasa jau esošos no labeled_candidates.csv (ja ir) ===
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = f"{row['symbol']}_{row['timestamp']}"
                already_labeled.add(key)

    # === Apstrādā kandidātus ===
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("symbol")
            key = f"{symbol}_{row['timestamp']}"

            if key in already_labeled:
                print(f"🔁 {symbol} jau apzīmēts agrāk, izlaižam.")
                continue

            try:
                timestamp = datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - timestamp
                print(f"⏳ Apstrādājam: {symbol} | Vecums: {round(age.total_seconds() / 3600, 2)} h")

                if age < timedelta(hours=6):
                    print(f"⏭️ Izlaižam {symbol} — vēl nav pagājušas 6h.")
                    continue

                price_then = float(row["price"])
                ticker = exchange.fetch_ticker(symbol)
                price_now = ticker.get("last")

                if price_now is None or price_then == 0:
                    print(f"⚠️ Trūkst cenas datu: {symbol} | price_now={price_now}, price_then={price_then}")
                    continue

                change_pct = (price_now - price_then) / price_then * 100

                row["profit_after_6h"] = round(change_pct, 2)
                row["label"] = int(change_pct >= 5)

                print(f"✅ {symbol} | Cena: {price_then} → {price_now} | Izmaiņas: {change_pct:.2f}% | Label: {row['label']}")
                labeled.append(row)

            except Exception as e:
                print(f"❌ Kļūda apstrādājot {symbol}: {e}")

    # === Saglabā papildināti ===
    if labeled:
        try:
            file_exists = os.path.exists(OUTPUT_FILE)
            with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                for row in labeled:
                    writer.writerow({key: row.get(key, "") for key in FIELDNAMES})
            print(f"\n✅ Saglabāts: {OUTPUT_FILE} (+{len(labeled)} jauni ieraksti)")
        except Exception as e:
            print(f"❌ Kļūda saglabājot labeled_candidates.csv: {e}")

        try:
            pending = [row["symbol"] for row in labeled if int(row.get("label", 0)) == 1]
            with open(PENDING_FILE, "w", encoding="utf-8") as f:
                json.dump(pending, f, indent=2)
            print(f"📝 Saglabāts: {PENDING_FILE} ({len(pending)} tokeni)")
        except Exception as e:
            print(f"❌ Kļūda saglabājot pending_training.json: {e}")
    else:
        print("\n❌ Nav neviena, ko labelot.")

if __name__ == "__main__":
    label_candidates()
