"""Experimental macOS-only GN SDK metadata from actual Apple CLT receipts.

Legacy xcode_version fields encode the installed CLT toolset version for GN
compatibility. They do not assert that Xcode.app is installed. Never use this
mode for official builds or to emulate the missing Apple resource compilers.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess


def output(command, env=None):
    return subprocess.check_output(command, env=env, timeout=20).decode().strip()


def settings():
    developer = Path(output(['xcode-select', '-p'])).resolve(strict=True)
    if developer.name != 'CommandLineTools' or not (developer / 'usr/bin/clang').is_file():
        raise ValueError('Select an actual Apple CommandLineTools installation for experimental CLT mode')
    env = {**os.environ, 'DEVELOPER_DIR': str(developer)}
    receipt = plistlib.loads(subprocess.check_output(
        ['pkgutil', '--pkg-info-plist', 'com.apple.pkg.CLTools_Executables'], timeout=20))
    version = receipt['pkg-version']
    if not re.fullmatch(r'\d+(?:\.\d+)+', version):
        raise ValueError('Unrecognized Apple CLT package version')
    major, minor, patch = version.split('.')[:3]
    compatibility = f'{int(major):02}{int(minor)}{int(patch)}'
    def sdk_value(name):
        return output(['xcrun', '--sdk', 'macosx', '--show-sdk-' + name], env)
    sdk = Path(sdk_value('path')).resolve(strict=True)
    binary = Path(output(['xcrun', '--find', 'clang'], env)).resolve(strict=True).parent
    return {
        'apple_toolchain_type': 'command_line_tools',
        'apple_toolchain_version': version,
        'xcode_version': compatibility,
        'xcode_version_int': int(compatibility),
        'xcode_version_verbatim': 'Command Line Tools ' + version,
        'xcode_build': 'CLT-' + version,
        'sdk_path': str(sdk),
        'sdk_version': sdk_value('version'),
        'sdk_build': sdk_value('build-version'),
        # CLT has no .platform or .xctoolchain bundles. These real roots
        # contain its SDKs and usr/bin; never invent Xcode bundle paths.
        'sdk_platform_path': str(developer),
        'toolchains_path': str(developer),
        'mac_bin_path': str(binary) + '/',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minimum-sdk', default='15')
    parser.add_argument('platform', choices=['macosx'])
    args = parser.parse_args()
    try:
        values = settings()
        def version(value):
            if not re.fullmatch(r'\d+(?:\.\d+)*', value):
                raise ValueError('Unrecognized numeric SDK version: ' + value)
            return tuple(int(part) for part in (value.split('.') + ['0', '0'])[:3])
        if version(values['sdk_version']) < version(args.minimum_sdk):
            raise ValueError('SDK is older than required minimum')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + '\n')
    for key, value in sorted(values.items()):
        print(key + '=' + json.dumps(value))


if __name__ == '__main__':
    main()
