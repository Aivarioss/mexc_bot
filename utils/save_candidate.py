import csv
import os
from datetime import datetime
from utils.indicators import calculate_indicators_for_token

def save_candidate(token, exchange, file_path="data/candidate_tokens.csv"):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 🔍 Aprēķina indikatorus uzreiz pirms saglabāšanas
    token = calculate_indicators_for_token(token, exchange)

    fields_to_save = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": token.get("symbol"),
        "price": token.get("last_price"),
        "rsi": token.get("rsi"),
        "macd": token.get("macd"),
        "macd_signal": token.get("macd_signal"),
        "volume": token.get("volume"),
        "avg_volume": token.get("avg_volume"),
        "safety_score": token.get("safety_score"),
        "strategy": token.get("strategy"),
        "ai_confidence": token.get("ai_confidence"),
        "reject_reason": token.get("reject_reason", "unknown")
    }

    fields_to_save = {k: v for k, v in fields_to_save.items() if v is not None}

    file_exists = os.path.exists(file_path)

    with open(file_path, mode="a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields_to_save.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(fields_to_save)
