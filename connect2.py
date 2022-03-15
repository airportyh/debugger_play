import sys
import websocket
from time import sleep
import json


# {"id": 1, "method": "Debugger.enable"}

def main():
    if len(sys.argv) < 2:
        print("Please provide a WS endpoint.")
        exit(1)

    ws_endpoint = sys.argv[1]
    ws = websocket.WebSocket()
    ws.connect(ws_endpoint)
    while True:
        answer_json = input(">> ")
        try:
            answer = json.loads(answer_json)
        except:
            print("Invalid json, try again.")
            continue
        ws.send(answer_json)
        while True:
            result_json = ws.recv()
            result = json.loads(result_json)
            print("RECV:", result)
            if result.get("id") == answer.get("id"):
                break
    ws.close()

if __name__ == "__main__":
    main()

