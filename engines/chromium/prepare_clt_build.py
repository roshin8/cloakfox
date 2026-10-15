"""Apply the opt-in CLT GN adaptation to the pinned Chromium source tree only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def prepare(root):
    lock = json.loads((HERE / 'clt-build-lock.json').read_text())
    gni = root / lock['path']
    data = gni.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    helper = root / 'build/config/apple/clt_sdk_info.py'
    bundled_helper = HERE / 'clt_sdk_info.py'
    backup = gni.with_suffix('.gni.cloakfox-original')
    if digest not in (lock['originalSha256'], lock['patchedSha256']):
        raise ValueError('Unsupported Chromium GN input; refusing to patch changed source')
    if backup.exists() and hashlib.sha256(backup.read_bytes()).hexdigest() != lock['originalSha256']:
        raise ValueError('Existing original backup differs; refusing to overwrite')
    if helper.exists() and helper.read_bytes() != bundled_helper.read_bytes():
        raise ValueError('Existing CLT helper differs; refusing to overwrite')
    if digest == lock['patchedSha256']:
        if not backup.exists() or not helper.exists():
            raise ValueError('Incomplete prior CLT preparation; restore the pinned input before retrying')
        return
    patch = HERE / 'patches/command-line-tools.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root, check=True, timeout=20)
    # Preserve recovery input before changing the source. A failed apply can
    # safely be retried; never leave a changed GN file without its original.
    backup.write_bytes(data)
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundled_helper, helper)
    subprocess.run(['git', 'apply', str(patch)], cwd=root, check=True, timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.source_root.resolve(strict=True))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + '\n')
    print('CLT preparation complete. Opt in with mac_use_command_line_tools=true, use_system_xcode=true, is_official_build=false.')


if __name__ == '__main__':
    main()
