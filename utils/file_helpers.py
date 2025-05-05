import os
import json
import numpy as np
from pathlib import Path
from filelock import FileLock

def convert_numpy(obj):
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(v) for v in obj]
    return obj

def load_json(path, default=None, verbose=True):
    """
    Droši ielādē JSON failu. Ja fails neeksistē vai ir bojāts, atgriež default ({} vai []).
    Ja ir .bak fails, mēģina atgūt no tā.
    """
    if not os.path.exists(path):
        if verbose:
            print(f"ℹ️ JSON fails nav atrasts: {path}")
        return default if default is not None else {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        if verbose:
            print(f"⚠️ Nevar parsēt JSON (bojāts?): {path}")
        backup_path = path + ".bak"
        if os.path.exists(backup_path):
            if verbose:
                print(f"🔁 Mēģinu ielādēt backup: {backup_path}")
            try:
                with open(backup_path, "r", encoding="utf-8") as bf:
                    return json.load(bf)
            except Exception as e:
                if verbose:
                    print(f"❌ Neizdevās ielādēt arī backup: {e}")
        return default if default is not None else {}
    except Exception as e:
        if verbose:
            print(f"⚠️ Kļūda lasot JSON {path}: {e}")
        return default if default is not None else {}

def save_json(path, data, pretty=True, use_lock=False):
    try:
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)

        # Backup pirms pārrakstīšanas
        if os.path.exists(path):
            backup_path = path + ".bak"
            with open(path, "r", encoding="utf-8") as original, open(backup_path, "w", encoding="utf-8") as backup:
                backup.write(original.read())

        if use_lock:
            lock_path = path + ".lock"
            with FileLock(lock_path):
                _write_json(path, data, pretty)
        else:
            _write_json(path, data, pretty)

        print(f"✅ JSON saglabāts: {path}")  # ← pievienots
        if "B2USDT" in data:
            print(f"📌 B2USDT max_price saglabāts kā: {data['B2USDT'].get('max_price')}")  # ← pievienots
    except Exception as e:
        print(f"❌ Neizdevās saglabāt JSON {path}: {e}")

def _write_json(path, data, pretty):
    clean_data = convert_numpy(data)
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(clean_data, f, indent=4)
        else:
            json.dump(clean_data, f)
