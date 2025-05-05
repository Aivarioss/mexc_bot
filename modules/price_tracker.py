import os
import time
import pandas as pd
from config import settings
from utils.file_helpers import load_json, save_json
from utils.telegram_alerts import send_telegram_message
from utils.trade_logger import log_trade, log_test_trade
from utils.indicators import compute_atr
from modules.adaptive_trade_helper import get_adaptive_tp_sl

TRACKED_TOKENS_FILE = (
    "data/test_tracked_tokens.json" if settings.is_test_mode() else "data/tracked_tokens.json"
)

def track_token(symbol, exchange):
    tracked = load_json(TRACKED_TOKENS_FILE)
    if symbol not in tracked:
        print(f"⚠️ {symbol} nav atrasts track sarakstā.")
        return

    entry_price = tracked[symbol]["buy_price"]
    amount = tracked[symbol]["amount"]
    strategy = tracked[symbol]["strategy"]

    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        atr_series = compute_atr(df)
        atr_value = atr_series.dropna().iloc[-1]
        current_price = df["close"].iloc[-1]
        volatility = atr_value / current_price

        confidence = tracked[symbol].get("ai_confidence", 0.85)
        strategy = tracked[symbol].get("strategy", "simple")

        # ✅ Izmanto saglabātos TP/SL, ja pieejami
        saved_tp = tracked[symbol].get("tp_levels")
        saved_sl = tracked[symbol].get("sl_threshold")

        if saved_tp and saved_sl:
            tp_multipliers = saved_tp
            sl_threshold = saved_sl
            print(f"🧠 Saglabāti TP/SL izmantoti no tracked_tokens.json")
        else:
            tp_multipliers, sl_threshold = get_adaptive_tp_sl(confidence, volatility, strategy)
            print(f"⚠️ TP/SL nebija saglabāti, aprēķināti atkārtoti.")

        stop_loss = entry_price * (1 - sl_threshold)
        print(f"📉 SL: {stop_loss:.6f} | SL %: {sl_threshold:.2%} | Volatility: {volatility:.3f}")

        tp_levels = [
            (mult, portion, f"TP +{int((mult - 1) * 100)}%")
            for mult, portion in zip(tp_multipliers, [0.3, 0.3, 0.2, 0.2])
        ]

    except Exception as e:
        print(f"⚠️ ATR/TP/SL kļūda — izmantojam statiskos: {e}")
        stop_loss = entry_price * (1 - settings.get_stop_loss_threshold())
        tp_levels = [
            (mult, portion, f"TP +{int((mult - 1) * 100)}%")
            for mult, portion in settings.get_tp_partial_levels()
        ]

    peak_price = entry_price
    trailing_stop = settings.get_trailing_stop_loss()
    print(f"📈 Start sekošana: {symbol} | Entry: {entry_price:.6f} | Stratēģija: {strategy}")

    while True:
        try:
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker.get('last')

            if current_price is None:
                print(f"⚠️ Nav cenas simbolam {symbol}, gaidām...")
                time.sleep(30)
                continue

            if current_price > peak_price:
                peak_price = current_price
                stop_loss = max(stop_loss, peak_price * trailing_stop)
                print(f"🚀 Jauns maksimums {symbol}: {peak_price:.6f} | SL pielāgots: {stop_loss:.6f}")

            if current_price < stop_loss:
                print(f"🛑 {symbol} nokrita zem SL ({stop_loss:.6f})! Pārdodam visu.")
                send_telegram_message(f"🛑 STOP-LOSS: {symbol}\nCena: {current_price:.4f}")
                sell_token(symbol, exchange, reason="Stop-Loss", portion=1.0)
                break

            for multiplier, portion, label in tp_levels:
                if current_price >= entry_price * multiplier and not tracked[symbol].get(label):
                    print(f"📈 {symbol} {label} — pārdodam {int(portion*100)}%.")
                    send_telegram_message(f"💰 {label} sasniegts: {symbol}\nCena: {current_price:.4f}")
                    sell_token(symbol, exchange, reason=label, portion=portion)

                    tracked = load_json(TRACKED_TOKENS_FILE)
                    if symbol in tracked:
                        tracked[symbol][label] = True
                        save_json(TRACKED_TOKENS_FILE, tracked)
                    break

            time.sleep(60)

        except Exception as e:
            print(f"⚠️ Kļūda sekojot {symbol}: {e}")
            time.sleep(10)


