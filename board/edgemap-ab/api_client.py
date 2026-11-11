#!/usr/bin/env python3
"""CLI test client for API v1; independent local installer remains available."""
import argparse
import json
import socket
import sys
import time
import uuid


def call(socket_path, method, params):
    identity = uuid.uuid4().hex
    request = dict(api=1, id=identity, method=method, params=params)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(30)
        connection.connect(str(socket_path))
        connection.sendall(json.dumps(request).encode() + b'\n')
        with connection.makefile('rb') as stream:
            raw = stream.readline(131073)
        if len(raw) > 131072 or not raw.endswith(b'\n'):
            raise ValueError('Invalid response framing')
    response = json.loads(raw)
    if response.get('api') != 1 or response.get('id') != identity:
        raise ValueError('API response ID/version mismatch')
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', default='/run/edgemap-update-api/control.sock')
    commands = parser.add_subparsers(dest='method', required=True)
    for name in ('status', 'check', 'cancel'):
        commands.add_parser(name)
    for name in ('download', 'install'):
        command = commands.add_parser(name)
        command.add_argument('--offer', required=True)
        command.add_argument('--accept', action='store_true', help='Explicitly accept this exact release')
    finish = commands.add_parser('finish')
    finish.add_argument('--accept', action='store_true')
    wait = commands.add_parser('wait')
    wait.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args()
    params = dict(offer_id=args.offer, accept=args.accept) if args.method in ('download', 'install') else (dict(accept=args.accept) if args.method == 'finish' else {})
    deadline = time.monotonic() + getattr(args, 'timeout', 0)
    try:
        while True:
            response = call(args.socket, 'status' if args.method == 'wait' else args.method, params)
            if args.method != 'wait' or not response['ok'] or response['result']['job']['phase'] not in ('checking', 'downloading', 'installing'):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Polling deadline exceeded; the job was not cancelled')
            time.sleep(0.5)
        print(json.dumps(response, indent=2))
        if not response['ok']:
            return 2
        if args.method == 'wait' and response['result']['job']['phase'] in ('failed', 'interrupted', 'cancelled'):
            return 3
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
