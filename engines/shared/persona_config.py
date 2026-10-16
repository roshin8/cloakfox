"""Versioned engine-neutral persona snapshots; no Gecko preferences or page scripts.

Only implemented portable option names belong in v1. A backend must additionally
check its own capability report before accepting a snapshot. The store is the
controller authority, not a second browser profile or an engine adapter.
"""
import contextlib
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat

SCHEMA_VERSION = 1
DEFAULT_OPTIONS = {'canvas': True, 'blockWebGPUReadback': False}
MAX_REVISION = 2147483647


def validate_snapshot(value):
    """Return an independent validated snapshot, rejecting all unknown fields."""
    def fields(obj, expected):
        if type(obj) is not dict or set(obj) != set(expected):
            raise ValueError('Unsupported snapshot fields')
    fields(value, ('schemaVersion', 'engine', 'containerId', 'private', 'revision', 'enabled', 'persona'))
    if type(value['schemaVersion']) is not int or value['schemaVersion'] != SCHEMA_VERSION:
        raise ValueError('Unsupported snapshot schema')
    if value['engine'] not in ('gecko', 'chromium'):
        raise ValueError('Unsupported engine')
    container = value['containerId']
    if type(container) is not str or not re.fullmatch(r'[1-9][0-9]{0,9}', container) or int(container) > MAX_REVISION:
        raise ValueError('Invalid container ID')
    if type(value['private']) is not bool or type(value['enabled']) is not bool:
        raise ValueError('Invalid snapshot flags')
    if type(value['revision']) is not int or not 1 <= value['revision'] <= MAX_REVISION:
        raise ValueError('Invalid config revision')
    persona = value['persona']
    fields(persona, ('seed', 'options', 'overrides'))
    if type(persona['seed']) is not str or not re.fullmatch('[0-9a-f]{64}', persona['seed']):
        raise ValueError('Invalid persona seed')
    fields(persona['options'], DEFAULT_OPTIONS)
    for name in ('options', 'overrides'):
        options = persona[name]
        if type(options) is not dict or any(k not in DEFAULT_OPTIONS or type(v) is not bool for k, v in options.items()):
            raise ValueError('Unsupported persona option')
    return copy.deepcopy(value)


def _private_file(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
        raise ValueError('Unsafe persona file')


class PersonaStore:
    """Atomic controller-owned records; private snapshots never touch disk.

    Regeneration/config changes take effect in a *new* backend context/session.
    They do not mutate live browser realms. Each operation re-reads the record
    under a filesystem lock so separate controllers cannot lose revisions.
    """
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Persona directory must be private and owned by this user')
        self._private = {}

    @contextlib.contextmanager
    def _locked(self):
        folder = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd = -1
        try:
            info = os.fstat(folder)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError('Unsafe persona directory')
            fd = os.open('.persona-lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=folder)
            _private_file(fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield folder
        except OSError as error:
            raise ValueError('Cannot safely access persona store') from error
        finally:
            if fd >= 0: os.close(fd)
            os.close(folder)

    def _read(self, folder, name):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        except FileNotFoundError:
            return None
        try:
            _private_file(fd)
            if os.fstat(fd).st_size > 65536:
                raise ValueError('Oversized persona snapshot')
            with os.fdopen(fd, 'r', closefd=False) as source:
                return validate_snapshot(json.load(source))
        finally:
            os.close(fd)

    def _write(self, folder, name, value):
        # Create relative to the same open directory; rename never follows a file
        # symlink and readers either see the entire old or entire new snapshot.
        temp = '.pending-' + secrets.token_hex(16)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
        try:
            with os.fdopen(fd, 'w', closefd=False) as target:
                json.dump(value, target, sort_keys=True); target.write('\n'); target.flush(); os.fsync(fd)
            os.rename(temp, name, src_dir_fd=folder, dst_dir_fd=folder)
            os.fsync(folder)
        finally:
            os.close(fd)
            with contextlib.suppress(FileNotFoundError): os.unlink(temp, dir_fd=folder)

    def get(self, container, engine, *, private=False):
        value = validate_snapshot({'schemaVersion': 1, 'engine': engine, 'containerId': container,
            'private': private, 'revision': 1, 'enabled': True,
            'persona': {'seed': secrets.token_hex(32), 'options': DEFAULT_OPTIONS.copy(), 'overrides': {}}})
        key = (engine, container)
        if private:
            return copy.deepcopy(self._private.setdefault(key, value))
        name = f'{engine}-{container}.json'
        with self._locked() as folder:
            saved = self._read(folder, name)
            if saved is None: self._write(folder, name, value)
            else: value = saved
        if (value['engine'], value['containerId'], value['private']) != (engine, container, False):
            raise ValueError('Persona record ownership mismatch')
        return value

    def update(self, snapshot, *, enabled=None, options=None, overrides=None, private=None, regenerate=False, clear_overrides=False):
        before = validate_snapshot(snapshot)
        if private is not None and private != before['private']:
            raise ValueError('Cannot change persona ownership')
        after = copy.deepcopy(before)
        after['revision'] += 1
        if enabled is not None: after['enabled'] = enabled
        if options is not None: after['persona']['options'] = copy.deepcopy(options)
        if overrides is not None: after['persona']['overrides'] = copy.deepcopy(overrides)
        if regenerate: after['persona']['seed'] = secrets.token_hex(32)
        if clear_overrides: after['persona']['overrides'] = {}
        after = validate_snapshot(after)
        key = (before['engine'], before['containerId'])
        if before['private']:
            if self._private.get(key) != before: raise ValueError('Stale persona snapshot')
            self._private[key] = after
        else:
            with self._locked() as folder:
                name = f'{key[0]}-{key[1]}.json'
                if self._read(folder, name) != before: raise ValueError('Stale persona snapshot')
                self._write(folder, name, after)
        return copy.deepcopy(after)

    def regenerate(self, snapshot, *, clear_overrides=False):
        return self.update(snapshot, regenerate=True, clear_overrides=clear_overrides)

    def forget_private(self, container, engine):
        """End private ownership after the controller has closed its last window."""
        self._private.pop((engine, container), None)
