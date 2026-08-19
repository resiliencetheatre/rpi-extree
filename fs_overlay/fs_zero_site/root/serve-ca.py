#!/usr/bin/env python3

import argparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--bind", default="192.168.50.1")
parser.add_argument("--directory", default="/var/www/certs")
args = parser.parse_args()

os.chdir(args.directory)

server = ThreadingHTTPServer(
    (args.bind, args.port),
    SimpleHTTPRequestHandler,
)

print(f"Serving {args.directory} on http://{args.bind}:{args.port}/")
server.serve_forever()
