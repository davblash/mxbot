from mexc_cancel_order import mexc_crypto
import os
from dotenv import load_dotenv
import requests
import time
import hmac
import hashlib

"""
def generate_signature(params, timestamp, api_key, secret_key):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    string_to_sign = f"{api_key}{timestamp}{query_string}"
    signature = hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
    return signature
"""
def cancel_trigger_order(webkey, obj):
    url = "https://futures.mexc.com/api/v1/private/planorder/cancel"
    
    signature = mexc_crypto(webkey, obj)
    headers = {
        'Content-Type': 'application/json',
        'x-mxc-sign': signature['sign'],
        'x-mxc-nonce': signature['time'],
        #'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'User-Agent':  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'Authorization': webkey
    }
    
    """
    timestamp = int(time.time() * 1000)
    signature = generate_signature(obj, timestamp, api_key, api_secret)
    headers = {
        'Conten-Type': 'application/json',
        'ApiKey': api_key,
        'Request-Time': str(timestamp),
        'Signature': signature
    }
    """    
    response = requests.post(url, headers=headers, json=obj)

    return response.json()

load_dotenv()
key = os.getenv("WEBKEY")
oid = "668134391855336960"
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")
obj = [
    {
        "symbol": "LINK_USDT",
        "orderId": oid
    }
]
response = cancel_trigger_order(key, obj)
print("Cancel Order Response:" + str(response))