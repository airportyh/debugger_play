#! /usr/bin/env python3
# Attempt with websocket blockingIO library
# but I want to convert it to non-blocking

import asyncio
import aiohttp
from aiohttp.client_exceptions import ClientConnectorError
import websocket
import functools
import requests
import sys
import json
import pdb
from subprocess import Popen
from asyncio import create_subprocess_shell, create_task
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
    "b": "break",
    "bt": "backtrace",
    "l": "list",
    "lc": "location",
    "p": "print",
    "pa": "pause",
    "r": "run",
    "rl": "reload",
}
parsed_scripts = {}
script_sources = {}
call_frames = None
command_number = 1
pending_requests = {}
first_script_id = None

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
    my_q = asyncio.Queue()
    pending_requests[command_number] = my_q
    command["id"] = command_number
    command_number += 1
    await ws_send(ws, json.dumps(command))
    reply = await my_q.get()
    return reply

@run_in_executor
def ws_connect(ws, endpoint):
    ws.connect(endpoint)

async def print_program_location(ws):
    await ensure_script_source(ws)
    frame = call_frames[0]
    function_name = frame["functionName"]
    location = frame["location"]
    script_id = location["scriptId"]
    script_source = script_sources[script_id]
    lines = script_source.split("\n")
    line_no = location["lineNumber"]
    line_source = lines[line_no]
    url = frame["url"]
    match = FILE_URL_REGEX.match(url)
    if match:
        url = match.group(1)
        if url.startswith(CWD):
            url = url[len(CWD):]
    print()
    print("Paused at %s line %d:" % (url, line_no))
    print("-> %d %s" % (line_no + 1, line_source))
    show_prompt()

def print_backtrace():
    for frame in call_frames:
        function_name = frame["functionName"]
        location = frame["location"]
        line_number = location["lineNumber"]
        url = frame["url"]
        print("  %s: %d" % (url, line_number))

async def ensure_script_source(ws):
    frame = call_frames[0]
    script_id = frame["location"]["scriptId"]
    if script_id not in script_sources:
        reply = await ws_send_command(ws, {
            'method': 'Debugger.getScriptSource', 
            'params': {'scriptId': script_id}
        })
        script_source = reply['result']['scriptSource']
        script_sources[script_id] = script_source

async def list_source(ws):
    await ensure_script_source(ws)
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
            print("-> %3d %s" % (i + 1, line))
        else:
            print("   %3d %s" % (i + 1, line))
    show_prompt()

async def ws_consumer_handler(ws, q):
    global call_frames
    global first_script_id
    while True:
        result = await ws_recv(ws)
        method = result.get("method")
        id = result.get("id")
        if id:
            if id in pending_requests:
                await pending_requests[id].put(result)
                del pending_requests[id]
        elif method:
            if method == "Debugger.paused":
                call_frames = result["params"]["callFrames"]
                if first_script_id is None:
                    frame = call_frames[0]
                    location = frame["location"]
                    first_script_id = script_id = location["scriptId"]
                create_task(q.put("location"))
            elif method == "Debugger.scriptParsed":
                # print("script %s: %s" % (result["params"]["scriptId"], result["params"]["url"]))
                pass
            elif method == "Debugger.resumed":
                pass
            else:
                print()
                print(result)
                show_prompt()
        else:
            raise Exception("A message should have id or method")

async def eval_and_print(expr, call_frame_id, ws):
    reply = await ws_send_command(ws, {
        "method": "Debugger.evaluateOnCallFrame",
        "params": {
            "callFrameId": call_frame_id,
            "expression": expr
        }
    })
    result = reply["result"]["result"]
    if result["type"] == "undefined":
        print("undefined")
    elif "value" in result:
        print(result["value"])
    else:
        print(result)
    show_prompt()

async def ws_producer_handler(ws, q):
    last_line = None
    while True:
        line = await create_task(q.get())
        line = line.strip()
        if line == "" and last_line is not None:
            line = last_line
        parts = line.split(" ")
        cmd, *args = parts
        if cmd in command_aliases:
            cmd = command_aliases[cmd]
        if cmd is None:
            show_prompt()
        elif cmd == "step":
            create_task(ws_send_command(ws, {"method": "Debugger.stepInto"}))
        elif cmd == "next":
            create_task(ws_send_command(ws, {"method": "Debugger.stepOver"}))
        elif cmd == "out":
            create_task(ws_send_command(ws, {"method": "Debugger.stepOut"}))
        elif cmd == "continue":
            create_task(ws_send_command(ws, {"method": "Debugger.resume"}))
        elif cmd == "backtrace":
            print()
            print_backtrace()
            show_prompt()
        elif cmd == "location":
            create_task(print_program_location(ws))
            continue
        elif cmd == "list":
            print()
            await list_source(ws)
        elif cmd == "pause":
            create_task(ws_send_command(ws, {"method": "Debugger.pause"}))
            show_prompt()
        elif cmd == "print":
            frame = call_frames[0]
            call_frame_id = frame['callFrameId']
            if len(args) == 0:
                print("Wrong number of arguments for print")
                show_prompt()
            else:
                create_task(eval_and_print(" ".join(args), call_frame_id, ws))
        elif cmd == "reload":
            create_task(ws_send_command(ws, {"method": "Page.waitForDebugger"}))            
            await ws_send_command(ws, {"method": "Page.reload"})
            show_prompt()
        elif cmd == "run":
            create_task(ws_send_command(ws, {"method": "Runtime.runIfWaitingForDebugger"}))
            create_task(ws_send_command(ws, {"method": "Debugger.enable"}))
            show_prompt()
        elif cmd == "break":
            if len(args) != 2:
                print("Wrong number of arguments for break")
                show_prompt()
                continue
            url, line_no = args
            reply = await ws_send_command(ws, {
                "method": "Debugger.setBreakpointByUrl",
                "params": {
                    "lineNumber": int(line_no),
                    "url": url
                }
            })
            print(reply)
            show_prompt()
        elif cmd == "q":
            break
        else:
            print("Unknown command: %s" % cmd)
            show_prompt()
        last_line = line

