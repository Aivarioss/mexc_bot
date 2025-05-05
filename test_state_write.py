import os
import json

STATE_FILE = "config/state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"TEST_MODE": False}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("❌ Kļūda: bojāts state.json.")
        return {"TEST_MODE": False}

def save_state(state):
    path = os.path.abspath(STATE_FILE)
    print(f"💾 Saglabājam state.json → {path}")
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"✅ Saglabāts: {state}")

# === Testēšana ===
print("📥 Esošais state:")
print(load_state())

print("\n🔁 Pārslēdzam TEST_MODE...")
state = load_state()
state["TEST_MODE"] = not state.get("TEST_MODE", False)
save_state(state)

print("\n📤 Jaunais state:")
print(load_state())
