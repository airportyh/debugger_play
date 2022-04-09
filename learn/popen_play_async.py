import sys
import atexit
import asyncio
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
import re

WS_URL_PATTERN = re.compile("^Debugger listening on (.*)\n$")

async def start_node_process():
    node = await create_subprocess_shell(
        "node --inspect-brk=9226 ../example.js", 
        stdout=PIPE,
        stderr=PIPE
    )

    line1 = (await node.stderr.readline()).decode("utf-8")
    print("LINE 1", line1)
    match = WS_URL_PATTERN.match(line1)
    url = match.group(1)
    print("URL: %s" % url)
    
    line2 = (await node.stderr.readline()).decode("utf-8")
    print("LINE 2", line2)

    atexit.register(node.terminate)

asyncio.run(start_node_process())

    
    
        

