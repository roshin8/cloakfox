#!/usr/bin/env python3
"""Replay the pinned, partial native canvas patch after the upstream CEF patches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--check', action='store_true', help='Only verify the patched sources')
    args = parser.parse_args()
    root = args.source_root.resolve(strict=True)
    here = Path(__file__).resolve().parent
    lock = json.loads((here / 'canvas-patch-lock.json').read_text())
    states = []
    for entry in lock['inputs']:
        path = root / entry['path']
        if not path.resolve().is_relative_to(root):
            raise SystemExit('Patch input escapes source root')
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual == entry['afterSha256']:
            states.append('patched')
        elif actual == entry['beforeSha256']:
            states.append('original')
        else:
            raise SystemExit('Unexpected source input: ' + entry['path'])
    if all(state == 'patched' for state in states):
        print('Verified native canvas patch source hashes')
        return
    if args.check or any(state != 'original' for state in states):
        raise SystemExit('Canvas patch missing or partially applied; restore pinned inputs first')
    patch = here / lock['patch']
    command = ['patch', '-p1', '--batch', '--forward', '-i', str(patch)]
    subprocess.run(command + ['--dry-run'], cwd=root, check=True)
    subprocess.run(command, cwd=root, check=True)
    for entry in lock['inputs']:
        assert hashlib.sha256((root / entry['path']).read_bytes()).hexdigest() == entry['afterSha256']
    print('Applied and verified native canvas patch')


if __name__ == '__main__':
    main()
