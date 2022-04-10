#! /usr/bin/env python3
# Attempt with websocket blockingIO library
# but I want to convert it to non-blocking

import asyncio
import websocket
import functools
import sys
import json
import pdb
from subprocess import Popen
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
import re
import atexit
import colorama
import os

CWD = os.getcwd() + "/"
FILE_URL_REGEX = re.compile("^file\:\/\/(.*)$")

command_aliases = {
    "n": "next",
    "s": "step",
    "c": "continue",
    "o": "out",
    "bt": "backtrace",
    "l": "list",
}
parsed_scripts = {}
script_sources = {}
call_frames = None
command_number = 1
list_pending = None

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
    match = FILE_URL_REGEX.match(url)
    if match:
        url = match.group(1)
        if url.startswith(CWD):
            url = url[len(CWD):]
    print("%s line %d" % (url, line_number))

def print_backtrace():
    for frame in call_frames:
        function_name = frame["functionName"]
        location = frame["location"]
        line_number = location["lineNumber"]
        url = frame["url"]
        print("  %s: %d" % (url, line_number))

async def list_source(ws):
    global list_pending
    frame = call_frames[0]
    script_id = frame["location"]["scriptId"]
    if script_id not in script_sources:
        list_pending = (command_number, script_id)
        await ws_send_command(ws, {
            'method': 'Debugger.getScriptSource', 
            'params': {'scriptId': script_id}
        })
    else:
        actually_list_source()

def actually_list_source():
    frame = call_frames[0]
    location = frame["location"]
    line_no = location["lineNumber"]
    script_id = location["scriptId"]
    script_source = script_sources[script_id]
    lines = list(enumerate(script_source.split("\n")))
    shown_lines = lines[max(0, line_no - 5):line_no + 5]
    print("Script %s" % script_id)
    for i, line in shown_lines:
        if i == line_no:
            print("->  %s" % line)
        else:
            print("    %s" % line)
    show_prompt()

async def ws_consumer_handler(ws, q):
    global call_frames
    global list_pending
    while True:
        result = await ws_recv(ws)
        method = result.get("method")
        id = result.get("id")
        if method == "Debugger.paused":
            call_frames = result["params"]["callFrames"]
            print()
            print("Paused at ", end="")
            print_program_location()
            show_prompt()
        elif method == "Debugger.scriptParsed":
            # save_script(result)
            pass
        else:
            if list_pending and list_pending[0] == id:
                script_source = result['result']['scriptSource']
                script_id = list_pending[1]
                script_sources[script_id] = script_source
                list_pending = None
                actually_list_source()
            else:
                print()
                print(result)
                show_prompt()

async def ws_producer_handler(ws, q):
    last_line = None
    while True:
        line = await asyncio.create_task(q.get())
        line = line.strip()
        if line == "":
            line = last_line
        parts = line.split(" ")
        if len(parts) == 1:
            cmd = parts[0]
        else:
            cmd, *args = parts
        if cmd in command_aliases:
            cmd = command_aliases[cmd]
        if cmd is None:
            show_prompt()
        elif cmd == "step":
            await ws_send_command(ws, {"method": "Debugger.stepInto"})
        elif cmd == "next":
            await ws_send_command(ws, {"method": "Debugger.stepOver"})
        elif cmd == "out":
            await ws_send_command(ws, {"method": "Debugger.stepOut"})
        elif cmd == "continue":
            script_id, line_no = args
            await ws_send_command(ws, {
                "method": "Debugger.continueToLocation",
                "params": {
                    "location": {
                        "scriptId": script_id,
                        "lineNumber": int(line_no)
                    }
                }
            })
        elif cmd == "backtrace":
            print()
            print_backtrace()
            show_prompt()
        elif cmd == "list":
            print()
            await list_source(ws)
        elif cmd == "q":
            print("Bye")
            break
        else:
            print("Unknown command: %s" % cmd)
            show_prompt()
        last_line = line

async def web_socket_handler(endpoint, q):
    ws = websocket.WebSocket()
    await ws_connect(ws, endpoint)
    
    await ws_send_command(ws, {"method": "Runtime.runIfWaitingForDebugger"})
    await ws_send_command(ws, {"method": "Debugger.enable"})
    
    consumer_task = asyncio.create_task(ws_consumer_handler(ws, q))
    producer_task = asyncio.create_task(ws_producer_handler(ws, q))
    
    # From producer/consumer pattern in
    #   https://websockets.readthedocs.io/en/stable/howto/patterns.html
    done, pending = await asyncio.wait(
        [consumer_task, producer_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

def got_stdin_data(q):
    line = sys.stdin.readline()
    asyncio.create_task(q.put(line))

def show_prompt():
    print(">> ", end="")
    sys.stdout.flush()

WS_URL_PATTERN = re.compile("^Debugger listening on (.*)\n$")

async def stream_printer(stream):
    while True:
        line = (await stream.readline()).decode("utf-8")
        print(colorama.Fore.YELLOW + line, end=colorama.Style.RESET_ALL)

async def start_node_process(q):
    def cleanup_process():
        nonlocal node
        if node is not None:
            try:
                node.terminate()
            except ProcessLookupError:
                pass
    node = await create_subprocess_shell(
        "node --inspect-brk=9218 ./example.js", 
        stdout=PIPE,
        stderr=PIPE
    )
    atexit.register(cleanup_process)

    line1 = (await node.stderr.readline()).decode("utf-8")
    match = WS_URL_PATTERN.match(line1)
    if match:
        url = match.group(1)
    else:
        print(line1)
        return
    print(colorama.Fore.YELLOW + line1, end=colorama.Style.RESET_ALL)
    line2 = (await node.stderr.readline()).decode("utf-8")
    print(colorama.Fore.YELLOW + line2, end=colorama.Style.RESET_ALL)
    
    ws_handler = asyncio.create_task(web_socket_handler(url, q))
    stdout_printer = asyncio.create_task(stream_printer(node.stdout))
    stderr_printer = asyncio.create_task(stream_printer(node.stderr))
    
    # From producer/consumer pattern inu
    #   https://websockets.readthedocs.io/en/stable/howto/patterns.html
    _, pending = await asyncio.wait(
        [ws_handler, stdout_printer, stderr_printer],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    
    node.terminate()
    node = None

async def main():
    ws_endpoint = None
    if len(sys.argv) >= 2:
        ws_endpoint = sys.argv[1]
    
    q = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.add_reader(sys.stdin, got_stdin_data, q)
    handler = None
    
    show_prompt()
    try:
        if ws_endpoint:
            await connect_and_initialize(ws_endpoint, q)
        else:
            await start_node_process(q)
        pass
    except KeyboardInterrupt:
        pass
    
if __name__ == "__main__":
    asyncio.run(main())