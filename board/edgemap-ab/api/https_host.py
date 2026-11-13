#!/usr/bin/env python3
"""LAN-only lab HTTPS artifact host. Never builds, signs releases or installs."""
import argparse
import http.server
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import urllib.parse

PORT = 9443


def initialize(directory, address, port=PORT):
    address = str(ipaddress.IPv4Address(address))
    if not 1024 <= port <= 65535:
        raise ValueError('Choose an unprivileged TCP port (1024..65535)')
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Directory is not empty; reuse serve or choose a fresh directory. Existing TLS trust is never overwritten.')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    tls, www = directory / 'tls', directory / 'www'
    tls.mkdir(mode=0o700)
    www.mkdir(mode=0o755)
    def openssl(*args):
        result = subprocess.run(['openssl', *map(str, args)], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
    ca_key, ca = tls / 'ca-key.pem', tls / 'ca.pem'
    server_key, csr, cert = tls / 'server-key.pem', tls / 'server.csr', tls / 'server.pem'
    openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',ca_key)
    ca_key.chmod(0o600)
    openssl('req','-new','-x509','-sha256','-days','365','-key',ca_key,
            '-subj','/CN=EdgeMap local update test CA',
            '-addext','basicConstraints=critical,CA:TRUE,pathlen:0',
            '-addext','keyUsage=critical,keyCertSign,cRLSign',
            '-addext','subjectKeyIdentifier=hash','-out',ca)
    openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',server_key)
    server_key.chmod(0o600)
    openssl('req','-new','-sha256','-key',server_key,'-subj',f'/CN={address}','-out',csr)
    ext = tls / 'server-extensions.cnf'
    ext.write_text('basicConstraints=critical,CA:FALSE\n'
                   'keyUsage=critical,digitalSignature,keyEncipherment\n'
                   'extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\n'
                   'authorityKeyIdentifier=keyid,issuer\n'
                   f'subjectAltName=IP:{address},IP:127.0.0.1,DNS:localhost\n')
    openssl('x509','-req','-sha256','-days','30','-in',csr,'-CA',ca,'-CAkey',ca_key,
            '-CAcreateserial','-extfile',ext,'-out',cert)
    openssl('verify','-CAfile',ca,'-verify_ip',address,cert)
    config = dict(address=address, port=port)
    (directory / 'host.json').write_text(json.dumps(config, indent=2) + '\n')
    (www / 'health.json').write_text(json.dumps(dict(service='edgemap-update-test-host', https=True)) + '\n')
    return config


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'EdgeMapTestHost/1'

    def do_GET(self):
        self.send_file(head=False)

    def do_HEAD(self):
        self.send_file(head=True)

    def send_file(self, head):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        name = path.lstrip('/')
        allowed = (name in ('health.json','latest.json') or
                   re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\.(swu|SHA256SUMS)', name))
        if not allowed or path != '/' + name:
            self.send_error(404)
            return
        source = self.server.www / name
        if source.is_symlink() or not source.is_file():
            self.send_error(404)
            return
        with source.open('rb') as stream:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json' if name.endswith('.json') else 'application/octet-stream')
            self.send_header('Content-Length', str(os.fstat(stream.fileno()).st_size))
            self.send_header('Cache-Control', 'no-store' if name.endswith('.json') else 'no-cache')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            if not head:
                shutil.copyfileobj(stream, self.wfile, 1024**2)


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def get_request(self):
        connection, peer = self.socket.accept()
        connection.settimeout(30)
        try:
            return self.context.wrap_socket(connection, server_side=True), peer
        except Exception:
            connection.close()
            raise


def serve(directory):
    directory = directory.resolve()
    config = json.loads((directory / 'host.json').read_text())
    address = str(ipaddress.IPv4Address(config['address']))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(directory / 'tls/server.pem', directory / 'tls/server-key.pem')
    with Server((address, config['port']), Handler) as server:
        server.www = directory / 'www'
        server.context = context
        print(f"Serving ONLY {server.www} at https://{address}:{config['port']}/", flush=True)
        print('Read-only lab server. No uploads, directory listings, firewall changes or updates.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Generate a separate local TLS CA and server certificate')
    init.add_argument('--directory', type=Path, required=True)
    init.add_argument('--address', required=True)
    init.add_argument('--port', type=int, default=PORT)
    start = commands.add_parser('serve', help='Start a read-only HTTPS server on the configured LAN IP')
    start.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if not args.directory.is_absolute():
        parser.error('Use an absolute host directory')
    if args.command == 'init':
        config = initialize(args.directory, args.address, args.port)
        print(f"Prepared https://{config['address']}:{config['port']}/health.json")
        print(f'Copy only {args.directory.resolve()}/tls/ca.pem to EdgeMap, never the private keys.')
        print('No server started and no UFW rule changed.')
    else:
        serve(args.directory)


if __name__ == '__main__':
    main()
