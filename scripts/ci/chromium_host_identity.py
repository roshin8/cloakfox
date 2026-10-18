"""Content identity for macOS host inputs; runner image is separate provenance."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import time


def tree_identity(directory, *, python_runtime=False, homebrew_package=False):
    root = Path(directory).resolve(strict=True)
    checksum = hashlib.sha256()
    files = size = 0
    reported = time.monotonic()

    def record(value):
        checksum.update(json.dumps(value, separators=(',', ':')).encode() + b'\n')

    for current, directories, names in os.walk(root, followlinks=False):
        directories.sort()
        if homebrew_package and Path(current) == root:
            directories[:] = [name for name in directories if name != '.brew']
            names = [name for name in names if name != 'INSTALL_RECEIPT.json']
        if python_runtime:
            # CPython validates these disposable caches against the .py inputs.
            # Cache creation by imports is not a compiler/stdlib revision change.
            directories[:] = [name for name in directories if name != '__pycache__']
        for name in sorted(directories + names):
            source = Path(current) / name
            relative = source.relative_to(root).as_posix()
            metadata = source.lstat()
            if source.is_symlink():
                target = source.resolve(strict=True)
                record(['link', relative, os.readlink(source)])
                if not target.is_relative_to(root):
                    if target.is_dir():
                        raise ValueError('Unfingerprinted external directory: ' + str(source))
                    with target.open('rb') as stream:
                        record(['external-file', str(target), hashlib.file_digest(stream, 'sha256').hexdigest()])
            elif stat.S_ISREG(metadata.st_mode):
                with source.open('rb') as stream:
                    sha = hashlib.file_digest(stream, 'sha256').hexdigest()
                record(['file', relative, stat.S_IMODE(metadata.st_mode), sha])
                files += 1
                size += metadata.st_size
            elif source.is_dir():
                record(['directory', relative])
            else:
                raise ValueError('Unsupported host input type: ' + str(source))
            if time.monotonic() - reported >= 30:
                print(f'CHECKPOINT fingerprinting {root} files={files} bytes={size}', flush=True)
                reported = time.monotonic()
    return {'path': str(root), 'sha256': checksum.hexdigest(), 'files': files, 'bytes': size}


def python_dependencies(directory, executable):
    """Bind Mach-O extension/interpreter dependencies outside the Python prefix.

    OS libraries are bound by the exact macOS build. Resolve explicit dyld
    loader/executable paths and LC_RPATH entries; fail closed on ambiguity.
    """
    root = Path(directory).resolve()
    executable = Path(executable).resolve()
    magic = {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce',
             b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}
    pending = []
    for path in root.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream:
                if stream.read(4) in magic:
                    pending.append(path.resolve())
    visited, external, info_cache = set(), {}, {}

    def expand(reference, loader):
        return Path(reference.replace('@loader_path', str(loader.parent))
                    .replace('@executable_path', str(executable.parent)))

    def info(loader):
        if loader not in info_cache:
            result = subprocess.check_output(['otool', '-l', str(loader)], text=True)
            paths, dependencies, command = [], [], ''
            for line in result.splitlines():
                line = line.strip()
                if line.startswith('cmd '):
                    command = line[4:]
                elif command == 'LC_RPATH' and line.startswith('path '):
                    paths.append(expand(line[5:].split(' (offset ', 1)[0], loader))
                elif command in {'LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB', 'LC_REEXPORT_DYLIB',
                                 'LC_LAZY_LOAD_DYLIB', 'LC_LOAD_UPWARD_DYLIB'} and line.startswith('name '):
                    dependencies.append(line[5:].split(' (offset ', 1)[0])
            # LC_ID_DYLIB is an install name, not a dependency to resolve.
            info_cache[loader] = paths, dependencies
        return info_cache[loader]

    inherited = info(executable)[0] if executable in pending else []
    pending = [(path, tuple(inherited)) for path in pending]
    while pending:
        loader, inherited = pending.pop()
        context = loader, inherited
        if context in visited:
            continue
        visited.add(context)
        own_paths, dependencies = info(loader)
        search = tuple(dict.fromkeys([*own_paths, *inherited]))
        for reference in dependencies:
            if reference.startswith(('/usr/lib/', '/System/Library/')):
                continue
            if reference.startswith('@rpath/'):
                candidates = {path.resolve() for path in
                              (base / reference[7:] for base in search) if path.is_file()}
                if len(candidates) != 1:
                    raise ValueError('Unresolved or ambiguous host dependency: ' + reference)
                target = candidates.pop()
            else:
                target = expand(reference, loader)
                if not target.is_absolute() or '@' in str(target):
                    raise ValueError('Unresolved host dependency: ' + reference)
                target = target.resolve()
            if not target.is_file():
                raise ValueError('Missing host dependency: ' + str(target))
            if not target.is_relative_to(root):
                with target.open('rb') as stream:
                    external[str(target)] = hashlib.file_digest(stream, 'sha256').hexdigest()
            pending.append((target, search))
    return external


def install_provenance(inputs):
    receipts = {}
    for name, package in inputs['homebrewBuildTools'].items():
        path = Path(package['path']) / 'INSTALL_RECEIPT.json'
        if path.is_file():
            receipts[name] = json.loads(path.read_text())
    return receipts


def metal_toolchains(output):
    # Xcode 26 installs Metal outside Xcode.app. Bind the entire resolved
    # toolchain, including libraries and headers, rather than version labels.
    metal = {}
    for tool in ('metal', 'metallib'):
        executable = Path(output(['xcrun', '--sdk', 'macosx', '--find', tool])).resolve(strict=True)
        root = next((p for p in executable.parents if p.suffix == '.xctoolchain'), None)
        if root is None:
            raise ValueError('Metal tool is outside a fingerprintable toolchain: ' + str(executable))
        if str(root) not in metal:
            metal[str(root)] = tree_identity(root)
    return metal


def collect(developer):
    if platform.system() != 'Darwin' or platform.machine() not in ('arm64', 'x86_64'):
        raise ValueError('Chromium hosted checkpoints require macOS arm64 or x86_64')

    def output(command):
        return subprocess.check_output(command, text=True).strip()

    # Hash the selected Xcode bundle, including SDKs, toolchains, host utilities
    # and their bundled frameworks. Never infer equality from version labels.
    xcode = Path(developer).resolve().parents[1]
    if xcode.suffix != '.app':
        raise ValueError('A full selected Xcode application is required')
    formulas = {'cmake', 'ninja', 'ccache'}
    formulas.update(output(['brew', 'deps', '--installed', '--formula', '--union', *sorted(formulas)]).splitlines())
    packages = {}
    for formula in sorted(formulas):
        packages[formula] = tree_identity(output(['brew', '--prefix', formula]), homebrew_package=True)
    commands = {}
    for name in ('cmake', 'ninja', 'ccache'):
        executable = shutil.which(name)
        if not executable or not Path(executable).resolve().is_relative_to(packages[name]['path']):
            raise ValueError('Build tool resolves outside fingerprinted package: ' + name)
        commands[name] = str(Path(executable).resolve())
    return {
        'schemaVersion': 1,
        'metalToolchains': metal_toolchains(output),
        'macos': output(['sw_vers', '-productVersion']),
        'macosBuild': output(['sw_vers', '-buildVersion']),
        'architecture': platform.machine(),
        'xcodeBundle': tree_identity(xcode),
        'pythonRuntime': tree_identity(sys.base_prefix, python_runtime=True),
        'pythonExternalLibraries': python_dependencies(sys.base_prefix, sys.executable),
        'homebrewBuildTools': packages,
        'commands': commands,
    }