async def web_socket_handler(endpoint, q):
    ws = websocket.WebSocket()
    await ws_connect(ws, endpoint)
    print("Connected!")
    
    create_task(ws_send_command(ws, {"method": "Runtime.runIfWaitingForDebugger"}))
    create_task(ws_send_command(ws, {"method": "Debugger.enable"}))
    
    consumer_task = create_task(ws_consumer_handler(ws, q))
    producer_task = create_task(ws_producer_handler(ws, q))

    show_prompt()
    
    # From producer/consumer pattern in
    #   https://websockets.readthedocs.io/en/stable/howto/patterns.html
    done, pending = await asyncio.wait(
        [consumer_task, producer_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    
    ws.close()

def got_stdin_data(q):
    line = sys.stdin.readline()
    create_task(q.put(line))

def show_prompt():
    print(">> ", end="")
    sys.stdout.flush()

WS_URL_PATTERN = re.compile("^Debugger listening on (.*)\n$")

async def stream_printer(stream):
    while True:
        line = (await stream.readline()).decode("utf-8")
        print(colorama.Fore.YELLOW + line, end=colorama.Style.RESET_ALL)

async def connect_to_node_process(port, q):
    resp = requests.get('http://localhost:%d/json/list' % port)
    data = resp.json()
    url = data[0]['webSocketDebuggerUrl']
    await web_socket_handler(url, q)

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
    
    ws_handler = create_task(web_socket_handler(url, q))
    stdout_printer = create_task(stream_printer(node.stdout))
    stderr_printer = create_task(stream_printer(node.stderr))
    
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

async def request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data

async def connect_node(stdin_q):
    await connect_to_port(9229, "Select Node.js process:", stdin_q)

async def connect_chrome(stdin_q):
    await connect_to_port(9222, "Select Chrome target:", stdin_q)

async def enter_port(stdin_q):
    while True:
        print("Enter port # (q to quit):")
        show_prompt()
        reply = (await stdin_q.get()).strip()
        if reply == 'q':
            return
        try:
            port = int(reply)
            await connect_to_port(port, "Select target:", stdin_q)
        except ValueError as e:
            print("Invalid port number")
            continue

async def connect_to_port(port, message, stdin_q):
    url = 'http://localhost:%d/json/list' % port
    try:
        endpoints = await request(url)
    except ClientConnectorError as e:
        print(e)
        return

    while True:
        print(message)
        for i, endpoint in enumerate(endpoints):
            title = endpoint["title"]
            if title == '\ufeff':
                title = "(Blank)"
            desc = endpoint["description"]
            display = title
            if len(desc) > 0:
                display += " - %s" % desc
            print("%d. %s" % (i + 1, display))
        print("q. Quit")
        show_prompt()
        reply = (await stdin_q.get()).strip()
        if reply == 'q':
            return
        try:
            idx = int(reply) - 1
            endpoint = endpoints[idx]
            endpoint_url = endpoint["webSocketDebuggerUrl"]
            await web_socket_handler(endpoint_url, stdin_q)
        except ValueError:
            print("Invalid input %s", reply)
            continue

async def enter_ws_url(stdin_q):
    while True:
        print("Enter WS URL (q to quit):")
        show_prompt()
        reply = (await stdin_q.get()).strip()
        if reply == 'q':
            return
        try:
            await web_socket_handler(reply, stdin_q)
        except Exception as e:
            print(e)

async def launch_node(stdin_q):
    print("Launch node")

async def launch_chrome(stdin_q):
    print("Launch Chrome")

async def start_options():
    return [
        {
            "text": "Connect to Node.js",
            "action": connect_node
        },
        {
            "text": "Connect to Chrome",
            "action": connect_chrome
        },
        {
            "text": "Enter WS URL",
            "action": enter_ws_url
        },
        {
            "text": "Enter custom port #",
            "action": enter_port
        },
        {
            "text": "Launch Node.js",
            "action": launch_node
        },
        {
            "text": "Launch Chrome",
            "action": launch_chrome
        }
    ]

async def startup(stdin_q):
    options = await start_options()
    while True:
        print("What to do?")
        for i, option in enumerate(options):
            print("%d. %s" % (i + 1, option['text']))
        print("q. Quit")
        show_prompt()
        reply = (await stdin_q.get()).strip()
        if reply == 'q':
            print("Bye")
            return
        try:
            idx = int(reply) - 1
            if idx < -1 or idx > len(options):
                print("Invalid choice: %s" % reply)
                continue
        except ValueError:
            print("Invalid choice: %s" % reply)
            continue
        option = options[idx]
        await option["action"](stdin_q)
    
async def main():
    stdin_q = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.add_reader(sys.stdin, got_stdin_data, stdin_q)
    await startup(stdin_q)
    
if __name__ == "__main__":
    asyncio.run(main())