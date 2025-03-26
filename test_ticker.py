import json
import pandas as pd
#import pandas_ta as ta
import websocket
import requests
import time
import rel, threading
from datetime import datetime
from mexc_request import place_order
#from mexc_open_positions import get_open_positions
REST_API_URL = 'https://contract.mexc.com'
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
PAIR = "ADA_USDT"
CONTRACT_SIZE = 0
QTY = 50
VOLUME = 0
KEY = 'WEB5658da2d99ac1be73faea816885e4f3967bcdf23eb11a3348b52e7bb0706c765'
INTERVAL = "Min1"


# WebSocket open handler
def on_open(ws):
    print("### opened ###")
    params = {"method": "sub.ticker",
              "param": {
                        "symbol": PAIR,
            }}  # Subscribe to ticker data for {PAIR}

    # Send authentication request
    ws.send(json.dumps(params))


# WebSocket message handler
def on_message(ws, message):
    data = json.loads(message)
    if 'channel' in data:
        if data['channel'] == "rs.sub.ticker":
            print(f"{data['data']}, timestamp {datetime.fromtimestamp(data['timestamp']/1000)}")
    if 'data' in data:
        data = data['data']
        print(f"{PAIR}: lastPrice {data['lastPrice']}, timestamp {datetime.fromtimestamp(data['timestamp']/1000)}")

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

# Main function to start the WebSocket connection
def main():
    global CONTRACT_SIZE
    #CONTRACT_SIZE = float(get_contract_size(PAIR))
    connect_websocket()

if __name__ == "__main__":
    main()