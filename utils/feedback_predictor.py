# feedback_predictor.py

import os
import joblib
import numpy as np
import pandas as pd  # ✅ nepieciešams priekš DataFrame

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "feedback_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "feedback_scaler.pkl")
FEATURES_PATH = os.path.join(MODEL_DIR, "feedback_features.pkl")

def is_feedback_model_positive(data: dict, return_score=False, threshold=0.5):
    """
    📊 Prognozē vai darījums šķistu 'pozitīvs' (apmierinošs).
    
    Parametri:
        data: dict ar pazīmēm, piem.:
            {
              "price": 0.018,
              "volatility": 0.032,
              "ai_confidence": 0.91,
              "strategy_aggressive": 1,
              ...
            }
        return_score: ja True → atgriež proba skaitli (0.0–1.0)
        threshold: slieksnis pozitīvai klasifikācijai (default: 0.5)
    """
    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        features = joblib.load(FEATURES_PATH)

        # 🧠 Sagatavo ievadi kā DataFrame
        input_df = pd.DataFrame([data])

        # Nodrošina, ka visiem nepieciešamajiem feature ir vērtības (aizvieto trūkstošos ar 0)
        for col in features:
            if col not in input_df.columns:
                input_df[col] = 0

        # Atlasām tikai vajadzīgos un korektā secībā
        input_df = input_df[features]

        # Skalēšana
        X_scaled = scaler.transform(input_df)

        # Prognoze
        score = model.predict_proba(X_scaled)[0][1]
        return score if return_score else score >= threshold

    except Exception as e:
        print(f"⚠️ Feedback modeļa kļūda: {e}")
        return None if return_score else False
