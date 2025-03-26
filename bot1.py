import asyncio
import websocket
import json
import schedule
import time
from datetime import datetime, timedelta
import pytz
import rel, threading

# Constants
MARKET_OPEN_TIME = "09:30"
MARKET_CLOSE_TIME = "11:00"
TICK_SIZE = 0.01  # Replace with the actual tick size of the asset
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
PAIR = "ADA-USDT"

# Global variables
highest_price = float('-inf')
lowest_price = float('inf')

est = pytz.timezone("US/Eastern")

async def fetch_price_data():
    global highest_price, lowest_price

    uri = "wss://contract.mexc.com/ws"  # Replace with the correct MEXC WebSocket endpoint
    async with websocket.connect(uri) as websocket:
        # Subscribe to ticker data
        subscribe_message = {
            "method": "sub.ticker",
            "param": {"symbol": "BTC_USDT"},  # Replace with your desired trading pair
            "id": 1
        }
        await websocket.send(json.dumps(subscribe_message))

        while True:
            response = await websocket.recv()
            data = json.loads(response)

            if "data" in data and "lastPrice" in data["data"]:
                last_price = float(data["data"]["lastPrice"])
                print(f"Received price: {last_price}")

                # Update highest and lowest prices
                if last_price > highest_price:
                    highest_price = last_price
                    print(f"New highest price: {highest_price}")
                    await handle_new_high(last_price)

                if last_price < lowest_price:
                    lowest_price = last_price
                    print(f"New lowest price: {lowest_price}")
                    await handle_new_low(last_price)

async def handle_new_high(price):
    buy_price = price + 2 * TICK_SIZE
    print(f"Placing limit buy order at {buy_price}")
    # Place limit buy order (implement API call here)

    await asyncio.sleep(20)  # Wait for 20 seconds

    sell_price = buy_price + 10 * TICK_SIZE
    print(f"Placing limit sell order at {sell_price}")
    # Place limit sell order (implement API call here)

async def handle_new_low(price):
    sell_price = price - 2 * TICK_SIZE
    print(f"Placing limit sell order at {sell_price}")
    # Place limit sell order (implement API call here)

    await asyncio.sleep(20)  # Wait for 20 seconds

    buy_price = sell_price - 10 * TICK_SIZE
    print(f"Placing limit buy order at {buy_price}")
    # Place limit buy order (implement API call here)

def start_bot():
    print("Starting bot...")
    connect_websocket()
    asyncio.run(fetch_price_data())

def schedule_bot():
    # Schedule the bot to start 15 minutes before market open and stop at market close
    today = datetime.now(tz=pytz.utc)
    market_open = est.localize(datetime(today.year, today.month, today.day, hour=13, minute=17)).astimezone(pytz.timezone("Asia/Tokyo"))
    #start_time = (market_open - timedelta(minutes=15)).time()
    start_time = market_open
    close_time = est.localize(datetime(today.year, today.month, today.day, hour=12, minute=20)).astimezone(pytz.utc)

    schedule.every().day.at(start_time.strftime("%H:%M")).do(start_bot)
    schedule.every().day.at(close_time.strftime("%H:%M")).do(stop_bot)

    while True:
        schedule.run_pending()
        time.sleep(1)

def on_open(ws):
    print("### opened ###")
    params = {"method": "sub.ticker",
              "param": {
                        "symbol": PAIR,
            }}  # Subscribe to ticker data for {PAIR}

    # Send authentication request
    ws.send(json.dumps(params))

def on_message(ws, message):
    data = json.loads(message)
    """
    if 'channel' in data:
        if data['channel'] == "rs.sub.ticker":
            print(f"{data['data']}, timestamp {datetime.fromtimestamp(data['timestamp']/1000)}")
    if 'data' in data:
        data = data['data']
        print(f"{PAIR}: lastPrice {data['lastPrice']}, timestamp {datetime.fromtimestamp(data['timestamp']/1000)}")
    """
    
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

def stop_bot():
    print("Stopping bot...")
    # Implement any cleanup logic if necessary
    exit()

if __name__ == "__main__":
    #connect_websocket()
    schedule_bot()