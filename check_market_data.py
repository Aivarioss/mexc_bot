import os
import json
import pandas as pd

DATA_DIR = "data/market_data"
MODEL_DIR = "models"
PENDING_FILE = "data/pending_training.json"

REQUIRED_COLUMNS = [
    'volume', 'EMA_50', 'EMA_200', 'RSI', 'MACD', 'Signal', 'MACD_HIST',
    'Upper_BB', 'Lower_BB', 'Middle_BB', 'BB_WIDTH', 'ATR', 'MOMENTUM',
    'RSI_SLOPE', 'safety_score', 'volume_change_3', 'price_above_ema_50',
    'bollinger_bandwidth', 'trend_angle', 'volume_spike', 'range_position',
    'candle_body_ratio', 'upper_wick_ratio', 'lower_wick_ratio', 'relative_volume',
    'proximity_to_upper_bb', 'volatility'
]

def extract_symbol(file):
    return file.replace(".csv", "").replace("USDT", "/USDT")

print("\n🔍 Pārbaudām market_data...\n")
valid_symbols = []
problem_files = {}

for file in os.listdir(DATA_DIR):
    if not file.endswith(".csv"):
        continue

    path = os.path.join(DATA_DIR, file)
    try:
        df = pd.read_csv(path)

        if df.empty:
            problem_files[file] = ["Tukšs fails"]
            continue

        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]

        if missing:
            problem_files[file] = missing
            continue

        symbol = extract_symbol(file)
        model_path = os.path.join(MODEL_DIR, file.replace(".csv", "_model.pkl"))
        if not os.path.exists(model_path):
            valid_symbols.append(symbol)

    except Exception as e:
        problem_files[file] = [f"CSV kļūda: {e}"]

if valid_symbols:
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(valid_symbols, f, indent=2)
    print(f"\n✅ Saglabāts pending_training.json ({len(valid_symbols)} tokeni)")
else:
    print("⚠️ Netika atrasts neviens derīgs fails AI apmācībai")

if problem_files:
    print("\n📛 Faili ar problēmām:")
    for f, issues in problem_files.items():
        print(f"❌ {f}: trūkst {issues}")

print("\n🏁 Gatavs!")
