#!/usr/bin/env python3
"""Integration test with native evdev records and a recording ptt_helper.
"""
import os
from pathlib import Path
import signal
import time
import struct
import subprocess
import sys
import tempfile

script = Path(__file__).resolve().parents[1] / 'rootfs-overlay/usr/libexec/reterminal-ptt'
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    helper = root / 'ptt_helper'
    helper.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$PTT_TEST_LOG"\n')
    helper.chmod(0o755)
    log = root / 'commands'
    log.touch()
    commands = log.open()
    fifo = root / 'events'
    os.mkfifo(fifo)
    writer = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    path = str(root / 'control.sock')
    Path(path).touch()
    env = dict(os.environ, PATH=directory + ':' + os.environ['PATH'],
               RETERMINAL_PTT_DEVICE=str(fifo), RETERMINAL_PTT_SOCKET=path, PTT_TEST_LOG=str(log))
    process = subprocess.Popen([sys.executable, str(script)], env=env,
                               stdout=subprocess.PIPE, text=True)

    def event(kind, code, value):
        return struct.pack('@llHHi', 0, 0, kind, code, value)

    def expect(command):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            line = commands.readline()
            if line:
                option = '--ptt_down' if command == 'DOWN' else '--ptt_up'
                assert line.strip() == '--socket ' + path + ' ' + option, line
                return
            time.sleep(0.02)
        raise AssertionError('Timed out waiting for ' + command)

    try:
        expect('UP')
        assert 'PTT input:' in process.stdout.readline()
        # Ignore unrelated keys and repeat events, preserving both edges even
        # when a short press/release is returned in a single read.
        os.write(writer, event(1, 30, 1) + event(1, 33, 1) +
                 event(1, 33, 2) + event(1, 33, 0))
        expect('DOWN')
        expect('UP')
        os.write(writer, event(1, 33, 1))
        expect('DOWN')
        os.write(writer, event(0, 3, 0) + event(1, 33, 1) + event(0, 0, 0))
        expect('UP')
        os.write(writer, event(1, 33, 1))
        expect('DOWN')
        # A restarted client receives the held state on its new socket.
        os.unlink(path)
        Path(path).touch()
        expect('DOWN')
        process.send_signal(signal.SIGTERM)
        expect('UP')
        assert process.wait(timeout=3) == 0
        print('PASS: edges, autorepeat, unrelated keys, dropped events, socket restart, shutdown')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        commands.close()
        os.close(writer)
