import pygmc
import os
import time

#
# Connect radiation sensor
#
gc = pygmc.connect('/dev/radsensor')
ver = gc.get_version()
serial = gc.get_serial()
cpm = gc.get_cpm()

#
# Demo how to send CPM over Meshtastic message channel directly
# fifo_path = "/tmp/msgincoming"
# message="bravo|" + str(cpm) + " CPM\n"
# if not os.path.exists(fifo_path):
#    os.mkfifo(fifo_path)
# with open(fifo_path, "w") as fifo:
#    fifo.write(message)
#    fifo.flush()
#

# Loop which will send 'radsensor' message to web ui websocket
try:
	while True:
		cpm = gc.get_cpm()
		webui_message = "radsensor," + str(cpm)
		fifo_write = open('/tmp/statusin', 'w')
		fifo_write.write(webui_message)
		fifo_write.flush()
		fifo_write.close()
		time.sleep(60)

except Exception as e:
	print(f"Exception caught: {e}")
	sys.stdout.flush()
	os._exit(0)  

