# Attempt with websocket (singular) library
# This is a blocking IO library and it works

import sys
import websocket
from time import sleep
import json


# {"id": 1, "method": "Debugger.enable"}
def print_reply(reply):
    if "id" in reply:
        print(reply)
    elif "method" in reply:
        method = reply["method"]
        if method == "Debugger.scriptParsed":
            params = reply["params"]
            scriptId = params["scriptId"]
            url = params["url"]
            stackTrace = params.get("stackTrace")
            print("scriptParsed: %s, %s, %r" % (scriptId, url, stackTrace != None))
        elif method == "Debugger.paused":
            callFrames = reply["params"]["callFrames"]
            firstFrame = callFrames[0]
            url = firstFrame["url"]
            location = firstFrame["location"]
            functionName = firstFrame["functionName"]
            lineNumber = location["lineNumber"] + 1
            print("paused: %s, %d" % (url, lineNumber))
            print("first frame: %r" % firstFrame)
        else:
            print("%s: %r" % (method, reply))

def receive_until_id(id, ws):
    while True:
        result_json = ws.recv()
        result = json.loads(result_json)
        print_reply(result)
        if result.get("id") == id:
            break

def receive_until_pause(ws):
    while True:
        result_json = ws.recv()
        result = json.loads(result_json)
        print_reply(result)
        if result.get("method") == "Debugger.paused":
            break

def main():
    if len(sys.argv) < 2:
        print("Please provide a WS endpoint.")
        exit(1)

    ws_endpoint = sys.argv[1]
    ws = websocket.WebSocket()
    ws.connect(ws_endpoint)
    ws.send('{"id":1, "method": "Runtime.runIfWaitingForDebugger"}')
    ws.send('{"id":2, "method": "Debugger.enable"}')
    receive_until_pause(ws)
    while True:
        answer_json = input(">> ")
        try:
            answer = json.loads(answer_json)
        except:
            print("Invalid json, try again.")
            continue
        ws.send(answer_json)
        receive_until_pause(ws)
    ws.close()

if __name__ == "__main__":
    main()

