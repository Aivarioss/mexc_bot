import os

files_to_delete = [
    "data/test_tracked_tokens.json",
    "data/test_trade_history.json",
    "data/test_log.json",
    "data/test_summary_log.json"
]

for file_path in files_to_delete:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ Deleted: {file_path}")
        else:
            print(f"✅ Already clean: {file_path}")
    except Exception as e:
        print(f"❌ Error deleting {file_path}: {e}")
