import os
import time
import pandas as pd
from filelock import FileLock
from datetime import datetime

from config import settings
from utils.file_helpers import load_json, save_json
from utils.telegram_alerts import send_telegram_message
from utils.trade_logger import log_trade, log_test_trade
from utils.indicators import compute_atr
from modules.adaptive_trade_helper import get_adaptive_tp_sl
from utils.volatility_logger import log_volatility

def extract_filled_amount(order):
    """
    Iegūst aizpildīto daudzumu no MEXC order objekta, izmantojot drošus fallback laukus.
    """
    try:
        # 1. Pamēģina `filled` tieši no order objekta
        filled = order.get("filled")
        if filled and filled > 0:
            return float(filled)

        # 2. Mēģina no order["info"]["executedQty"] vai "origQty"
        info = order.get("info", {})
        for key in ["executedQty", "origQty", "dealQuantity", "filledAmount"]:
            val = info.get(key)
            if val:
                filled = float(val)
                if filled > 0:
                    print(f"ℹ️ Iegūts 'filled' no info['{key}']: {filled}")
                    return filled

        # 3. Kā pēdējais variants — amount no order objekta
        fallback = order.get("amount")
        if fallback:
            filled = float(fallback)
            print(f"ℹ️ Fallback uz order['amount']: {filled}")
            return filled

        print("⚠️ Neizdevās noteikt aizpildīto daudzumu.")
        return 0.0

    except Exception as e:
        print(f"🚫 Kļūda extract_filled_amount(): {e}")
        return 0.0

def calculate_dynamic_budget(token, ai_confidence=0.85, safety_score=0.5):
    base = 2
    gain = token.get("price_change_5m", 0)
    strategy = token.get("strategy", "simple")
    max_usdt = settings.trade_max_usdt()

    confidence_bonus = max(0, (ai_confidence - 0.85) * 10)
    safety_bonus = max(0, (safety_score - 0.5) * 4)
    gain_multiplier = 0.5 if strategy == "aggressive" else 0.3
    dynamic_budget = base + gain * gain_multiplier + confidence_bonus + safety_bonus

    return min(dynamic_budget, max_usdt)

def estimate_volatility(symbol, exchange):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        atr_series = compute_atr(df)
        atr = atr_series.dropna().iloc[-1]
        close = df["close"].iloc[-1]
        volatility = atr / close

        if volatility < 0.005:
            print(f"⚠️ Volatilitāte {symbol} ir pārāk zema ({volatility:.4f}), izmantojam noklusēto.")
            volatility = 0.03
        return volatility
    except Exception as e:
        print(f"⚠️ Neizdevās noteikt volatilitāti {symbol}: {e}")
        return 0.03

