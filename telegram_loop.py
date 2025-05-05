import os
import sys
import time
import psutil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.telegram_commands import check_telegram_commands, clear_old_updates
from utils.telegram_commands import stop_process_if_running, start_process_if_not_running
from config.settings import load_state, save_state, is_test_mode

# === Konfigurācija ===
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "default")
LOCK_FILE = f"telegram_{EXCHANGE_NAME}.lock"

# === 1. Lock fails pārbaude ===
if os.path.exists(LOCK_FILE):
    print(f"🔒 Lock fails '{LOCK_FILE}' jau eksistē. Cita instance iespējams darbojas.")
    sys.exit()

# === 2. Process-level bloķēšana (ja vēl kāds telegram_loop darbojas)
current_pid = os.getpid()
for proc in psutil.process_iter(['pid', 'cmdline']):
    try:
        if proc.pid == current_pid:
            continue
        cmdline = " ".join(proc.info.get("cmdline") or [])
        if "telegram_loop.py" in cmdline:
            print(f"⚠️ Cita telegram_loop.py instance jau darbojas priekš '{EXCHANGE_NAME}' (PID {proc.pid})")
            sys.exit()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

# === 3. Izveido lock failu ===
with open(LOCK_FILE, "w") as f:
    f.write(str(current_pid))

print(f"📡 Telegram loops palaists priekš '{EXCHANGE_NAME}'. Process ID: {current_pid}")

# === 4. Notīra vecos update ID
clear_old_updates()

# === 5. Galvenais komandu cikls
# === 5. Galvenais komandu cikls
try:
    if "--restarted" in sys.argv:
        print("✅ Skripts tika restartēts (no /restartloop) – nepieņemam /restartloop vēlreiz.")
    else:
        while True:
            restart_requested = check_telegram_commands()

            if restart_requested:
                print("🔄 Restartējam procesus pēc režīma maiņas...")
                stop_process_if_running("main.py", "Tirdzniecības bots (main.py)")
                stop_process_if_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")
                time.sleep(2)
                start_process_if_not_running("main.py", "Tirdzniecības bots (main.py)")
                start_process_if_not_running("tracker_loop.py", "TP/SL uzraudzītājs (tracker_loop.py)")

            time.sleep(3)

except Exception as e:
    print(f"⚠️ Telegram loop kļūda: {e}")

finally:
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print(f"🔓 Lock fails '{LOCK_FILE}' noņemts.")
