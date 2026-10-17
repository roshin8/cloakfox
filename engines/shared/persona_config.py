"""Versioned engine-neutral persona snapshots; no Gecko preferences or page scripts.

Only implemented portable option names belong in v1. A backend must additionally
check its own capability report before accepting a snapshot. The store is the
controller authority, not a second browser profile or an engine adapter.
"""
import contextlib
import copy
import fcntl
import json
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import stat

SCHEMA_VERSION = 1
BASE_OPTIONS = {'canvas': True, 'blockWebGPUReadback': False}
DEFAULT_OPTIONS = {**BASE_OPTIONS, 'navigator': True, 'language': True, 'timezone': True}
REGIONS = (
    (('en-US', 'en'), 'America/New_York'),
    (('en-GB', 'en'), 'Europe/London'),
    (('de-DE', 'de'), 'Europe/Berlin'),
    (('fr-FR', 'fr'), 'Europe/Paris'),
    (('ja-JP', 'ja'), 'Asia/Tokyo'),
)
TIMEZONES = {'UTC', 'America/Los_Angeles', *(zone for _, zone in REGIONS)}


def validate_presentation(value):
    if type(value) is not dict or set(value) != {'hardwareConcurrency', 'deviceMemory', 'languages', 'timezone'}:
        raise ValueError('Unsupported presentation fields')
    if type(value['hardwareConcurrency']) is not int or not 1 <= value['hardwareConcurrency'] <= 128:
        raise ValueError('Unsupported hardware concurrency')
    if type(value['deviceMemory']) is not int or value['deviceMemory'] not in (4, 8):
        raise ValueError('Unsupported device memory')
    if type(value['languages']) is not list or tuple(value['languages']) not in tuple(langs for langs, _ in REGIONS):
        raise ValueError('Unsupported language preset')
    if type(value['timezone']) is not str or value['timezone'] not in TIMEZONES:
        raise ValueError('Unsupported timezone preset')
    return copy.deepcopy(value)


def sample_presentation(seed):
    digest = hmac.new(bytes.fromhex(seed), b'cloakfox-presentation-v1', hashlib.sha256).digest()
    languages, timezone = REGIONS[digest[0] % len(REGIONS)]
    return {'hardwareConcurrency': (4, 8, 16)[digest[1] % 3],
            'deviceMemory': (4, 8)[digest[2] % 2],
            'languages': list(languages), 'timezone': timezone}
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
    fields(persona, {'seed', 'options', 'overrides'} | ({'presentation'} if 'presentation' in persona else set()))
    if type(persona['seed']) is not str or not re.fullmatch('[0-9a-f]{64}', persona['seed']):
        raise ValueError('Invalid persona seed')
    if type(persona['options']) is not dict or not set(BASE_OPTIONS) <= set(persona['options']):
        raise ValueError('Missing persona options')
    if 'presentation' in persona:
        validate_presentation(persona['presentation'])
    for name in ('options', 'overrides'):
        options = persona[name]
        if type(options) is not dict: raise ValueError('Unsupported persona option')
        for key, item in options.items():
            if key == 'presentation' and name == 'overrides' and 'presentation' in persona:
                if validate_presentation(item) != persona['presentation']:
                    raise ValueError('Presentation override not applied')
            elif key not in DEFAULT_OPTIONS or type(item) is not bool:
                raise ValueError('Unsupported persona option')
            if key in ('navigator', 'language', 'timezone') and 'presentation' not in persona:
                raise ValueError('Presentation is required for identity options')
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
        seed = secrets.token_hex(32)
        value = validate_snapshot({'schemaVersion': 1, 'engine': engine, 'containerId': container,
            'private': private, 'revision': 1, 'enabled': True,
            'persona': {'seed': seed, 'options': DEFAULT_OPTIONS.copy(), 'overrides': {}, 'presentation': sample_presentation(seed)}})
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

    def update(self, snapshot, *, enabled=None, options=None, overrides=None, presentation=None, private=None, regenerate=False, clear_overrides=False):
        before = validate_snapshot(snapshot)
        if private is not None and private != before['private']:
            raise ValueError('Cannot change persona ownership')
        after = copy.deepcopy(before)
        after['revision'] += 1
        if enabled is not None: after['enabled'] = enabled
        if options is not None: after['persona']['options'] = copy.deepcopy(options)
        if overrides is not None: after['persona']['overrides'] = copy.deepcopy(overrides)
        if presentation is not None:
            after['persona']['overrides']['presentation'] = validate_presentation(presentation)
        if regenerate:
            after['persona']['seed'] = secrets.token_hex(32)
            after['persona']['options'] = {**DEFAULT_OPTIONS, **after['persona']['options']}
        if clear_overrides: after['persona']['overrides'] = {}
        if presentation is not None or regenerate or 'presentation' in after['persona']:
            after['persona']['presentation'] = copy.deepcopy(after['persona']['overrides'].get(
                'presentation', sample_presentation(after['persona']['seed'])))
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