def buy_token(token, exchange, confidence=0.85, safety_score=0.5):
    symbol = token['symbol']
    last_price = token['last_price']
    strategy = token['strategy']

    usdt_amount = calculate_dynamic_budget(token, confidence, safety_score)
    volatility = estimate_volatility(symbol, exchange)
    log_volatility(symbol, volatility)

    tp_multipliers, sl_threshold = get_adaptive_tp_sl(confidence, volatility, strategy)

    try:
        if settings.is_test_mode():
            tracked_file = "data/test_tracked_tokens.json"
            amount = round(usdt_amount / last_price, 6)

            print(f"🧪 TEST_MODE: simulēts pirkums {symbol} @ {last_price:.4f} | Daudzums: {amount:.6f}")

            log_test_trade({
                "type": "test_buy",
                "symbol": symbol,
                "price": last_price,
                "amount": amount,
                "timestamp": time.time(),
                "strategy": strategy,
                "ai_decision": True
            })

            lock = FileLock(tracked_file + ".lock")
            with lock:
                tracked = load_json(tracked_file, default={})
                tracked[symbol] = {
                    "buy_price": last_price,
                    "amount": amount,
                    "strategy": strategy,
                    "timestamp": time.time(),
                    "ai_confidence": confidence,
                    "tp_levels": tp_multipliers,
                    "sl_threshold": sl_threshold,
                    "max_price": last_price,
                    "executed_tp_levels": [],
                    "volatility": volatility,
                    "feedback_score": 0.0
                }
                save_json(tracked_file, tracked)
                print(f"✅ Token {symbol} pievienots tracked sarakstam.")

            send_telegram_message(
                f"🧪 *TEST BUY*: {symbol}\nCena: {last_price:.4f} USDT\nDaudzums: {amount:.6f}\nStratēģija: {strategy}"
            )
            return True

        # === LIVE MODE
        tracked_file = "data/tracked_tokens.json"

        balance = exchange.fetch_balance()
        available = balance.get("USDT", {}).get("free", 0)

        if available < usdt_amount:
            print(f"🚫 Nepietiek USDT: Pieejams {available:.2f}, vajag {usdt_amount:.2f}.")
            return False

        market = exchange.markets.get(symbol, {})
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.0001)

        raw_amount = usdt_amount / last_price
        amount = round(max(raw_amount, min_amount), 6)

        print(f"🛒 BUY {symbol} | Cena: {last_price:.4f} | Požītais daudzums: {amount:.6f}")

        order = exchange.create_market_order(symbol, 'buy', amount)
        order_id = order.get("id")

        # ⏳ Gaidām nelielu brīdi, lai birža apstrādā orderi korekti
        time.sleep(1.5)

        # 🔄 Iegūstam atjauninātu ordera statusu no MEXC
        order_info = exchange.fetch_order(order_id, symbol)
        filled = extract_filled_amount(order_info)
        real_price = order_info.get("average") or last_price
        status = order_info.get("status", "").lower()

        # ❌ Pārbaude: ja nav izpildīts, neko nesaglabā
        if filled < 0.00001 or status not in ("closed", "filled"):
            print(f"🚫 Orderis netika izpildīts. Statuss: {status}, filled: {filled}")
            send_telegram_message(
                f"🚫 *Orderis neizpildījās!* `{symbol}`\n"
                f"Stāvoklis: `{status}` | Aizpildīts: `{filled}`"
            )
            return False

        amount = round(filled, 6)

        send_telegram_message(
            f"🛒 *PIRKUMS VEIKTS!*\n\n"
            f"📈 *Token*: `{symbol}`\n"
            f"💵 *Cena*: `{real_price:.4f}` USDT\n"
            f"📦 *Daudzums*: `{amount:.6f}`\n"
            f"🎯 *Stratēģija*: `{strategy}`\n"
            f"🧠 *AI confidence*: `{confidence:.2f}`\n"
            f"📉 *Volatility*: `{volatility:.3f}`\n"
            f"🏹 *TP līmeņi*: `{', '.join([str(round(x, 2)) for x in tp_multipliers])}`\n"
            f"🛡️ *SL slieksnis*: `{sl_threshold:.3f}`"
        )

        lock = FileLock(tracked_file + ".lock")
        with lock:
            tracked = load_json(tracked_file, default={})
            tracked[symbol] = {
                "buy_price": real_price,
                "amount": amount,
                "strategy": strategy,
                "timestamp": time.time(),
                "ai_confidence": confidence,
                "tp_levels": tp_multipliers,
                "sl_threshold": sl_threshold,
                "max_price": real_price,
                "executed_tp_levels": [],
                "volatility": volatility,
                "feedback_score": 0.0
            }
            save_json(tracked_file, tracked)
            print(f"✅ Token {symbol} veiksmīgi pievienots tracked sarakstam.")

        log_trade({
            "type": "buy",
            "symbol": symbol,
            "price": real_price,
            "amount": amount,
            "timestamp": time.time(),
            "strategy": strategy,
            "ai_decision": True
        })

        return True

    except Exception as e:
        print(f"⚠️ Kļūda pērkot {symbol}: {e}")
        return False
