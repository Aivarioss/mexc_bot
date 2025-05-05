import os
import time

MARKET_DATA_DIR = "data/market_data"
CANDIDATE_FILE = "data/candidate_tokens.csv"
DAYS_TO_KEEP_MARKET = 3  # Tirgus datiem
DAYS_TO_KEEP_CANDIDATE = 1  # Kandidātiem

def cleanup_old_csv_files():
    """Tīra vecos tirgus datus un kandidātu failu."""
    now = time.time()
    cutoff_market = now - DAYS_TO_KEEP_MARKET * 86400
    cutoff_candidate = now - DAYS_TO_KEEP_CANDIDATE * 86400

    deleted_market = 0

    # Dzēš vecos tirgus CSV failus
    for filename in os.listdir(MARKET_DATA_DIR):
        if filename.endswith(".csv"):
            path = os.path.join(MARKET_DATA_DIR, filename)
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff_market:
                os.remove(path)
                deleted_market += 1

    # Dzēš kandidātu failu, ja vecāks par 1 dienu
    candidate_deleted = False
    if os.path.exists(CANDIDATE_FILE) and os.path.getmtime(CANDIDATE_FILE) < cutoff_candidate:
        try:
            os.remove(CANDIDATE_FILE)
            candidate_deleted = True
        except Exception as e:
            print(f"⚠️ Neizdevās dzēst kandidātu failu: {e}")

    print(f"✅ Dzēsti {deleted_market} tirgus faili.")
    if candidate_deleted:
        print(f"🗑️ Dzēsts: {CANDIDATE_FILE}")

    return deleted_market + (1 if candidate_deleted else 0)

# Standalone palaišanai
if __name__ == "__main__":
    print("🧹 Tīrīšanas skripts sākts...")
    cleanup_old_csv_files()
    print("🧼 Viss tīrs!")
