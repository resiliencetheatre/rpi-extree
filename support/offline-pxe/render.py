#!/usr/bin/env python3
"""Render the target overlay or a generation's installer configuration."""
import argparse
import json
from pathlib import Path
from common import settings, write


def target(s, root):
    a, iface = s['address'], s['interface']
    write(root, 'etc/offline-pxe/settings.json', json.dumps(s, indent=2)+'\n')
    write(root, 'etc/offline-pxe/runtime.conf', f"SSD_UUID='{s['ssd_uuid']}'\nSERVER='{a}'\nINTERFACE='{iface}'\n")
    write(root, 'etc/offline-pxe/upstream-urls', '\n'.join([
        s['debian_upstream'].rstrip('/')+'/dists/'+s['codename']+'/InRelease',
        s['debian_upstream'].rstrip('/')+'/dists/'+s['codename']+'-updates/InRelease',
        s['security_upstream'].rstrip('/')+'/dists/'+s['codename']+'-security/InRelease',
    ])+'\n')
    write(root, 'etc/systemd/network/10-offline.network', f'''[Match]
Name={iface}
[Link]
RequiredForOnline=no
[Network]
Address={s['server']}
DHCP=no
DHCPServer=no
IPv6AcceptRA=no
LinkLocalAddressing=no
LLMNR=no
MulticastDNS=no
ConfigureWithoutCarrier=yes
''')
    write(root, 'etc/dnsmasq.conf', f'''interface={iface}
bind-dynamic
no-resolv
no-hosts
domain-needed
bogus-priv
local=/home.arpa/
local=/#/
domain=home.arpa
host-record=pxe.home.arpa,{a}
dhcp-authoritative
dhcp-range={s['pool_start']},{s['pool_end']},{s['netmask']},12h
dhcp-option=option:router
dhcp-option=option:dns-server,{a}
dhcp-leasefile=/run/offline-pxe/dnsmasq/leases
pid-file=/run/offline-pxe/dnsmasq/dnsmasq.pid
log-facility=-
enable-tftp
tftp-root=/srv/offline/current/tftp
dhcp-match=set:bios,option:client-arch,0
dhcp-match=set:efi64,option:client-arch,7
dhcp-match=set:efi64,option:client-arch,9
dhcp-boot=tag:bios,pxelinux.0,,{a}
dhcp-boot=tag:efi64,debian-installer/amd64/bootnetx64.efi,,{a}
''')
    locations=''
    for url, path in [('debian','/srv/offline/current/debian'), ('debian-security','/srv/offline/current/debian-security'), ('preseed','/srv/offline/current/www/preseed'), ('status','/run/offline-pxe/status')]:
        locations += f'        location /{url}/ {{ alias {path}/; autoindex off; }}\n'
    write(root, 'etc/nginx/nginx.conf', f'''user nobody nobody;
worker_processes 1;
pid /run/offline-pxe/nginx.pid;
error_log stderr warn;
events {{ worker_connections 256; }}
http {{
    access_log off;
    default_type application/octet-stream;
    sendfile on;
    client_body_temp_path /run/offline-pxe/nginx/client-body;
    proxy_temp_path /run/offline-pxe/nginx/proxy;
    fastcgi_temp_path /run/offline-pxe/nginx/fastcgi;
    uwsgi_temp_path /run/offline-pxe/nginx/uwsgi;
    scgi_temp_path /run/offline-pxe/nginx/scgi;
    server {{
        listen {a}:80;
        server_name pxe.home.arpa;
        disable_symlinks off;
{locations}        location / {{ return 404; }}
    }}
}}
''')
    write(root, 'etc/systemd/system/srv-offline.mount', f'''[Unit]
Description=Offline Debian data partition (read only while serving)
JobTimeoutSec=20s
[Mount]
What=/dev/disk/by-uuid/{s['ssd_uuid']}
Where=/srv/offline
Type=ext4
Options=ro,nosuid,nodev,noexec
TimeoutSec=15
[Install]
WantedBy=multi-user.target
''')
    for name, command in [('dnsmasq','/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/etc/dnsmasq.conf'), ('nginx','/usr/sbin/nginx -g "daemon off;"')]:
        write(root, f'etc/systemd/system/offline-{name}.service', f'''[Unit]
Description=Offline PXE {name}
RequiresMountsFor=/srv/offline
BindsTo=srv-offline.mount
After=srv-offline.mount systemd-networkd.service
[Service]
ExecStartPre=/usr/sbin/offline-ready
ExecStart={command}
Restart=on-failure
RestartSec=10
RuntimeDirectory=offline-pxe/{name}
RuntimeDirectoryMode=0755
ReadOnlyPaths=/srv/offline
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=/run/offline-pxe
PrivateTmp=yes
''')
    write(root, 'etc/systemd/system/offline-recover.service', '''[Unit]
Description=Retry offline installer services after storage recovery
[Service]
Type=oneshot
ExecStart=/usr/sbin/offline-recover
''')
    write(root, 'etc/systemd/system/offline-recover.timer', '''[Unit]
Description=Retry offline storage and installer readiness
[Timer]
OnBootSec=20s
OnUnitActiveSec=30s
[Install]
WantedBy=timers.target
''')
    write(root, 'etc/systemd/journald.conf.d/offline.conf', '[Journal]\nStorage=volatile\nRuntimeMaxUse=32M\nRateLimitIntervalSec=30s\nRateLimitBurst=200\n')
    write(root, 'etc/sysctl.d/90-offline.conf', 'net.ipv4.ip_forward=0\nnet.ipv6.conf.all.forwarding=0\n')


