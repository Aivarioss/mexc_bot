from config import settings

def classify_token(token):
    """
    🚦 Klasificē tokenu pēc 5m pieauguma:
    - < MIN_GAIN_5M → Atmet
    - < 0.05 drošības indekss → Atmet
    - ≥ AGGRESSIVE_THRESHOLD → Agresīvā stratēģija
    - Ja volume pēkšņi ļoti liels (mirušais tokens) → revival
    - Citādi → Vienkāršā stratēģija
    """

    try:
        market = settings.get_market_criteria()

        min_gain = market["MIN_GAIN_5M"]
        min_volume = market["MIN_VOLUME_24H"]
        min_safety = 0.01 if settings.is_test_mode() else 0.05
        aggressive_threshold = market["AGGRESSIVE_THRESHOLD"]

        gain = token.get("price_change_5m", 0)
        volume = token.get("volume", 0)
        market_cap = token.get("market_cap", 0)

        if market_cap == 0:
            print(f"⚠️ Token {token['symbol']} izslēgts: market_cap = 0")
            return False

        safety_score = token.get("safety_score", volume / market_cap)
        volume_change = token.get("volume_change_24h", 1)

        if gain < min_gain:
            return False  # Nepietiekams pieaugums

        if safety_score < min_safety:
            print(f"⚠️ Token {token['symbol']} izslēgts: safety_score ({safety_score:.3f}) pārāk zems.")
            return False

        if volume >= min_volume and volume_change >= 5:
            return "revival"

        if gain >= aggressive_threshold:
            return "aggressive"
            
        # ✅ JAUNS BLOKS: Momentum stratēģija
        momentum_multiplier = settings.market_momentum_gain_multiplier()
        if volume >= min_volume and 2 <= volume_change < 5 and gain >= (min_gain * momentum_multiplier):

            print(f"⚡ Token {token['symbol']} klasificēts kā momentum_safe")
            return "momentum_safe"    

        return "simple"

    except Exception as e:
        print(f"⚠️ Kļūda tokena klasifikācijā: {e}")
        return False
