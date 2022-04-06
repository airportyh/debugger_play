#! /usr/bin/env python3
# Attempt with websocket blockingIO library
# but I want to convert it to non-blocking

import asyncio
import websocket
import functools
import sys
import json

command_aliases = {
    "n": "next",
    "s": "step",
    "c": "continue",
    "o": "out",
    "bt": "backtrace",
}
parsed_scripts = {}
call_frames = None
command_number = 1

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

async def ws_send_command(ws, command):
    global command_number
    command["id"] = command_number
    command_number += 1
    ws_send(ws, json.dumps(command))

@run_in_executor
def ws_connect(ws, endpoint):
    ws.connect(endpoint)

def print_program_location():
    frame = call_frames[0]
    function_name = frame["functionName"]
    location = frame["location"]
    line_number = location["lineNumber"]
    url = frame["url"]
    print("  %s: %d" % (url, line_number))

def print_backtrace():
    for frame in call_frames:
        function_name = frame["functionName"]
        location = frame["location"]
        line_number = location["lineNumber"]
        url = frame["url"]
        print("  %s: %d" % (url, line_number))

async def ws_consumer_handler(ws, q):
    global call_frames
    while True:
        result = await ws_recv(ws)
        method = result.get("method")
        if method == "Debugger.paused":
            call_frames = result["params"]["callFrames"]
            print()
            print("Paused at")
            print_program_location()
            show_prompt()
        elif method == "Debugger.scriptParsed":
            print(result)
            pass
        else:
            print()
            print(result)
            show_prompt()

async def ws_producer_handler(ws, q):
    while True:
        cmd = await asyncio.create_task(q.get())
        cmd = cmd.strip()
        if cmd in command_aliases:
            cmd = command_aliases[cmd]
        if cmd == "step":
            await ws_send_command(ws, {"method": "Debugger.stepInto"})
        elif cmd == "next":
            await ws_send_command(ws, {"method": "Debugger.stepOver"})
        elif cmd == "out":
            await ws_send_command(ws, {"method": "Debugger.stepOut"})
        elif cmd == "continue":
            await ws_send_command(ws, {"method": "Debugger.continueToLocation"})
        elif cmd == "backtrace":
            print()
            print_backtrace()
            show_prompt()
        elif cmd == "q":
            print("Bye")
            exit(0)
        else:
            print("Unknown command: %s" % cmd)
            show_prompt()

async def connect_and_initialize(ws, endpoint, q):
    await ws_connect(ws, endpoint)
    await ws_send_command(ws, {"method": "Runtime.runIfWaitingForDebugger"})
    await ws_send_command(ws, {"method": "Debugger.enable"})
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