# == Standarta importi ==
import os
import sys
import time
import joblib
import pandas as pd
from dotenv import load_dotenv
from filelock import FileLock
import ccxt

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.abspath("."))  # .env & local imports
load_dotenv()

api_key = os.getenv("MEXC_API_KEY")
api_secret = os.getenv("MEXC_API_SECRET")
if not api_key or not api_secret:
    raise ValueError("❌ API atslēgas nav ielādētas! Pārbaudi .env failu.")

exchange = ccxt.mexc({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})

try:
    exchange.load_markets()
    supported_symbols = list(exchange.symbols)
    print(f"✅ MEXC atbalsta {len(supported_symbols)} simbolus caur API.")
except Exception as e:
    print(f"⚠️ Neizdevās ielādēt tirgus: {e}")
    sys.exit(1)

# == Moduļi ==
from modules.mexc_fetcher import get_hype_tokens
from modules.token_filter import classify_token
from modules.price_tracker import track_token
from modules.symbol_checker import is_symbol_valid
from modules.collect_and_save import collect_and_save
from modules.ai_trainer import train_ai_model
from modules.ai_predictor import ai_filter
from utils.feedback_predictor import is_feedback_model_positive
from utils.telegram_alerts import send_telegram_message
from utils.telegram_commands import check_telegram_commands
from utils.save_candidate import save_candidate
from utils.data_helpers import prepare_X_for_model
from utils.file_helpers import load_json, save_json
from utils.trade_logger import log_trade, log_test_trade
import config.settings as settings
from modules.trade_executor import buy_token, calculate_dynamic_budget, estimate_volatility

print(f"🔧 STARTA STATUSS — TEST_MODE: {settings.is_test_mode()}")

# == Helper funkcija ==
def log(msg):
    print(msg, flush=True)

def ensure_tracked_entry_complete(entry):
    return {
        "buy_price": entry.get("buy_price", 0),
        "amount": entry.get("amount", 0),
        "strategy": entry.get("strategy", "unknown"),
        "max_price": entry.get("max_price", entry.get("buy_price", 0)),
        "executed_tp_levels": entry.get("executed_tp_levels", []),
        "ai_confidence": entry.get("ai_confidence", 0.85),
        "volatility": entry.get("volatility", 0.03),
        "feedback_score": entry.get("feedback_score", 0.0)
    }

send_telegram_message("✅ Bots veiksmīgi startēts! Meklējam hype tokenus...")

