import os
import time
import threading
from datetime import datetime
from collections import defaultdict
import datetime as dt
from config.settings import is_test_mode
from utils.file_helpers import load_json, save_json
from modules.price_tracker import track_token
from utils.telegram_alerts import escape_markdown

# === Ceļi ===
TRACKED_TOKENS_FILE = "data/tracked_tokens.json"
TEST_TRACKED_TOKENS_FILE = "data/test_tracked_tokens.json"
TRADE_HISTORY_FILE = "data/trade_history.json"
TEST_TRADE_HISTORY_FILE = "data/test_trade_history.json"

def clear_tracked_tokens(exchange):
    tracked = load_json(TRACKED_TOKENS_FILE)
    if not tracked:
        return []

    try:
        balance = exchange.fetch_balance()
    except Exception as e:
        print(f"⚠️ Neizdevās iegūt bilanci: {e}")
        return []

    removed = []
    for symbol in list(tracked.keys()):
        base = symbol.replace("USDT", "")
        token_amount = balance.get("total", {}).get(base, 0)

        if not token_amount or token_amount < 0.0001:
            print(f"🧹 Notīram no tracked: {symbol} (bilance 0)")
            removed.append(symbol)
            del tracked[symbol]

    save_json(TRACKED_TOKENS_FILE, tracked)
    return removed
    
def resync_tracked_tokens(exchange=None, test_mode=False):
    """
    Sinhronizē tracked tokenus no trade vēstures un biržas bilances.
    Atjauno pozīcijas, pievieno trūkstošos tokenus, izdzēš neesošos.
    """
    import threading
    from datetime import datetime

    tracked_file = TEST_TRACKED_TOKENS_FILE if test_mode or is_test_mode() else TRACKED_TOKENS_FILE
    history_file = TEST_TRADE_HISTORY_FILE if test_mode or is_test_mode() else TRADE_HISTORY_FILE

    history = load_json(history_file, default=[])
    tracked = load_json(tracked_file, default={})
    open_positions = {}
    changed = False

    # Ignorējamie simboli (HODL vai ilgtermiņa)
    ignored_symbols = {"PIUSDT", "XRPUSDT"}

    # 1. Solis: No vēstures atrast atvērtos pirkumus
    for trade in history:
        symbol = trade.get("symbol")
        if not symbol or symbol in ignored_symbols:
            continue

        if trade["type"] in ["buy", "test_buy"]:
            open_positions[symbol] = {
                "buy_price": trade["price"],
                "amount": trade["amount"],
                "strategy": trade.get("strategy", "unknown"),
                "timestamp": datetime.utcfromtimestamp(trade["timestamp"]).isoformat() + "Z",
                "ai_confidence": trade.get("ai_confidence", 0.85),
                "tp_levels": [1.05, 1.10, 1.20, 1.30],
                "sl_threshold": 0.05,
                "max_price": trade["price"],
                "executed_tp_levels": [],
                "volatility": 0.03,
                "feedback_score": 0.0
            }
        elif trade["type"] in ["sell", "test_sell"] and symbol in open_positions:
            del open_positions[symbol]

    # 2. Solis: Pievieno atvērtās pozīcijas uz tracked
    for symbol, data in open_positions.items():
        if symbol not in tracked:
            print(f"🔁 Resync: no vēstures pievienots {symbol}")
            tracked[symbol] = data
            changed = True
            if exchange:
                threading.Thread(target=track_token, args=(symbol, exchange), daemon=True).start()

    # 3. Solis: Pievieno tokenus no konta, ja nav tracked
    if exchange:
        try:
            balance = exchange.fetch_balance()
            existing_tracked = set(tracked.keys())

            for asset, amount in balance.get('total', {}).items():
                if asset in ["USDT", "MX"] or not amount or amount < 0.0001:
                    continue

                amount = float(amount)
                symbol = f"{asset}USDT"

                if symbol in ignored_symbols:
                    print(f"🚫 Ignorējam {symbol} — iekļauts ilgtermiņa sarakstā.")
                    continue

                if symbol in tracked and tracked[symbol].get("amount", 0) <= 0.00001:
                    print(f"🔁 Atjaunojam {symbol} — biržā amount = {amount}")
                    tracked[symbol]["amount"] = round(amount, 6)
                    changed = True
                    continue

                if symbol not in existing_tracked:
                    print(f"🔄 Resync no konta: {symbol} (amount: {amount})")

                    # Mēģinām iegūt pirkuma cenu no biržas vēstures
                    buy_price = 0.0
                    try:
                        trades = exchange.fetch_my_trades(symbol)
                        buys = [t for t in trades if t["side"] == "buy"]
                        if buys:
                            total_cost = sum(t["cost"] for t in buys if t["cost"])
                            total_amount = sum(t["amount"] for t in buys if t["amount"])
                            if total_amount > 0:
                                buy_price = round(total_cost / total_amount, 6)
                    except Exception as e:
                        print(f"⚠️ Neizdevās iegūt {symbol} pirkuma cenu: {e}")

                    tracked[symbol] = {
                        "buy_price": buy_price,
                        "amount": round(amount, 6),
                        "strategy": "resynced",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "ai_confidence": 0.85,
                        "tp_levels": [1.05, 1.10, 1.20, 1.30],
                        "sl_threshold": 0.05,
                        "max_price": buy_price,
                        "executed_tp_levels": [],
                        "volatility": 0.03,
                        "feedback_score": 0.0
                    }
                    changed = True
                    threading.Thread(target=track_token, args=(symbol, exchange), daemon=True).start()

            # 4. Solis: Izdzēš tokenus ar amount = 0 un bez atlikuma biržā
            for symbol in list(tracked.keys()):
                if symbol in ignored_symbols:
                    continue
                amount = tracked[symbol].get("amount", 0)
                if amount <= 0.00001:
                    coin = symbol.replace("USDT", "")
                    balance_amount = balance['total'].get(coin, 0)
                    if not balance_amount or balance_amount < 0.0001:
                        print(f"🧹 Noņemam {symbol} — nav amount un nav atlikuma biržā.")
                        del tracked[symbol]
                        changed = True

        except Exception as e:
            print(f"⚠️ Neizdevās nolasīt biržas bilanci resync laikā: {e}")

    # 5. Saglabā rezultātu
    if changed:
        save_json(tracked_file, tracked)
        print(f"✅ Resync pabeigts ({len(tracked)} tokeni tracked).")
    else:
        print(f"ℹ️ Resync pabeigts — nekādas izmaiņas ({len(tracked)} tokeni).")

