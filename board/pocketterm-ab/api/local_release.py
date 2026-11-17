"""Local filesystem transport for the shared verified publication engine."""
import json
import os
from pathlib import Path
import shutil
import tempfile
from public_release import log


class LocalBackend:
    def __init__(self, host):
        host = Path(host)
        if not host.is_absolute() or not (host/'host.json').is_file():
            raise ValueError('An absolute initialized local HTTPS host is required')
        self.root = host/'www'
        if not self.root.is_dir() or self.root.is_symlink():
            raise ValueError('Local document root must be a real directory')

    def path(self, value):
        value = str(value)
        if not value.startswith('local:root/'):
            raise ValueError('Invalid local publication path')
        name = value[len('local:root/'):]
        if not name or '/' in name or name in ('.', '..'):
            raise ValueError('Invalid publication filename')
        result = self.root/name
        if result.is_symlink():
            raise ValueError('Publication symlinks are not allowed')
        return result

    def flush(self):
        fd = os.open(self.root, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def __call__(self, action, *args):
        log(f'Local publication: {action}')
        if action == 'backend':
            return b'{"Features":{"Move":true}}'
        if action == 'lsjson':
            return json.dumps([dict(Name=p.name) for p in self.root.iterdir()]).encode()
        if action == 'cat':
            return self.path(args[0]).read_bytes()
        if action == 'copyto':
            source, destination = Path(args[0]), self.path(args[1])
            # Stage on this filesystem, flush, then publish without overwriting
            # an existing immutable name. A failed copy never exposes a partial SWU.
            with tempfile.NamedTemporaryFile(dir=self.root, prefix='.copy-', delete=False) as out:
                stage = Path(out.name)
                try:
                    with source.open('rb') as stream:
                        shutil.copyfileobj(stream, out, 1024**2)
                    out.flush()
                    os.fsync(out.fileno())
                    os.link(stage, destination)
                finally:
                    stage.unlink(missing_ok=True)
            self.flush()
            return b''
        if action == 'moveto':
            source, destination = self.path(args[0]), self.path(args[1])
            if not source.name.startswith('.latest-') or destination.name != 'latest.json':
                raise ValueError('Only staged metadata may replace latest.json')
            os.replace(source, destination)
            self.flush()
            return b''
        raise ValueError('Unsupported local publication action')
