import sys
import asyncio
from websockets import connect

def got_stdin_data():
    line = sys.stdin.readline()
    print("Got line:", line)

loop = asyncio.get_event_loop()
loop.add_reader(sys.stdin, got_stdin_data)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

loop.close()