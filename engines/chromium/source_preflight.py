"""Read-only preflight for a Chromium/CEF source build; never installs tools."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.build_root.resolve(strict=True)
    info = {}
    for location in (root, *root.parents):
        disk = subprocess.run(['diskutil', 'info', '-plist', str(location)], capture_output=True)
        if disk.returncode == 0:
            info = plistlib.loads(disk.stdout)
            break
    xcode = subprocess.run(['xcodebuild', '-version'], capture_output=True, text=True)
    sdk = subprocess.run(['xcrun', '--sdk', 'macosx', '--show-sdk-version'], capture_output=True, text=True)
    free = shutil.disk_usage(root).free
    problems = []
    if xcode.returncode or not xcode.stdout.startswith('Xcode '):
        problems.append('Full Xcode is not available in the active developer directory')
    if info.get('FilesystemType', '').lower() != 'apfs':
        problems.append('Chromium source builds require an APFS volume')
    if free < 128 * 1024 ** 3:
        problems.append('Less than the prototype source-build budget of 128 GiB free')
    result = {'ready': not problems, 'buildRoot': str(root), 'filesystem': info.get('FilesystemType'),
        'freeBytes': free, 'sourceBuildBudgetGiB': 128,
        'xcode': xcode.stdout.strip() if not xcode.returncode else None,
        'sdkVersion': sdk.stdout.strip() if not sdk.returncode else None, 'problems': problems}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ready'] else 2)


if __name__ == '__main__':
    main()
