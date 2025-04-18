import os
from dotenv import load_dotenv
from mexc_limit_order import place_trigger_order, place_limit_order
from mexc_query_order import query_trigger_order
from mexc_request import mexc_crypto
import time

SYMBOL = "LINK_USDT"
load_dotenv()
WEBKEY = os.getenv("WEBKEY")
MHASH = os.getenv("MHASH")
CHASH = os.getenv("CHASH")
MTOKEN = os.getenv("MTOKEN")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

#triggerPrice = 0.61
#triggerPrice = 0.59
triggerPrice = 12.75
volume = 1
leverage = 1
side = 1

tp = 12.7
sl = 12.1
#sl = 0.4
#tp = 0.9
#tp = 0.5
#sl = 0.7


key = WEBKEY
# Place a trigger order
response = place_trigger_order(SYMBOL, triggerPrice, volume, leverage, side, sl, tp, key, MHASH, CHASH, MTOKEN)
print("Trigger Order Response:" + str(response))

if 'data' in response:
    oid = response['data']
    #oid = '667449597957915648'

    while True:
        response = query_trigger_order(API_KEY, API_SECRET, SYMBOL, 1, 10)
        #print("Query Order Response:" + str(response))
        data = response['data']
        for item in data:
            if item['id'] == str(oid):
                print(f"state: {item['state']}")
                break
        time.sleep(0.5)