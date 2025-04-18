import requests
import time
import hmac
import hashlib
from mexc_request import place_order

# Replace with your MEXC API key and secret
API_KEY = 'mx0vgldfeNOhoYdin6'
API_SECRET = '6c6bef17d51341d98f6296f51eca3a98'
# MEXC API endpoints
REST_API_URL = 'https://contract.mexc.com'
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
#PAIR = "ADA_USDT"
#CONTRACT_SIZE = 1
#QTY = 1
VOLUME = 1
REST_API_URL = 'https://contract.mexc.com'
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
#PAIR = "ZEC_USDT"
KEY = 'WEB53877d828cd0cdf90dbe40bb5bf2159c3b9e2a3156cd25edf17f8586b05082c3'

BASE_URL = 'https://api.mexc.com'

"""
def create_signature(params, secret):
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    return hmac.new(secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
"""

def place_limit_order(symbol, price, volume, leverage, side, sl, tp, key):
    obj = { 
        "symbol": symbol, 
        "side": side, 
        "openType": 1,  # Isolated margin
        "type": 1,    # Limit order
        "vol": volume, 
        "leverage": leverage, 
        "price": price, 
        "priceProtect": "0",
        "stopLossPrice": sl,
        "takeProfitPrice": tp
    }

    response = place_order(key, obj, 'https://futures.mexc.com/api/v1/private/order/create')

#    print(f"Placing {side} order")
    return response

def place_trigger_order(symbol, triggerPrice, volume, leverage, side, sl, tp, key, mhash, chash, mtoken):
    obj = { 
        "chash": chash,
        "executeCycle": 3,
        "mhash": mhash,
        "mtoken": mtoken,
        "symbol": symbol, 
        "side": side, 
        "openType": 1,  # Isolated margin
        #"type": 1,    # Market order
        "orderType": 5,  # Trigger order
        "positionMode": 1,
        "vol": volume, 
        "leverage": leverage, 
        #"price": price, 
        "triggerPrice": triggerPrice,
        "triggerType": 1 if side == 1 else 2,  # Trigger order
        "priceProtect": "0",
        "stopLossPrice": sl,
        "takeProfitPrice": tp,
          #"lossTrend": '1',
          #"profitTrend": '1',
          "trend": '1',
    }

    response = place_order(key, obj, f'https://futures.mexc.com/api/v1/private/planorder/place/v2?mhash={mhash}')

#    print(f"Placing {side} order")
    return response

# Example usage
if __name__ == '__main__':
    symbol = 'ADA_USDT'
    price = 0.25  # Replace with your desired price
    volume = 1  # Replace with your desired quantity
    side = 1  # Use 'BUY' or 'SELL'

    result = place_limit_order(symbol, price, volume, side, KEY)
    print(result)