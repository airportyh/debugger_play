import sys
import asyncio
from websockets import connect
import logging

logging.basicConfig(
    format="%(asctime)s %(message)s",
    level=logging.DEBUG,
)

async def connect_to_websocket(uri):
    async with connect(uri) as ws:
        await ws.send('{ "id": 1, "method": "Debugger.enable" }')
        async for message in ws:
            print("RECV:", message)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide a WS endpoint.")
        exit(1)

    ws_endpoint = sys.argv[1]
    asyncio.run(connect_to_websocket(ws_endpoint))
