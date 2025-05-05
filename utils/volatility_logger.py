import os
import json
from datetime import datetime

VOLATILITY_LOG_PATH = "data/volatility_log.json"

def log_volatility(symbol, volatility):
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    if os.path.exists(VOLATILITY_LOG_PATH):
        with open(VOLATILITY_LOG_PATH, "r") as f:
            log = json.load(f)
    else:
        log = {}

    if timestamp not in log:
        log[timestamp] = {}

    log[timestamp][symbol] = round(volatility, 5)

    with open(VOLATILITY_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
