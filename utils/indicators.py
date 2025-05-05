import pandas as pd
import numpy as np
import ccxt

# === Pamata indikatori ===

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def compute_rsi_slope(series, period=14):
    rsi = compute_rsi(series, period)
    return rsi.diff()

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def compute_macd_histogram(series, fast=12, slow=26, signal=9):
    macd, signal_line = compute_macd(series, fast, slow, signal)
    return macd - signal_line

def compute_bollinger_bands(series, period=20, std=2):
    sma = series.rolling(window=period).mean()
    std_dev = series.rolling(window=period).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    return upper, lower, sma

def compute_bollinger_bandwidth(series, period=20, std=2):
    upper, lower, sma = compute_bollinger_bands(series, period, std)
    return (upper - lower) / (sma + 1e-10)

def compute_atr(df, period=14):
    df = df.copy()
    df["high_low"] = (df["high"] - df["low"]).abs()
    df["high_close"] = (df["high"] - df["close"].shift()).abs()
    df["low_close"] = (df["low"] - df["close"].shift()).abs()
    tr = df[["high_low", "high_close", "low_close"]].max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def compute_price_above_ema(series, ema_period=50):
    ema = series.ewm(span=ema_period, adjust=False).mean()
    return (series > ema).astype(int)

def compute_volume_change(volume_series, period=3):
    return volume_series.pct_change(periods=period).fillna(0)

def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

# === Papildu breakout indikatori ===

def compute_trend_angle(series, period=10):
    diff = series.diff(periods=period)
    return diff / period

def compute_volume_spike(volume_series, window=10, threshold=2):
    avg_volume = volume_series.rolling(window=window).mean()
    return (volume_series > threshold * avg_volume).astype(int)

def compute_range_position(close, high, low):
    return (close - low) / (high - low + 1e-10)

def compute_heikin_ashi_close(df):
    return (df["open"] + df["high"] + df["low"] + df["close"]) / 4

def compute_candle_body_ratio(open_, close, high, low):
    body = (close - open_).abs()
    total = (high - low).abs() + 1e-10
    return body / total

def compute_upper_wick_ratio(open_, close, high):
    max_val = pd.DataFrame({"a": open_, "b": close}).max(axis=1)
    min_val = pd.DataFrame({"a": open_, "b": close}).min(axis=1)
    return (high - max_val) / (high - min_val + 1e-10)

def compute_lower_wick_ratio(open_, close, low):
    min_val = pd.DataFrame({"a": open_, "b": close}).min(axis=1)
    max_val = pd.DataFrame({"a": open_, "b": close}).max(axis=1)
    return (min_val - low) / (max_val - low + 1e-10)

def compute_relative_volume(volume_series, period=20):
    vol_sma = volume_series.rolling(window=period).mean()
    return volume_series / (vol_sma + 1e-10)

def compute_proximity_to_upper_bb(close, upper_bb):
    return close / (upper_bb + 1e-10)

def compute_volatility(close_series, period=14):
    return close_series.pct_change().rolling(window=period).std().fillna(0)
    
def calculate_indicators_for_token(token, exchange=None):
    symbol = token["symbol"]
    
    try:
        if exchange is None:
            raise ValueError("Exchange objekts nepieciešams indikatoru iegūšanai.")

        # Iegūst OHLCV (100 pēdējās sveces)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1m", limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Aprēķina indikatorus
        df["rsi"] = compute_rsi(df["close"])
        df["macd"], df["macd_signal"] = compute_macd(df["close"])

        # Pēdējās vērtības
        token["rsi"] = round(df["rsi"].iloc[-1], 2)
        token["macd"] = round(df["macd"].iloc[-1], 5)
        token["macd_signal"] = round(df["macd_signal"].iloc[-1], 5)

        return token

    except Exception as e:
        print(f"⚠️ Neizdevās aprēķināt indikatorus tokenam {symbol}: {e}")
        return token  # Atgriež token pat ja nespēj aprēķināt
   
