import json
import pandas as pd
import websocket
import requests
import time
import rel, threading
from mexc_limit_order import place_limit_order
from mexc_cancel_order import cancel_order
from mexc_query_order import query_order
from mexc_open_positions import get_open_positions
from mexc_request import place_order
from datetime import datetime, timedelta
import logging
import asyncio

RESTAPI_URL = "https://contract.mexc.com/"
WEBSOCKET_URL = "wss://contract.mexc.com/edge"
KEY = 'WEB53877d828cd0cdf90dbe40bb5bf2159c3b9e2a3156cd25edf17f8586b05082c3'

class TradingBot():
    def __init__(self, symbol, key, api_key, api_secret):
        self.symbol = symbol
        self.key = key
        self.api_key = api_key
        self.api_secret = api_secret

        self.tick_size = self.get_ticker_size(symbol)
        self.ticks_when_order_placed = 2
        self.ticks_when_order_filled = 5
        self.timeout_open_order = 10
        self.timeout_filled_order = 60
        self.stop_loss = self.tick_size * 5
        self.volume = 1
        self.leverage = 10
        self.active_order = {"orderId": 0, "time": None, "deadline": None}

        self.lookback_interval = 3
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

        self.get_past_max_min()

    def get_past_max_min(self):
        endpoint = f"api/v1/contract/kline/{self.symbol}"
        url = RESTAPI_URL + endpoint
        params = {
            "symbol": self.symbol,
            "interval": "Min1",
        }
        # Get timestamp of now
        now = datetime.now()
        end = int(now.timestamp())
        start = now - timedelta(seconds=self.lookback_interval)
        params["start"] = int(start.timestamp())
        params["end"] = end
        response = requests.get(url)
        response = response.json()
        if response["success"]:
            if response["code"] == 0:
                data = response["data"]
                self.min_price = min(data["low"][-self.lookback_interval:])
                self.max_price = max(data["high"][-self.lookback_interval:])
                self.logger.info(f"Min price: {self.min_price}, Max price: {self.max_price}")
                return True
        logging.warning(f"Coundn't get past prices!")
        return False

    def get_ticker_size(self, symbol):
        with open("mexc_contract_info.json", "r") as f:
            data = json.load(f)
        for item in data:
            if item["symbol"] == symbol:
                return item["priceUnit"]
    
    def place_and_track_order(self, direction):
        with self.lock:
            if self.active_order["orderId"] != 0:
                self.logger.info(f"  Order already placed: {self.active_order['orderId']}")
                return False
            
        assert direction == "buy" or direction == "sell"
        if direction == "buy":
            price = self.max_price + self.tick_size * self.ticks_when_order_placed
            sl_price = price - self.stop_loss
            tp_price = price + 2 * self.stop_loss
        else:
            price = self.min_price - self.tick_size * self.ticks_when_order_placed
            sl_price = price + self.stop_loss
            tp_price = price - 2 * self.stop_loss
        
        response = place_limit_order(self.symbol, 
                                     price, 
                                     self.volume, 
                                     self.leverage,
                                     1 if direction == "buy" else 3, 
                                     sl_price,
                                     tp_price,
                                     self.key)
        
        success = response["success"]
        if success:
            positionId = 0
            with self.lock:
                tm = datetime.fromtimestamp(response["data"]["ts"] / 1000)
                deadline = tm + timedelta(seconds=self.timeout_open_order)
                self.active_order = {"orderId": int(response["data"]["orderId"]),
                                    "time": tm,
                                    "deadline": deadline}
                self.logger.info(f"Placed {direction} order with ID {self.active_order["orderId"]} at {self.active_order["time"]}")
            
            order_filled = False
            while datetime.now() < deadline:
                if self.active_order["orderId"] == 0:
                    break
                response = query_order(self.api_key, self.api_secret, self.active_order["orderId"])
                success = response["success"]
                code = response["code"]
                if success:
                    if code == 0:
                        positionId = response["data"]["positionId"]
                        if positionId != 0:
                            self.logger.info(f"  Order filled successfully. Position ID: {positionId}")
                            order_filled = True
                            break
                    else:
                        self.logger.warning(f"  Error while querying order {self.active_order["orderId"]}. Code : {code}")
                else:
                    self.logger.warning("  Failed to query order.")
                time.sleep(0.3)
            if not order_filled:
                # Check again if the order is filled
                response = query_order(self.api_key, self.api_secret, self.active_order["orderId"])
                success = response["success"]
                code = response["code"]
                if success:
                    if code == 0:
                        positionId = response["data"]["positionId"]
                        if positionId != 0:
                            self.logger.info(f"  Order filled successfully. Position ID: {positionId}")
                            order_filled = True

            if not order_filled:
                self.logger.info("  Order not filled within the timeout period.")
                
                response = cancel_order(self.key, [self.active_order["orderId"]])
                
                success = response["success"]
                if success:
                    data = response["data"]
                    found = False
                    for item in data:
                        if item["orderId"] == self.active_order["orderId"]:
                            errorCode = item["errorCode"]
                            found = True
                            break
                    if not found:
                        self.logger.warning(f"  Order {self.active_order["orderId"]} NOT FOUND!")
                    else:
                        if errorCode == 0:
                            self.logger.info(f"  Order {self.active_order["orderId"]} cancelled successfully.")
                            with self.lock:
                                self.active_order = {"orderId": 0, "time": None, "deadline": None}
                            return True
                        else:
                            response = query_order(self.api_key, self.api_secret, self.active_order["orderId"])
                            success = response["success"]
                            code = response["code"]
                            if success:
                                if code == 0:
                                    positionId = response["data"]["positionId"]
                                    if positionId != 0:
                                        self.logger.info(f"  Order filled successfully. Position ID: {positionId}")
                                        order_filled = True
                                else:
                                    self.logger.warning(f"  Error while querying order {self.active_order["orderId"]}. Code : {code}")
                            else:
                                self.logger.warning("  Failed to query order.")
            
            if order_filled:
                tm = datetime.now()
                deadline = tm + timedelta(seconds=self.timeout_filled_order)
                while datetime.now() < deadline:
                    response = get_open_positions(self.symbol, self.api_key, self.api_secret)
                    success = response["success"]
                    if success:
                        if response["code"] == 0:
                            data = response["data"]
                            found = False
                            assert positionId != 0
                            for item in data:
                                if item["positionId"] == positionId:
                                    status = item["state"]
                                    realized = item["realised"]
                                    openAvgPrice = item["openAvgPrice"]
                                    closeAvgPrice = item["closeAvgPrice"]
                                    found = True
                                    break
                            if not found:
                                self.logger.info(f"  Position {positionId} closed")
                                with self.lock:
                                    self.active_order = {"orderId": 0, "time": None, "deadline": None}
                                return True
                            else:
                                if status == 3:
                                    self.logger.info(f"  Position {positionId} closed successfully."
                                                     f" openAvgPrice: {openAvgPrice}, "
                                                     f" closeAvgPrice: {closeAvgPrice}, Realized profit: {realized}")
                                    with self.lock:
                                        self.active_order = {"orderId": 0, "time": None, "deadline": None}
                                    return True
                        else:
                            self.logger.warning(f"  Failed to query open positions. {response["code"]}: {response["message"]}")
                    else:
                        self.logger.warning(f"  Failed to query open positions. {response["code"]}: {response["message"]}")
                    time.sleep(0.3)
                
                self.logger.info("  Position not closed within the timeout period. Closing it.")
                
                response = self.close_position(positionId, 4 if direction == "buy" else 2, self.volume, self.lastPrice, self.key)
                
                if response["success"]:
                    if response["code"] == 0:
                        self.logger.info(f"  Position {positionId} closed with response: {response}")
                    else:
                        self.logger.warning(f"  Error while closing position {positionId}. Code: {response["code"]}")
                else:
                    self.logger.warning(f"  Failed to close position {positionId}")

                with self.lock:
                    self.active_order = {"orderId": 0, "time": None, "deadline": None}
                return True

            else:
                self.logger.error(f"Failed to cancel order {self.active_order["orderId"]}. Abandon it.")
                with self.lock:
                    self.active_order = {"orderId": 0, "time": None, "deadline": None}
                return True
        else:
            self.logger.warning(f"Failed to place {direction} order.")
        
        return success

    def close_position(self, positionId, side, volume, price, key):
        obj = { 
            "symbol": self.symbol, 
            "side": side, 
            "openType": 1,  # Isolated margin
            "positionId": positionId,
            "type": 5,    # Market order
            "vol": volume, 
            #"leverage": 1, 
            "price": price, 
            "priceProtect": "0",
        }

        response = place_order(key, obj, 'https://futures.mexc.com/api/v1/private/order/create')
        return response

    # WebSocket message handler
    def on_message(self, ws, message):
        data = json.loads(message)
        if 'channel' in data:
            if data['channel'] == "rs.sub.ticker":
                self.logger.info(f"{data['data']}, timestamp {datetime.fromtimestamp(data['ts']/1000)}")
            elif data['channel'] == "push.ticker":
                if 'data' in data:
                    data = data['data']
                    price = data['lastPrice']
                    self.lastPrice = price
                    self.logger.info(f"{self.symbol}: lastPrice {price}, timestamp {datetime.fromtimestamp(data['timestamp']/1000)}")
                    direction = ""
                    if price > self.max_price:
                        self.max_price = price
                        self.logger.info(f"    Max price updated: {self.max_price}")
                        direction = "buy"
                    elif price < self.min_price:
                        self.min_price = price
                        self.logger.info(f"    Min price updated: {self.min_price}")
                        direction = "sell"
                    if direction != "":
                        threading.Thread(target=self.place_and_track_order, args=(direction,), daemon=True).start()



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
        params = {"method": "sub.ticker",
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
                self.logger.error("Ping failed, WebSocket might be closed:", e)
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

if __name__ == "__main__":
    bot = TradingBot("ADA_USDT", KEY, 'mx0vgldfeNOhoYdin6', '6c6bef17d51341d98f6296f51eca3a98')
    bot.run()