def sell_token(symbol, exchange, reason="TP", portion=1.0):
    tracked = load_json(TRACKED_TOKENS_FILE)
    if symbol not in tracked:
        print(f"⚠️ {symbol} nav atrodams pārdošanai.")
        return

    total_amount = tracked[symbol]["amount"]
    if total_amount <= 0:
        print(f"⚠️ {symbol} pozīcija jau slēgta.")
        return

    amount_to_sell = total_amount * portion
    buy_price = tracked[symbol]["buy_price"]
    strategy = tracked[symbol].get("strategy", "unknown")

    if settings.is_test_mode():
        print(f"🧪 TEST_MODE: simulēta pārdošana {symbol} | Daudzums: {amount_to_sell:.4f} | Iemesls: {reason}")
        simulated_mult = {
            "TP +5%": 1.05,
            "TP +10%": 1.10,
            "TP +15%": 1.15,
            "TP +20%": 1.20,
            "TP +25%": 1.25,
            "TP +30%": 1.30,
            "TP +35%": 1.35,
            "TP +40%": 1.40,
            "Stop-Loss": 0.95
        }.get(reason, 1.00)

        current_price = buy_price * simulated_mult
        profit = (current_price - buy_price) * amount_to_sell
        
        percentage = ((current_price - buy_price) / buy_price) * 100

        send_telegram_message(
            f"🧪 *TEST SELL* – {symbol}\n"
            f"📈 Cena: {current_price:.6f} USDT\n"
            f"📦 Daudzums: {amount_to_sell:.6f}\n"
            f"💰 Peļņa: {profit:.2f} USDT ({percentage:.2f}%)\n"
            f"🧠 Stratēģija: {strategy}"
        )

        log_test_trade({
            "type": "test_sell",
            "symbol": symbol,
            "price": current_price,
            "amount": amount_to_sell,
            "timestamp": time.time(),
            "profit": profit,
            "strategy": strategy,
            "result": "profit" if profit > 0 else "loss",
            "ai_decision": True
        })

        if portion == 1.0 or amount_to_sell >= total_amount:
            del tracked[symbol]
        else:
            tracked[symbol]["amount"] -= amount_to_sell

        save_json(TRACKED_TOKENS_FILE, tracked)
        return

    try:
        exchange.create_market_order(symbol, 'sell', amount_to_sell)
        price = exchange.fetch_ticker(symbol).get('last', buy_price)
        print(f"✅ SELL {symbol} ({reason}) | Daudzums: {amount_to_sell:.4f}")
        send_telegram_message(
            f"✅ SELL {symbol} | {reason} | Daudzums: {amount_to_sell:.4f} | Cena: {price:.4f}"
        )

        profit = (price - buy_price) * amount_to_sell
        percentage = ((price - buy_price) / buy_price) * 100

        send_telegram_message(
            f"✅ *{reason} SELL* – {symbol}\n"
            f"📈 Cena: {price:.6f} USDT\n"
            f"📦 Daudzums: {amount_to_sell:.6f}\n"
            f"💰 Peļņa: {profit:.2f} USDT ({percentage:.2f}%)\n"
            f"🧠 Stratēģija: {strategy}"
        )

        log_trade({
            "type": "sell",
            "symbol": symbol,
            "price": price,
            "amount": amount_to_sell,
            "timestamp": time.time(),
            "profit": profit,
            "strategy": strategy,
            "result": "profit" if profit > 0 else "loss",
            "ai_decision": True
        })

        if portion == 1.0 or amount_to_sell >= total_amount:
            del tracked[symbol]
        else:
            tracked[symbol]["amount"] -= amount_to_sell

        save_json(TRACKED_TOKENS_FILE, tracked)

    except Exception as e:
        print(f"⚠️ Kļūda SELL orderī {symbol}: {e}")
