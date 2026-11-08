#!/usr/bin/env python3
"""Pinned progress ABI tests. No SWUpdate process, slot writes or reboot."""
import socket
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from swupdate_progress import ACK,MESSAGE,VERSION,Monitor,decode


def record(**changes):
    values=dict(version=VERSION,status=8,download=0,total=0,steps=2,step=1,percent=42,
                image=b'boot-b.vfat',handler=b'raw',source=4,length=0,info=b'')
    values.update(changes)
    return MESSAGE.pack(*values.values())


class Tests(unittest.TestCase):
    def test_packed_record_and_readback_stage(self):
        self.assertEqual(MESSAGE.size,2408)
        value=decode(record())
        self.assertEqual((value['image'],value['percent'],value['step'],value['steps']),('boot-b.vfat',42,1,2))
        self.assertEqual(value['status'],'progress')
        self.assertEqual(decode(record(status=3,percent=100))['status'],'success')

    def test_unknown_abi_and_invalid_fields_rejected(self):
        for change in (dict(version=0x30000),dict(percent=101),dict(status=99),dict(step=3),dict(length=2049)):
            with self.assertRaises(ValueError):decode(record(**change))
        with self.assertRaises(ValueError):decode(record()[:-1])

    def test_partial_stream_and_timeout_preserve_frame(self):
        monitor=Monitor(Mock())
        connection=Mock()
        connection.recv.side_effect=[b'ab',socket.timeout(),b'cd']
        self.assertEqual(monitor.receive(connection,4),b'abcd')
        monitor.stop.set()
        with self.assertRaises(ConnectionError):monitor.receive(connection,4)

    def test_wrong_ack_never_reports_progress(self):
        callback=Mock();monitor=Monitor(callback)
        with patch('swupdate_progress.socket.socket'),patch.object(monitor,'receive',return_value=ACK.pack(0x30000,b'ACK\0')):
            monitor.run()
        callback.assert_not_called()

    def test_monitor_reports_only_valid_progress(self):
        seen=[]
        monitor=Monitor(lambda value:(seen.append(value),monitor.stop.set()))
        with patch('swupdate_progress.socket.socket'),patch.object(monitor,'receive',side_effect=[ACK.pack(VERSION,b'ACK\0'),record()]):
            monitor.run()
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0]['percent'],42)


if __name__=='__main__':unittest.main()
