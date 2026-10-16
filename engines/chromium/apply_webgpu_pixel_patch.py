#!/usr/bin/env python3
"""Apply/verify selective Metal WebGPU pixels after worker/GPU privacy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.source_root.resolve(strict=True)
    here = Path(__file__).resolve().parent
    lock = json.loads((here/'webgpu-pixel-patch-lock.json').read_text())
    inherited = {}
    def ancestors(name):
        parent = json.loads((here/name).read_text())
        if parent.get('applyAfter'):
            ancestors(parent['applyAfter'])
        for entry in parent['inputs']:
            inherited[entry['path']] = entry
    ancestors(lock['applyAfter'])
    changed = {entry['path'] for entry in lock['inputs']}
    for path, entry in inherited.items():
        if path not in changed and digest(root/path) != entry['afterSha256']:
            raise SystemExit('Native privacy prerequisite missing/changed: '+path)
    states = []
    for entry in lock['inputs']:
        path = root/entry['path']
        if not path.resolve().is_relative_to(root):
            raise SystemExit('Patch input escapes source root')
        actual = digest(path)
        if actual == entry['afterSha256']:
            states.append('patched')
        elif actual == entry['beforeSha256']:
            states.append('original')
        else:
            raise SystemExit('Unexpected source input: '+entry['path'])
    if all(state == 'patched' for state in states):
        print('Verified selective WebGPU pixel patch and inherited native privacy hashes')
        return
    if args.check or any(state != 'original' for state in states):
        raise SystemExit('WebGPU pixel patch missing or partially applied; restore pinned inputs first')
    command = ['patch','-p1','--batch','--forward','-i',str(here/lock['patch'])]
    subprocess.run(command+['--dry-run'],cwd=root,check=True)
    subprocess.run(command,cwd=root,check=True)
    for entry in lock['inputs']:
        assert digest(root/entry['path']) == entry['afterSha256']
    print('Applied and verified selective WebGPU pixel privacy patch')


if __name__ == '__main__':
    main()
