#!/usr/bin/env python3
"""Fail early unless the selected Xcode can compile and link offline Metal shaders."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


def command(argv):
    result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120, check=True)
    return result.stdout.strip()


def verify(directory, run=command):
    directory.mkdir(parents=True, exist_ok=True)
    tools = {}
    for name in ('metal', 'metallib', 'clang', 'clang++', 'ld', 'libtool', 'nm', 'otool'):
        tools[name] = run(['xcrun', '--sdk', 'macosx', '--find', name])
    for name in ('git', 'patch', 'tar', 'gzip', 'curl', 'cmake', 'ninja', 'ccache'):
        run(['/usr/bin/which', name])
    source = directory / 'preflight.metal'
    air = directory / 'preflight.air'
    library = directory / 'preflight.metallib'
    source.write_text('#include <metal_stdlib>\nusing namespace metal;\nkernel void preflight(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i + 1; }\n')
    variants = {}
    for name, flags in (('arm64', ['-target', 'air64-apple-macos26.0']),
                        ('angle', ['--std=macos-metal2.1', '-mmacosx-version-min=10.14'])):
        air = directory / (name + '.air')
        library = directory / (name + '.metallib')
        run(['xcrun', '--sdk', 'macosx', 'metal', *flags, '-c', str(source), '-o', str(air)])
        if not air.is_file() or not air.stat().st_size:
            raise ValueError('Metal compiler did not produce AIR: ' + name)
        run(['xcrun', '--sdk', 'macosx', 'metallib', str(air), '-o', str(library)])
        if not library.is_file() or not library.stat().st_size:
            raise ValueError('Metal linker did not produce a library: ' + name)
        variants[name] = {'flags': flags, 'libraryBytes': library.stat().st_size,
                          'librarySha256': hashlib.sha256(library.read_bytes()).hexdigest()}
    return {'shaderCompileAndLink': True, 'tools': tools, 'variants': variants,
            'metalVersion': run(['xcrun', '--sdk', 'macosx', 'metal', '--version']),
            'xcodeVersion': run(['xcodebuild', '-version']),
            'sdkVersion': run(['xcrun', '--sdk', 'macosx', '--show-sdk-version']),
            'libraryBytes': library.stat().st_size,
            'librarySha256': hashlib.sha256(library.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != 'Darwin' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('This toolchain verification is restricted to hosted macOS CI')
    args.directory.mkdir(parents=True, exist_ok=True)
    report = {'shaderCompileAndLink': False}
    try:
        report = verify(args.directory)
        from chromium_host_identity import metal_toolchains
        report['toolchainIdentity'] = metal_toolchains(command)
    except Exception as error:
        report['error'] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            report['output'] = error.stdout
        raise
    finally:
        (args.directory / 'metal-toolchain.json').write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__': main()
