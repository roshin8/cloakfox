#!/usr/bin/env python3
"""Stage pinned AMO container extensions. Firefox verifies signatures on installation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile
from stage_ublock import HTTPSRedirects, MAX_PACKAGE
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {'@testpilot-containers', '{c607c8df-14a7-4f28-894f-29e8722976af}'}

def verify(data, pin):
    if len(data) != pin['size'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise ValueError('Container extension size/hash mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate XPI entries')
        for name in ['META-INF/mozilla.rsa','META-INF/mozilla.sf','META-INF/manifest.mf','META-INF/cose.sig']:
            if name not in names:
                raise ValueError('Missing signature envelope')
        if archive.getinfo('manifest.json').file_size > 128 * 1024:
            raise ValueError('Manifest too large')
        manifest = json.loads(archive.read('manifest.json'))
    gecko = manifest.get('browser_specific_settings',manifest.get('applications',{})).get('gecko',{})
    if gecko.get('id') != pin['addon_id'] or manifest.get('version') != pin['version']:
        raise ValueError('Extension identity/version mismatch')
    if 'update_url' in gecko or 'update_url' in manifest:
        raise ValueError('Unexpected custom update URL')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    pins=json.loads((ROOT/'settings/container-addons.json').read_text())
    if len(pins)!=2 or {pin['addon_id'] for pin in pins}!=EXPECTED_IDS:
        raise ValueError('Unexpected bundled extension IDs')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for pin in pins:
        if not pin['url'].startswith('https://addons.mozilla.org/firefox/downloads/file/') or not 0 < pin['size'] <= MAX_PACKAGE:
            raise ValueError('Invalid AMO package pin')
        output=args.output_dir/(pin['addon_id']+'.xpi')
        if output.is_symlink():
            raise ValueError('Cache must not be a symlink')
        if output.exists():
            with output.open('rb') as stream:data=stream.read(MAX_PACKAGE+1)
        else:
            with urllib.request.build_opener(HTTPSRedirects()).open(pin['url'],timeout=60) as response:data=response.read(MAX_PACKAGE+1)
        verify(data,pin)
        if not output.exists():output.write_bytes(data)
        print(f"Staged {pin['addon_id']} {pin['version']}")

if __name__=='__main__':main()
