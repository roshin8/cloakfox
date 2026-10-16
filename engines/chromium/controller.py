"""Private inherited-pipe controller for versioned Chromium persona snapshots.

This is a development companion adapter, not the Gecko UI bridge. No listening
socket, CDP endpoint, script injection or engine impersonation is introduced.
"""
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

from engines.shared.persona_config import SCHEMA_VERSION, PersonaStore, validate_snapshot


class ChromiumController:
    def __init__(self, binary: Path, profile_root: Path, *, store=None):
        self.store = store if store is not None else PersonaStore(profile_root / 'personas')
        self.applied = {}
        self._private_configs = set()
        self._serial = 0
        self._lock = threading.Lock()
        self._messages = queue.Queue()
        self._reader_error = False
        self.process = subprocess.Popen([str(binary.resolve()), '--profile-root=' + str(profile_root.resolve()), '--test-keychain'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        def read():
            try:
                for line in self.process.stdout:
                    self._messages.put(json.loads(line))
            except (ValueError, OSError):
                self._reader_error = True
            finally:
                self._messages.put({'event': 'eof'})
        self._reader = threading.Thread(target=read, daemon=True)
        self._reader.start()
        try:
            self.ready = self._wait(lambda value: value.get('event') == 'ready')
            if (self.ready.get('version') != 1 or self.ready.get('engine') != 'chromium'
                    or self.ready.get('configSchemaVersion') != SCHEMA_VERSION):
                raise RuntimeError('Companion config protocol is incompatible')
        except BaseException:
            self.close()
            raise

    def _wait(self, match, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('Companion response timed out')
            try: value = self._messages.get(timeout=remaining)
            except queue.Empty: raise TimeoutError('Companion response timed out') from None
            if type(value) is not dict: raise RuntimeError('Invalid companion response')
            if value.get('event') == 'configDiscarded' and value.get('private') is True:
                container = value.get('container')
                self.store.forget_private(container, 'chromium')
                self._private_configs.discard(container)
                self.applied.pop((container, True), None)
            if value.get('event') in ('eof', 'crashed'):
                raise RuntimeError('Companion exited or renderer crashed')
            if match(value): return value

    def _request(self, command, **fields):
        self._serial += 1
        request = dict(version=1, id=self._serial, command=command, **fields)
        self.process.stdin.write(json.dumps(request) + '\n'); self.process.stdin.flush()
        result = self._wait(lambda value: value.get('id') == self._serial)
        if result.get('version') != 1 or type(result.get('ok')) is not bool:
            raise RuntimeError('Invalid companion acknowledgement')
        if not result['ok']:
            raise RuntimeError(result.get('error', 'Companion request rejected'))
        return result

    def _apply(self, snapshot):
        config = validate_snapshot(snapshot)
        if config['engine'] != 'chromium': raise ValueError('Wrong engine for Chromium adapter')
        supported = self.ready.get('supportedPersonaOptions', [])
        if any(key not in supported for key in config['persona']['options']):
            raise RuntimeError('Companion does not implement requested persona options')
        if config['private']:
            if config != self.store.get(config['containerId'], 'chromium', private=True):
                raise ValueError('Private config does not belong to current controller session')
            self._private_configs.add(config['containerId'])
        result = self._request('applyConfig', config=config)
        if (result.get('event') != 'configApplied' or result.get('engine') != 'chromium'
                or result.get('container') != config['containerId']
                or result.get('private') is not config['private']
                or result.get('configRevision') != config['revision']):
            raise RuntimeError('Companion acknowledged a different config snapshot')
        self.applied[(config['containerId'], config['private'])] = config['revision']
        return config

    def apply(self, snapshot):
        with self._lock:
            return self._apply(snapshot)

    def open(self, snapshot, url):
        with self._lock:
            config = self._apply(snapshot)
            result = self._request('open', container=config['containerId'], private=config['private'],
                                   configRevision=config['revision'], url=url)
            if (result.get('configRevision') != config['revision'] or
                    result.get('container') != config['containerId'] or result.get('private') is not config['private']):
                raise RuntimeError('Opened browser has a different config snapshot')
            return result

    def close_browser(self, browser):
        with self._lock:
            self._request('close', browser=browser)
            self._wait(lambda value: value.get('event') == 'closed' and value.get('browser') == browser)

    def wait(self):
        """Wait for UI closure, reporting renderer failure instead of hanging."""
        while self.process.poll() is None:
            try: self._wait(lambda value: value.get('event') == 'closed', timeout=1)
            except TimeoutError: continue
            except RuntimeError:
                if self._reader_error: raise
                try: code = self.process.wait(timeout=2)
                except subprocess.TimeoutExpired: raise
                if code: raise
                break
        if self.process.wait() != 0: raise RuntimeError('Companion exited unsuccessfully')

    def close(self):
        if not self.process.stdin.closed: self.process.stdin.close()
        if self.process.poll() is None:
            try: self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.terminate(); self.process.wait(timeout=10)
        self._reader.join(timeout=2)
        self.process.stdout.close()
        # EOF/process exit retires even a config acknowledged before any window
        # was created. A reused controller store must not reuse private seeds.
        for container in self._private_configs:
            self.store.forget_private(container, 'chromium')
            self.applied.pop((container, True), None)
        self._private_configs.clear()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
