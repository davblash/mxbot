import asyncio
import websockets
import logging
import json
from mexc_limit_order import place_limit_order
from mexc_cancel_order import cancel_order
from mexc_query_order import query_order
from datetime import datetime, timedelta

WEBSOCKET_URL = "wss://contract.mexc.com/edge"
KEY = 'WEB53877d828cd0cdf90dbe40bb5bf2159c3b9e2a3156cd25edf17f8586b05082c3'

class TradingBot():
    def __init__(self, symbol, key, api_key, api_secret):
        self.symbol = symbol
        self.key = key
        self.api_key = api_key
        self.api_secret = api_secret

        self.tick_size = self.get_ticker_size(symbol)
        self.ticks_when_order_placed = -10
        self.ticks_when_order_filled = 5
        self.timeout_open_order = 10
        self.timeout_filled_order = 60
        self.stop_loss = 1e-3
        self.active_order = {"orderId": 0, "time": None, "deadline": None}
        
        self.max_price = 0
        # Set the minimum price to a very large number so that the first price update will be less than this value
        self.min_price = 1e9

        self.websocket = None
        self.ping_interval = 5
        self.lock = asyncio.Lock()

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
    
    async def start(self):
        task_price = asyncio.create_task(self.get_real_time_price(WEBSOCKET_URL))
        task_order = asyncio.create_task(self.track_order())
        task_ping = asyncio.create_task(self.ping())

        await asyncio.gather(task_price, task_order)
        #await self.get_real_time_price(WEBSOCKET_URL)

    async def get_real_time_price(self, url):
        async with websockets.connect(url) as websocket:
            self.websocket = websocket

            # Subscribe to the ticker channel for a specific symbol (e.g., BTC_USDT)
            subscribe_message = {"method": "sub.ticker",
                "param": {
                            "symbol": self.symbol,
            }}  
            await websocket.send(json.dumps(subscribe_message))
            self.logger.info(f"Subscribed to {subscribe_message['method']} price updates.")

            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if "symbol" in data:
                        price = data["data"]["lastPrice"]
                        self.logger.info(f"Real-time price update: {price}")
                        if price > self.max_price:
                            self.max_price = price
                            self.logger.info(f"    Max price updated: {self.max_price}")
                            direction = "buy"
                            #success = await self.place_order("buy")
                        elif price < self.min_price:
                            self.min_price = price
                            self.logger.info(f"    Min price updated: {self.min_price}")
                            direction = "sell"
                            #success = await self.place_order("sell")
                        async with self.lock:
                            if self.active_order["orderId"] == 0:
                                success = await self.place_order(direction)

                except Exception as e:
                    self.logger.error("Error:", e)
                    break

    async def track_order(self):
        while True:
            async with self.lock:
                if self.active_order["orderId"] != 0:
                    try:
                        response = query_order(self.api_key, self.api_secret, self.active_order["orderId"])
                        success = response["success"]
                        if success:
                            positionId = response["data"]["positionId"]
                            if positionId > 0:
                                self.logger.info("  Order filled successfully. Position ID: {positionId}")
                            #self.logger.info(f"Order placed successfully. orderId = {self.active_order}")
                            #tm_start = datetime.now()
                            #tm_end = tm_start + timedelta(seconds=5)
                            #while datetime.now() < tm_end:
                            #    await asyncio.sleep(1)
                            else:
                                if datetime.now() > self.active_order["deadline"]:
                                    self.logger.info("  Order timed out.")
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
                                                self.active_order["orderId"] = 0
                                            else:
                                                response = query_order(self.api_key, self.api_secret, self.active_order)
                                                success = response["success"]
                                                if success:
                                                    positionId = response["data"]["positionId"]
                                                    self.logger.info("  Position ID: {positionId}")
                                                    self.logger.info("  Order filled successfully.")
                                                else:
                                                    self.logger.warning("  Failed to query order.")
                                    else:
                                        self.logger.warning("Failed to cancel order.")
                        else:
                            self.logger.warning("Failed to place order.")
                    
                    except Exception as e:
                        self.logger.error("Error:", e)
                        break
            await asyncio.sleep(0.5)

    async def place_order(self, direction):
        assert direction == "buy" or direction == "sell"
        if direction == "buy":
            price = self.max_price + self.tick_size * self.ticks_when_order_placed
        else:
            price = self.min_price - self.tick_size * self.ticks_when_order_placed
        response = place_limit_order(self.symbol, price, 1, 1 if direction == "buy" else 3, self.key)
        success = response["success"]
        if success:
            tm = datetime.fromtimestamp(response["data"]["ts"] / 1000)
            deadline = tm + timedelta(seconds=self.timeout_open_order)
            self.active_order = {"orderId": int(response["data"]["orderId"]),
                                 "time": tm,
                                 "deadline": deadline}
            self.logger.info(f"Placed {direction} order with ID {self.active_order["orderId"]} at {self.active_order["time"]}")
        else:
            self.logger.warning(f"Failed to place {direction} order.")
        
        return success

    async def ping(self):
        """Periodically send ping messages to keep the connection alive"""
        try:
            while True:
                if self.websocket:
                    try:
                        await self.websocket.ping()
                        self.logger.info("Ping sent to server")
                    except Exception as e:
                        self.logger.warning(f"Ping failed: {e}")
                await asyncio.sleep(self.ping_interval)
        except asyncio.CancelledError:
            self.logger.error("Ping task cancelled")

# Run the event loop
if __name__ == "__main__":
    bot = TradingBot("ADA_USDT", KEY, 'mx0vgldfeNOhoYdin6', '6c6bef17d51341d98f6296f51eca3a98')
    asyncio.run(bot.start())
    
