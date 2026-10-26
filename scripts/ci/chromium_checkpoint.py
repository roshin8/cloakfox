"""Same-run full-workspace handoff; preserve compiler objects and source timestamps."""
from contextlib import contextmanager
from decimal import Decimal
import signal
import subprocess
import tempfile
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time

GIB = 1024**3
ZSTD = 'zstd'
HOST_LINK_DIR = PurePosixPath('chromium/src/out/Release_GN_arm64/sdk/xcode_links')


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


def verified_host_link(relative, target, identity):
    allowed = (identity or {}).get('hostSdkLinks', {})
    if (PurePosixPath(relative).parent != HOST_LINK_DIR or '..' in PurePosixPath(relative).parts
            or allowed.get(relative) != target or not Path(target).is_absolute()
            or str(Path(target).resolve()) != target or not Path(target).is_dir()):
        raise ValueError('Unverified checkpoint host SDK link (external symlink): ' + relative)
    return target


def validate_links(root, identity=None):
    root = Path(root).resolve()
    count = 0
    for source in root.rglob('*'):
        if source.is_symlink():
            if source.resolve().is_relative_to(root):
                internal_link(source, root)
            else:
                verified_host_link(source.relative_to(root).as_posix(), str(source.resolve()), identity)
            count += 1
    print(f'CHECKPOINT preflight verified {count} contained or pinned SDK symlinks', flush=True)


class WriteOnlyTarFile(tarfile.TarFile):
    """Do not retain serialized TarInfo/PAX objects for a write-only handoff.

    CPython 3.12 appends every written member to self.members. Hardlink
    detection uses self.inodes, not that list; keep its genuine hardlinks.
    Restore deliberately continues using the unmodified standard reader.
    """
    def addfile(self, tarinfo, fileobj=None):
        super().addfile(tarinfo, fileobj)
        self.members.clear()


def _save_gzip(root, archive, identity, provenance=None):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    if archive.is_relative_to(root):
        raise ValueError('Checkpoint archive must be outside the workspace')
    archive.parent.mkdir(parents=True, exist_ok=True)
    require_space(archive.parent)
    started = time.monotonic()
    host_links = {}
    def preserve(member):
        relative = PurePosixPath(member.name).relative_to('workspace')
        source = root / str(relative)
        metadata = source.lstat()
        # gettarinfo also caches every single-link regular file, although it
        # cannot be the target of a later hardlink. Keep only actual links.
        if member.isreg() and metadata.st_nlink == 1:
            bundle.inodes.pop((metadata.st_ino, metadata.st_dev), None)
        if member.issym():
            if source.resolve().is_relative_to(root):
                member.linkname = internal_link(source, root)
            else:
                key = source.relative_to(root).as_posix()
                host_links[key] = verified_host_link(key, str(source.resolve()), identity)
                return None  # Recreate verified SDK links only after extraction.
        member.pax_headers['cloakfox.mtime_ns'] = str(metadata.st_mtime_ns)
        return member
    with archive.open('wb') as file:
        with WriteOnlyTarFile.open(fileobj=GuardedWriter(file, archive.parent), mode='w:gz', compresslevel=1) as bundle:
            bundle.add(root, arcname='workspace', filter=preserve)
    record = {'schemaVersion': 1, 'identity': identity, 'provenance': provenance or {},
              'hostLinks': host_links, 'sha256': digest(archive),
              'bytes': archive.stat().st_size, 'seconds': round(time.monotonic() - started, 1)}
    archive.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f"CHECKPOINT saved bytes={record['bytes']} seconds={record['seconds']}", flush=True)


def stop_process(process):
    if process is not None and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some macOS hosts reject killpg after the child has exited.
            if process.poll() is None:
                process.kill()
        process.wait()


