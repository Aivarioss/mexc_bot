import os
import time
import ccxt
import pandas as pd
from dotenv import load_dotenv
from utils import indicators
from modules.symbol_checker import is_symbol_valid
import sys
import numpy as np

# === TERMINĀĻA UTF-8 ATBALSTS ===
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# === INIT ===
load_dotenv()
api_key = os.getenv("MEXC_API_KEY")
api_secret = os.getenv("MEXC_API_SECRET")

exchange = ccxt.mexc({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'timeout': 30000
})

# === MAPE DATIEM ===
DATA_DIR = "data/market_data"

if not os.path.exists(DATA_DIR):
    print(f"📁 Mape {DATA_DIR} neeksistē. Izveidojam to.")
    os.makedirs(DATA_DIR, exist_ok=True)

# === PARAMETRI ===
MIN_VOLUME = 100_000
TIMEFRAME = "5m"
LIMIT = 1000
SLEEP_BETWEEN = 1

print("🔍 Lejupielādējam tirgus simbolus no MEXC...")

# === SYMBOLU IEGŪŠANA ===
try:
    exchange.load_markets()
    symbols = [s for s in exchange.symbols if s.endswith("/USDT") and ":USDT" not in s]
except Exception as e:
    print(f"❌ Neizdevās ielādēt tirgus: {e}")
    sys.exit(1)

# === FILTRĒ PĒC VALIDĀCIJAS UN VOLUMENA ===
filtered = []
for symbol in symbols:
    if not is_symbol_valid(symbol, exchange):
        continue

    for attempt in range(3):
        try:
            ticker = exchange.fetch_ticker(symbol)
            volume = ticker.get("quoteVolume", 0) or 0
            if volume >= MIN_VOLUME:
                filtered.append(symbol)
                print(f"✅ {symbol} | Vol: {volume:,.0f}")
            else:
                print(f"❌ {symbol} | Vol: {volume:,.0f} — pārāk mazs")
            time.sleep(0.4)
            break
        except Exception as e:
            print(f"⚠️ Kļūda simbolam {symbol}: {e} | Mēģinājums {attempt+1}/3")
            time.sleep(2)
            if attempt == 2:
                print(f"⛔️ Izlaižam {symbol} pēc 3 mēģinājumiem.")

print(f"\n✅ Atrasti {len(filtered)} validēti simboli ar volume > {MIN_VOLUME}")

# === DATUS VĀKŠANA UN APSTRĀDE ===
total = len(filtered)
failed_symbols = []

for i, symbol in enumerate(filtered, start=1):
    print(f"\n[{i}/{total}] ⬇️ Lejupielādē OHLCV: {symbol}")
    for attempt in range(3):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            print(f"🧠 Aprēķinam indikatorus: {symbol}")

            try:
                df["rsi"] = indicators.compute_rsi(df["close"])
                print("• RSI ✔️")
            except Exception as e:
                print(f"⚠️ RSI kļūda: {e}")
                df["rsi"] = np.nan

            try:
                df["macd"], df["macd_signal"] = indicators.compute_macd(df["close"])
                print("• MACD & Signal ✔️")
            except Exception as e:
                print(f"⚠️ MACD kļūda: {e}")
                df["macd"], df["macd_signal"] = np.nan, np.nan

            try:
                df["bollinger_upper"], df["bollinger_lower"], _ = indicators.compute_bollinger_bands(df["close"])
                print("• Bollinger Bands ✔️")
            except Exception as e:
                print(f"⚠️ Bollinger Bands kļūda: {e}")
                df["bollinger_upper"], df["bollinger_lower"] = np.nan, np.nan

            try:
                df["atr"] = indicators.compute_atr(df)
                print("• ATR ✔️")
            except Exception as e:
                print(f"⚠️ ATR kļūda: {e}")
                df["atr"] = np.nan

            try:
                df["range_position"] = indicators.compute_range_position(df["close"], df["high"], df["low"])
                print("• Range Position ✔️")
            except Exception as e:
                print(f"⚠️ Range Position kļūda: {e}")
                df["range_position"] = np.nan

            try:
                df["heikin_ashi_close"] = indicators.compute_heikin_ashi_close(df)
                print("• Heikin Ashi Close ✔️")
            except Exception as e:
                print(f"⚠️ Heikin Ashi Close kļūda: {e}")
                df["heikin_ashi_close"] = np.nan

            # === PAPILDU FEATURES ===
            try:
                df["ema_50"] = indicators.compute_ema(df["close"], span=50)
                df["ema_200"] = indicators.compute_ema(df["close"], span=200)
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
                print("• Papildu indikatori ✔️")
            except Exception as e:
                print(f"⚠️ Papildu indikatoru kļūda: {e}")

            df.dropna(inplace=True)

            if len(df) < 200:
                print(f"⚠️ {symbol} — pārāk maz sveču pēc indikatoriem. Netiek saglabāts.")
                break

            print("📊 Indikatoru vērtību priekšskats (pēdējā rinda):")
            print(df.tail(1).to_string(index=False))

            safe_symbol = symbol.replace("/", "").replace(":", "")
            file_path = os.path.join(DATA_DIR, f"{safe_symbol}.csv")

            if not os.path.exists(DATA_DIR):
                print(f"📁 Mape {DATA_DIR} vairs neeksistē. Izveidojam atkārtoti.")
                os.makedirs(DATA_DIR, exist_ok=True)

            df.to_csv(file_path, index=False)
            print(f"✅ Saglabāts: {file_path}")
            break

        except Exception as e:
            print(f"⚠️ Kļūda datu vākšanā {symbol}: {e} | Mēģinājums {attempt+1}/3")
            time.sleep(2)
            if attempt == 2:
                failed_symbols.append(symbol)
                print(f"⛔️ Izlaižam {symbol} pēc 3 mēģinājumiem.")

    time.sleep(SLEEP_BETWEEN)

# === KOPSAVILKUMS ===
print("\n🌟 Gatavs! Visi dati savākti.")
if failed_symbols:
    print("\n🚫 Neizdevās apstrādāt šādus simbolus:")
    for sym in failed_symbols:
        print(f"• {sym}")
else:
    print("✅ Visi simboli veiksmīgi apstrādāti.")
