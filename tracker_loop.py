import time
import os
import math
import ccxt
from dotenv import load_dotenv
from collections import deque
from filelock import FileLock
import sys
import io
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

from config import settings
from utils.file_helpers import load_json, save_json
from utils.telegram_alerts import send_telegram_message
from utils.trade_logger import log_trade, log_test_trade
from data.trade_summary import summarize_trades
from modules.adaptive_trade_helper import get_adaptive_tp_sl

load_dotenv()
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_API_SECRET"),
    'enableRateLimit': True
})

def log(msg):
    print(msg, flush=True)

def sanitize_tracked_tokens(tracked):
    for symbol, info in tracked.items():
        if isinstance(info.get("executed_tp_levels"), set):
            info["executed_tp_levels"] = list(info["executed_tp_levels"])
        if isinstance(info.get("price_history"), set):
            info["price_history"] = list(info["price_history"])
        if isinstance(info.get("dynamic_peak"), set):
            info["dynamic_peak"] = max(info["dynamic_peak"]) if info["dynamic_peak"] else 0
    return tracked

def should_wave_sell(current_price, info, stop_loss_pct=0.97, window_size=5, confirmation_seconds=30):
    max_price = info.get("max_price", current_price)
    price_history = info.get("price_history", [])

    if not isinstance(price_history, deque):
        price_history = deque(price_history, maxlen=window_size)

    price_history.append(current_price)
    info["price_history"] = list(price_history)

    if current_price > max_price:
        info["max_price"] = current_price
        info.pop("trailing_breach_time", None)
        info["__changed__"] = True  # <-- būtiski, lai saglabātu max_price uz diska
        print(f"📈 [WAVE] Jauns maksimums: {current_price:.4f}")
        return False

    threshold = max_price * stop_loss_pct

    if current_price < threshold:
        if not info.get("trailing_breach_time"):
            info["trailing_breach_time"] = time.time()
            info["__changed__"] = True  # <-- saglabājam arī šo stāvokli
            print(f"⏳ [WAVE] Cena zem sliekšņa: {current_price:.4f} < {threshold:.4f} — gaidām apstiprinājumu...")
            return False
        elif time.time() - info["trailing_breach_time"] >= confirmation_seconds:
            highest_in_window = max(price_history)
            if highest_in_window < max_price * 0.995:
                print(f"📉 [WAVE] Zemāka virsotne — pārdodam!")
                return True
            else:
                print(f"🔄 Cena mēģina atkopties — vēl nepārdodam.")
                return False
        else:
            elapsed = int(time.time() - info["trailing_breach_time"])
            print(f"⌛ [WAVE] Zem sliekšņa, bet vēl neapstiprināts ({elapsed}s)...")
            return False
    else:
        if "trailing_breach_time" in info:
            print(f"⬆ [WAVE] Cena atkopa virs sliekšņa: {current_price:.4f} >= {threshold:.4f}")
            del info["trailing_breach_time"]
            info["__changed__"] = True  # <-- arī šeit jāatzīmē, ka bija izmaiņas
        return False

def get_min_amount(symbol):
    market = exchange.market(symbol)
    return market.get('limits', {}).get('amount', {}).get('min', 0.01)

