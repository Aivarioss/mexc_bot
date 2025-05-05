# === 📁 Standarta Python bibliotēkas ===
import os
import sys
import time
import requests
import subprocess
import psutil
import platform as pf
import datetime
import threading
import subprocess

# === 🌐 3rd-party bibliotēkas (no pip) ===
import ccxt

# === ⚙️ Konfigurācija un stāvokļa pārvaldība ===
from config import settings
from config.settings import load_state, save_state
from config.settings import is_test_mode
from modules.market_sentiment import get_market_sentiment  # Ja vēl nav

# === 🤖 Modeļu treniņš un AI ===
from train_from_labeled import train_feedback_model

# === 📬 Telegram helperi un atbildes ===
from utils.telegram_alerts import send_reply

# === 🧠 AI aktivitātes kopsavilkumi (AI žurnāls) ===
from utils.summary import generate_summary, generate_test_summary

# === 📦 Tokenu uzraudzība un MEXC integrācija ===
from utils.tracking import (
    resync_tracked_tokens,
    get_tracked_summary,
    clear_tracked_tokens,
    get_usdt_balance,
    get_help_message
)

# === 🧹 Datu failu dzēšana (piemēram, vecie OHLC CSV) ===
from utils.cleanup import cleanup_old_csv_files
from clearmodels import clear_models

# === 📊 Tirdzniecības pārskati (real un test režīms) ===
from data.trade_summary import summarize_trades
from data.test_trade_summary import summarize_test_trades
# === 📍 Ceļi ===
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPDATE_ID_FILE = os.path.join(PROJECT_ROOT, "data", "last_update_id.txt")

def stream_process_output(proc, log_file, label):
    def stream():
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"\n\n--- ✅ {label} STARTED ({datetime.datetime.now()}) ---\n")
            for line in proc.stdout:
                decoded = line.rstrip()
                print(f"[{label}] {decoded}")  # CMD logā
                if any(err in decoded.lower() for err in ["error", "traceback", "exception"]):
                    log.write(f"[{label}] {decoded}\n")  # Tikai kļūdas
            log.write(f"--- 🔚 {label} BEIDZĀS ({datetime.datetime.now()}) ---\n")
    threading.Thread(target=stream, daemon=True).start()

