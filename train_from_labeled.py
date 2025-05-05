import os
import pandas as pd
import joblib
import numpy as np
import json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, log_loss, roc_auc_score
from sklearn.utils import resample
import xgboost as xgb
import sys

# Emoji un UTF-8 output atbalsts
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

LABELED_FILE = "data/labeled_candidates.csv"
MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

def train_feedback_model():
    if not os.path.exists(LABELED_FILE):
        print("❌ Labeled faili nav atrasti.")
        return

    try:
        df = pd.read_csv(LABELED_FILE)
    except Exception as e:
        print(f"❌ Kļūda nolasot CSV: {e}")
        return

    if df.empty:
        print("❌ CSV fails ir tukšs.")
        return

    if "label" not in df.columns:
        print("❌ Trūkst 'label' kolonnas.")
        return

    print("🗞 Datu priekšskatījums:")
    print(df.head())

    try:
        df["label"] = df["label"].astype(int)
    except Exception as e:
        print(f"❌ Nevar konvertēt 'label' uz skaitli: {e}")
        return

    # === Stratēģiju kolonnas ===
    df["strategy_simple"] = (df["strategy"] == "simple").astype(int)
    df["strategy_aggressive"] = (df["strategy"] == "aggressive").astype(int)
    df["strategy_revival"] = (df["strategy"] == "revival").astype(int)
    df["strategy_momentum_safe"] = (df["strategy"] == "momentum_safe").astype(int)

    # Atlasām tikai skaitliskas kolonnas ar <20% tukšo vērtību
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # ❗ Pārliecināmies, ka "profit_after_6h" netiek izmantots kā features
    features = [col for col in numeric_cols if col not in ["label", "profit_after_6h"] and df[col].isna().mean() < 0.2]

    print("✅ Izmantotie features:", features)

    df.dropna(subset=features + ["label"], inplace=True)

    if df.empty or df["label"].nunique() < 2:
        print("⚠️ Nepietiek klases daudzveidības (vajag gan 0, gan 1).")
        return

    print("\n📊 Label sadalījums:")
    print(df["label"].value_counts())

    # === Datu balansēšana ===
    df_pos = df[df.label == 1]
    df_neg = df[df.label == 0]

    print(f"📉 Pirms balansēšanas — 1: {len(df_pos)} | 0: {len(df_neg)}")

    if len(df_pos) == 0 or len(df_neg) == 0:
        print("⚠️ Nepietiek datu vienai no klasēm.")
        return

    n_samples = min(len(df_pos), len(df_neg))

    df_pos_downsampled = resample(df_pos, replace=False, n_samples=n_samples, random_state=42)
    df_neg_downsampled = resample(df_neg, replace=False, n_samples=n_samples, random_state=42)

    df_balanced = pd.concat([df_pos_downsampled, df_neg_downsampled])

    X = df_balanced[features]
    y = df_balanced["label"]

    print(f"\n🔍 Balansēti dati — Piemēri: {len(df_balanced)} | Pozitīvīie: {y.sum()} | Negatīvīie: {(y == 0).sum()}")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if not np.all(np.isfinite(X_scaled)):
        print("❌ Atrasti NaN vai Inf skalētajos datos.")
        return

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.25, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        eval_metric='logloss',
        max_depth=4,
        learning_rate=0.05,
        n_estimators=100,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)

    if len(np.unique(y_test)) < 2:
        print("⚠️ Testa datos tikai viena klase – AUC un LogLoss izlaisti.")
        auc = None
        loss = None
    else:
        auc = roc_auc_score(y_test, y_proba)
        loss = log_loss(y_test, y_proba)

    print("\n✅ Feedback modelis apmācīts uz balansētiem datiem")
    print(f"• Accuracy: {acc:.4f}")
    print(f"• Precision: {prec:.4f}")
    print(f"• AUC: {auc:.4f}" if auc is not None else "• AUC: nav aprēķināms")
    print(f"• LogLoss: {loss:.4f}" if loss is not None else "• LogLoss: nav aprēķināms")

    joblib.dump(model, os.path.join(MODEL_DIR, "feedback_model.pkl"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "feedback_scaler.pkl"))
    joblib.dump(features, os.path.join(MODEL_DIR, "feedback_features.pkl"))

    metrics = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "log_loss": round(loss, 4) if loss else None,
        "roc_auc": round(auc, 4) if auc else None,
        "samples": int(len(df_balanced)),
        "positive_ratio": round(y.mean(), 4)
    }

    with open(os.path.join(MODEL_DIR, "feedback_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print("📂 Saglabāts: feedback_model.pkl, scaler, features un metrics")

if __name__ == "__main__":
    train_feedback_model()