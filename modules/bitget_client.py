# bitget_bot/modules/bitget_client.py
import requests
import time
import hmac
import hashlib

class BitgetClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.secret = api_secret

    def get_symbols(self):
        url = "https://api.bitget.com/api/spot/v1/public/symbols"
        r = requests.get(url)
        return [s['symbolName'] for s in r.json()['data']]

    def get_ohlcv(self, symbol, interval='1m', limit=100):
        url = f"https://api.bitget.com/api/spot/v1/market/candles"
        params = {
            "symbol": symbol,
            "period": interval,
            "limit": limit
        }
        r = requests.get(url, params=params)
        candles = r.json()['data']
        candles.reverse()
        return [[float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in candles]

    def place_order(self, symbol, side, quantity):
        print(f"SIMULATED ORDER: {side} {quantity} {symbol} @ Bitget")
        # Šeit pievieno reālu POST order logiku, ja vajadzīgs

    def get_balance(self):
        print("SIMULATED BALANCE: 1000 USDT @ Bitget")
        # Reālam scenārijam: pievieno autentificētu balance pieprasījumu
