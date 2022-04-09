import asyncio
from asyncio import streams

async def run():
    stdout = streams.StreamReader()
    node = await asyncio.create_subprocess_shell(
        "node",
        stdout,
        stderr=asyncio.subprocess.PIPE
    )
    
    data = stdout.read(10)
    print(data)

asyncio.run(run())