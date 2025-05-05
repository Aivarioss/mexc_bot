import os
import json
import numpy as np
from datetime import datetime, timezone
from config.settings import is_test_mode

LOG_FILE = "data/bot_log.json"
TEST_LOG_FILE = "data/test_log.json"

# === Palīgfunkcija Numpy datu apstrādei ===
def convert_numpy(obj):
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# === Drošs formatējums Telegram ziņām ===
def clean_telegram_message(text):
    for ch in ["*", "_", "`", "[", "]", "(", ")", "|"]:
        text = text.replace(ch, "")
    return text

def generate_summary(log_file=LOG_FILE):
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            events = json.load(f)
    except Exception:
        return "❌ Nav pieejams bot žurnāls."

    if not events:
        return "📭 Nav notikumu, par ko ziņot."

    # Filtrē tikai reālos notikumus
    real_events = [e for e in events if not e.get("test_mode")]

    def count(event_type):
        return len([e for e in real_events if e.get("type") == event_type])

    now = datetime.now(timezone.utc)
    summary_lines = ["📊 *AI aktivitātes kopsavilkums:*"]
    summary_lines.append(f"🔁 Apstrādāti tokeni: {len(real_events)}")
    summary_lines.append(f"📥 Pirkumi veikti: {count('buy')}")
    summary_lines.append(f"📤 Pārdošanas veikti: {count('sell')}")
    summary_lines.append(f"❌ Noraidīti: {count('reject')}")
    summary_lines.append(f"🤖 Modeļi trenēti: {count('train')}")
    summary_lines.append(f"✅ Tikai pārbaudīti: {count('check')}")

    # Pēdējā notikuma laiks
    try:
        last_event_time = datetime.fromisoformat(real_events[-1]["timestamp"]).astimezone(timezone.utc)
        elapsed = now - last_event_time
        summary_lines.append(f"\n🕒 Kopš pēdējā notikuma: {elapsed}")
    except Exception:
        summary_lines.append("🕒 Pēdējā notikuma laiks nav pieejams.")

    return clean_telegram_message("\n".join(summary_lines))

def generate_test_summary():
    try:
        with open(TEST_LOG_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)
    except Exception:
        return "❌ Nav pieejams TEST log fails."

    if not events:
        return "📭 TEST logā nav notikumu."

    def count(events, event_type):
        return len([e for e in events if e.get("type") == event_type])

    now = datetime.now(timezone.utc)
    last_ts = events[-1].get("timestamp")

    lines = ["🧪 *TEST_MODE aktivitātes kopsavilkums:*"]
    lines.append(f"🔁 Apstrādāti tokeni: {len(events)}")
    lines.append(f"❌ Noraidīti: {count(events, 'test_rejected')}")
    lines.append(f"🤖 Modeļi trenēti: {count(events, 'test_train')}")
    lines.append(f"💰 Pirkumi veikti: {count(events, 'test_buy')}")
    lines.append(f"📤 Pārdošanas veikti: {count(events, 'test_sell')}")
    lines.append(f"✅ Tikai pārbaudīti: {count(events, 'test_check')}")

    if last_ts:
        try:
            last_event_time = datetime.fromisoformat(last_ts).astimezone(timezone.utc)
            elapsed = now - last_event_time
            lines.append(f"\n🕒 Kopš pēdējā notikuma: {elapsed}")
        except Exception:
            lines.append("🕒 Pēdējā notikuma laiks nav pieejams.")

    return clean_telegram_message("\n".join(lines))

from datetime import datetime, timezone, timedelta
from config.settings import get_log_time_window_hours

def log_event(event_type, symbol=None, extra=None):
    if is_test_mode():
        return  # ⛔ Nelogot test notikumus bot_log.json

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type
    }
    if symbol:
        event["symbol"] = symbol
    if extra:
        event.update({k: convert_numpy(v) for k, v in extra.items()})

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=get_log_time_window_hours())

        if not os.path.exists(LOG_FILE):
            data = []
        else:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print("⚠️ LOG bojāts – sākam no jauna.")
                    data = []

        # Filtrējam vecos notikumus
        data = [e for e in data if datetime.fromisoformat(e["timestamp"]) >= cutoff]
        data.append(event)

        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        print(f"⚠️ Neizdevās ierakstīt LOG: {e}")

# === TEST režīma log ieraksts ===
def log_test_event(event_type, symbol=None, extra=None):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type
    }
    if symbol:
        event["symbol"] = symbol
    if extra:
        event.update({k: convert_numpy(v) for k, v in extra.items()})

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=get_log_time_window_hours())

        if not os.path.exists(TEST_LOG_FILE):
            data = []
        else:
            with open(TEST_LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print("⚠️ TEST_LOG bojāts – sākam no jauna.")
                    data = []

        data = [e for e in data if datetime.fromisoformat(e["timestamp"]) >= cutoff]
        data.append(event)

        with open(TEST_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        print(f"⚠️ Neizdevās ierakstīt TEST log: {e}")
