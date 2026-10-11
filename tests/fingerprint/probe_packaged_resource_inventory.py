"""Assert the actual packaged resource inventory, including removed assets.
Run with CLOAKFOX_BIN pointing to the binary inside a mounted development DMG.
"""
import os
from pathlib import Path
import zipfile


def check_packaged_resources(binary):
    resources=Path(binary).parents[1]/'Resources'
    with zipfile.ZipFile(resources/'omni.ja') as archive:
        names=archive.namelist()
        for suffix in ['html','js','css']:
            assert any(n.endswith('content/global/crashes.'+suffix) for n in names),suffix
    with zipfile.ZipFile(resources/'browser/omni.ja') as archive:
        names=archive.namelist()
        assert not any(n.endswith('browser-development-helpers.js') for n in names), 'obsolete helper shipped'
        main=next(n for n in names if n.endswith('content/browser/browser-main.js'))
        assert b'browser-development-helpers.js' not in archive.read(main), 'helper startup call shipped'
        manifests=[n for n in names if n.endswith('.manifest')]
        assert manifests, 'no browser manifests found'
        assert all(b'DevelopmentHelpers.init' not in archive.read(n) for n in manifests), 'helper category registration shipped'
    print('PASS: packaged crash resources and development-helper removal')

if __name__=='__main__': check_packaged_resources(os.environ['CLOAKFOX_BIN'])
