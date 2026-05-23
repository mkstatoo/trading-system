import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosed

from app.core.logger import setup_logger

logger = setup_logger()


class CoinExWebSocket:

    URL = "wss://socket.coinex.com/v2/spot"

    def __init__(self):
        self.ws = None
        self.running = False
        self.subscriptions: list[dict] = []

    async def connect(self):
        self.ws = await websockets.connect(self.URL, ping_interval=20, ping_timeout=10)
        self.running = True
        logger.info("coinex websocket connected")

    async def subscribe_ticker(self, market: str = "BTCUSDT"):
        payload = {
            "method": "state.subscribe",
            "params": {"market_list": [market]},
            "id": 1,
        }
        self.subscriptions.append(payload)
        await self.ws.send(json.dumps(payload))

    async def listen(self):
        while self.running:
            try:
                message = await self.ws.recv()
                yield json.loads(message)
            except ConnectionClosed as e:
                logger.error(f"websocket closed: {e}")
                await self.reconnect()
            except Exception as e:
                logger.error(f"websocket error: {e}")
                await self.reconnect()

    async def reconnect(self):
        logger.warning("reconnecting websocket")
        self.running = False
        try:
            await self.ws.close()
        except Exception:
            pass

        await asyncio.sleep(5)
        await self.connect()
        self.running = True

        for sub in self.subscriptions:
            await self.ws.send(json.dumps(sub))

    async def close(self):
        self.running = False
        if self.ws:
            await self.ws.close()
