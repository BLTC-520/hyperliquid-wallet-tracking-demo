import asyncio
import json
import websockets
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Hyperliquid WebSocket endpoint
WS_URL = "wss://api.hyperliquid.xyz/ws"

class WalletTracker:
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address
        self.known_trades = set()

    async def connect_and_subscribe(self):
        async with websockets.connect(WS_URL) as websocket:
            # Subscribe to user events
            subscribe_message = {
                "method": "subscribe",
                "params": {
                    "type": "user_events",
                    "user": self.wallet_address
                }
            }
            
            await websocket.send(json.dumps(subscribe_message))
            print(f"Tracking wallet: {self.wallet_address}")
            
            while True:
                try:
                    response = await websocket.recv()
                    await self.process_message(json.loads(response))
                except Exception as e:
                    print(f"Error: {e}")
                    break

    async def process_message(self, message):
        if "data" not in message:
            return

        data = message["data"]
        
        # Process different types of events
        if "fills" in data:
            for fill in data["fills"]:
                trade_id = fill.get("id")
                if trade_id not in self.known_trades:
                    self.known_trades.add(trade_id)
                    await self.process_trade(fill)

    async def process_trade(self, trade):
        timestamp = datetime.fromtimestamp(trade.get("time", 0) / 1000)
        coin = trade.get("coin", "Unknown")
        side = trade.get("side", "Unknown")
        size = trade.get("size", 0)
        price = trade.get("price", 0)
        
        print(f"\nNew Trade Detected:")
        print(f"Time: {timestamp}")
        print(f"Coin: {coin}")
        print(f"Side: {side}")
        print(f"Size: {size}")
        print(f"Price: {price}")
        print("-" * 50)

async def main():
    # Get wallet address from environment variable or use default
    wallet_address = 0xd5f7974e1be5b336094a18c230f39607934e367d
    if not wallet_address:
        wallet_address = input("Enter the wallet address to track: ")
    
    tracker = WalletTracker(wallet_address)
    await tracker.connect_and_subscribe()

if __name__ == "__main__":
    asyncio.run(main()) 