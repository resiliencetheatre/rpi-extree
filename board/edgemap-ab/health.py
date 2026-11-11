"""Local Situation map readiness, independent of external network/GPS availability."""
import json
from pathlib import Path
import subprocess
import urllib.request


def ready():
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'situation-map.service']).returncode:
        return False
    # Ensure this slot contains the application, rather than only Apache's index.
    if not (Path('/opt/situation/web/index.html').is_file()
            and Path('/opt/situation/python-front.py').is_file()):
        return False
    try:
        # Ignore proxy environment and use a local non-PHP static readiness asset.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:8080/api/status', timeout=2) as response:
            return response.status == 200 and json.loads(response.read(1024)) == {'status': 'ok', 'service': 'Situation'}
    except (OSError, ValueError):
        return False