while True:
    try:
        prefix = "[TEST_MODE] " if settings.is_test_mode() else "[LIVE] "
        print(f"\n🔍 {prefix}Pārbaudām aktīvās pozīcijas...")

        TRACKED_TOKENS_FILE = "data/test_tracked_tokens.json" if settings.is_test_mode() else "data/tracked_tokens.json"

        lock = FileLock(TRACKED_TOKENS_FILE + ".lock")
        with lock:
            tracked = sanitize_tracked_tokens(load_json(TRACKED_TOKENS_FILE) or {})
            changed = False

            for symbol, info in list(tracked.items()):
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    buy_price = info['buy_price']
                    amount = info['amount']
                    strategy = info.get('strategy', 'unknown')
                    max_price = info.get('max_price', buy_price)
                    executed_levels = list(info.get("executed_tp_levels", []))
                    confidence = info.get("ai_confidence", 0.85)

                    print(f"\n📈 {symbol} | Cena: {current_price:.4f} | Pirkts: {buy_price:.4f} | Max: {max_price:.4f}")

                    change_pct = (current_price - buy_price) / buy_price
                    gain_multiplier = current_price / buy_price

                    # === Dinamisks SL un TP pārrēķins ===
                    try:
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=6)
                        ranges = [(c[2] - c[3]) / c[4] for c in ohlcv[-5:] if c[4] > 0]
                        volatility = sum(ranges) / len(ranges) if ranges else 0.03

                        tp_levels, sl_threshold = get_adaptive_tp_sl(confidence, volatility, strategy)

                        if volatility > 0.05:
                            sl_threshold *= 1.2
                        elif volatility < 0.015:
                            sl_threshold *= 0.8

                        info["sl_threshold"] = sl_threshold  # saglabāšanas nolūkiem (izvēles)
                        print(f"🔁 [SL] {symbol} | Volatility: {volatility:.4f} → SL: {sl_threshold:.4f}")
                    except Exception as e:
                        print(f"⚠️ SL pārrēķina kļūda {symbol}: {e}")
                        tp_levels = info.get("tp_levels", [])
                        sl_threshold = info.get("sl_threshold", 0.035)

                    # === Frakciju sadalījums pēc confidence ===
                    if confidence >= 0.95:
                        fractions = [0.2, 0.2, 0.3, 0.3][:len(tp_levels)]
                    elif confidence <= 0.85:
                        fractions = [0.5, 0.3, 0.2][:len(tp_levels)]
                    else:
                        fractions = [0.4, 0.3, 0.2, 0.1][:len(tp_levels)]

                    # === TAKE-PROFIT izpilde ===
                    for gain_target, sell_fraction in zip(tp_levels, fractions):
                        if gain_multiplier >= gain_target and gain_target not in executed_levels:
                            portion_amount = round(amount * sell_fraction, 6)
                            if current_price * portion_amount < 1.0:
                                print(f"⚠️ {symbol} daļējā pārdošana ({portion_amount}) zem 1 USDT — pārdodam visu atlikumu.")
                                portion_amount = round(amount, 6)

                            reason = f"💰 TAKE-PROFIT {gain_target:.2f}x ({int(sell_fraction * 100)}%)"
                            min_amount = get_min_amount(symbol)
                            if portion_amount < min_amount:
                                print(f"⚠️ {symbol} — Pārdošanas daudzums {portion_amount} mazāks par minimālo ({min_amount}), izlaižam.")
                                continue

                            if settings.is_test_mode():
                                print(f"🧪 Simulēta pārdošana {symbol} @ {current_price:.4f} | {reason}")
                                log_test_trade({
                                    "symbol": symbol,
                                    "type": "test_sell",
                                    "price": current_price,
                                    "amount": portion_amount,
                                    "buy_price": buy_price,
                                    "reason": reason
                                })
                            else:
                                print(f"💰 Reāla pārdošana {symbol} @ {current_price:.4f} | {reason}")
                                exchange.create_market_sell_order(symbol, portion_amount)
                                log_trade({
                                    "symbol": symbol,
                                    "type": "sell",
                                    "price": current_price,
                                    "amount": portion_amount,
                                    "buy_price": buy_price,
                                    "reason": reason
                                })

                            send_telegram_message(f"{symbol} — {reason} pie {current_price:.4f} USDT")

                            executed_levels.append(gain_target)
                            info["executed_tp_levels"] = executed_levels
                            info["amount"] = round(amount - portion_amount, 6)
                            changed = True

                            if info["amount"] <= 0.00001:
                                del tracked[symbol]
                            else:
                                tracked[symbol] = info
                            break

                    else:
                        # === Dynamic TP trailing sell ===
                        if len(executed_levels) == len(tp_levels):
                            if "dynamic_peak" not in info:
                                info["dynamic_peak"] = current_price

                            if current_price > info["dynamic_peak"]:
                                info["dynamic_peak"] = current_price

                            if current_price < info["dynamic_peak"] * 0.97:
                                reason = "🚀 Dynamic Trailing TP Sell"
                                portion_amount = amount
                                min_amount = get_min_amount(symbol)
                                if portion_amount < min_amount:
                                    print(f"⚠️ {symbol} — Pārdošanas daudzums {portion_amount} mazāks par minimālo ({min_amount}), izlaižam.")
                                    continue
                                if settings.is_test_mode():
                                    print(f"🧪 Dynamic TP pārdošana {symbol}")
                                    log_test_trade({
                                        "symbol": symbol,
                                        "type": "test_sell",
                                        "price": current_price,
                                        "amount": portion_amount,
                                        "buy_price": buy_price,
                                        "reason": reason
                                    })
                                else:
                                    exchange.create_market_sell_order(symbol, portion_amount)
                                    log_trade({
                                        "symbol": symbol,
                                        "type": "sell",
                                        "price": current_price,
                                        "amount": portion_amount,
                                        "buy_price": buy_price,
                                        "reason": reason
                                    })
                                send_telegram_message(f"{symbol} — {reason} pie {current_price:.4f} USDT")
                                del tracked[symbol]
                                changed = True

                        # === Trailing wave sell (serfošana) ===
                        elif gain_multiplier >= 1.01:
                            # Atsevišķi izsaucam, lai pēc tam varam saglabāt info izmaiņas
                            wave_triggered = should_wave_sell(current_price, info, stop_loss_pct=1 - sl_threshold)
                            tracked[symbol] = info  # saglabā max_price un price_history uz diska
                            
                            if info.get("__changed__"):
                                changed = True
                                del info["__changed__"]

                            if wave_triggered:
                                reason = "📉 Trailing Stop Sell"
                                portion_amount = amount
                                min_amount = get_min_amount(symbol)
                                if portion_amount < min_amount:
                                    print(f"⚠️ {symbol} — Pārdošanas daudzums {portion_amount} mazāks par minimālo ({min_amount}), izlaižam.")
                                    continue
                                if settings.is_test_mode():
                                    print(f"🧪 Trailing Stop pārdošana {symbol}")
                                    log_test_trade({
                                        "symbol": symbol,
                                        "type": "test_sell",
                                        "price": current_price,
                                        "amount": portion_amount,
                                        "buy_price": buy_price,
                                        "reason": reason
                                    })
                                else:
                                    exchange.create_market_sell_order(symbol, portion_amount)
                                    log_trade({
                                        "symbol": symbol,
                                        "type": "sell",
                                        "price": current_price,
                                        "amount": portion_amount,
                                        "buy_price": buy_price,
                                        "reason": reason
                                    })
                                send_telegram_message(f"{symbol} — {reason} pie {current_price:.4f} USDT")
                                del tracked[symbol]
                                changed = True
                        
                        # === Cietais stop-loss ===
                        elif change_pct <= -sl_threshold:
                            reason = "🛑 Stop Loss"
                            portion_amount = amount
                            min_amount = get_min_amount(symbol)
                            if portion_amount < min_amount:
                                print(f"⚠️ {symbol} — Pārdošanas daudzums {portion_amount} mazāks par minimālo ({min_amount}), izlaižam.")
                                continue
                            if settings.is_test_mode():
                                print(f"🧪 Stop Loss pārdošana {symbol}")
                                log_test_trade({
                                    "symbol": symbol,
                                    "type": "test_sell",
                                    "price": current_price,
                                    "amount": portion_amount,
                                    "buy_price": buy_price,
                                    "reason": reason
                                })
                            else:
                                exchange.create_market_sell_order(symbol, portion_amount)
                                log_trade({
                                    "symbol": symbol,
                                    "type": "sell",
                                    "price": current_price,
                                    "amount": portion_amount,
                                    "buy_price": buy_price,
                                    "reason": reason
                                })
                            send_telegram_message(f"{symbol} — {reason} pie {current_price:.4f} USDT")
                            del tracked[symbol]
                            changed = True

                except Exception as e:
                    tracked[symbol] = info
                    if info.get("__changed__"):     # ← šo bloku pievieno uzreiz pēc iepriekšējās rindas
                        changed = True
                        del info["__changed__"]
                    print(f"⚠️ Kļūda apstrādājot {symbol}: {e}")
                    continue
            
            for symbol, info_obj in list(tracked.items()):
                tracked[symbol] = info_obj
                
            if changed:
                print("💾 Saglabājam izmaiņas failā...")
                
                save_json(TRACKED_TOKENS_FILE, tracked)
                summarize_trades()

        time.sleep(30)

    except Exception as global_e:
        print(f"⚠️ Kļūda visā ciklā: {global_e}")
        time.sleep(60)
