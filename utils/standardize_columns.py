import os
import pandas as pd

DATA_DIR = "data/market_data"

# Nosaukumu pārveidošanas vārdnīca
column_map = {
    "bb_upper": "bollinger_upper",
    "bb_lower": "bollinger_lower",
    "Middle_BB": "bollinger_middle",
    "BB_WIDTH": "bollinger_width",
    "EMA_50": "ema_50",
    "EMA_200": "ema_200",
    "MACD_HIST": "macd_hist",
    "MOMENTUM": "momentum",
    "RSI_SLOPE": "rsi_slope",
    "range_pos": "range_position",
    "ha_close": "heikin_ashi_close",
    "proximity_to_upper_bb": "proximity_to_bollinger_upper",
    # Atstāj šos nemainīgus, bet vari pielāgot vēlāk
    # "timestamp": "timestamp",
    # "open": "open",
    # "high": "high",
    # ...
}

def standardize_csv_columns(file_path):
    try:
        df = pd.read_csv(file_path)
        original_columns = df.columns.tolist()

        new_columns = [
            column_map.get(col, col.lower())  # samazina un aizvieto ja vajag
            for col in original_columns
        ]
        df.columns = new_columns

        df.to_csv(file_path, index=False)
        print(f"✅ Pārveidots: {file_path}")
    except Exception as e:
        print(f"❌ Kļūda failā {file_path}: {e}")

def main():
    print("🔁 Standartizējam kolonnu nosaukumus CSV failos...\n")
    if not os.path.exists(DATA_DIR):
        print(f"❌ Mape {DATA_DIR} neeksistē.")
        return

    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            filepath = os.path.join(DATA_DIR, filename)
            standardize_csv_columns(filepath)

    print("\n🌟 Gatavs! Visas kolonnas standarta formātā.")

if __name__ == "__main__":
    main()
