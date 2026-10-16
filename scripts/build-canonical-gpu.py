#!/usr/bin/env python3
"""Build the pinned, separately named macOS arm64 CPU-only SwANGLE backend.

This never changes default Gecko ANGLE, application sandbox policy, or GPU
provenance. Installing/testing the browser remains an independent release gate.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = Path(__file__).with_name('canonical-gpu')
ANGLE_REVISION = '464fd3e879d6bb72fe8210b3e58b59836f711951'
SWIFTSHADER_REVISION = 'a7c547b55474c3d8bde53711eae24ae0e28bbc0a'
DEPOT_REVISION = '7f885f604cef0f45937752073e0fc34c9e43ec83'
LIBRARIES = ('libEGL_cloakfox_canonical.dylib', 'libGLESv2_cloakfox_canonical.dylib', 'libvk_swiftshader.dylib')


def run(command, cwd, **kwargs):
    return subprocess.run(command, cwd=cwd, check=True, **kwargs)


def output(command, cwd):
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def write_integrity_manifest(directory, metadata):
    files = {p.relative_to(directory).as_posix(): digest(p)
             for p in sorted(directory.rglob('*'))
             if p.is_file() and p != directory / 'manifest.json'}
    (directory / 'manifest.json').write_text(json.dumps({**metadata, 'files': files}, indent=2) + '\n')


def verify_integrity_manifest(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    for relative, expected in manifest['files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError(f'unsafe artifact path: {relative}')
        artifact = directory / path
        if not artifact.is_file():
            raise ValueError(f'missing artifact: {relative}')
        if artifact.is_symlink() or not artifact.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f'unsafe artifact path: {relative}')
        if digest(artifact) != expected:
            raise ValueError(f'digest mismatch: {relative}')
    for name in LIBRARIES:
        if name not in manifest['files']:
            raise ValueError(f'required GPU library absent from manifest: {name}')
    revisions = manifest.get('revisions', {})
    if (manifest.get('rendererVersion') != 1 or manifest.get('platform') != 'macos-arm64'
            or revisions.get('.') != ANGLE_REVISION
            or revisions.get('third_party/SwiftShader') != SWIFTSHADER_REVISION
            or manifest.get('hostRendererFallback') is not False
            or manifest.get('driverEnvironmentMutation') is not False):
        raise ValueError('GPU renderer manifest identity mismatch')
    return manifest


def checkout(directory, url, revision):
    if not directory.exists():
        directory.mkdir(parents=True)
        run(['git', 'init', '-q'], directory)
        run(['git', 'remote', 'add', 'origin', url], directory)
    if output(['git', 'remote', 'get-url', 'origin'], directory) != url:
        raise ValueError(f'wrong pinned origin in {directory}')
    head = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=directory,
                          capture_output=True, text=True)
    if head.returncode:
        # Resume an initialized repository whose first fetch never completed.
        # Only transient transport failures are retried; bad pins fail directly.
        for attempt in range(3):
            try:
                result = run(['git', 'fetch', '--depth', '1', 'origin', revision], directory,
                             capture_output=True, text=True, timeout=300)
                print(result.stderr, end='', file=sys.stderr, flush=True)
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                detail = error.stderr or ''
                if isinstance(detail, bytes):
                    detail = detail.decode('utf-8', errors='replace')
                print(detail, end='', file=sys.stderr, flush=True)
                transient = isinstance(error, subprocess.TimeoutExpired) or re.search(
                    r'HTTP (?:429|500|502|503|504)\b|Could not resolve host|Connection reset|Connection timed out',
                    detail, re.IGNORECASE)
                if not transient or attempt == 2:
                    raise
                print(f'Pinned fetch transport failed; retry {attempt + 2}/3', flush=True)
                time.sleep(10 * (attempt + 1))
        if output(['git', 'rev-parse', 'FETCH_HEAD'], directory) != revision:
            raise ValueError(f'fetched revision differs from pin in {directory}')
        run(['git', 'checkout', '--detach', revision], directory)
    if output(['git', 'rev-parse', 'HEAD'], directory) != revision:
        raise ValueError(f'wrong pinned revision in {directory}; use a fresh work directory')


def acquisition_config(angle):
    # Read dependency keys with AST; never execute upstream DEPS as Python.
    tree = ast.parse((angle / 'DEPS').read_text())
    dependencies = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'deps' for t in node.targets):
            dependencies = [key.value for key in node.value.keys if isinstance(key, ast.Constant)]
    keep = {'build', 'buildtools', 'buildtools/mac', 'testing', 'third_party/abseil-cpp',
            'third_party/astc-encoder/src', 'third_party/cpu_features/src', 'third_party/googletest/src',
            'third_party/jinja2', 'third_party/markupsafe', 'third_party/jsoncpp', 'third_party/rapidjson/src',
            'third_party/SwiftShader', 'third_party/vulkan-deps', 'third_party/glslang/src',
            'third_party/spirv-headers/src', 'third_party/spirv-tools/src', 'third_party/vulkan-headers/src',
            'third_party/vulkan-loader/src', 'third_party/vulkan_memory_allocator', 'third_party/zlib',
            'tools/clang', 'tools/rust'}
    return {'name': '.', 'url': 'https://chromium.googlesource.com/angle/angle.git', 'managed': False,
            'custom_deps': {key: None for key in dependencies if key not in keep},
            'custom_vars': {'checkout_angle_restricted_traces': False, 'checkout_angle_dawn_deps': False,
                            'checkout_angle_mesa': False, 'checkout_angle_cl_deps': False}}


def acquire(work):
    checkout(work / 'angle', 'https://chromium.googlesource.com/angle/angle', ANGLE_REVISION)
    checkout(work / 'depot_tools', 'https://chromium.googlesource.com/chromium/tools/depot_tools.git', DEPOT_REVISION)
    marker = work / 'acquired.json'
    identity = {'angle': ANGLE_REVISION, 'swiftshader': SWIFTSHADER_REVISION, 'depot_tools': DEPOT_REVISION}
    if marker.is_file():
        if json.loads(marker.read_text()) != identity:
            raise ValueError('acquired dependency identity changed; use a fresh work directory')
        return
    angle = work / 'angle'
    (angle / '.gclient').write_text('solutions = ' + repr([acquisition_config(angle)]) + '\n')
    env = {**os.environ, 'DEPOT_TOOLS_UPDATE': '0', 'PATH': str(work / 'depot_tools') + os.pathsep + os.environ['PATH']}
    with (work / 'gclient-sync.log').open('w') as log:
        run([str(work / 'depot_tools/gclient'), 'sync', '--nohooks', '--no-history', '--jobs=4'], angle, env=env, stdout=log, stderr=subprocess.STDOUT)
    if output(['git', 'rev-parse', 'HEAD'], angle / 'third_party/SwiftShader') != SWIFTSHADER_REVISION:
        raise ValueError('ANGLE dependency does not match the reviewed SwiftShader revision')
    marker.write_text(json.dumps(identity, indent=2) + '\n')


def apply_patch(checkout_dir, patch):
    check = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=checkout_dir, capture_output=True)
    if check.returncode == 0:
        return
    run(['git', 'apply', '--check', str(patch)], checkout_dir)
    run(['git', 'apply', str(patch)], checkout_dir)


def build(work, jobs, live_logs=False):
    angle = work / 'angle'
    apply_patch(angle, RESOURCES / 'canonical-only.patch')
    if output(['xcode-select', '-print-path'], angle).endswith('/CommandLineTools'):
        apply_patch(angle / 'build', RESOURCES / 'command-line-tools.patch')
    target = angle / 'out/Canonical'
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RESOURCES / 'args.gn', target / 'args.gn')
    commands = [('gn-gen', [str(angle / 'buildtools/mac/gn'), 'gen', str(target)]),
                ('ninja-build', ['ninja', '-C', str(target), f'-j{jobs}', 'libEGL', 'libGLESv2'])]
    if live_logs:
        # Reuse the tested file-backed child logger and 10GiB reserve guard;
        # this does not invoke Chromium's source acquisition/build methods.
        spec = importlib.util.spec_from_file_location('ci_child_logger', ROOT / 'scripts/ci/chromium_source.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pipeline = module.Pipeline(work)
        for name, command in commands:
            pipeline.run('canonical-' + name, command, angle)
    else:
        for name, command in commands:
            with (work / (name + '.log')).open('w') as log:
                run(command, angle, stdout=log, stderr=subprocess.STDOUT)
    run([sys.executable, str(ROOT / 'tests/fingerprint/probe_canonical_gpu_standalone.py'), str(target)], ROOT)


def stage(work, destination):
    angle = work / 'angle'
    target = angle / 'out/Canonical'
    # Validate the actual CPU producer before copying any deployable artifact.
    run([sys.executable, str(ROOT / 'tests/fingerprint/probe_canonical_gpu_standalone.py'), str(target)], ROOT)
    if destination.exists():
        raise ValueError(f'stage destination already exists: {destination}; verify or choose a fresh destination')
    destination.mkdir(parents=True)
    for name in LIBRARIES:
        shutil.copy2(target / name, destination / name)
    revisions = {}
    for directory, children, _files in os.walk(angle):
        path = Path(directory)
        if '.git' in children or (path / '.git').is_file():
            revisions[path.relative_to(angle).as_posix()] = output(['git', 'rev-parse', 'HEAD'], path)
        children[:] = [child for child in children if child not in {'.git', 'out', '__pycache__'} and not child.startswith('_gclient_')]
    notices = destination / 'notices'
    for directory, children, files in os.walk(angle):
        children[:] = [child for child in children if child not in {'.git', 'out', '__pycache__'} and not child.startswith('_gclient_')]
        for name in files:
            if name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'AUTHORS')):
                source = Path(directory) / name
                if source.is_symlink():
                    continue
                dest = notices / source.relative_to(angle)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
    # WebGPU's Apple Vulkan feature adds these bindings to Gecko's binary.
    renderdoc = ROOT / 'additions/third_party/rust/renderdoc-sys'
    renderdoc_notices = notices / 'gecko/renderdoc-sys-1.1.0'
    renderdoc_notices.mkdir(parents=True, exist_ok=True)
    for name in ('LICENSE-APACHE', 'LICENSE-MIT'):
        shutil.copy2(renderdoc / name, renderdoc_notices / name)
    shutil.copy2(RESOURCES / 'args.gn', destination / 'args.gn')
    metadata = {'rendererVersion': 1, 'platform': 'macos-arm64', 'backend': 'ANGLE Vulkan / SwiftShader CPU',
                'hostRendererFallback': False, 'driverEnvironmentMutation': False, 'revisions': revisions,
                'localPatches': {p.name: digest(p) for p in sorted(RESOURCES.glob('*.patch'))},
                'integrityScope': 'Verify before packaging; signed application validates loaded library code. No cross-host pixel identity claim.'}
    write_integrity_manifest(destination, metadata)
    verify_integrity_manifest(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=lambda p: Path(p).resolve(), default=ROOT / '.canonical-gpu-build')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--acquire', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--ci-live-logs', action='store_true')
    parser.add_argument('--stage', type=lambda p: Path(p).resolve())
    parser.add_argument('--verify', type=lambda p: Path(p).resolve())
    args = parser.parse_args()
    if args.verify:
        verify_integrity_manifest(args.verify)
        print(f'Integrity verified: {args.verify}')
        return
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.error('This reviewed build configuration supports macOS arm64 only')
    if not (args.acquire or args.build or args.stage):
        parser.error('select --acquire, --build, --stage DIR, or --verify DIR')
    if args.acquire:
        acquire(args.work_dir)
    if args.build:
        build(args.work_dir, args.jobs, args.ci_live_logs)
    if args.stage:
        stage(args.work_dir, args.stage)


if __name__ == '__main__':
    main()
