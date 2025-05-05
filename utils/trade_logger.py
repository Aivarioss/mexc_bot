import json
import os
import time
from datetime import datetime, timezone

from utils.summary import log_event, log_test_event

TRADE_HISTORY_FILE = "data/trade_history.json"
TEST_TRADE_HISTORY_FILE = "data/test_trade_history.json"

def ensure_file_exists(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)

def _append_trade_to_file(file_path, trade_data):
    ensure_file_exists(file_path)
    
    try:
        with open(file_path, "r") as f:
            trades = json.load(f)
            if not isinstance(trades, list):
                print(f"⚠️ {file_path} nav saraksts. Tīram...")
                trades = []
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"⚠️ Nevarēja nolasīt {file_path}. Izveidojam jaunu...")
        trades = []

    trade_data["timestamp"] = trade_data.get("timestamp", time.time())

    if trade_data["type"] in ["sell", "test_sell"]:
        buy_price = trade_data.get("buy_price")
        sell_price = trade_data.get("price")
        if buy_price and sell_price:
            if sell_price > buy_price:
                trade_data["result"] = "profit"
            elif sell_price < buy_price:
                trade_data["result"] = "loss"

    trades.append(trade_data)

    with open(file_path, "w") as f:
        json.dump(trades, f, indent=4)

# === Reālo darījumu pieraksts ===
def log_trade(trade_data):
    if trade_data["type"] in ["buy", "sell"]:
        _append_trade_to_file(TRADE_HISTORY_FILE, trade_data)
        log_event(
            trade_data["type"],
            symbol=trade_data.get("symbol"),
            extra={
                "price": trade_data.get("price"),
                "amount": trade_data.get("amount"),
                "strategy": trade_data.get("strategy"),
                "ai_confidence": trade_data.get("ai_confidence"),
            }
        )

# === Test darījumu pieraksts ===
def log_test_trade(trade_data):
    if trade_data["type"] in ["test_buy", "test_sell"]:
        _append_trade_to_file(TEST_TRADE_HISTORY_FILE, trade_data)
        log_test_event(
            trade_data["type"],
            symbol=trade_data.get("symbol"),
            extra={
                "price": trade_data.get("price"),
                "amount": trade_data.get("amount"),
                "strategy": trade_data.get("strategy"),
                "ai_confidence": trade_data.get("ai_confidence"),
            }
        )

# === Nolasīšanas funkcijas, ja vajag ===
def get_trades(real=True):
    path = TRADE_HISTORY_FILE if real else TEST_TRADE_HISTORY_FILE
    ensure_file_exists(path)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []
