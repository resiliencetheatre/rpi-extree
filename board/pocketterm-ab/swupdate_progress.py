"""Read-only observer for the pinned SWUpdate 2026.05.1 progress ABI v2.0.

No commands are sent, and these messages never authorize activation or commit.
"""
import socket
import struct
import threading

ACK = struct.Struct('<I4s')
MESSAGE = struct.Struct('<IIIQIII256s64sII2048s')
VERSION = 0x20000
NAMES = ('idle','start','run','success','failure','download','done','subprocess','progress')


def decode(data):
    if len(data) != MESSAGE.size:
        raise ValueError('Incomplete SWUpdate progress record')
    version,status,_,_,steps,step,percent,image,handler,_,length,info = MESSAGE.unpack(data)
    if version != VERSION or status >= len(NAMES) or percent > 100 or step > steps or length > 2048:
        raise ValueError('Unsupported SWUpdate progress record')
    def text(raw):
        return ''.join(c if c.isprintable() else ' ' for c in raw.split(b'\0',1)[0].decode('utf-8','replace'))
    return dict(status=NAMES[status], step=step, steps=steps, percent=percent,
                image=text(image), handler=text(handler), info=text(info[:length]))


class Monitor:
    def __init__(self, callback, path='/run/pocketterm-ab/progress'):
        self.callback,self.path = callback,path
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run,daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self,*_):
        self.stop.set()
        self.thread.join(1)

    def receive(self,connection,size):
        data=bytearray()
        while len(data)<size and not self.stop.is_set():
            try:
                chunk=connection.recv(size-len(data))
            except socket.timeout:
                continue
            if not chunk:
                raise ConnectionError('Progress socket closed')
            data.extend(chunk)
        if self.stop.is_set():
            raise ConnectionError('Observer stopped')
        return bytes(data)

    def run(self):
        while not self.stop.is_set():
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
                    connection.settimeout(0.2)
                    connection.connect(self.path)
                    version,magic=ACK.unpack(self.receive(connection,ACK.size))
                    if version != VERSION or magic != b'ACK\0':
                        return  # Do not guess the layout of an unknown progress ABI.
                    while not self.stop.is_set():
                        self.callback(decode(self.receive(connection,MESSAGE.size)))
            except (OSError,ValueError):
                pass  # Missing/restarted progress stream does not affect installation.
            self.stop.wait(0.2)
