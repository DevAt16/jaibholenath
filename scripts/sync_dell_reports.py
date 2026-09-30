"""Pull private Dell report snapshots over pinned SSH; never run discovery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import os

MAX_BYTES = 250 * 1024 * 1024


def atomic_bytes(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.sync-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def sync_reports(output, fetch):
    output = Path(output)
    manifest_bytes = fetch('latest.json')
    if len(manifest_bytes) > 16384:
        raise ValueError('Manifest exceeds size limit.')
    manifest = json.loads(manifest_bytes)
    sid = manifest.get('snapshot_id', '')
    counts = ('baseline_candidates','database_candidates','overlapping_place_ids',
              'added_since_baseline','combined_candidates','geography_high_priority')
    if (manifest.get('schema_version') != 1 or not re.fullmatch(r'[a-f0-9]{64}', sid)
        or any(type(manifest.get(key)) is not int or manifest[key] < 0 for key in counts)
        or manifest['combined_candidates'] != manifest['baseline_candidates'] + manifest['added_since_baseline']
        or manifest['database_candidates'] != manifest['overlapping_place_ids'] + manifest['added_since_baseline']):
        raise ValueError('Invalid report manifest.')
    snapshot_path = output / 'snapshots' / (sid + '.json')
    if snapshot_path.exists():
        snapshot_bytes = snapshot_path.read_bytes()
    else:
        snapshot_bytes = fetch('snapshots/' + sid + '.json')
    if len(snapshot_bytes) > MAX_BYTES:
        raise ValueError('Snapshot exceeds size limit.')
    snapshot = json.loads(snapshot_bytes)
    encoded = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, sort_keys=True).encode()
    if hashlib.sha256(encoded).hexdigest() != sid:
        raise ValueError('Snapshot content does not match the manifest.')
    if snapshot.get('schema_version') != 1 or len(snapshot['reports']['candidates']) != manifest['combined_candidates']:
        raise ValueError('Snapshot candidate counts do not match.')
    # Publish the verified content before moving the pointer. Retain old snapshots.
    if not snapshot_path.exists(): atomic_bytes(snapshot_path, snapshot_bytes)
    old = output / 'latest.json'
    if old.exists() and json.loads(old.read_text()).get('snapshot_id') == sid:
        return {'status':'unchanged','snapshot_id':sid,'combined_candidates':manifest['combined_candidates']}
    atomic_bytes(old, manifest_bytes)
    return {'status':'synced','snapshot_id':sid,'combined_candidates':manifest['combined_candidates']}


def ssh_fetch(config, config_dir, relative):
    if relative != 'latest.json' and not re.fullmatch(r'snapshots/[a-f0-9]{64}\.json', relative):
        raise ValueError('Invalid report path.')
    host = config['host']
    remote = config['remote_directory']
    if not re.fullmatch(r'[A-Za-z0-9_-]+@[A-Za-z0-9.-]+', host) or not re.fullmatch(r'/[A-Za-z0-9_/-]+', remote):
        raise ValueError('Invalid SSH destination.')
    command = ['ssh','-T','-i',str(config_dir / config['key']),'-o','IdentitiesOnly=yes',
               '-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
               '-o','UserKnownHostsFile='+str(config_dir / config['known_hosts']),
               '-o','ConnectTimeout=5',host,
               'wsl.exe -d Ubuntu -u devashish --exec cat '+remote+'/'+relative]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.DEVNULL, check=True,
                       timeout=15 if relative == 'latest.json' else 150)
        if stream.tell() > MAX_BYTES: raise ValueError('Remote file exceeds size limit.')
        stream.seek(0)
        return stream.read()


def main():
    root = Path(__file__).resolve().parents[1]
    config_dir = root / '.node-access'
    if not (config_dir / 'config.json').exists():
        print(json.dumps({'status':'not_configured'})); return 0
    try:
        config = json.loads((config_dir / 'config.json').read_text())
        result = sync_reports(root / 'reports/expansion', lambda path: ssh_fetch(config, config_dir, path))
        print(json.dumps(result)); return 0
    except Exception as error:
        print(json.dumps({'status':'sync_failed','error_type':type(error).__name__,
                          'reason':'Retaining the last successful local snapshot.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
