import json
import pandas as pd
import pandas_ta as ta
import websocket
import requests
import time
import rel, threading
from mexc_request import place_order
from mexc_open_positions import get_open_positions

# MEXC API endpoints
REST_API_URL = 'https://contract.mexc.com'
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
PAIR = "ZEC_USDT"
CONTRACT_SIZE = 0
QTY = 50
VOLUME = 0
KEY = 'WEB53aab8aa50979de7c271c28058364172f9be436db71c5f428acea9116a101d51'
POSITION_STATUS = "hold"
# POSITION_ID = 0
HISTORY = 26
INTERVAL = "Min1"
INTERVAL_SEC = 60
LAST_TIMESTAMP = 0

# Initialize an empty DataFrame to store OHLCV data
ohlcv_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# Function to fetch historical data using REST API
def fetch_historical_data(symbol, interval, start_time, end_time):
    #url = f"{REST_API_URL}/api/v3/klines"
    url = f"{REST_API_URL}/api/v1/contract/kline/{PAIR}"
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time
    }
    response = requests.get(url, params=params)
    data = response.json()
    data = data['data']
    # Create a DataFrame out of data
    data = pd.DataFrame(data)
    data = data[['time', 'open', 'high', 'low', 'close', 'vol']]
    # Rename timestamp as time
    data.rename(columns={'time': 'timestamp', 'vol': 'volume'}, inplace=True)
    return data
    #data = {k: data[k] for k in ['time', 'open', 'high', 'low', 'close', 'volume']}
    #return pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

def check_gap(df):
    global INTERVAL_SEC
    last_time = df.index[-1]
    found_gap = False
    for i in range(1, HISTORY + 1):
        check_time = last_time - i * INTERVAL_SEC
        if check_time not in df.index:
            found_gap = True
            break
    if found_gap:
        print(f"Data gap detected at {check_time}. Fetching historical data...")
        start_time = check_time
        end_time = check_time + INTERVAL_SEC
        historical_data = fetch_historical_data(PAIR, INTERVAL, start_time, end_time)
        if len(historical_data) > 0:
            historical_data.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
            historical_data.set_index('timestamp', inplace=True)
            df = pd.concat([df, historical_data])
            df.sort_index(inplace=True)
            #df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
            df = df.loc[~df.index.duplicated(keep='last')]
            #df.reset_index(inplace=True)
            return df
    else:
        return df

# WebSocket message handler
def on_message(ws, message):
    global ohlcv_df, LAST_TIMESTAMP
    data = json.loads(message)
    if 'data' in data and 'symbol' in data:
        kline = data['data']
        new_row = {
            'timestamp': kline['t'],
            'open': float(kline['o']),
            'high': float(kline['h']),
            'low': float(kline['l']),
            'close': float(kline['c']),
            'volume': float(kline['q'])
        }
        
        ts_updated = kline['t'] > LAST_TIMESTAMP
        LAST_TIMESTAMP = kline['t']

        #ohlcv_df = ohlcv_df.append(new_row, ignore_index=True)
        if len(ohlcv_df) == 0:
            ohlcv_df.loc[len(ohlcv_df)] = new_row
            ohlcv_df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
            ohlcv_df.set_index('timestamp', inplace=True)
        else:
            ohlcv_df.loc[new_row['timestamp']] = {'open': new_row['open'], 
                                              'high': new_row['high'], 
                                              'low': new_row['low'], 
                                              'close': new_row['close'], 
                                              'volume': new_row['volume']}
        ohlcv_df = check_gap(ohlcv_df)
        #ohlcv_df.sort_index(inplace=True)
        #ohlcv_df.reset_index(inplace=True)
        #ohlcv_df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        #print(ohlcv_df.tail())

        # Calculate indicators
        ohlcv_df['MACD'] = ta.macd(ohlcv_df['close'])['MACD_12_26_9']
        ohlcv_df['RSI'] = ta.rsi(ohlcv_df['close'])
        ohlcv_df['Stoch'] = ta.stoch(ohlcv_df['high'], ohlcv_df['low'], ohlcv_df['close'])['STOCHk_14_3_3']
        ohlcv_df['MA'] = ta.sma(ohlcv_df['close'], length=50)

        print(ohlcv_df.tail())

        response = None
        if ts_updated:
            # Trading logic
            '''
            if ohlcv_df['MACD'].iloc[-1] > 0 and ohlcv_df['RSI'].iloc[-1] < 30:
                response = submit_order('buy')
            elif ohlcv_df['MACD'].iloc[-1] < 0 and ohlcv_df['RSI'].iloc[-1] > 70:
                response = submit_order('sell')
            '''
            if ohlcv_df['close'].iloc[-2] > ohlcv_df['MA'].iloc[-2]:
                response = submit_order('buy')
            elif ohlcv_df['close'].iloc[-2] < ohlcv_df['MA'].iloc[-2]:
                response = submit_order('sell')
        
        if response is not None:
            if response['success']:
                orderID = response['data']['orderId']
                print("Order placed successfully. Order ID:", orderID)
            else:
                print("Error: Failed to place order\n", response)

