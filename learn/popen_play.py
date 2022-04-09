from subprocess import Popen, PIPE
from io import StringIO
from time import sleep
import sys
import atexit

node = Popen(
    ["node", "--inspect-brk=9226", "../example.js"], 
    stdout=PIPE,
    stderr=PIPE
)

line1 = node.stderr.readline().decode("utf-8")
print("LINE 1", line1)
line2 = node.stderr.readline().decode("utf-8")
print("LINE 2", line2)

atexit.register(node.terminate)

while True:
    pass


    
    
        