def log_trade(trade_data):
    is_test = trade_data.get("type", "").startswith("test_")
    file_path = TEST_TRADE_HISTORY_FILE if is_test else TRADE_HISTORY_FILE
    history = load_json(file_path, default=[])
    history.append(trade_data)
    save_json(file_path, history)
    print(f"📝 {'TEST ' if is_test else ''}Darījums pierakstīts: {trade_data['symbol']} ({trade_data['type']})")

def get_test_summary():
    history = load_json(TEST_TRADE_HISTORY_FILE, default=[])
    buys = [t for t in history if t["type"] == "test_buy"]
    sells = [t for t in history if t["type"] == "test_sell"]

    if not history:
        return "📭 Nav neviena test darījuma."

    lines = [
        f"🧪 *Test darījumu kopsavilkums:*",
        f"📥 Test pirkumi: {len(buys)}",
        f"📤 Test pārdošanas: {len(sells)}",
        f"📦 Kopā darījumu: {len(history)}",
    ]

    last = history[-1]
    lines.append(f"🕒 Pēdējais: {last['symbol']} | {last['type']} | {dt.datetime.utcfromtimestamp(last['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)

def get_tracked_summary(test_mode=False, force_real=False):
    if force_real:
        file_path = TRACKED_TOKENS_FILE
    else:
        file_path = TEST_TRACKED_TOKENS_FILE if test_mode or is_test_mode() else TRACKED_TOKENS_FILE

    tracked = load_json(file_path)

    if not tracked:
        return "📭 Pašlaik netiek sekots nevienam tokenam." if not test_mode else "🧪 Test režīmā netiek sekots nevienam tokenam."

    label = "📈 *Aktīvie sekojamie tokeni:*" if not test_mode else "🧪 *Test režīma sekojamie tokeni:*"
    lines = [label]
    for symbol, info in tracked.items():
        price = info.get("buy_price", 0)
        amount = info.get("amount", 0)
        strategy = info.get("strategy", "?")
        lines.append(f"• {escape_markdown(symbol)} | Cena: {price:.4f} | Daudzums: {amount:.4f} | Stratēģija: {escape_markdown(strategy)}")

    return "\n".join(lines)

def get_help_message():
    return (
        "🆘 *Telegram bot komandas:*\n\n"
        "🤖 *Tirdzniecības cikls:*\n"
        "/startbot – Palaist bota tirdzniecības ciklu\n"
        "/stopbot – Apturēt bota ciklu\n"
        "/stopall – Apturēt visus bota ciklu\n"
        "/restartbot – Restartēt botu\n"
        "/restartloop – Restartēt telegramloop\n\n"
        "🧠 *AI trenēšana:*\n"
        "/starttrain – Startē AI treniņu (4 posmi)\n"
        "/stoptrain – Aptur AI treniņu\n"
        "/retrainfeedback – Trenē feedback AI no labeled datiem\n\n"
        "🧪 *Testēšanas režīms:*\n"
        "/testmodeon – Aktivizēt TEST_MODE (mīkstāki filtri, nav pirkumu)\n"
        "/teststatus – Tast aktīvie procesi\n"
        "/testmodeoff – Deaktivizēt TEST_MODE (iespējama reāla tirdzniecība)\n\n"
        "📊 *Darbības kopsavilkumi:*\n"
        "/status – Aktīvie procesi\n"
        "/sentiment – Tirgus tendence\n"
        "/ping – Vai bots darbojas?\n"
        "/summary – Īss tirdzniecības kopsavilkums\n"
        "/testsummary – Īss test tirdzniecības kopsavilkums\n"
        "/testactivity – Test AI aktivitātes kopsavilkums\n"
        "/activity – AI aktivitātes kopsavilkums\n\n"
        "📦 *Token sekošana:*\n"
        "/tracked – Saraksts ar sekojamajiem tokeniem\n"
        "/testtracked – Saraksts ar test sekojamajiem tokeniem\n"
        "/resync – Sinhronizēt tracked tokenus ar bilanci\n"
        "/cleartracked – Notīrīt tokenus, kuru tev vairs nav\n"
        "/balance – Parāda USDT bilanci biržā\n\n"
        "🧹 *Apkope:*\n"
        "/clearmodels – Notīra modeļus,ja pievieno jaunus indikatorus \n"
        "/cleartestdata – Notīra vecos Test datus\n"      
        "/cleanup – Dzēš vecos CSV failus (>3 dienām)\n\n"
        "ℹ️ /help – Šī palīdzības izvēlne"
    )

def get_usdt_balance(exchange):
    try:
        balance = exchange.fetch_balance()
        usdt_info = balance.get("USDT", {})
        free_usdt = usdt_info.get("free", 0)
        total_usdt = usdt_info.get("total", 0)

        report = [
            f"💰 *USDT bilance:*",
            f"Brīvi: {free_usdt:.2f} USDT",
            f"Kopā: {total_usdt:.2f} USDT",
            "\n📦 *Citi tokeni makā:*"
        ]

        asset_count = 0
        for asset, total_token in balance.get('total', {}).items():
            if asset in ["USDT", "MX"]:
                continue

            if total_token and total_token > 0.0001:
                try:
                    symbol = f"{asset}/USDT"
                    ticker = exchange.fetch_ticker(symbol)
                    price = ticker.get("last", 0)
                    value_usdt = total_token * price
                    report.append(f"• {asset}: {total_token:.4f} ≈ {value_usdt:.2f} USDT")
                    asset_count += 1
                except:
                    report.append(f"• {asset}: {total_token:.4f} (nav cenu info)")

        if asset_count == 0:
            report.append("• Nav citu tokenu makā.")

        return "\n".join(report)

    except Exception as e:
        return f"\n⚠️ Neizdevās iegūt bilanci: {e}"
