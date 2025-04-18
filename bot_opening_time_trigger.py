import json
import pandas as pd
import websocket
import requests
import time
import rel, threading
from collections import deque
from mexc_limit_order import place_trigger_order
from mexc_cancel_order import cancel_order
from mexc_query_order import query_order, query_trigger_order
from mexc_open_positions import get_open_positions
from mexc_request import place_order
from datetime import datetime, timedelta
import schedule
import logging
import asyncio
import os
from dotenv import load_dotenv

RESTAPI_URL = "https://contract.mexc.com/"
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
#KEY = 'WEB53877d828cd0cdf90dbe40bb5bf2159c3b9e2a3156cd25edf17f8586b05082c3'

class TradingBot():
    def __init__(self, symbol, warmup_interval, running_time, key, mhash, chash, mtoken, api_key, api_secret):
        self.symbol = symbol
        self.key = key
        self.mhash = mhash
        self.chash = chash
        self.mtoken = mtoken
        self.api_key = api_key
        self.api_secret = api_secret

        self.prices = deque()
        self.rolling_window = 300   # 5 minutes
        self.started = False
        self.warmup_interval = warmup_interval  # 5 minutes
        self.running_time = running_time * 60

        self.tick_size = self.get_ticker_size(symbol)
        self.ticks_when_order_placed = 2
        #self.ticks_when_order_filled = 5
        self.tp_ticks = 2
        self.sl_ticks = 1
        self.trigger_ticks = 4
        self.close_ticks = 2

        self.timeout_open_order = 30
        self.timeout_filled_order = 60
        #self.stop_loss = self.tick_size * 5
        self.volume = 1
        self.leverage = 10
        self.active_order = {"orderId": 0, "time": None, "deadline": None}
        #self.can_place_new_order = True
        self.pending_orders = {"buy": 0, "sell": 0}

        self.lookback_interval = 60
        self.lastPrice = 0
        self.max_price = 0
        # Set the minimum price to a very large number so that the first price update will be less than this value
        self.min_price = 1e9
        
        self.websocket_url = WEBSOCKET_URL
        self.ping_interval = 10
        #self.lock = asyncio.Lock()
        self.lock = threading.Lock()

        self.logger = logging.getLogger(__name__)
        tm = datetime.now()
        tm_str = tm.strftime("%Y-%m-%d-%H%M%S")
        logging.basicConfig(filename=f'log/log_{tm_str}.log', encoding='utf-8', level=logging.INFO)
        logging.info(f"Trading bot started at {tm_str}")

    def get_ticker_size(self, symbol):
        with open("mexc_contract_info.json", "r") as f:
            data = json.load(f)
        for item in data:
            if item["symbol"] == symbol:
                return item["priceUnit"]
    
    def place_and_track_order(self, direction):
        assert direction == "buy" or direction == "sell"
        # Get average price
        
        if direction == "buy":
            with self.lock:
                price = self.max_price + self.tick_size * self.ticks_when_order_placed
                sl_price = self.avg_price
            if price <= sl_price:
                return
            tp_price = price * 2 - sl_price
            #trigger_price = price + self.tick_size * self.trigger_ticks
            #close_price = price + self.tick_size * self.close_ticks
        else:
            with self.lock:
                price = self.min_price - self.tick_size * self.ticks_when_order_placed
                sl_price = self.avg_price
            if price >= sl_price:   
                return
            tp_price = price * 2 - sl_price
            #trigger_price = price - self.tick_size * self.trigger_ticks
            #close_price = price - self.tick_size * self.close_ticks
        
        response = place_trigger_order(self.symbol, 
                                       price, 
                                       self.volume, 
                                       self.leverage, 
                                       1 if direction == "buy" else 3, 
                                       sl_price, 
                                       tp_price, 
                                       self.key, 
                                       self.mhash, 
                                       self.chash, 
                                       self.mtoken)
        success = response["success"]
        if success:
            #positionId = 0
            #tm = datetime.fromtimestamp(response["data"]["t"] / 1000)
            tm = datetime.now()
            deadline = tm + timedelta(seconds=self.timeout_open_order)
            with self.lock:    
                oid = int(response["data"])
                """
                self.active_order = {
                                    #"orderId": int(response["data"]["orderId"]),
                                    "orderId": oid,
                                    #"positionId": 0,
                                    #"triggerPrice": trigger_price,
                                    #"closePrice": close_price,
                                    "direction": direction,
                                    "time": tm,
                                    "deadline": deadline}
                """
                self.pending_orders[direction] += 1
            self.logger.info(f"Placed {direction} order: ID {oid}, price {price}, tp {tp_price}, sl {sl_price} at {tm}")

            while datetime.now() < deadline:
                page_num = 1
                state = 0
                """
                while page_num <= 10:
                    response = query_trigger_order(self.api_key, self.api_secret, self.symbol, page_num, 100)
                    if response['success'] == False:
                        self.logger.error(f"Failed to query order: {response['message']}")
                        time.sleep(1)
                        continue
                    data = response['data']
                    for item in data:
                        if item['id'] == str(oid):
                            state = item['state']
                            break
                    page_num += 1
                    time.sleep(0.2)
                """
                response = query_trigger_order(self.api_key, self.api_secret, self.symbol, page_num, 100)
                if response['success'] :
                    data = response['data']
                    for item in data:
                        if item['id'] == str(oid):
                            state = item['state']
                            break
                else:
                    self.logger.error(f"Failed to query order: {response['message']}")
                
                if state == 0:
                    # Order not found
                    self.logger.warning(f"Order {oid} not found. Retrying...")
                    with self.lock:
                        self.pending_orders[direction] -= 1
                    return False
                elif state == 3:
                    # Order filled
                    self.logger.info(f"Order {oid} completed.")
                    with self.lock:
                        self.pending_orders[direction] -= 1
                    return True
                
                time.sleep(1)
            # Order not filled within the timeout
            self.logger.info(f"Order {oid} not filled within the timeout.")
            with self.lock:
                self.pending_orders[direction] -= 1
        
        return success

    def close_position(self, positionId, side, volume, price, type, key):
        assert type == "market" or type == "limit"
        type = 5 if type == "market" else 1
        obj = { 
            "symbol": self.symbol, 
            "side": side, 
            "openType": 1,  # Isolated margin
            "positionId": positionId,
            "type": type,    # Market order
            "vol": volume, 
            "price": price, 
            "priceProtect": "0",
        }

        response = place_order(key, obj, 'https://futures.mexc.com/api/v1/private/order/create')
        return response

    def drop_old_prices(self):
        # Drop old prices from the deque if it exceeds the lookback interval
        now = datetime.now().timestamp()
        while len(self.prices) > 0 and now - self.prices[0]["timestamp"] > self.rolling_window:
            self.prices.popleft()
    
    # WebSocket message handler
    def on_message(self, ws, message):
        data = json.loads(message)
        if 'channel' in data:
            if data['channel'] == "push.deal":
                if 'data' in data:
                    data = data['data']
                    price = data['p']

                    with self.lock:
                        self.lastPrice = price
                        #self.logger.info(f"{self.symbol}: lastPrice {price}, timestamp {datetime.fromtimestamp(data['t']/1000)}")
                        
                        """
                        if price > self.max_price:
                            self.max_price = price
                            self.logger.info(f"    Max price updated: {self.max_price}")
                            direction = "buy"
                        elif price < self.min_price:
                            self.min_price = price
                            self.logger.info(f"    Min price updated: {self.min_price}")
                            direction = "sell"
                        """
                        
                        self.prices.append({"price": price, "timestamp": data['t']/1000})
                        self.drop_old_prices()
                        price_values = [item["price"] for item in self.prices]
                        self.max_price = max(price_values)
                        self.min_price = min(price_values)
                        self.avg_price = sum(price_values) / len(price_values)

                        if not self.started:
                            self.started = True
                            self.start_time = datetime.now()
                            self.logger.info(f"Started at {self.start_time}")
                        
                        if datetime.now() - self.start_time < timedelta(seconds=self.warmup_interval):
                            return
                        if datetime.now() - self.start_time > timedelta(seconds=self.running_time):
                            self.logger.info(f"Running time exceeded. Stopping the bot.")
                            ws.close()
                            return

                        if self.pending_orders["buy"] == 0:
                            threading.Thread(target=self.place_and_track_order, 
                                            args=("buy",),
                                            daemon=True).start()
                        if self.pending_orders["sell"] == 0:
                            threading.Thread(target=self.place_and_track_order, 
                                            args=("sell",),
                                            daemon=True).start()


    # WebSocket error handler
    def on_error(self, ws, error):
        self.logger.error(error)

    # WebSocket close handler
    def on_close(self, ws, close_status_code, close_msg):
        self.logger.info("### websocket closed ###")
        self.logger.info(f"WebSocket closed with status code: {close_status_code}, message: {close_msg}")
        self.logger.info("WebSocket closed. Reconnecting in 5 seconds...")
        time.sleep(5)
        self.start_websocket()

    # WebSocket open handler
    def on_open(self, ws):
        self.logger.info("### websocket opened ###")
        params = {"method": "sub.deal",
                        "param": {
                                "symbol": self.symbol,
        }}  # Subscribe to ticker data for {self.symbol}

        # Send authentication request
        ws.send(json.dumps(params))

    def start_websocket(self):
        ws = websocket.WebSocketApp(WEBSOCKET_URL,
                              on_open=self.on_open,
                              on_message=self.on_message,
                              on_error=self.on_error,
                              on_close=self.on_close)

        ws.run_forever(dispatcher=rel, reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
        rel.signal(2, rel.abort)  # Keyboard Interrupt
        rel.dispatch()
        
        # Start the ping thread (20 seconds interval)
        ping_thread = threading.Thread(target=self.send_ping, args=(ws, self.ping_interval), daemon=True)
        ping_thread.start()

    def send_ping(self, ws, interval=10):
        """Continuously sends a ping message every 'interval' seconds"""
        while True:
            time.sleep(interval)
            try:
                ws.send(json.dumps({"method": "ping"}))
                self.logger.info("Ping sent")
            except Exception as e:
                self.logger.warning(f"Ping failed, WebSocket might be closed: {e}")
                break  # Exit thread if WebSocket is closed

    def run(self):
        """
        Main method to start the trading bot
        """
        try:
            self.start_websocket()
            

            # Keep the main thread running
            #while not self.order_placed:
            #    time.sleep(1)
        
        except KeyboardInterrupt:
            self.looger.info("Trading bot stopped by user")
        finally:
            if self.ws:
                self.ws.close()

def job():
    webkey = os.getenv('WEBKEY')
    if webkey is None:
        print("WEBKEY not found in .env file")
        return
    print(f"WEBKEY: {webkey}")
    
    api_key = os.getenv('API_KEY')
    
    api_secret = os.getenv('API_SECRET')
    if api_key is None or api_secret is None:
        print("API_KEY or API_SECRET not found in .env file")
        return
    print(f"API_KEY: {api_key}")

    symbol = os.getenv('SYMBOL')
    if symbol is None:
        print("SYMBOL not found in .env file")
        return
    print(f"SYMBOL: {symbol}")
    
    mhash = os.getenv('MHASH')
    if mhash is None:
        print("MHASH not found in .env file")
        return
    print(f"MHASH: {mhash}")

    chash = os.getenv('CHASH')
    if chash is None:
        print("CHASH not found in .env file")
        return
    print(f"CHASH: {chash}")

    mtoken = os.getenv('MTOKEN')
    if mtoken is None:
        print("MTOKEN not found in .env file")
        return
    print(f"MTOKEN: {mtoken}")

    mode = os.getenv('APPMODE')
    
    # Initialize the trading bot with the symbol and API keys
    warmup = 60 if mode == "development" else 300
    running_time = 5 if mode == "development" else 60 * 2
    bot = TradingBot(symbol, warmup, running_time, webkey, mhash, chash, mtoken, api_key, api_secret)
    #bot = TradingBot("XLM_USDT", KEY, 'mx0vgldfeNOhoYdin6', '6c6bef17d51341d98f6296f51eca3a98')
    print("### Starting bot ###")
    bot.run()

if __name__ == "__main__":
    load_dotenv()

    mode = os.getenv('APPMODE')
    if mode == "production":
        start_time = "09:25"
        schedule.every().monday.at(start_time, "US/Eastern").do(job)
        schedule.every().tuesday.at(start_time, "US/Eastern").do(job)
        schedule.every().wednesday.at(start_time, "US/Eastern").do(job)
        schedule.every().thursday.at(start_time, "US/Eastern").do(job)
        schedule.every().friday.at(start_time, "US/Eastern").do(job)
    elif mode == "development":
        # Run the bot immediately
        job()

    #bot.run()
    while True:
        schedule.run_pending()
        time.sleep(1)
