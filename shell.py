import asyncio
import sys
import tty
import termios
import atexit
from events import decode_input

# https://stackoverflow.com/a/64317899/5304
async def connect_stdin_stdout():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    w_transport, w_protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
    return reader, writer

def restore_term(settings, writer):
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, settings)
    writer.write(bytes("\x1B[0m\n", "utf-8"))

async def start_menu(stdin, stdout):
    line = []
    cursor_idx = 0
    quit = False
    history = []
    history_idx = 0
    while not quit:
        input = (await stdin.read(100)).decode("utf-8")
        events = decode_input(input)
        for event in events:
            if event.type == "keypress":
                if len(event.key) == 1:
                    if ord(event.key) == 3: # Ctrl-C
                        quit = True
                        break
                    elif event.key == "\r":
                        # got line
                        cmd = "".join(line)
                        stdout.write(bytes("\n\rCMD %s\n\r" % cmd, "utf-8"))
                        history.insert(history_idx, cmd)
                        history_idx += 1
                        if line == ["q"]:
                            stdout.write(bytes("Bye", "utf-8"))
                            quit = True
                            break
                        line = []
                        cursor_idx = 0
                    else:
                        stdout.write(bytes(event.key, "utf-8"))
                        if cursor_idx == len(line):
                            line.append(event.key)
                            cursor_idx = len(line)
                        else:
                            assert cursor_idx < len(line) and cursor_idx >= 0
                            line[cursor_idx] = event.key
                            # TODO: make this insert instead of overwrite
                            cursor_idx += 1
                elif event.key == "LEFT_ARROW":
                    stdout.write(bytes("\u001b[1D", "utf-8"))
                    cursor_idx -= 1
                elif event.key == "RIGHT_ARROW":
                    stdout.write(bytes("\u001b[1C", "utf-8"))
                    cursor_idx += 1
                elif event.key == "UP_ARROW":
                    history_idx -= 1
                    if history_idx < 0:
                        history_idx = len(history)
                    if history_idx == len(history):
                        cmd = ""
                    else:
                        cmd = history[history_idx]
                    cursor_idx = len(cmd)
                    stdout.write(bytes("\u001b[2K\r%s" % cmd, "utf-8"))
                elif event.key == "DOWN_ARROW":
                    history_idx += 1
                    if history_idx > len(history):
                        history_idx = len(history)
                    if history_idx == len(history):
                        cmd = ""
                    else:
                        cmd = history[history_idx]
                    cursor_idx = len(cmd)
                    stdout.write(bytes("\u001b[2K\r%s" % cmd, "utf-8"))
                elif event.key == "DEL":
                    stdout.write(bytes("\u001b[1D", "utf-8"))
                    if cursor_idx == len(line):
                        line = line[:len(line) - 1]
                        stdout.write(bytes(" \u001b[1D", "utf-8"))
                    else:
                        del line[cursor_idx - 1]
                        rest = "".join(line[cursor_idx-1:])
                        stdout.write(bytes(rest + " ", "utf-8"))
                        stdout.write(bytes("\u001b[%dD" % (len(rest) + 1), "utf-8"))
                    cursor_idx -= 1
                

async def main():
    term_settings = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin)
    stdin, stdout = await connect_stdin_stdout()
    atexit.register(restore_term, term_settings, stdout)
    await start_menu(stdin, stdout)

if __name__ == "__main__":
    asyncio.run(main())