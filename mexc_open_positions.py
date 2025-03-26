import time
import hmac
import hashlib
import requests
import json

# Replace with your API Key and Secret Key
API_KEY = 'mx0vglgZKFlnQKdKfe'
SECRET_KEY = 'f392536bdf784b7c975259a09523bbd4'
BASE_URL = 'https://contract.mexc.com'

def generate_signature(params, timestamp, api_key, secret_key):
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params)])
    string_to_sign = f"{api_key}{timestamp}{query_string}"
    #signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    signature = hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
    return signature

# Example: Fetch account balances
def get_open_positions(symbol, api_key, api_secret):
    path = '/api/v1/private/position/open_positions'
    url = BASE_URL + path
    timestamp = int(time.time() * 1000)
    
    #params = {}
    params = {'symbol': symbol}
    #params['signature'] = generate_signature(params, timestamp, SECRET_KEY)
    signature = generate_signature(params, timestamp, api_key, api_secret)

    headers = {
        'Conten-Type': 'application/json',
        'ApiKey': api_key,
        'Request-Time': str(timestamp),
        'Signature': signature
    }

    response = requests.get(url, headers=headers, params=params)

    return response.json()

# Fetch and print account balances
#balances = get_account_balance()
#print(balances)

#result = requests.get(BASE_URL + '/api/v1/private/account/assets').json()
'''
result = get_open_positions()
print(result)
if result['success']:
    with open('open_positions.json', 'w') as f:
        json.dump(result, f, indent='\t')
'''