def submit_order(side):
    global POSITION_STATUS, POSITION_ID
    response = get_open_positions(PAIR)
    if response['success']:
        if len(response['data']) == 0:
            POSITION_STATUS = "hold"
            POSITION_ID = 0
        
            _side = 1 if side == 'buy' else 3
            if _side == 1:
                TP = ohlcv_df.iloc[-1]['close'] * 1.014
                SL = ohlcv_df.iloc[-1]['close'] * 0.98
            else:
                TP = ohlcv_df.iloc[-1]['close'] * 0.986
                SL = ohlcv_df.iloc[-1]['close'] * 1.02

            response = open_position(_side, QTY, 1, TP, SL)
            if response['success']:
                POSITION_STATUS = side
                # POSITION_ID = response['data']['orderId']
            return response
        else:
            POSITION_STATUS = "long" if response['data'][0]['positionType'] == 1 else "short"
            if POSITION_STATUS == "long" and side == "sell" or POSITION_STATUS == "short" and side == "buy":    
                POSITION_ID = response['data']['positionId']
                VOLUME = response['data']['holdVol']

                response = close_position(POSITION_STATUS, POSITION_ID)
                if response['success']:
                    POSITION_STATUS = "hold"
                    # POSITION_ID = 0
                else:
                    print("Error: Failed to close position")
                return response
    else:
        print("Error: Failed to get open positions")
        return response
    

def close_position(positionStatus, posID):
    side = 4 if positionStatus == 'long' else 2
    
    obj = {
        "symbol": PAIR,
        "type": "5",
        "positionId": posID,
        "side": side,
        "vol": VOLUME
    }
    return place_order(KEY, obj, 'https://futures.mexc.com/api/v1/private/order/create')
        
# Function to place an order
def open_position(side, quantity, leverage, TP, SL):
    global CONTRACT_SIZE

    #_side = 1 if side == 'buy' else 3
    if side == 1 or side == 3:
        price = ohlcv_df.iloc[-1]['close']
    else:
        price = 0
    VOL = int(quantity / price / CONTRACT_SIZE)
    if VOL == 0:
        VOL = 1

    obj = { 
        "symbol": PAIR, 
        "side": side, 
        "openType": 1,  # Isolated margin
        "type": "5",    # Market order
        "vol": VOL, 
        "leverage": leverage, 
        "price": price, 
        "priceProtect": "0",
    }
    if TP is not None:
        obj['takeProfitPrice'] = TP
    if SL is not None:
        obj['stopLossPrice'] = SL

    response = place_order(KEY, obj, 'https://futures.mexc.com/api/v1/private/order/create')
    print(f"Placing {side} order")
    return response
    # Implement order placement logic here

# WebSocket error handler
def on_error(ws, error):
    print(error)

# WebSocket close handler
def on_close(ws, close_status_code, close_msg):
    print("### closed ###")
    print(f"WebSocket closed with status code: {close_status_code}, message: {close_msg}")
    print("WebSocket closed. Reconnecting in 5 seconds...")
    time.sleep(5)
    connect_websocket()

# WebSocket open handler
def on_open(ws):
    print("### opened ###")
    params = {"method": "sub.kline",
              "param": {
                        "symbol": PAIR,
                        "interval": INTERVAL
            }}  # Subscribe to 5 min kline data for {PAIR}

    # Send authentication request
    ws.send(json.dumps(params))


def send_ping(ws, interval=10):
    """Continuously sends a ping message every 'interval' seconds"""
    while True:
        time.sleep(interval)
        try:
            ws.send(json.dumps({"method": "ping"}))
            print("Ping sent")
        except Exception as e:
            print("Ping failed, WebSocket might be closed:", e)
            break  # Exit thread if WebSocket is closed

def connect_websocket():
    ws = websocket.WebSocketApp(WEBSOCKET_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=rel, reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
    
    # Start the ping thread (20 seconds interval)
    ping_thread = threading.Thread(target=send_ping, args=(ws, 10), daemon=True)
    ping_thread.start()

def get_contract_size(PAIR):
    with open('mexc_futures_detail.json', 'rt') as f:
        data = json.load(f)
    for contract in data['data']:
        if contract['symbol'] == PAIR:
            return contract['contractSize']
    raise Exception(f"Contract size not found for {PAIR}")
    
# Main function to start the WebSocket connection
def main():
    global CONTRACT_SIZE
    CONTRACT_SIZE = float(get_contract_size(PAIR))
    connect_websocket()

if __name__ == "__main__":
    main()