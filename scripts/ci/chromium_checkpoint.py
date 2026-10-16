"""Same-run full-workspace handoff; preserve compiler objects and source timestamps."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time

GIB = 1024**3


def digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def require_space(path, needed=0):
    if shutil.disk_usage(path).free - needed < 10 * GIB:
        raise RuntimeError('Checkpoint would exhaust the 10 GiB storage reserve')


class GuardedWriter:
    def __init__(self, file, folder):
        self.file = file
        self.folder = folder
        self.checked = 0
        self.reported = time.monotonic()
        self.bytes = 0

    def write(self, data):
        now = time.monotonic()
        if now - self.checked >= 1:
            require_space(self.folder, len(data))
            self.checked = now
        written = self.file.write(data)
        self.bytes += written
        if now - self.reported >= 30:
            print(f'CHECKPOINT compressing bytes={self.bytes} free={shutil.disk_usage(self.folder).free/GIB:.1f}GiB', flush=True)
            self.reported = now
        return written

    def flush(self):
        return self.file.flush()


def internal_link(source, root):
    target = source.resolve()
    if not target.is_relative_to(root):
        raise ValueError('Checkpoint external symlink: ' + str(source.relative_to(root)))
    return os.path.relpath(target, source.parent)


def validate_links(root):
    root = Path(root).resolve()
    count = 0
    for source in root.rglob('*'):
        if source.is_symlink():
            internal_link(source, root)
            count += 1
    print(f'CHECKPOINT preflight verified {count} internal symlinks', flush=True)


def save(root, archive, identity):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    if archive.is_relative_to(root):
        raise ValueError('Checkpoint archive must be outside the workspace')
    archive.parent.mkdir(parents=True, exist_ok=True)
    require_space(archive.parent)
    started = time.monotonic()
    def preserve(member):
        relative = PurePosixPath(member.name).relative_to('workspace')
        source = root / str(relative)
        if member.issym():
            member.linkname = internal_link(source, root)
        member.pax_headers['cloakfox.mtime_ns'] = str(source.lstat().st_mtime_ns)
        return member
    with archive.open('wb') as file:
        with tarfile.open(fileobj=GuardedWriter(file, archive.parent), mode='w:gz', compresslevel=1) as bundle:
            bundle.add(root, arcname='workspace', filter=preserve)
    record = {'schemaVersion': 1, 'identity': identity, 'sha256': digest(archive),
              'bytes': archive.stat().st_size, 'seconds': round(time.monotonic() - started, 1)}
    archive.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f"CHECKPOINT saved bytes={record['bytes']} seconds={record['seconds']}", flush=True)


def restore(root, archive, identity):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    receipt = json.loads(archive.with_suffix('.json').read_text())
    if receipt.get('schemaVersion') != 1:
        raise ValueError('Unsupported checkpoint schema')
    if receipt.get('identity') != identity:
        raise ValueError('Checkpoint identity differs from current commit/toolchain/root')
    if digest(archive) != receipt['sha256']:
        raise ValueError('Checkpoint SHA256 mismatch')
    if root.exists():
        raise ValueError('Checkpoint destination already exists; preserve it for diagnosis')
    root.mkdir(parents=True)
    stamps = []
    reported = time.monotonic()
    count = 0
    started = time.monotonic()
    with tarfile.open(archive, 'r:gz') as bundle:
        def members():
            nonlocal reported, count
            for member in bundle:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] != 'workspace' or '..' in parts:
                    raise ValueError('Checkpoint member escapes workspace')
                member.name = str(PurePosixPath(*parts[1:]))
                if member.islnk():
                    link = PurePosixPath(member.linkname)
                    if not link.parts or link.parts[0] != 'workspace' or '..' in link.parts:
                        raise ValueError('Checkpoint hardlink escapes workspace')
                    member.linkname = str(PurePosixPath(*link.parts[1:]))
                require_space(root, member.size if member.isfile() else 0)
                count += 1
                if time.monotonic() - reported >= 30:
                    print(f'CHECKPOINT extracting files={count} free={shutil.disk_usage(root).free/GIB:.1f}GiB', flush=True)
                    reported = time.monotonic()
                if 'cloakfox.mtime_ns' in member.pax_headers:
                    stamps.append((root / member.name, int(member.pax_headers['cloakfox.mtime_ns'])))
                yield member
        bundle.extractall(root, members=members(), filter='data')
    for path, stamp in reversed(stamps):
        os.utime(path, ns=(stamp, stamp), follow_symlinks=False)
    print(f'CHECKPOINT restored seconds={time.monotonic()-started:.1f}', flush=True)
