"""Fetch the exact official binary distribution pinned by cef-lock.json."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir', type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads(Path(__file__).with_name('cef-lock.json').read_text())
    cache = args.cache_dir.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / lock['archive']
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + '.partial')
        with urllib.request.urlopen(lock['downloadUrl'], timeout=30) as response, partial.open('wb') as target:
            while data := response.read(1024 * 1024):
                target.write(data)
        archive = partial
    with archive.open('rb') as source:
        actual = hashlib.file_digest(source, 'sha256').hexdigest()
    if archive.stat().st_size != lock['archiveSize'] or actual != lock['archiveSha256']:
        raise SystemExit('CEF archive verification failed; keep it aside and retry the official download')
    final = cache / lock['archive']
    if archive != final:
        archive.rename(final)
    destination = cache / lock['archive'].removesuffix('.tar.bz2')
    if not destination.exists():
        with tarfile.open(final) as bundle:
            bundle.extractall(cache, filter='data')
    print(destination)


if __name__ == '__main__':
    main()
