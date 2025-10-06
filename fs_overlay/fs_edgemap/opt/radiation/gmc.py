import pygmc
import os

fifo_path = "/tmp/msgincoming"

gc = pygmc.connect('/dev/radsensor')

ver = gc.get_version()
serial = gc.get_serial()
cpm = gc.get_cpm()

message="bravo|" + str(cpm) + " CPM\n"

if not os.path.exists(fifo_path):
    os.mkfifo(fifo_path)

with open(fifo_path, "w") as fifo:
    fifo.write(message)
    fifo.flush()

