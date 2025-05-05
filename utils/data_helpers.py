import pandas as pd
import joblib

def prepare_X_for_model(df: pd.DataFrame, feature_path: str, scaler_path: str):
    """
    Sagatavo X real-time datiem, pielāgojoties treniņa laikā izmantotajiem feature.
    - Pievieno trūkstošos feature ar 0
    - Garantē pareizu secību
    - Skalē ar iepriekš saglabāto StandardScaler

    Parametri:
        df: DataFrame ar visiem pieejamajiem indikatoriem
        feature_path: ceļš uz .pkl failu ar feature sarakstu
        scaler_path: ceļš uz saglabāto StandardScaler

    Atgriež:
        X_scaled: sagatavots un skalēts numpy masīvs
    """
    # Ielādē feature sarakstu un scaler
    features = joblib.load(feature_path)
    scaler = joblib.load(scaler_path)

    # Nodrošina, ka trūkstošie feature tiek pievienoti ar 0
    for col in features:
        if col not in df.columns:
            df[col] = 0

    # Atlasām un pārliecināmies par pareizu secību
    X = df[features].copy()
    X = X.fillna(0)

    # Skalēšana
    X_scaled = scaler.transform(X)
    return X_scaled
