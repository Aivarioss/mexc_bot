import os
import json
from dotenv import load_dotenv
from modules.market_sentiment import get_market_sentiment

load_dotenv()

# === API ===
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_API_SECRET = os.getenv("MEXC_API_SECRET")

# === TEST MODE: State management ===
STATE_FILE = "config/state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"TEST_MODE": False}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("❌ Kļūda: Bojāts state.json — ielādēts noklusētais režīms.")
        return {"TEST_MODE": False}
        
# === LOG saglabāšanas ilgums (stundās) ===
def get_log_time_window_hours():
    return 24  # Var pielāgot jebkurā brīdī

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print("📝 State saglabāts:", state)

def is_test_mode():
    return load_state().get("TEST_MODE", False)
    
def get_market_criteria():
    sentiment = get_market_sentiment()

    if is_test_mode():
        # Test režīma iestatījumi paliek fiksēti
        return {
            "MIN_MARKET_CAP": 1_000_000,
            "MAX_MARKET_CAP": 100_000_000,
            "MIN_VOLUME_24H": 150_000,
            "MIN_GAIN_5M": 1.0,
            "AGGRESSIVE_THRESHOLD": 2.0,
            "MOMENTUM_GAIN_MULTIPLIER": 1.50
        }
    else:
        if sentiment == 'bullish':
            return {
                "MIN_MARKET_CAP": 3_000_000,
                "MAX_MARKET_CAP": 150_000_000,
                "MIN_VOLUME_24H": 300_000,
                "MIN_GAIN_5M": 3.5,
                "AGGRESSIVE_THRESHOLD": 6.0,
                "MOMENTUM_GAIN_MULTIPLIER": 4.5
            }
        elif sentiment == 'bearish':
            return {
                "MIN_MARKET_CAP": 1_000_000,
                "MAX_MARKET_CAP": 50_000_000,
                "MIN_VOLUME_24H": 100_000,
                "MIN_GAIN_5M": 0.5,
                "AGGRESSIVE_THRESHOLD": 1.5,
                "MOMENTUM_GAIN_MULTIPLIER": 1.0
            }
        else:  # neutral
            return {
                "MIN_MARKET_CAP": 2_000_000,
                "MAX_MARKET_CAP": 120_000_000,
                "MIN_VOLUME_24H": 200_000,
                "MIN_GAIN_5M": 2.0,
                "AGGRESSIVE_THRESHOLD": 4.0,
                "MOMENTUM_GAIN_MULTIPLIER": 3.0
            }
    
# === TIRDZNIECĪBAS LIMITI ===
def get_trailing_trigger_gain():
    return 1.05 if is_test_mode() else 1.10
    
def market_momentum_gain_multiplier():
    return get_market_criteria().get("MOMENTUM_GAIN_MULTIPLIER", 1.05)
    

def get_trailing_stop_loss():
    return 0.98 if is_test_mode() else 0.97

def get_trade_limits():
    if is_test_mode():
        return {
            "MAX_USDT_BALANCE": 15,
            "MIN_USDT_PER_TRADE": 3,
        }
    else:
        return {
            "MAX_USDT_BALANCE": 50,
            "MIN_USDT_PER_TRADE": 5,
        }

# === CIKLA INTERVALS ===
def get_check_interval():
    return 60 if is_test_mode() else 600

# === AI PROBABILITY THRESHOLD ===
def get_min_ai_probability():
    return 0.01 if is_test_mode() else 0.03

def get_stop_loss_threshold():
    return 0.04 if is_test_mode() else 0.05

# === Helperfunkcijas ērtākai piekļuvei ===
def market_min_cap():
    return get_market_criteria()["MIN_MARKET_CAP"]

def market_max_cap():
    return get_market_criteria()["MAX_MARKET_CAP"]

def market_min_volume():
    return get_market_criteria()["MIN_VOLUME_24H"]

def market_min_gain():
    return get_market_criteria()["MIN_GAIN_5M"]

def market_aggressive_threshold():
    return get_market_criteria()["AGGRESSIVE_THRESHOLD"]

def trade_min_usdt():
    return get_trade_limits()["MIN_USDT_PER_TRADE"]

def trade_max_usdt():
    return get_trade_limits()["MAX_USDT_BALANCE"]

# === Debug helper (pēc izvēles) ===
def debug_settings():
    return {
        "TEST_MODE": is_test_mode(),
        "MIN_MARKET_CAP": market_min_cap(),
        "MAX_MARKET_CAP": market_max_cap(),
        "MIN_VOLUME_24H": market_min_volume(),
        "MIN_GAIN_5M": market_min_gain(),
        "AGGRESSIVE_THRESHOLD": market_aggressive_threshold(),
        "MIN_USDT": trade_min_usdt(),
        "MAX_USDT": trade_max_usdt(),
        "AI_THRESHOLD": get_min_ai_probability(),
        "CHECK_INTERVAL": get_check_interval()
    }

