"""Carry same-build macOS xpcshell and codec source inputs to runtime jobs."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

REQUIRED_BINARIES = ('xpcshell', 'XUL', 'libmozglue.dylib',
                     'libmozavcodec.dylib', 'libmozavutil.dylib')
FIXTURES = ('dom/media/webvtt/test/reftest/black.mp4',
            'dom/media/test/hevc_white_frame.mp4', 'dom/media/test/red-48x46.mp4')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pack(source, binary, output, commit):
    required = [binary / name for name in REQUIRED_BINARIES]
    required += [source / name for name in FIXTURES]
    required += [source / 'media/ffvpx/libavcodec/avcodec.h']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    quads = sorted((source / 'dom/media/test/reftest/color_quads').glob('*.mp4'))
    if not quads:
        raise FileNotFoundError('Missing upstream color_quads MP4 corpus')
    files = {f'bin/{path.name}': path for path in binary.iterdir() if path.is_file()}
    for directory in ('defaults', 'components', 'res'):
        for path in (binary / directory).rglob('*'):
            if path.is_file():
                files['bin/' + path.relative_to(binary).as_posix()] = path
    for path in [*(source / name for name in FIXTURES), *quads,
                 *sorted((source / 'media/ffvpx').rglob('*.h'))]:
        files['firefox-src/' + path.relative_to(source).as_posix()] = path
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'native-inputs.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1, dereference=True) as bundle:
        for name, path in sorted(files.items()):
            bundle.add(path, arcname=name, recursive=False)
    receipt = {'gitSha': commit, 'archiveSha256': digest(archive),
               'binaries': {name: digest(binary / name) for name in REQUIRED_BINARIES},
               'files': len(files)}
    (output / 'native-inputs.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'Native test inputs: {len(files)} files, {archive.stat().st_size} bytes', flush=True)


def restore(inputs, destination, commit):
    receipt = json.loads((inputs / 'native-inputs.json').read_text())
    archive = inputs / 'native-inputs.tar.gz'
    if receipt['gitSha'] != commit or receipt['archiveSha256'] != digest(archive):
        raise ValueError('Native test input commit/archive mismatch')
    if destination.exists():
        raise ValueError('Native test input destination must be fresh')
    with tarfile.open(archive) as bundle:
        for member in bundle:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or '..' in path.parts
                    or not path.parts or path.parts[0] not in ('bin', 'firefox-src')):
                raise ValueError(f'Invalid native test member: {member.name}')
        destination.mkdir(parents=True)
        bundle.extractall(destination, filter='data')
    for name in REQUIRED_BINARIES:
        if digest(destination / 'bin' / name) != receipt['binaries'][name]:
            raise ValueError(f'Native test input binary mismatch: {name}')
    print(f'Verified same-commit native test inputs: {commit}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('pack', 'restore'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if args.mode == 'pack':
        if not args.source or not args.binary:
            parser.error('pack requires --source and --binary')
        pack(args.source, args.binary, args.inputs, args.commit)
    else:
        if not args.destination:
            parser.error('restore requires --destination')
        restore(args.inputs, args.destination, args.commit)
