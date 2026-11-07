"""Factory-only Data growth. Routine bundles never carry the opt-in marker."""
import json
import os
from pathlib import Path
import subprocess
from common import PROFILE, LAYOUT, SIZES, UUIDS

MARKER = Path('/data/.reterminal-factory-grow-v1')
BACKUP = Path('/data/ab/factory-partitions-before.json')
DONE = Path('/data/ab/factory-growth.json')

def table(disk):
    return json.loads(subprocess.check_output(['sfdisk', '--json', disk]))['partitiontable']

def validate_table(value):
    assert value['label'] == 'gpt' and value['unit'] == 'sectors' and value['sectorsize'] == 512
    entries = value['partitions']
    assert len(entries) == 6, 'factory growth requires exactly six partitions'
    start = 2048
    for i, entry in enumerate(entries):
        assert entry['uuid'].lower() == UUIDS[i] and entry['start'] == start
        minimum = SIZES[i] * 2048
        assert entry['size'] >= minimum if i == 5 else entry['size'] == minimum
        start += entry['size']
    assert start - 1 <= value['lastlba']
    return entries

def check_preserved(before, after):
    old, new = validate_table(before), validate_table(after)
    assert before['id'] == after['id'] and before['firstlba'] == after['firstlba']
    assert old[:5] == new[:5], 'boot/root partitions changed'
    assert {k:v for k,v in old[5].items() if k != 'size'} == {k:v for k,v in new[5].items() if k != 'size'}
    assert new[5]['size'] >= old[5]['size'], 'Data must never shrink'

def grow_factory_data(parts, slot, trial, state, run, atomic):
    if not MARKER.exists():
        return
    assert MARKER.read_text() == f'{PROFILE} {LAYOUT}\n', 'invalid factory growth marker'
    assert slot == 'a' and not trial and not state, 'growth only permitted on initial factory Boot A'
    # Called after Data mount validation and before any persistence bind mounts.
    assert not any(m for m in parts[5]['mountpoints'] or [] if m != '/data'), 'Data already in use'
    disk, data = parts[5]['pkname'], parts[5]['name']
    before = table(disk)
    validate_table(before)
    if not BACKUP.exists():
        atomic(BACKUP, json.dumps(before, sort_keys=True).encode())
    else:
        check_preserved(json.loads(BACKUP.read_text()), before)
    options = ['--lock=yes', '--no-reread', '--no-tell-kernel']
    # Move backup GPT to the physical media end, then grow only partition 6.
    run('sfdisk', *options, '--relocate', 'gpt-bak-std', disk)
    relocated = table(disk)
    check_preserved(before, relocated)
    assert relocated['partitions'] == before['partitions']
    start = relocated['partitions'][5]['start']
    size = relocated['lastlba'] - start + 1
    assert size >= before['partitions'][5]['size']
    if size > before['partitions'][5]['size']:
        run('sfdisk', *options, '--wipe', 'never', '--wipe-partitions', 'never',
            '-N', '6', disk, input=f'start={start}, size={size}\n', text=True)
    after = table(disk)
    check_preserved(before, after)
    assert after['partitions'][5]['size'] == size
    os.sync()
    # BLKPG updates only partition 6, without rereading the mounted root entries.
    # Replay this even when the table already grew before a previous reset.
    run('partx', '--update', '--nr', '6', disk)
    actual = int(subprocess.check_output(['blockdev', '--getsize64', data]).strip())
    assert actual == size * 512, 'kernel has not accepted new Data size'
    run('resize2fs', data)
    os.sync()
    atomic(DONE, json.dumps(dict(profile=PROFILE, layout=LAYOUT, bytes=actual), sort_keys=True).encode())
    MARKER.unlink()
    fd = os.open(MARKER.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