# === 🔁 GALVENAIS CIKLS AR STATISTIKU ===
while True:
    try:
        start_time = time.time()

        # Statistikas skaitītāji
        stats = {
            "total_hype": 0,
            "revivals_found": 0,
            "classified": {
                "simple": 0,
                "aggressive": 0,
                "revival": 0,
                "momentum_safe": 0
            },
            "ai_accepted": 0,
            "ai_rejected": 0,
            "feedback_rejected": 0,
            "test_buys": 0,
            "real_buys": 0
        }

        # 🚨 DYNAMISKA TEST_MODE PARBAUDE
        test_mode = settings.is_test_mode()
        print("\n🔄 Jauns cikls: skenējam hype tokenus...")
        print("🤙 TEST_MODE AKTĪVS!" if test_mode else "📈 LIVE_MODE AKTĪVS!")

        market_params = settings.get_market_criteria()
        ai_threshold = settings.get_min_ai_probability()

        hype_tokens = get_hype_tokens()

        if not hype_tokens:
            print("😴 Nav atrasti hype tokeni.")
            check_telegram_commands()
            time.sleep(settings.get_check_interval())
            continue

        print(f"🔥 ATRASTI HYPE TOKENI:")
        for token in hype_tokens:
            stats["total_hype"] += 1
            if token.get("revival"):
                stats["revivals_found"] += 1

            print(f"🔸 {token['symbol']} | 5m: {token['price_change_5m']:.2f}% | Vol: ${token['volume']:.0f}")
            strategy = classify_token(token)
            print(f"   → Stratēģija: {strategy}")
            token["strategy"] = strategy

            if strategy not in ["simple", "aggressive", "revival", "momentum_safe"]:
                continue

            if strategy in stats["classified"]:
                stats["classified"][strategy] += 1

            if not is_symbol_valid(token["symbol"], exchange):
                print(f"❌ Token {token['symbol']} nav validēts kā tirgojams. Izlaižam.")
                continue

            current_price = float(token.get("last_price") or token.get("price") or 0)
            if current_price <= 0:
                print(f"❌ Token {token['symbol']} cenai nav derīgas vērtības (0 vai mazāk).")
                continue

            skip_ai_filter_strategies = ["aggressive", "revival", "momentum_safe"]
            if strategy in skip_ai_filter_strategies:
                print(f"⚠️ Stratēģija '{strategy}' → izlaižam AI filtru priekš {token['symbol']}")
                if strategy == "aggressive":
                    confidence = 0.90
                    safety_score = 0.10
                elif strategy == "revival":
                    confidence = 0.85
                    safety_score = 0.20
                elif strategy == "momentum_safe":
                    confidence = 0.87
                    safety_score = 0.25
                prediction = 1
            else:
                try:
                    prediction, confidence, safety_score = ai_filter(token, exchange, return_score=True)
                    if prediction != 1:
                        stats["ai_rejected"] += 1
                        print(f"❌ Individuālais AI atmeta {token['symbol']} → prediction: {prediction}")
                        save_candidate(token, exchange)
                        continue
                    stats["ai_accepted"] += 1
                    print(f"✅ AI confidence {token['symbol']}: {confidence:.2f} | Safety: {safety_score:.2f}")
                except Exception as e:
                    print(f"❌ AI filtrēšana neizdevās {token['symbol']}: {e}")
                    save_candidate(token, exchange)
                    continue

            volatility = estimate_volatility(token["symbol"], exchange)
            feedback_input = {
                "price": current_price,
                "volatility": volatility,
                "ai_confidence": confidence,
                "strategy_simple": 1 if strategy == "simple" else 0,
                "strategy_aggressive": 1 if strategy == "aggressive" else 0,
                "strategy_revival": 1 if strategy == "revival" else 0,
                "strategy_momentum_safe": 1 if strategy == "momentum_safe" else 0
            }

            feedback_score = is_feedback_model_positive(feedback_input, return_score=True)

            if feedback_score is None:
                print(f"⚠️ Feedback modelis nav pieejams – izlaižam {token['symbol']}")
                save_candidate(token, exchange)
                continue

            print(f"🧠 Feedback score {token['symbol']}: {feedback_score:.3f}")
            if feedback_score < ai_threshold:
                stats["feedback_rejected"] += 1
                print(f"🧠 Feedback AI atmeta {token['symbol']} (score: {feedback_score:.3f})")
                save_candidate(token, exchange)
                continue

            # 🚨 ATKĀRTOT TEST_MODE PARBAUDI PIRMS PIRKUMA
            if settings.is_test_mode():
                stats["test_buys"] += 1
                print(f"🥚 TEST_MODE: simulēts pirkums {token['symbol']}")
                usdt_amount = calculate_dynamic_budget(token, confidence, safety_score)
                amount = round(usdt_amount / current_price, 6)

                log_test_trade({
                    "symbol": token["symbol"],
                    "type": "test_buy",
                    "price": current_price,
                    "amount": amount,
                    "strategy": token["strategy"],
                    "ai_decision": True
                })

                tracked_test_file = "data/test_tracked_tokens.json"
                tracked = load_json(tracked_test_file, default={})
                tracked[token["symbol"]] = ensure_tracked_entry_complete({
                    "buy_price": current_price,
                    "amount": amount,
                    "strategy": token["strategy"],
                    "max_price": current_price,
                    "executed_tp_levels": [],
                    "ai_confidence": confidence,
                    "volatility": volatility,
                    "feedback_score": feedback_score
                })
                save_json(tracked_test_file, tracked)
                continue

            if buy_token(token, exchange, confidence=confidence, safety_score=safety_score):
                stats["real_buys"] += 1
                send_telegram_message(
                    f"🤝 PIRKUMS: {token['symbol']}\n"
                    f"📈 Cena: {current_price:.4f} USDT\n"
                    f"🧠 AI: {confidence:.2f} | FB: {feedback_score:.2f}\n"
                    f"🿦 Stratēģija: {strategy}"
                )
                log_trade({
                    "symbol": token["symbol"],
                    "type": "buy",
                    "price": current_price,
                    "amount": 0,
                    "strategy": token["strategy"],
                    "ai_decision": True
                })

        # == Cikla beigu statistika ==
        duration = int(time.time() - start_time)
        print("\n📊 CIKLA ATSKAITE:")
        print(f"🔍 Atrasti tokeni: {stats['total_hype']} (revival: {stats['revivals_found']})")
        print("🧠 Stratēģiju sadalījums:")
        for strat, count in stats["classified"].items():
            print(f"   • {strat}: {count}")
        print(f"✅ AI akceptēti: {stats['ai_accepted']} | ❌ AI atmesti: {stats['ai_rejected']}")
        print(f"🧠 Feedback atmesti: {stats['feedback_rejected']}")
        print(f"🥚 Test trades: {stats['test_buys']} | 💰 Reāli pirkumi: {stats['real_buys']}")
        print(f"⏱️ Cikla ilgums: {duration}s")

        check_telegram_commands()
        interval = settings.get_check_interval()
        print(f"⏳ Gaidām {interval // 60} min līdz nākamajai pārbaudei...")
        time.sleep(interval)

    except Exception as main_error:
        send_telegram_message(f"❌ Kļūda galvenajā ciklā: {main_error}")
        print(f"❌ Kļūda galvenajā ciklā: {main_error}")
        time.sleep(60)