def save(root, archive, identity, provenance=None):
    # Retain legacy gzip handoffs for old receipts and fixtures. New jobs use zst.
    if Path(archive).suffix != '.zst':
        return _save_gzip(root, archive, identity, provenance)
    root, archive = Path(root).resolve(), Path(archive).resolve()
    if archive.is_relative_to(root):
        raise ValueError('Checkpoint archive must be outside the workspace')
    archive.parent.mkdir(parents=True, exist_ok=True)
    receipt = archive.with_suffix('.json')
    if receipt.exists() or archive.exists():
        raise ValueError('Checkpoint output already exists; preserve it for diagnosis')
    require_space(archive.parent)
    validate_links(root, identity)
    host_links = {}
    host_link_metadata = {}
    for relative, target in identity.get('hostSdkLinks', {}).items():
        source = root / relative
        if source.is_symlink():
            host_links[relative] = verified_host_link(relative, str(source.resolve()), identity)
            info = source.lstat()
            host_link_metadata[relative] = {'mtimeNs': info.st_mtime_ns, 'mode': info.st_mode & 0o777}
    command = ['/usr/bin/tar', '--format=pax', '--no-xattrs', '-C', str(root.parent)]
    for relative in host_links:
        command += ['--exclude', str(PurePosixPath(root.name) / relative)]
    command += ['-cf', '-', root.name]
    started = time.monotonic()
    tar = compressor = None
    with tempfile.TemporaryFile() as tar_log, tempfile.TemporaryFile() as zstd_log, archive.open('xb') as output:
        try:
            tar = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=tar_log,
                                   env={**os.environ, 'COPYFILE_DISABLE': '1'}, start_new_session=True)
            compressor = subprocess.Popen([ZSTD, '-3', '-T2', '-c'], stdin=tar.stdout,
                                          stdout=output, stderr=zstd_log, start_new_session=True)
            tar.stdout.close()
            reported = 0
            while tar.poll() is None or compressor.poll() is None:
                require_space(archive.parent)
                now = time.monotonic()
                if now-reported >= 30:
                    print(f'CHECKPOINT native archive bytes={archive.stat().st_size}', flush=True)
                    reported = now
                if compressor.poll() not in (None, 0) or tar.poll() not in (None, 0):
                    raise RuntimeError('Native checkpoint tar/zstd pipeline failed')
                time.sleep(.2)
            if tar.returncode or compressor.returncode:
                raise RuntimeError(f'Native checkpoint pipeline failed: tar={tar.returncode}, zstd={compressor.returncode}')
            require_space(archive.parent)
        finally:
            stop_process(tar)
            stop_process(compressor)
    record = {'schemaVersion': 1, 'compression': 'zstd', 'archivePrefix': root.name,
              'sourceRoot': str(root), 'identity': identity, 'provenance': provenance or {},
              'hostLinks': host_links, 'hostLinkMetadata': host_link_metadata, 'sha256': digest(archive), 'bytes': archive.stat().st_size,
              'seconds': round(time.monotonic()-started, 1)}
    receipt.write_text(json.dumps(record, indent=2)+'\n')
    print(f"CHECKPOINT saved native bytes={record['bytes']} seconds={record['seconds']}", flush=True)


@contextmanager
def open_archive(archive, receipt):
    if receipt.get('compression') != 'zstd':
        with tarfile.open(archive, 'r:gz') as bundle:
            yield bundle
        return
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([ZSTD, '-d', '-c', str(archive)], stdout=subprocess.PIPE,
                                   stderr=errors, start_new_session=True)
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as bundle:
                yield bundle
            # Drain to EOF to validate the zstd trailer; never leave a blocked child.
            while process.stdout.read(1024*1024):
                pass
            if process.wait(timeout=30):
                raise RuntimeError('Checkpoint zstd decompression failed')
        finally:
            process.stdout.close()
            stop_process(process)