def generation(s, root):
    root=Path(root); a=s['address']; c=s['codename']
    components=' '.join(s['components'])
    sources=''
    for archive, suites in [('debian',f'{c} {c}-updates'), ('debian-security',f'{c}-security')]:
        sources+=f'''Types: {'deb deb-src' if s['sources'] else 'deb'}
URIs: http://{a}/{archive}
Suites: {suites}
Components: {components}
Architectures: {' '.join(s['architectures'])}
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
Check-Valid-Until: no
By-Hash: no

'''
    write(root, 'www/preseed/offline.sources', sources)
    template=(Path(__file__).parent/'preseed/offline.cfg.in').read_text()
    for k,v in [('ADDRESS',a),('CODENAME',c),('COMPONENTS',components)]:
        template=template.replace('@'+k+'@', v)
    for profile in ('offline','interactive'):
        text=template
        if profile=='interactive':
            text+='\nd-i debconf/priority select high\n'
        write(root, f'www/preseed/{profile}.cfg', text)
    # Network preseeding must be on the kernel command line: fetching the HTTP
    # preseed itself requires the initial network configuration to finish.
    network=f'interface=auto netcfg/get_nameservers={a}'
    args=f'auto=true priority=critical {network} preseed/url=http://{a}/preseed/offline.cfg'
    interactive=f'priority=high {network} preseed/url=http://{a}/preseed/interactive.cfg'
    # Stock Debian loaders and modules are preserved; only entry configuration changes.
    write(root, 'tftp/debian-installer/amd64/boot-screens/syslinux.cfg', f'''DEFAULT offline
PROMPT 1
TIMEOUT 100
SAY Enter offline (guided) or interactive; disk changes always require confirmation.
LABEL offline
 KERNEL debian-installer/amd64/linux
 APPEND initrd=debian-installer/amd64/initrd.gz {args} ---
LABEL interactive
 KERNEL debian-installer/amd64/linux
 APPEND initrd=debian-installer/amd64/initrd.gz {interactive} ---
''')
    write(root, 'tftp/debian-installer/amd64/grub/grub.cfg', f'''set default=0
set timeout=10
menuentry 'Offline Debian guided installation' {{
 linux /debian-installer/amd64/linux {args} ---
 initrd /debian-installer/amd64/initrd.gz
}}
menuentry 'Interactive local installation' {{
 linux /debian-installer/amd64/linux {interactive} ---
 initrd /debian-installer/amd64/initrd.gz
}}
''')
    for name in ('early.sh','late.sh'):
        text=(Path(__file__).parent/'preseed'/name).read_text().replace('@ADDRESS@',a)
        write(root, 'www/preseed/'+name, text, 0o755)
    write(root, 'settings.json', json.dumps(s, indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['target','generation']); p.add_argument('settings'); p.add_argument('destination')
    args=p.parse_args(); globals()[args.mode](settings(args.settings), args.destination)
