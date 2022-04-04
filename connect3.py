# Attempt with websocket blockingIO library
# but I want to convert it to non-blocking

import asyncio
import websocket
import functools
import sys
import json

def run_in_executor(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, lambda: f(*args, **kwargs))

    return inner

@run_in_executor
def ws_recv(ws):
    result_json = ws.recv()
    return json.loads(result_json)

@run_in_executor
def ws_send(ws, message):
    ws.send(message)

@run_in_executor
def ws_connect(ws, endpoint):
    ws.connect(endpoint)

async def ws_consumer_handler(ws, q):
    while True:
        result = await ws_recv(ws)
        print(result)

async def ws_producer_handler(ws, q):
    while True:
        message = await asyncio.create_task(q.get())
        print("SEND:", message)
        await ws.send(message)

async def connect_and_initialize(ws, endpoint, q):
    await ws_connect(ws, endpoint)
    await ws_send(ws, '{"id":1, "method": "Runtime.runIfWaitingForDebugger"}')
    await ws_send(ws, '{"id":2, "method": "Debugger.enable"}')
    # From producer/consumer pattern in
    #   https://websockets.readthedocs.io/en/stable/howto/patterns.html
    consumer_task = asyncio.create_task(ws_consumer_handler(ws, q))
    producer_task = asyncio.create_task(ws_producer_handler(ws, q))
    done, pending = await asyncio.wait(
        [consumer_task, producer_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

def got_stdin_data(q):
    line = sys.stdin.readline()
    asyncio.create_task(q.put(line))
    show_prompt()

def show_prompt():
    print(">> ", end="")
    sys.stdout.flush()

def main():
    if len(sys.argv) < 2:
        print("Please provide a WS endpoint.")
        exit(1)

    ws_endpoint = sys.argv[1]
    
    q = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.add_reader(sys.stdin, got_stdin_data, q)
    
    ws = websocket.WebSocket()
    loop.create_task(connect_and_initialize(ws, ws_endpoint, q))
    
    show_prompt()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    
if __name__ == "__main__":
    main()