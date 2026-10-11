#!/usr/bin/env python3
"""Stage the reviewed AMO uBlock Origin XPI for Firefox distribution installation.

The committed pin authenticates fetched bytes; Firefox verifies XPI signatures at
runtime. Presence of signature files alone is NOT cryptographic verification.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import zipfile

ADDON_ID = 'uBlock0@raymondhill.net'
MAX_PACKAGE = 16 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


def verify_xpi(data, pin):
    if len(data) != pin['size'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise ValueError('uBlock Origin package size/hash differs from reviewed AMO pin')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate XPI entries')
        for name in ('META-INF/mozilla.rsa', 'META-INF/mozilla.sf', 'META-INF/manifest.mf', 'META-INF/cose.sig'):
            if name not in names:
                raise ValueError('uBlock Origin signature envelope missing')
        if archive.getinfo('manifest.json').file_size > 128 * 1024:
            raise ValueError('unexpected manifest size')
        manifest = json.loads(archive.read('manifest.json'))
    gecko = manifest.get('browser_specific_settings', {}).get('gecko', {})
    if gecko.get('id') != ADDON_ID or manifest.get('version') != pin['version']:
        raise ValueError('uBlock Origin manifest identity/version differs from reviewed pin')
    if 'update_url' in gecko or 'update_url' in manifest:
        raise ValueError('unexpected custom update endpoint: retain standard AMO updates')


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('refusing non-HTTPS add-on redirect')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def get_package(pin, cached):
    if cached.exists():
        if cached.is_symlink() or not cached.is_file():
            raise ValueError('cached XPI must be a regular file')
        with cached.open('rb') as stream:
            data = stream.read(MAX_PACKAGE + 1)
    else:
        with urllib.request.build_opener(HTTPSRedirects()).open(pin['url'], timeout=60) as response:
            data = response.read(MAX_PACKAGE + 1)
    verify_xpi(data, pin)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Firefox source lw/ublock-origin directory; doubles as verified cache')
    args = parser.parse_args()
    try:
        pin = json.loads((ROOT / 'settings/ublock-origin.json').read_text())
        if (pin['addon_id'] != ADDON_ID or pin['amo_id'] != 607454 or
                pin['amo_author_id'] != 11423598 or pin['amo_author'] != 'gorhill' or
                not pin['url'].startswith('https://addons.mozilla.org/firefox/downloads/file/') or
                not 0 < pin['size'] <= MAX_PACKAGE):
            raise ValueError('invalid reviewed AMO ownership/download pin')
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f'{ADDON_ID}.xpi'
        data = get_package(pin, output)
        if not output.exists():
            descriptor, temporary = tempfile.mkstemp(prefix='.ubo-', dir=args.output_dir)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(data)
                os.chmod(temporary, 0o644)
                os.replace(temporary, output)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        print(f"Staged reviewed uBlock Origin {pin['version']} ({len(data)} bytes): {output}")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'uBlock Origin staging failed: {error}\n'
                    'Do not package without the blocker. For a stale/corrupt cache, remove only\n'
                    'the staged XPI and rerun with network access after reviewing the pin.\n')


if __name__ == '__main__':
    main()
