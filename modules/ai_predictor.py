import os
import joblib
import pandas as pd
from config import settings
from utils.indicators import (
    compute_rsi,
    compute_macd,
    compute_bollinger_bands,
    compute_atr,
    compute_volume_change,
    compute_price_above_ema,
    compute_bollinger_bandwidth,
    compute_trend_angle,
    compute_volume_spike,
    compute_range_position,
    compute_candle_body_ratio,
    compute_upper_wick_ratio,
    compute_lower_wick_ratio,
    compute_relative_volume,
    compute_proximity_to_upper_bb,
    compute_rsi_slope,
    compute_volatility
)

MODELS_DIR = "models"

def ai_filter(token, exchange, return_score=False):
    symbol = token["symbol"]
    base_name = symbol.replace("/", "_")
    model_path = os.path.join(MODELS_DIR, f"{base_name}_model.pkl")
    scaler_path = os.path.join(MODELS_DIR, f"{base_name}_scaler.pkl")
    features_path = os.path.join(MODELS_DIR, f"{base_name}_features.pkl")

    if not all(os.path.exists(p) for p in [model_path, scaler_path, features_path]):
        print(f"❌ Trūkst AI faili priekš {symbol}.")
        return False if not return_score else (0, 0, 0)

    try:
        # === Ielādē modeļus un feature sarakstu
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        features = joblib.load(features_path)

        # === OHLCV ielāde
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=300)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])

        # === Indikatoru aprēķins (nepieciešams visiem, bet izmantosim tikai atlasītos)
        df["ema_50"] = df["close"].ewm(span=50).mean()
        df["ema_200"] = df["close"].ewm(span=200).mean()
        df["rsi"] = compute_rsi(df["close"])
        df["macd"], df["macd_signal"] = compute_macd(df["close"])
        df["bollinger_upper"], df["bollinger_lower"], df["bollinger_middle"] = compute_bollinger_bands(df["close"])
        df["atr"] = compute_atr(df)
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        df["bb_width"] = df["bollinger_upper"] - df["bollinger_lower"]
        df["momentum"] = df["close"].diff()
        df["rsi_slope"] = compute_rsi_slope(df["close"])
        df["volume_change_3"] = compute_volume_change(df["volume"], period=3)
        df["price_above_ema_50"] = compute_price_above_ema(df["close"], ema_period=50)
        df["bollinger_bandwidth"] = compute_bollinger_bandwidth(df["close"])
        df["trend_angle"] = compute_trend_angle(df["ema_50"])
        df["volume_spike"] = compute_volume_spike(df["volume"])
        df["range_position"] = compute_range_position(df["close"], df["high"], df["low"])
        df["candle_body_ratio"] = compute_candle_body_ratio(df["open"], df["close"], df["high"], df["low"])
        df["upper_wick_ratio"] = compute_upper_wick_ratio(df["open"], df["close"], df["high"])
        df["lower_wick_ratio"] = compute_lower_wick_ratio(df["open"], df["close"], df["low"])
        df["relative_volume"] = compute_relative_volume(df["volume"])
        df["proximity_to_bollinger_upper"] = compute_proximity_to_upper_bb(df["close"], df["bollinger_upper"])
        df["volatility"] = compute_volatility(df["close"]).clip(upper=0.2)
        df["market_cap_proxy"] = df["volume"] * df["close"]
        df["safety_score"] = (df["volume"] / df["market_cap_proxy"]).clip(upper=1.0)

        # === Debug backup
        os.makedirs("debug_data", exist_ok=True)
        df.to_csv(f"debug_data/{symbol.replace('/', '_')}_raw.csv", index=False)

        # === Drop NaNs
        df.dropna(subset=features, inplace=True)

        if df.empty:
            print(f"⚠️ Nav derīgu datu rindu pēc NaN izmešanas: {symbol}")
            return False if not return_score else (0, 0, 0)

        # === Pēdējā rinda
        latest = df.iloc[-1]
        X = pd.DataFrame([latest[features]])
        X_scaled = scaler.transform(X)

        # === Prognoze
        prediction = model.predict(X_scaled)[0]
        confidence = model.predict_proba(X_scaled)[0][1]
        safety_score = latest.get("safety_score", 0.5)

        print(f"🤖 AI {symbol}: pred = {prediction} | confidence = {confidence:.2f} | safety = {safety_score:.2f}")

        passed = prediction == 1 and confidence >= settings.get_min_ai_probability()

        if not passed:
            print(f"⚠️ AI atmeta {symbol} | confidence = {confidence:.2f}")

        return passed if not return_score else (prediction, confidence, safety_score)

    except Exception as e:
        print(f"⚠️ Kļūda AI filtrā {symbol}: {e}")
        return False if not return_score else (0, 0, 0)
