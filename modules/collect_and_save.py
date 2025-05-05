import os
import time
import ccxt
import json
import pandas as pd
import numpy as np
from utils import indicators
from dotenv import load_dotenv

# === INIT ===
load_dotenv()
api_key = os.getenv("MEXC_API_KEY")
api_secret = os.getenv("MEXC_API_SECRET")

DATA_DIR = "data/market_data"
PENDING_FILE = "data/pending_training.json"
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(PENDING_FILE):
    with open(PENDING_FILE, 'w') as f:
        json.dump([], f)

# === Helper funkcija: default exchange ===
def get_default_exchange():
    return ccxt.mexc({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'timeout': 30000
    })

# === Galvenā funkcija ===
def collect_and_save(symbol, exchange=None, return_df=False):
    if exchange is None:
        exchange = get_default_exchange()

    try:
        print(f"⬇️ Lejupielādē datus: {symbol}")
        data = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=500)
        time.sleep(1.2)
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')

        # === Bāzes indikatori ===
        try: df["rsi"] = indicators.compute_rsi(df["close"])
        except: df["rsi"] = np.nan

        try: df["macd"], df["macd_signal"] = indicators.compute_macd(df["close"])
        except: df["macd"], df["macd_signal"] = np.nan, np.nan

        try: df["bollinger_upper"], df["bollinger_lower"], _ = indicators.compute_bollinger_bands(df["close"])
        except: df["bollinger_upper"], df["bollinger_lower"] = np.nan, np.nan

        try: df["atr"] = indicators.compute_atr(df)
        except: df["atr"] = np.nan

        try: df["range_position"] = indicators.compute_range_position(df["close"], df["high"], df["low"])
        except: df["range_position"] = np.nan

        try: df["heikin_ashi_close"] = indicators.compute_heikin_ashi_close(df)
        except: df["heikin_ashi_close"] = np.nan

        # === Papildu AI-indikatori ===
        try:
            df["ema_50"] = indicators.compute_ema(df["close"], 50)
            df["ema_200"] = indicators.compute_ema(df["close"], 200)
            df["macd_hist"] = df["macd"] - df["macd_signal"]
            df["bollinger_middle"] = (df["bollinger_upper"] + df["bollinger_lower"]) / 2
            df["bb_width"] = (df["bollinger_upper"] - df["bollinger_lower"]) / (df["close"] + 1e-10)
            df["momentum"] = df["close"].diff()
            df["rsi_slope"] = indicators.compute_rsi_slope(df["close"])
            df["market_cap_proxy"] = df["volume"] * df["close"]
            df["safety_score"] = (df["volume"] / df["market_cap_proxy"]).clip(upper=1.0)
            df["volume_change_3"] = indicators.compute_volume_change(df["volume"], period=3)
            df["price_above_ema_50"] = indicators.compute_price_above_ema(df["close"], 50)
            df["bollinger_bandwidth"] = indicators.compute_bollinger_bandwidth(df["close"])
            df["trend_angle"] = indicators.compute_trend_angle(df["close"])
            df["volume_spike"] = indicators.compute_volume_spike(df["volume"])
            df["candle_body_ratio"] = indicators.compute_candle_body_ratio(df["open"], df["close"], df["high"], df["low"])
            df["upper_wick_ratio"] = indicators.compute_upper_wick_ratio(df["open"], df["close"], df["high"])
            df["lower_wick_ratio"] = indicators.compute_lower_wick_ratio(df["open"], df["close"], df["low"])
            df["relative_volume"] = indicators.compute_relative_volume(df["volume"])
            df["proximity_to_bollinger_upper"] = indicators.compute_proximity_to_upper_bb(df["close"], df["bollinger_upper"])
            df["volatility"] = df["close"].pct_change().rolling(10).std()
        except Exception as e:
            print(f"⚠️ Papildu indikatoru kļūda: {e}")

        # === Tīrīšana ===
        df.dropna(inplace=True)
        if len(df) < 100:
            print(f"⚠️ {symbol} — pārāk maz sveču pēc indikatoriem. Netiek saglabāts.")
            return None

        # === Saglabāšana ===
        filename = os.path.join(DATA_DIR, symbol.replace("/", "") + ".csv")
        df.to_csv(filename, index=False)
        print(f"✅ Saglabāts: {filename}")

        # === Apmācības rinda pending_training.json ===
        with open(PENDING_FILE, 'r+') as f:
            try:
                pending = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Brīdinājums: pending_training.json bija bojāts, veidojam no jauna.")
                pending = []

            if symbol not in pending:
                pending.append(symbol)
                f.seek(0)
                json.dump(pending, f, indent=2)
                f.truncate()

        return df if return_df else None

    except Exception as e:
        print(f"❌ Kļūda apstrādājot {symbol}: {e}")
        return None if return_df else None
