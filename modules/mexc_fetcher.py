import time
import requests
import config.settings as settings  # ✅ Konfigurācijas imports

MEXC_BASE_URL = "https://api.mexc.com"

def get_hype_tokens():
    """🔍 Iegūst tokenus ar ievērojamu pieaugumu no MEXC."""
    print("🔍 Skenējam MEXC tirgus datus...")

    # ✅ Dinamiskie kritēriji atkarīgi no TEST_MODE
    market = settings.get_market_criteria()
    min_cap = market["MIN_MARKET_CAP"]
    max_cap = market["MAX_MARKET_CAP"]  # ← Tagad nāk no settings
    min_volume = market["MIN_VOLUME_24H"]
    min_gain = market["MIN_GAIN_5M"]

    try:
        response = requests.get(f"{MEXC_BASE_URL}/api/v3/ticker/24hr")
        response.raise_for_status()
        markets = response.json()
    except Exception as e:
        print(f"❌ Kļūda iegūstot tickerus: {e}")
        return []

    hype_tokens = []

    for market_data in markets:
        try:
            symbol = market_data['symbol']
            if not symbol.endswith("USDT"):
                continue

            quote_volume = float(market_data['quoteVolume'])
            last_price = float(market_data['lastPrice'])
            market_cap = quote_volume * last_price  # Proxy market cap

            if not (min_cap <= market_cap <= max_cap):
                continue
            if quote_volume < min_volume:
                continue

            # Drošības indekss
            safety_score = quote_volume / market_cap
            if safety_score < 0.05:
                print(f"⚠️ Token {symbol} noraidīts: zems drošības indekss ({safety_score:.3f})")
                continue

            # Vēsturiskie dati (5m sveces)
            time.sleep(0.25)
            klines_url = f"{MEXC_BASE_URL}/api/v3/klines?symbol={symbol}&interval=5m&limit=3"
            res = requests.get(klines_url)
            if res.status_code != 200:
                continue

            data = res.json()
            if len(data) < 3:
                continue

            price_5m_ago = float(data[-3][4])
            current_price = float(data[-1][4])
            price_change_5m = ((current_price - price_5m_ago) / price_5m_ago) * 100

            avg_5m_volume = sum(float(c[5]) for c in data[:-1]) / (len(data) - 1)
            current_5m_volume = float(data[-1][5])
            volume_change_24h = (current_5m_volume / avg_5m_volume) if avg_5m_volume > 0 else 0

            if price_change_5m >= min_gain:
                token = {
                    "symbol": symbol,
                    "price_change_5m": price_change_5m,
                    "volume": quote_volume,
                    "market_cap": market_cap,
                    "last_price": current_price,
                    "volume_change_24h": volume_change_24h,
                    "safety_score": safety_score
                }

                if avg_5m_volume > 0 and current_5m_volume / avg_5m_volume > 5:
                    token["revival"] = True
                    print(f"🧟 Atklāts mirušais token kas atdzīvojies: {symbol}")

                hype_tokens.append(token)

        except Exception as e:
            print(f"⚠️ Kļūda ar {symbol}: {e}")
            continue

    return hype_tokens
