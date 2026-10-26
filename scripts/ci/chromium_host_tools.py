"""Carry exact Homebrew build-tool bytes between segments of one hosted run.

Restore never extracts an archive into Homebrew. It validates every member in a
private staging directory, checks the complete installed layout, then atomically
replaces only pre-existing regular files. Keg/opt mappings cannot change.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile

TOOLS = {'cmake', 'ninja', 'ccache', 'zstd'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def mappings(packages, root):
    result = {}
    for name, value in sorted(packages.items()):
        if not re.fullmatch(r'[a-z0-9][a-z0-9+_.@-]*', name):
            raise ValueError('Invalid formula name')
        keg = Path(value)
        if not keg.is_absolute() or keg != keg.resolve(strict=True):
            raise ValueError('Keg must be a canonical directory')
        relative = keg.relative_to(root / 'Cellar')
        if len(relative.parts) != 2 or relative.parts[0] != name or not keg.is_dir():
            raise ValueError('Unexpected keg mapping')
        opt = root / 'opt' / name
        if not opt.is_symlink() or opt.resolve(strict=True) != keg:
            raise ValueError('Unexpected opt mapping')
        result[name] = {'keg': str(keg), 'optLink': os.readlink(opt)}
    return result


def inventory(packages, root):
    mapping = mappings(packages, root)
    allowed = [Path(value['keg']) for value in mapping.values()]
    entries = {}
    for name, value in mapping.items():
        keg = Path(value['keg'])
        for current, directories, files in os.walk(keg, followlinks=False):
            directories.sort()
            if Path(current) == keg:
                directories[:] = [part for part in directories if part != '.brew']
                files = [part for part in files if part != 'INSTALL_RECEIPT.json']
            for part in sorted(directories + files):
                path = Path(current) / part
                relative = path.relative_to(keg).as_posix()
                key = name + '/' + relative
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode):
                    target = path.resolve(strict=True)
                    if not any(target.is_relative_to(base) for base in allowed):
                        raise ValueError('Foreign tool symlink: ' + key)
                    entries[key] = {'type': 'link', 'target': os.readlink(path)}
                elif stat.S_ISDIR(mode):
                    entries[key] = {'type': 'directory'}
                elif stat.S_ISREG(mode):
                    entries[key] = {'type': 'file', 'mode': stat.S_IMODE(mode),
                                    'sha256': digest(path), 'size': path.stat().st_size}
                else:
                    raise ValueError('Unsupported tool entry: ' + key)
    return mapping, entries


def destination(key, mapping):
    parts = PurePosixPath(key).parts
    if len(parts) < 2 or any(part in ('', '.', '..') for part in parts) or PurePosixPath(key).is_absolute():
        raise ValueError('Unsafe archive path')
    if '/'.join(parts) != key or parts[0] not in mapping:
        raise ValueError('Unexpected archive formula')
    return Path(mapping[parts[0]]['keg']).joinpath(*parts[1:])


def snapshot(output, packages, root, commit, run_id):
    mapping, entries = inventory(packages, root)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'tools.tar.gz'
    with tarfile.open(archive, 'w:gz', dereference=True) as tar:
        for key, entry in entries.items():
            if entry['type'] == 'file':
                tar.add(destination(key, mapping), arcname=key, recursive=False)
    # Recheck after archiving so the manifest cannot describe different bytes.
    if inventory(packages, root) != (mapping, entries):
        raise ValueError('Homebrew tools changed during snapshot')
    (output / 'manifest.json').write_text(json.dumps({
        'schemaVersion': 1, 'commit': commit, 'runId': run_id,
        'mapping': mapping, 'entries': entries, 'archiveSha256': digest(archive),
    }, indent=2) + '\n')


def restore(source, packages, root, commit, run_id):
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['schemaVersion'] != 1 or manifest['commit'] != commit or manifest['runId'] != run_id:
        raise ValueError('Tool snapshot is not from this run and commit')
    archive = source / 'tools.tar.gz'
    if digest(archive) != manifest['archiveSha256']:
        raise ValueError('Tool archive hash mismatch')
    mapping, current = inventory(packages, root)
    entries = manifest['entries']
    (source / 'restore-differences.json').write_text(json.dumps({
        'currentMapping': mapping,
        'differences': {key: {'snapshot': entries.get(key), 'installed': current.get(key)}
                        for key in sorted(entries.keys() | current.keys())
                        if entries.get(key) != current.get(key)},
    }, indent=2) + '\n')
    if mapping != manifest['mapping'] or current.keys() != entries.keys():
        raise ValueError('Installed tool mappings or inventory changed')
    for key, entry in entries.items():
        destination(key, mapping)
        actual = current[key]
        if actual['type'] != entry['type'] or (entry['type'] != 'file' and actual != entry):
            raise ValueError('Installed tool type or symlink changed: ' + key)
    expected = {key for key, entry in entries.items() if entry['type'] == 'file'}
    with tempfile.TemporaryDirectory(prefix='chromium-tool-stage-') as temporary:
        stage = Path(temporary)
        seen = set()
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                destination(member.name, mapping)
                if member.name not in expected or member.name in seen or not member.isfile() or member.issparse():
                    raise ValueError('Unexpected tool archive member')
                entry = entries[member.name]
                if member.size != entry['size'] or stat.S_IMODE(member.mode) != entry['mode']:
                    raise ValueError('Tool archive metadata mismatch')
                staged = stage / member.name
                staged.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as incoming, staged.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                if digest(staged) != entry['sha256']:
                    raise ValueError('Tool file hash mismatch')
                seen.add(member.name)
        if seen != expected:
            raise ValueError('Tool archive is incomplete')
        # All archive bytes and all real paths are validated before any keg write.
        if inventory(packages, root) != (mapping, current):
            raise ValueError('Installed tools changed during restore validation')
        for key in sorted(expected):
            if current[key] == entries[key]:
                continue
            target = destination(key, mapping)
            with tempfile.NamedTemporaryFile(prefix='.chromium-tool-', dir=target.parent, delete=False) as temporary_file:
                replacement = Path(temporary_file.name)
                try:
                    with (stage / key).open('rb') as incoming:
                        shutil.copyfileobj(incoming, temporary_file)
                    temporary_file.flush()
                    os.fchmod(temporary_file.fileno(), entries[key]['mode'])
                    os.fsync(temporary_file.fileno())
                    os.replace(replacement, target)
                finally:
                    replacement.unlink(missing_ok=True)
        if inventory(packages, root) != (mapping, entries):
            raise ValueError('Restored tool identity mismatch')


def homebrew_root():
    roots = {'arm64': Path('/opt/homebrew'), 'x86_64': Path('/usr/local')}
    if platform.machine() not in roots:
        raise ValueError('Unsupported macOS build host architecture')
    return roots[platform.machine()]


def hosted_packages():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or platform.system() != 'Darwin' or platform.machine() not in ('arm64', 'x86_64'):
        raise ValueError('Tool snapshot requires GitHub Actions Darwin arm64 or x86_64')
    root = homebrew_root()
    if root.resolve(strict=True) != root or (root / 'Cellar').resolve(strict=True) != root / 'Cellar' or (root / 'opt').resolve(strict=True) != root / 'opt':
        raise ValueError('Unexpected Homebrew root')
    def output(argv):
        return subprocess.check_output(argv, text=True).strip()
    names = TOOLS | set(output(['brew', 'deps', '--installed', '--formula', '--union', *sorted(TOOLS)]).splitlines())
    packages = {name: str(Path(output(['brew', '--prefix', name])).resolve(strict=True)) for name in sorted(names)}
    return root, packages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('snapshot', 'restore'))
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    root, packages = hosted_packages()
    directory = args.directory.resolve()
    runner_temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    if not directory.is_relative_to(runner_temp) or directory == runner_temp:
        raise ValueError('Tool snapshot directory must be inside RUNNER_TEMP')
    globals()[args.action](directory, packages, root, os.environ['GITHUB_SHA'], os.environ['GITHUB_RUN_ID'])


if __name__ == '__main__':
    main()
