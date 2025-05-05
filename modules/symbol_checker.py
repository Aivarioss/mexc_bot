import ccxt
import json
import os
import time

VALID_SYMBOLS_FILE = "data/valid_symbols.json"

def load_valid_symbols():
    if os.path.exists(VALID_SYMBOLS_FILE):
        with open(VALID_SYMBOLS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_valid_symbols(valid_symbols):
    with open(VALID_SYMBOLS_FILE, "w") as f:
        json.dump(valid_symbols, f, indent=4)

def is_symbol_valid(symbol, exchange):
    valid_symbols = load_valid_symbols()

    if symbol in valid_symbols:
        return valid_symbols[symbol]

    # Test: izveido nelielu limitu ordera pieprasījumu
    try:
        exchange.fetch_ticker(symbol)
        time.sleep(0.3)
        # Uzskata, ka, ja ticker pieejams, tirgojams
        valid_symbols[symbol] = True
        save_valid_symbols(valid_symbols)
        print(f"✅ Validēts simbols: {symbol}")
        return True

    except Exception as e:
        print(f"❌ {symbol} nav tirgojams: {e}")
        valid_symbols[symbol] = False
        save_valid_symbols(valid_symbols)
        return False
