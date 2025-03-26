import asyncio
import websockets
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
        self.active_order = 0
        
        self.max_price = 0
        # Set the minimum price to a very large number so that the first price update will be less than this value
        self.min_price = 1e9

    def get_ticker_size(self, symbol):
        with open("mexc_contract_info.json", "r") as f:
            data = json.load(f)
        for item in data:
            if item["symbol"] == symbol:
                return item["priceUnit"]
    
    async def start(self):
        await self.get_real_time_price(WEBSOCKET_URL)

    async def get_real_time_price(self, url):
        async with websockets.connect(url) as websocket:
            # Subscribe to the ticker channel for a specific symbol (e.g., BTC_USDT)
            subscribe_message = {"method": "sub.ticker",
                "param": {
                            "symbol": self.symbol,
            }}  
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to {subscribe_message['method']} price updates.")

            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if "symbol" in data:
                        price = data["data"]["lastPrice"]
                        print("Real-time price update:", price)
                        if price > self.max_price:
                            self.max_price = price
                            print("    Max price updated:", self.max_price)
                            success = await self.place_order("buy")
                        elif price < self.min_price:
                            self.min_price = price
                            print("    Min price updated:", self.min_price)
                            success = await self.place_order("sell")
                        
                        if success:
                            print(f"Order placed successfully. orderId = {self.active_order}")
                            tm_start = datetime.now()
                            tm_end = tm_start + timedelta(seconds=5)
                            while datetime.now() < tm_end:
                                await asyncio.sleep(1)
                            response = cancel_order(self.key, [self.active_order])
                            success = response["success"]
                            if success:
                                errorCode = response["data"]["errorCode"]
                                if errorCode == 0:
                                    print(f"  Order {self.active_order}cancelled successfully.")
                                    self.active_order = 0
                                else:
                                    response = query_order(self.api_key, self.api_secret, self.active_order)
                                    success = response["success"]
                                    if success:
                                        positionId = response["data"]["positionId"]
                                        print("  Position ID:", positionId)
                                        print("  Order filled successfully.")
                                    else:
                                        print("  Failed to query order.")
                            else:
                                print("Failed to cancel order.")
                            #print(response)

                        else:
                            print("Failed to place order.")

                    
                except Exception as e:
                    print("Error:", e)
                    break
    async def place_order(self, direction):
        assert direction == "buy" or direction == "sell"
        if direction == "buy":
            price = self.max_price + self.tick_size * self.ticks_when_order_placed
        else:
            price = self.min_price - self.tick_size * self.ticks_when_order_placed
        response = place_limit_order(self.symbol, price, 1, 1 if direction == "buy" else 3, self.key)
        success = response["success"]
        if success:
            self.active_order = int(response["data"]["orderId"])
            print(f"Placed {direction} order with ID {self.active_order}")
        return success


# Run the event loop
if __name__ == "__main__":
    bot = TradingBot("ADA_USDT", KEY, 'mx0vgldfeNOhoYdin6', '6c6bef17d51341d98f6296f51eca3a98')
    asyncio.run(bot.start())
    
