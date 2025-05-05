# modules/market_sentiment.py

import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_API_SECRET"),
    'enableRateLimit': True
})

def get_market_sentiment():
    try:
        btc = exchange.fetch_ticker('BTC/USDT')
        change_24h = btc.get('percentage', 0)  # Dažreiz var nebūt - default uz 0

        if change_24h >= 2.0:
            return 'bullish'
        elif change_24h <= -2.0:
            return 'bearish'
        else:
            return 'neutral'

    except Exception as e:
        print(f"⚠️ Nevar noteikt tirgus sentimentu: {e}")
        return 'neutral'
