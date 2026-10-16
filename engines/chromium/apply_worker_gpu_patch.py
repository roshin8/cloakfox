#!/usr/bin/env python3
"""Apply/verify worker+GPU privacy after the pinned native canvas patch."""
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
    lock = json.loads((here/'worker-gpu-patch-lock.json').read_text())
    parent = json.loads((here/lock['applyAfter']).read_text())
    changed = {entry['path'] for entry in lock['inputs']}
    # The follow-up supersedes overlapping parent hashes, while untouched parent
    # hooks (2D/export/build registration) must still match the pinned baseline.
    for entry in parent['inputs']:
        if entry['path'] not in changed and digest(root/entry['path']) != entry['afterSha256']:
            raise SystemExit('Native canvas prerequisite missing/changed: '+entry['path'])
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
        print('Verified worker/GPU patch and untouched canvas prerequisite hashes')
        return
    if args.check or any(state != 'original' for state in states):
        raise SystemExit('Worker/GPU patch missing or partially applied; restore pinned inputs first')
    command = ['patch','-p1','--batch','--forward','-i',str(here/lock['patch'])]
    subprocess.run(command+['--dry-run'],cwd=root,check=True)
    subprocess.run(command,cwd=root,check=True)
    for entry in lock['inputs']:
        assert digest(root/entry['path']) == entry['afterSha256']
    print('Applied and verified worker/GPU privacy patch')


if __name__ == '__main__':
    main()
