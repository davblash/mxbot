import requests
import time
import hmac
import hashlib
from mexc_request import mexc_crypto

# Replace with your MEXC API key and secret
API_KEY = 'mx0vgldfeNOhoYdin6'
API_SECRET = '6c6bef17d51341d98f6296f51eca3a98'


def generate_signature(params, timestamp, secret_key):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    string_to_sign = f"{API_KEY}{timestamp}{query_string}"
    signature = hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
    return signature

def query_order(api_key, api_secret, order_id):
    REST_API_URL = 'https://contract.mexc.com/'
    ENDPOINT = 'api/v1/private/order/get/'

    timestamp = int(time.time() * 1000)
    obj = {}
    signature = generate_signature(obj, timestamp, api_secret)

    headers = {
        'Conten-Type': 'application/json',
        'ApiKey': api_key,
        'Request-Time': str(timestamp),
        'Signature': signature
    }

    response = requests.get(REST_API_URL + ENDPOINT + str(order_id), headers=headers, params=obj)

    return response.json()

def query_trigger_order(api_key, api_secret, symbol, page_num, page_size):
    REST_API_URL = 'https://contract.mexc.com/'
    ENDPOINT = 'api/v1/private/planorder/list/orders'

    timestamp = int(time.time() * 1000)
    obj = {
        "symbol": symbol,
        "page_num": page_num,
        "page_size": page_size
    }
    signature = generate_signature(obj, timestamp, api_secret)

    headers = {
        'Conten-Type': 'application/json',
        'ApiKey': api_key,
        'Request-Time': str(timestamp),
        'Signature': signature
    }

    response = requests.get(REST_API_URL + ENDPOINT, headers=headers, params=obj)

    return response.json()

# Example usage
if __name__ == '__main__':
    oid = 659077250775436288
    result = query_order(API_KEY, API_SECRET, oid)
    print(result)