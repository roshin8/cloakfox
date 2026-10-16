#!/usr/bin/env python3
"""Fetch the compiler pinned by the committed Chromium source, for hosted tests."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import tarfile
import time
import urllib.error
import urllib.request


def download(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    commit = json.loads((root / 'engines/chromium/source-lock.json').read_text())['chromiumCommit']
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Invalid source commit')
    upstream = f'https://chromium.googlesource.com/chromium/src/+/{commit}/'
    update = base64.b64decode(download(upstream + 'tools/clang/scripts/update.py?format=TEXT')).decode()
    revision = re.search(r"^CLANG_REVISION = '([a-zA-Z0-9-]+)'", update, re.M)[1]
    subrevision = re.search(r'^CLANG_SUB_REVISION = (\d+)', update, re.M)[1]
    name = f'Mac_arm64/clang-{revision}-{subrevision}.tar.xz'
    deps = base64.b64decode(download(upstream + 'DEPS?format=TEXT')).decode()
    record = re.search(re.escape(name) + r"',\s*'sha256sum': '([a-f0-9]{64})',\s*'size_bytes': (\d+)", deps)
    if not record:
        raise ValueError('Compiler archive missing from pinned source DEPS')
    archive = download('https://commondatastorage.googleapis.com/chromium-browser-clang/' + name)
    if len(archive) != int(record[2]) or hashlib.sha256(archive).hexdigest() != record[1]:
        raise ValueError('Compiler archive size/SHA256 mismatch')
    args.destination.mkdir(parents=True, exist_ok=False)
    package = args.destination.parent / 'compiler.tar.xz'
    package.write_bytes(archive)
    with tarfile.open(package) as bundle:
        bundle.extractall(args.destination, filter='data')
    (args.destination.parent / 'compiler-provenance.json').write_text(json.dumps({
        'chromiumCommit': commit, 'archive': name, 'archiveSha256': record[1],
        'archiveSize': int(record[2])}, indent=2) + '\n')


if __name__ == '__main__':
    main()