def start_process_if_not_running(script_name, label=""):
    script_path = os.path.join(PROJECT_ROOT, os.path.basename(script_name))
    log_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{script_name.replace('.py', '')}.log")

    # Jau darbojas?
    for proc in psutil.process_iter(['cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            if any(os.path.basename(part) == script_name for part in cmdline):
                print(f"🔁 {label} jau darbojas (PID {proc.pid})")
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print(f"🚀 Startējam {label} → {script_path}")

    proc = subprocess.Popen(
        ["python", "-u", script_path],  # -u = no buferēšanas
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1
    )

    stream_process_output(proc, log_file, label)

def stop_process_if_running(script_name, label=""):
    current_pid = os.getpid()
    label = label or script_name
    stopped = False

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get("cmdline") or []
            if not cmdline:
                continue

            if script_name in cmdline or any(script_name in part or part.endswith(script_name) for part in cmdline):
                if proc.pid != current_pid:
                    print(f"⛔ Apturam procesu: {script_name} (PID: {proc.pid})")
                    proc.kill()
                    try:
                        proc.wait(timeout=3)
                        send_reply(f"⛔ Apturēts: {label} (PID {proc.pid})")
                    except psutil.TimeoutExpired:
                        send_reply(f"⚠️ {label} (PID {proc.pid}) netika pilnībā apturēts 3 sekunžu laikā.")
                    stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            send_reply(f"⚠️ Neizdevās apturēt {label}: {e}")

    if not stopped:
        send_reply(f"ℹ️ {label} nav aktīvs.")

def clear_old_updates():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        response = requests.get(url, params={"timeout": 1}, timeout=3)
        data = response.json()

        if "result" in data and data["result"]:
            last_update_id = data["result"][-1]["update_id"]
            # Atzīmē kā apstrādātu
            requests.get(url, params={"offset": last_update_id + 1}, timeout=2)

            with open(UPDATE_ID_FILE, "w") as f:
                f.write(str(last_update_id))
            print(f"✅ Vecie update atzīmēti līdz ID {last_update_id}")
    except Exception as e:
        print(f"⚠️ Neizdevās notīrīt vecos update: {e}")

def load_last_update_id():
    try:
        with open(UPDATE_ID_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_update_id(update_id):
    with open(UPDATE_ID_FILE, "w") as f:
        f.write(str(update_id))

def is_process_running(name):
    for p in psutil.process_iter(['cmdline']):
        try:
            if any(name in part for part in (p.info['cmdline'] or [])):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def check_telegram_commands():
    restart_requested = False
    last_update_id = load_last_update_id()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 10}

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()

        for result in data.get("result", []):
            update_id = result["update_id"]
            message = result.get("message", {})
            text = message.get("text", "").strip().lower()
            chat_id = str(message.get("chat", {}).get("id", ""))

            if chat_id != CHAT_ID:
                continue

            print(f"📩 Komanda saņemta: {text}")

            if text == "/startbot":
                send_reply("🤖 Startējam bota ciklu...")
                start_process_if_not_running("main.py", "Tirdzniecības bots (main.py)")
                start_process_if_not_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")

            elif text == "/stopbot":
                send_reply("⛔ Apturam tirdzniecības botu...")

                stop_process_if_running("main.py", "Tirdzniecības bots (main.py)")
                stop_process_if_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")

                send_reply("✅ Bota pirkšanas/pārdošanas cikls apturēts.")


            elif text == "/stopall":
                send_reply("💥 Apturam visus bota procesus (izņemot šo Telegram loop)...")

                stop_process_if_running("main.py", "Tirdzniecības bots (main.py)")
                stop_process_if_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")
                stop_process_if_running("collect_all_data.py", "Datu vākšana (collect_all_data.py)")
                stop_process_if_running("train_pending_models.py", "AI treniņš (train_pending_models.py)")
                stop_process_if_running("label_candidates.py", "Kandidātu apzīmēšana (label_candidates.py)")
                stop_process_if_running("train_from_labeled.py", "Feedback AI treniņš (train_from_labeled.py)")
    
                send_reply("✅ Visi bota procesi apturēti (Telegram loop palika aktīvs).")
                
            elif text == "/restartbot":
                send_reply("🔄 Restartējam bota tirdzniecības procesus...")

                # Apturam galvenos procesus
                stop_process_if_running("main.py", "Tirdzniecības bots (main.py)")
                stop_process_if_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")

                time.sleep(2)  # Pagaidām, lai procesi pilnībā apstājas

                # Palaidžam atpakaļ
                start_process_if_not_running("main.py", "Tirdzniecības bots (main.py)")
                start_process_if_not_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")

                send_reply("✅ Bota procesi veiksmīgi restartēti!")
                               
            elif text == "/restartloop":
                send_reply("🔄 Restartēju Telegram komandu ciklu...")

                python_executable = sys.executable
                current_script = os.path.abspath(__file__)

                if pf.system() == "Windows":
                    # Uz Windows: atver jaunu cmd logu ar šo skriptu un `--restarted` parametru
                    subprocess.Popen(
                        ["cmd", "/c", python_executable, "-u", current_script, "--restarted"],
                        shell=True
                    )
                else:
                        # Uz Linux: palaist fona procesā ar to pašu parametru
                        subprocess.Popen(
                        [python_executable, "-u", current_script, "--restarted"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                sys.exit()
   
            elif text == "/sentiment":
                sentiment = get_market_sentiment()
                emoji = {
                    'bullish': "🌞",
                    'neutral': "🌤",
                    'bearish': "🌧"
                }.get(sentiment, "❓")

                send_reply(f"{emoji} Tirgus sentiment šobrīd: *{sentiment.upper()}*")
                

            elif text in ["/starttrain", "/trainall"]:
                send_reply("🧠 Startējam AI treniņa ciklu...")

                start_process_if_not_running("collect_all_data.py", "🧱 Datu savākšana (collect_all_data.py)")
                start_process_if_not_running("label_candidates.py", "🏷️ Breakout kandidātu apzīmēšana (label_candidates.py)")
                start_process_if_not_running("train_pending_models.py", "🧠 Individuālo modeļu treniņš (train_pending_models.py)")               
                start_process_if_not_running("train_from_labeled.py", "📈 Globālā AI modeļa treniņš (train_from_labeled.py)")

                send_reply("🚀 Visi AI treniņa posmi palaisti ciklā vienā telegramloop cmd")


            elif text == "/stoptrain":
                send_reply("🛑 Apturam AI treniņa procesus...")

                stop_process_if_running("collect_all_data.py", "🧱 Datu savākšana (collect_all_data.py)")
                stop_process_if_running("train_pending_models.py", "🧠 Individuālo modeļu treniņš (train_pending_models.py)")
                stop_process_if_running("label_candidates.py", "🏷️ Breakout kandidātu apzīmēšana (label_candidates.py)")
                stop_process_if_running("train_from_labeled.py", "📈 Globālā AI modeļa treniņš (train_from_labeled.py)")

                send_reply("✅ Visi AI treniņa procesi apturēti.")


            elif text == "/summary":
                send_reply(summarize_trades(return_text=True))
                
            elif text == "/testsummary":
                send_reply(summarize_test_trades(return_text=True))
    
            elif text == "/activity":
                send_reply(generate_summary())

            elif text == "/testactivity":
                send_reply(generate_test_summary())

            elif text == "/retrainfeedback":
                send_reply("🔁 Pārtrenējam feedback AI modeli no labeled kandidātiem...")
                try:
                    train_feedback_model()
                    send_reply("✅ Feedback AI modelis veiksmīgi pārtrenēts!")
                except Exception as e:
                    send_reply(f"❌ Neizdevās pārtrenēt feedback modeli:\n`{e}`")

            elif text == "/resync":
                import ccxt
                exchange = ccxt.mexc({
                    'apiKey': os.getenv("MEXC_API_KEY"),
                    'secret': os.getenv("MEXC_API_SECRET"),
                    'enableRateLimit': True
                })

                # Veicam resync un nolasām cik daudz tokenu tagad ir
                resync_tracked_tokens(exchange=exchange, test_mode=is_test_mode())

                # Pēc resync izvadām cik ir aktuālie tracked
                from utils.file_helpers import load_json
                tracked_file = "data/test_tracked_tokens.json" if is_test_mode() else "data/tracked_tokens.json"
                tracked = load_json(tracked_file, default={})
                tracked_count = len(tracked)

                send_reply(f"🔁 Resync veikts!\n📦 Pašlaik tracked {tracked_count} tokeni.")

            elif text == "/tracked":
                send_reply(get_tracked_summary(force_real=True))  # ← piespied reālos

            elif text == "/testtracked":
                send_reply(get_tracked_summary(test_mode=True))
    
            elif text == "/cleartracked":
                import ccxt
                from utils.tracking import clear_tracked_tokens
                exchange = ccxt.mexc({
                    'apiKey': os.getenv("MEXC_API_KEY"),
                    'secret': os.getenv("MEXC_API_SECRET"),
                    'enableRateLimit': True
                })
                removed = clear_tracked_tokens(exchange)
                if removed:
                    send_reply(f"🧹 Notīrīti no track: {', '.join(removed)}")
                else:
                    send_reply("✅ Visi tracked tokeni atbilst biržas bilancei.")
                    
            elif text == "/cleartestdata":
                try:
                    from clear_test_data import files_to_delete  # Importēt tikai sarakstu, lai saņemtu nosaukumus
                    import clear_test_data  # Palaižam kā moduli (izpilda failu)
                    send_reply(f"🧪 Test dati notīrīti:\n" + "\n".join([f"`{f}`" for f in files_to_delete]))
                except Exception as e:
                    send_reply(f"❌ Neizdevās notīrīt test datus:\n`{e}`")
        
            elif text == "/balance":
                import ccxt
                from utils.tracking import get_usdt_balance
                exchange = ccxt.mexc({
                    'apiKey': os.getenv("MEXC_API_KEY"),
                    'secret': os.getenv("MEXC_API_SECRET"),
                    'enableRateLimit': True
                })
                send_reply(get_usdt_balance(exchange))

            elif text == "/cleanup":
                from utils.cleanup import cleanup_old_csv_files
                deleted = cleanup_old_csv_files()
                send_reply(f"🧹 Notīrīti {deleted} veci tirgus faili (vecāki par 3 dienām).")
                
            elif text == "/clearmodels":
                clear_models()
                send_reply("🧹 Visi AI modeļu faili (`.pkl`, `.json`) notīrīti no `models/` mapes.")
    
            elif text == "/status":
                send_status()
           
            elif text == "/ping":
                from datetime import datetime
                import platform

                state = load_state()
                test_mode = state.get("TEST_MODE", False)
                test_txt = "🧪 *TEST_MODE IESLĒGTS*" if test_mode else "☑️ *TEST_MODE izslēgts*"

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                host = platform.node()

                send_reply(
                    f"✅ *Bots darbojas!*\n\n"
                    f"{test_txt}\n"
                    f"🕒 `{now}`\n"
                    f"📍 `{host}`"
                )
   
            elif text == "/help":
                from utils.tracking import get_help_message
                send_reply(get_help_message())
                
            elif text == "/testmodeon":
                state = load_state()
                state["TEST_MODE"] = True
                save_state(state)

                check = load_state().get("TEST_MODE", False)
                if check:
                    send_reply("🧪 *TEST_MODE ieslēgts!* Botā tiks izmantoti test parametri.")
                    restart_requested = True
                else:
                    send_reply("❌ Neizdevās ieslēgt TEST_MODE.")

                # Uzreiz atsūta statusu
                state = load_state()
                file_state = state.get("TEST_MODE", False)
                runtime_state = is_test_mode()
                file_txt = "🧪 IESLĒGTS" if file_state else "☑️ Izslēgts"
                runtime_txt = "🧪 IESLĒGTS" if runtime_state else "☑️ Izslēgts"
                send_reply(
                    f"📂 `state.json`: {file_txt}\n"
                    f"⚙️ Aktīvajā kodā: {runtime_txt}"
                )

            elif text == "/testmodeoff":
                state = load_state()
                state["TEST_MODE"] = False
                save_state(state)

                check = load_state().get("TEST_MODE", True)
                if not check:
                    send_reply("✅ *TEST_MODE izslēgts.* Bots darbojas normālā režīmā.")
                    restart_requested = True
                else:
                    send_reply("❌ Neizdevās izslēgt TEST_MODE.")

                # Uzreiz atsūta statusu
                state = load_state()
                file_state = state.get("TEST_MODE", False)
                runtime_state = is_test_mode()
                file_txt = "🧪 IESLĒGTS" if file_state else "☑️ Izslēgts"
                runtime_txt = "🧪 IESLĒGTS" if runtime_state else "☑️ Izslēgts"
                send_reply(
                    f"📂 `state.json`: {file_txt}\n"
                    f"⚙️ Aktīvajā kodā: {runtime_txt}"
                )

            elif text == "/teststatus":
                state = load_state()
                file_state = state.get("TEST_MODE", False)
                runtime_state = is_test_mode()
                file_txt = "🧪 IESLĒGTS" if file_state else "☑️ Izslēgts"
                runtime_txt = "🧪 IESLĒGTS" if runtime_state else "☑️ Izslēgts"
                send_reply(
                    f"📂 `state.json`: {file_txt}\n"
                    f"⚙️ Aktīvajā kodā: {runtime_txt}"
                )
        if restart_requested:
            stop_process_if_running("main.py", "Tirdzniecības bots (main.py)")
            time.sleep(2)
            start_process_if_not_running("main.py", "Tirdzniecības bots (main.py)")

        if 'update_id' in locals():
            save_last_update_id(update_id)
        return restart_requested

    except Exception as e:
        print(f"⚠️ Telegram komandu kļūda: {e}")
        return False

def send_status():
    script_map = {
        "main.py": "📊 Tirdzniecības bots",
        "tracker_loop.py": "🔁 TP/SL uzraudzītājs",
        "telegram_loop.py": "📡 Telegram komandas",
        "collect_all_data.py": "📥 Datu vākšana",
        "train_pending_models.py": "🧠 Individuālo modeļu treniņš",
        "label_candidates.py": "🏷️ Kandidātu apzīmēšana",
        "train_from_labeled.py": "📈 Feedback AI treniņš"
    }

    lines = ["📡 *Bota procesu statuss:*"]
    for script, label in script_map.items():
        status = "🟢 Aktīvs" if is_process_running(script) else "🔴 Nav aktīvs"
        lines.append(f"{label} → `{script}` → {status}")

    reply = "\n".join(lines)
    send_reply(reply)

def check_telegram_commands_forced(fake_text):
    if fake_text == "/status":
        send_status()

def send_error_alert(error_text):
    try:
        hostname = platform.node()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"❗️*Bots sastapa kļūdu!*\n\n"
            f"`{error_text}`\n\n"
            f"📍 Host: `{hostname}`\n🕒 Laiks: `{now}`"
        )
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Neizdevās nosūtīt kļūdas brīdinājumu: {e}")
