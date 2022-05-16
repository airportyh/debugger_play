import asyncio
from asyncio import create_task
import tty
import sys
import fcntl
import os
import termios
import atexit

def get_input():
    fl_state = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
    # in blocking mode, 
    # this blocks until next input byte, which can be keyboard or mouse data
    data = sys.stdin.read(1)
    if data == '\x1b':  # this control code marks start of a control
                        # sequence with more bytes to follow
        # temporarily set stdin to non-blocking mode so I can read
        # all the characters that's immediately available
        fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, fl_state | os.O_NONBLOCK)
        codes = ""
        while True:
            # in non-blocking mode, this returns '' when no more bytes are available
            ch = sys.stdin.read(1)
            if ch == '':
                # reset stdin back to blocking mode
                fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, fl_state)
                break
            else:
                codes += ch
        data += codes
    return data

def got_stdin_data(q):
    ipt = get_input()
    create_task(q.put(ipt))


def restore_term(settings, writer):
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, settings)
    writer.write(bytes("\x1B[0m\n", "utf-8"))

async def main():
    term_settings = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin)
    stdin_q = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.add_reader(sys.stdin, got_stdin_data, stdin_q)
    w_transport, w_protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(w_transport, w_protocol, None, loop)
    atexit.register(restore_term, term_settings, writer)
    while True:
        ipt = await stdin_q.get()
        if ipt == "q":
            break
        writer.write(bytes("INPUT:" + ipt, "utf-8"))

if __name__ == "__main__":
    asyncio.run(main())