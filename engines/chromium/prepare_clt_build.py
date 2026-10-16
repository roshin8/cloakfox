"""Apply the opt-in CLT GN adaptation to the pinned Chromium source tree only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(root):
    lock = json.loads((HERE / 'clt-build-lock.json').read_text())
    helper = root / 'build/config/apple/clt_sdk_info.py'
    bundled_helper = HERE / 'clt_sdk_info.py'
    legacy = lock['legacySdkPreparation']
    legacy_installed = (
        digest((root / lock['path']).read_bytes()) == legacy['patchedSha256']
        and helper.is_file() and digest(helper.read_bytes()) == legacy['helperSha256'])
    if helper.exists() and helper.read_bytes() != bundled_helper.read_bytes() and not legacy_installed:
        raise ValueError('Existing CLT helper differs; refusing to overwrite')
    inputs = [dict(lock, patch='command-line-tools.patch'), *lock.get('additionalPatches', [])]
    pending = []
    # Validate every input before changing any files, including the exact
    # previously shipped SDK/helper pair. Migrate it from its verified backup.
    with tempfile.TemporaryDirectory(prefix='cloakfox-clt-validate-') as temp:
        validation_root = Path(temp)
        for entry in inputs:
            source = root / entry['path']
            data = source.read_bytes()
            current = digest(data)
            backup = source.with_suffix(source.suffix + '.cloakfox-original')
            migrating = entry['path'] == lock['path'] and legacy_installed
            if current not in (entry['originalSha256'], entry['patchedSha256']) and not migrating:
                raise ValueError('Unsupported Chromium GN input; refusing to patch changed source: ' + entry['path'])
            if backup.exists() and digest(backup.read_bytes()) != entry['originalSha256']:
                raise ValueError('Existing original backup differs; refusing to overwrite')
            if current == entry['patchedSha256'] or migrating:
                if not backup.exists() or not helper.exists():
                    raise ValueError('Incomplete prior CLT preparation; restore the pinned input before retrying')
                if not migrating:
                    continue
                data = backup.read_bytes()
            patch = HERE / 'patches' / entry['patch']
            validation_input = validation_root / entry['path']
            validation_input.parent.mkdir(parents=True, exist_ok=True)
            validation_input.write_bytes(data)
            subprocess.run(['git', 'apply', '--check', str(patch)], cwd=validation_root, check=True, timeout=20)
            pending.append((source, backup, data, patch, entry['patchedSha256']))
        for source, backup, data, patch, expected in pending:
            backup.write_bytes(data)
            source.write_bytes(data)
            subprocess.run(['git', 'apply', str(patch)], cwd=root, check=True, timeout=20)
            if digest(source.read_bytes()) != expected:
                raise ValueError('Patched input hash mismatch: ' + str(source))
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundled_helper, helper)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.source_root.resolve(strict=True))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + '\n')
    print('CLT preparation complete. Opt in with mac_use_command_line_tools=true, use_system_xcode=true, is_official_build=false. CLT-only builds also need angle_precompile_internal_metal_shaders=false.')


if __name__ == '__main__':
    main()
