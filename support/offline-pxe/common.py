"""Shared settings and path validation for desk and the Pi 5 manual updater."""
import hashlib
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def settings(path):
    s = json.loads(Path(path).read_text())
    net = ipaddress.IPv4Interface(s['server'])
    if net.network.prefixlen != 24 or net.ip in (net.network.network_address, net.network.broadcast_address):
        raise ValueError('Choose a usable server address in a /24 installation LAN')
    pool = [ipaddress.IPv4Address(s[k]) for k in ('pool_start', 'pool_end')]
    if not all(p in net.network and p not in (net.ip, net.network.network_address, net.network.broadcast_address) for p in pool) or pool[0] > pool[1] or pool[0] <= net.ip <= pool[1]:
        raise ValueError('Invalid or overlapping DHCP pool')
    if s['interface'] != 'eth0':
        raise ValueError('This board uses net.ifnames=0 and eth0; verify hardware before changing naming policy')
    if s['codename'] != 'trixie':
        raise ValueError('Installer integration is reviewed for trixie only')
    if s['architectures'] not in (['amd64'], ['amd64', 'i386']):
        raise ValueError('Only amd64 with optional i386 co-architecture is supported')
    if s['components'] != ['main', 'contrib', 'non-free', 'non-free-firmware']:
        raise ValueError('Complete four-component coverage is required')
    if not isinstance(s['sources'], bool):
        raise ValueError('sources must be boolean')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', s['generation']):
        raise ValueError('Unsafe generation name')
    if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', s['ssd_uuid']):
        raise ValueError('Use an ext4 filesystem UUID')
    for name in ('debian_upstream', 'security_upstream'):
        url = urlsplit(s[name])
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in s[name])):
            raise ValueError('Use HTTPS upstream archive roots without credentials, query or whitespace')
    s['address'] = str(net.ip)
    s['netmask'] = str(net.network.netmask)
    return s


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def confined(root, name):
    root = Path(root).resolve()
    p = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts or not p.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes archive: {name}')
    return p


def write(root, name, text, mode=0o644):
    p = Path(root) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    p.chmod(mode)


def netboot_uefi_links(tftp):
    """Expose Debian's signed second-stage loader and GRUB tree at TFTP root."""
    tftp = Path(tftp)
    for name in ('grubx64.efi', 'grub'):
        target = 'debian-installer/amd64/' + name
        if not confined(tftp, target).exists():
            raise ValueError('Missing Debian UEFI artifact: ' + target)
        link = tftp / name
        if link.is_symlink() and link.readlink() == Path(target):
            continue
        if link.exists() or link.is_symlink():
            raise ValueError('Unexpected existing TFTP entry: ' + str(link))
        link.symlink_to(target)
