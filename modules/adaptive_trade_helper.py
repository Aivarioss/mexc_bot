"""
Adaptive TP/SL Helper Module
-----------------------------
Šis modulis nodrošina adaptīvu take-profit (TP) un stop-loss (SL) līmeņu aprēķinu,
balstoties uz AI uzticamības rādītāju (confidence), tirgus svārstīgumu (volatility)
un izvēlēto stratēģiju (strategy).
"""

def get_adaptive_tp_sl(confidence, volatility, strategy):
    """
    Ģenerē adaptīvus TP un SL līmeņus, balstoties uz AI confidence, volatility un stratēģiju.

    Parameters:
        confidence (float): AI uzticamības vērtība (0.0 līdz 1.0).
        volatility (float): Tirgus svārstīguma koeficients (parasti 0.01 līdz 0.1).
        strategy (str): Stratēģijas nosaukums. Atbalstītās: 'aggressive', 'revival', 'momentum_safe', 'simple'.

    Returns:
        tuple: (tp_levels: list of floats, sl_threshold: float)
    """
    
    # === Validācija ===
    if not (0 <= confidence <= 1):
        raise ValueError(f"AI confidence vērtībai jābūt starp 0.0 un 1.0, saņemts: {confidence}")
    if not (0 < volatility < 1):
        raise ValueError(f"Volatility vērtībai jābūt pozitīvai un <1, saņemts: {volatility}")
    if strategy not in ("aggressive", "revival", "momentum_safe", "simple", "default", None):
        raise ValueError(f"Neatbalstīta stratēģija: {strategy}")

    # === Bāzes TP un SL pēc confidence ===
    if confidence >= 0.95:
        tp = [1.10, 1.20, 1.30, 1.40]
        sl = 0.05
    elif confidence >= 0.85:
        tp = [1.05, 1.10, 1.20]
        sl = 0.035
    else:
        tp = [1.03, 1.06, 1.09]
        sl = 0.025

    # === Pielāgošana pēc stratēģijas ===
    if strategy == "aggressive":
        sl *= 1.2
        tp = [round(x * 1.2, 4) for x in tp]
    elif strategy == "revival":
        sl *= 0.9
        tp = [round(x * 0.9, 4) for x in tp]
    elif strategy == "momentum_safe":
        sl *= 0.8
        tp = [round(x * 1.05, 4) for x in tp]
    elif strategy == "simple":
        sl *= 0.95  # konservatīvāks stop loss
        tp = [round(x * 0.95, 4) for x in tp]  # mazliet zemāki TP līmeņi

    # "default" vai None — nemaina neko

    return tp, sl


# === Testēšana lokāli ===
if __name__ == "__main__":
    try:
        confidence = 0.88
        volatility = 0.03
        strategy = "simple"

        tp, sl = get_adaptive_tp_sl(confidence, volatility, strategy)
        print(f"[TEST] TP līmeņi: {tp}")
        print(f"[TEST] SL slieksnis: {sl:.4f}")
    except Exception as e:
        print(f"[KĻŪDA]: {e}")
