#!/usr/bin/env python3
"""Emit a self-contained Pi repair without copying or rehashing the package pool."""
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('output', type=Path)
a = p.parse_args()
base = Path(__file__).resolve().parent
early = (base / 'preseed/early.sh').read_text()
hook = early[early.index('# In apt-setup 0.198,'):]
template = (base / 'repair-installer-policy.sh.in').read_text()
a.output.write_text(template.replace('@POLICY_HOOK@', hook))
a.output.chmod(0o755)
print(a.output)
