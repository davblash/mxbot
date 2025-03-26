import hashlib
import json
import time
from curl_cffi import requests

def md5(value):
    return hashlib.md5(value.encode('utf-8')).hexdigest()

def mexc_crypto(key, obj):
    date_now = str(int(time.time() * 1000))  
    g = md5(key + date_now)[7:] 
    s = json.dumps(obj, separators=(',', ':'))  
    sign = md5(date_now + s + g)  
    return {'time': date_now, 'sign': sign}

def cancel_order(key, obj):
    url = 'https://futures.mexc.com/api/v1/private/order/cancel'  
    signature = mexc_crypto(key, obj)
    headers = {
        'Content-Type': 'application/json',
        'x-mxc-sign': signature['sign'],
        'x-mxc-nonce': signature['time'],
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Authorization': key
    }
    response = requests.post(url, headers=headers, json=obj)
    return response.json()

def main():
    key = 'WEB53877d828cd0cdf90dbe40bb5bf2159c3b9e2a3156cd25edf17f8586b05082c3'
    obj = [659077250775436288]
    response = cancel_order(key, obj)
    print(response)

if __name__ == "__main__":
    main()