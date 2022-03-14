import sys
import asyncio
from websockets import connect


# {"id": 1, "method": "Debugger.enable"}
# {"id": 2, "method": "
    
async def ws_consumer_handler(ws):
    async for message in ws:
        print("RECV:", message)
    
async def ws_producer_handler(ws, q):
    while True:
        message = await asyncio.create_task(q.get())
        print("SEND:", message)
        await ws.send(message)

async def connect_to_websocket(uri, q):
    # From producer/consumer pattern in
    #   https://websockets.readthedocs.io/en/stable/howto/patterns.html
    async with connect(uri) as ws:
        consumer_task = asyncio.create_task(ws_consumer_handler(ws))
        producer_task = asyncio.create_task(ws_producer_handler(ws, q))
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

def show_prompt():
    print(">> ", end="")
    sys.stdout.flush()

def got_stdin_data(q):
    line = sys.stdin.readline()
    asyncio.create_task(q.put(line))
    show_prompt()

def main():
    if len(sys.argv) < 2:
        print("Please provide a WS endpoint.")
        exit(1)

    ws_endpoint = sys.argv[1]
    
    q = asyncio.Queue()
    loop = asyncio.get_event_loop()
    # add_reader pattern from https://stackoverflow.com/a/29102047/5304
    loop.add_reader(sys.stdin, got_stdin_data, q)
    loop.create_task(connect_to_websocket(ws_endpoint, q))

    show_prompt()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    loop.close()

if __name__ == "__main__":
    main()