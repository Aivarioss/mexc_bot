import os
import json
import joblib
import xgboost as xgb
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from utils.indicators import (
    compute_rsi, compute_macd, compute_bollinger_bands, compute_atr,
    compute_volume_change, compute_price_above_ema, compute_bollinger_bandwidth,
    compute_trend_angle, compute_volume_spike, compute_range_position,
    compute_candle_body_ratio, compute_upper_wick_ratio, compute_lower_wick_ratio,
    compute_relative_volume, compute_proximity_to_upper_bb, compute_rsi_slope
)

def train_ai_model(symbol, exchange):
    print(f"\n📊 Trenējam AI modeli: {symbol}")

    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # === Indikatori ===
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['ema_200'] = df['close'].ewm(span=200).mean()
        df['rsi'] = compute_rsi(df['close'])
        df['macd'], df['macd_signal'] = compute_macd(df['close'])
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['bollinger_upper'], df['bollinger_lower'], df['bollinger_middle'] = compute_bollinger_bands(df['close'])
        df['bb_width'] = df['bollinger_upper'] - df['bollinger_lower']
        df['atr'] = compute_atr(df)
        df['momentum'] = df['close'] - df['close'].shift(5)
        df['rsi_slope'] = compute_rsi_slope(df['close'])
        df['volatility'] = (df['atr'] / df['close']).clip(upper=0.2)

        # === Papildus indikatori ===
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

        # === Drošības metrika ===
        df['market_cap_proxy'] = df['volume'] * df['close']
        df['safety_score'] = (df['volume'] / df['market_cap_proxy']).clip(upper=1.0)

        # === Mērķa mainīgais (label) ===
        df['future_max'] = df['close'].shift(-1).rolling(3).max()
        df['target'] = (df['future_max'] >= df['close'] * 1.01).astype(int)

        if df['target'].nunique() < 2:
            print(f"⚠️ Token {symbol} nevar trenēt — tikai viena klase ({df['target'].unique()})")
            return None, None

        features = [
            'volume', 'ema_50', 'ema_200', 'rsi', 'macd', 'macd_signal', 'macd_hist',
            'bollinger_upper', 'bollinger_lower', 'bollinger_middle', 'bb_width', 'atr',
            'momentum', 'rsi_slope', 'safety_score', 'volume_change_3', 'price_above_ema_50',
            'bollinger_bandwidth', 'trend_angle', 'volume_spike', 'range_position',
            'candle_body_ratio', 'upper_wick_ratio', 'lower_wick_ratio', 'relative_volume',
            'proximity_to_bollinger_upper', 'volatility'
        ]

        df.dropna(subset=features + ['target'], inplace=True)

        if df.empty:
            raise ValueError("❌ Tukšs DataFrame pēc dropna – nav iespējams trenēt.")

        if not isinstance(df['target'], pd.Series):
            raise ValueError("❌ 'target' nav pandas Series!")

        if df['target'].nunique() < 2:
            raise ValueError("❌ Tikai viena klase 'target' kolonnā – nav iespējams trenēt modeli.")

        for f in features:
            if f not in df.columns:
                raise ValueError(f"❌ Trūkst kolonnas: {f}")

        X = df[features]
        y = df['target']

        print("🧪 Datu pārbaude:")
        print("   • Rindu skaits:", len(X))
        print("   • Unikālās klases:", y.unique())
        print("   • Null target:", y.isnull().sum())

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

        if not np.isfinite(X_scaled).all():
            failed_symbol = symbol.replace('/', '_')
            os.makedirs("debug_data", exist_ok=True)
            pd.DataFrame(X_scaled, columns=features).to_csv(f"debug_data/{failed_symbol}_x_scaled_failed.csv", index=False)
            raise ValueError(f"⚠️ X_scaled satur NaN/Inf: {symbol}")

        if len(X_scaled) < 10:
            raise ValueError("⚠️ Nepietiek datu modeļa trenēšanai.")

        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )

        model = xgb.XGBClassifier(
            eval_metric='logloss',
            max_depth=5,
            learning_rate=0.05,
            n_estimators=100,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        loss = log_loss(y_test, y_proba)
        auc = roc_auc_score(y_test, y_proba)

        print(f"✅ Precizitāte: {acc:.4f} | LogLoss: {loss:.4f} | AUC: {auc:.4f}")

        os.makedirs("models", exist_ok=True)
        base_path = f"models/{symbol.replace('/', '_')}"
        joblib.dump(model, base_path + "_model.pkl")
        joblib.dump(scaler, base_path + "_scaler.pkl")
        joblib.dump(features, base_path + "_features.pkl")

        metrics = {
            "symbol": symbol,
            "accuracy": round(acc, 4),
            "log_loss": round(loss, 4),
            "roc_auc": round(auc, 4),
            "samples": int(len(df)),
            "positive_ratio": round(df['target'].mean(), 4)
        }

        with open(base_path + "_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        print("💾 Modelis un metrikas saglabātas!")
        return model, scaler

    except Exception as e:
        print(f"❌ AI apmācības kļūda: {e}")
        try:
            pending_file = "data/pending_training.json"
            if os.path.exists(pending_file):
                with open(pending_file, "r") as f:
                    pending = json.load(f)
            else:
                pending = []

            if symbol not in pending:
                pending.append(symbol)
                with open(pending_file, "w") as f:
                    json.dump(pending, f, indent=2)
                print(f"📥 Token pievienots 'pending_training.json': {symbol}")
        except Exception as pe:
            print(f"⚠️ Neizdevās pierakstīt pending tokenu: {pe}")

        return None, None