def restore(root, archive, identity):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    receipt = json.loads(archive.with_suffix('.json').read_text())
    if receipt.get('schemaVersion') != 1:
        raise ValueError('Unsupported checkpoint schema')
    if receipt.get('identity') != identity:
        previous = receipt.get('identity')
        fields = sorted(key for key in set(previous or {}) | set(identity)
                        if (previous or {}).get(key) != identity.get(key))
        raise ValueError('Checkpoint identity differs from current commit/toolchain/root: ' + ', '.join(fields))
    if digest(archive) != receipt['sha256']:
        raise ValueError('Checkpoint SHA256 mismatch')
    host_links = receipt.get('hostLinks', {})
    if type(host_links) is not dict:
        raise ValueError('Invalid checkpoint host SDK link manifest')
    for relative, target in host_links.items():
        verified_host_link(relative, target, identity)
    link_metadata = receipt.get('hostLinkMetadata', {})
    if (type(link_metadata) is not dict or set(link_metadata) - set(host_links)
            or any(type(item) is not dict or set(item) != {'mtimeNs', 'mode'}
                   or type(item['mtimeNs']) is not int or type(item['mode']) is not int
                   or not 0 <= item['mode'] <= 0o777 for item in link_metadata.values())):
        raise ValueError('Invalid checkpoint host SDK link metadata')
    if root.exists():
        raise ValueError('Checkpoint destination already exists; preserve it for diagnosis')
    root.mkdir(parents=True)
    stamps = []
    reported = time.monotonic()
    count = 0
    started = time.monotonic()
    with open_archive(archive, receipt) as bundle:
        def members():
            nonlocal reported, count
            for member in bundle:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] != receipt.get('archivePrefix', 'workspace') or '..' in parts:
                    raise ValueError('Checkpoint member escapes workspace')
                member.name = str(PurePosixPath(*parts[1:]))
                if member.islnk():
                    link = PurePosixPath(member.linkname)
                    if not link.parts or link.parts[0] != receipt.get('archivePrefix', 'workspace') or '..' in link.parts:
                        raise ValueError('Checkpoint hardlink escapes workspace')
                    member.linkname = str(PurePosixPath(*link.parts[1:]))
                if member.issym() and Path(member.linkname).is_absolute():
                    target = Path(member.linkname).resolve()
                    original = Path(receipt.get('sourceRoot', str(root)))
                    if not target.is_relative_to(original):
                        raise ValueError('Checkpoint external symlink')
                    member.linkname = os.path.relpath(root / target.relative_to(original), (root / member.name).parent)
                require_space(root, member.size if member.isfile() else 0)
                count += 1
                if time.monotonic() - reported >= 30:
                    print(f'CHECKPOINT extracting files={count} free={shutil.disk_usage(root).free/GIB:.1f}GiB', flush=True)
                    reported = time.monotonic()
                if 'cloakfox.mtime_ns' in member.pax_headers:
                    stamps.append((root / member.name, int(member.pax_headers['cloakfox.mtime_ns'])))
                elif receipt.get('compression') == 'zstd':
                    exact = member.pax_headers.get('mtime', str(member.mtime))
                    stamps.append((root / member.name, int(Decimal(exact) * 1000000000)))
                yield member
        bundle.extractall(root, members=members(), filter='data')
    for relative, target in host_links.items():
        destination = root / relative
        if not destination.parent.resolve().is_relative_to(root) or os.path.lexists(destination):
            raise ValueError('Checkpoint host SDK link destination is occupied or escapes workspace')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(target, target_is_directory=True)
        if relative in link_metadata:
            metadata = link_metadata[relative]
            os.chmod(destination, metadata['mode'], follow_symlinks=False)
            os.utime(destination, ns=(metadata['mtimeNs'], metadata['mtimeNs']), follow_symlinks=False)
    for path, stamp in reversed(stamps):
        os.utime(path, ns=(stamp, stamp), follow_symlinks=False)
    print(f'CHECKPOINT restored seconds={time.monotonic()-started:.1f}', flush=True)
