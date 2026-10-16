"""Pinned upstream fixtures and assertions shared by both native engine audits."""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'tests/fingerprint/libraries'
CREEP = ROOT / 'tests/fingerprint/reports/library-fixtures/creepjs'
MANIFEST = json.loads((LIB / 'upstreams.json').read_text())
FP_BUNDLE = LIB / 'node_modules/@fingerprintjs/fingerprintjs' / MANIFEST['fingerprintjs']['bundle']
FP_PAGE = '''<!doctype html><meta charset=utf-8><title>Local FingerprintJS</title>
<script src="/vendor/fp.js"></script><script>
FingerprintJS.load({monitoring:false}).then(a=>a.get()).then(r=>window.libraryResult={...r,rawCanvas:FingerprintJS.getUnstableCanvasFingerprint(false)},
e=>window.libraryResult={error:String(e)});
</script>'''


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        self.server.requests.append({'host': self.headers.get('Host'), 'path': path,
                                     'ua': self.headers.get('User-Agent'),
                                     'hints': {k: v for k, v in self.headers.items() if k.lower().startswith('sec-ch-')}})
        if path == '/fp.html':
            content, mime = FP_PAGE.encode(), 'text/html; charset=utf-8'
        elif path == '/vendor/fp.js':
            content, mime = FP_BUNDLE.read_bytes(), 'text/javascript'
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_):
        pass



def verify_fixtures():
    assert FP_BUNDLE.is_file() and (CREEP / 'docs/creep.js').is_file(), 'Run scripts/setup-fingerprint-libraries.py first'
    assert (CREEP / '.git').is_dir() and not (CREEP / '.git').is_symlink(), 'Fixture requires its own Git directory'
    commit = subprocess.check_output(['git', '-C', str(CREEP), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == MANIFEST['creepjs']['commit'], 'CreepJS fixture revision drift'
    assert Path(subprocess.check_output(['git', '-C', str(CREEP), 'rev-parse', '--show-toplevel'], text=True).strip()).resolve() == CREEP.resolve(), 'Fixture must have its own Git checkout'
    assert not subprocess.check_output(['git', '-C', str(CREEP), 'status', '--porcelain', '--untracked-files=normal'], text=True).strip(), 'CreepJS fixture is modified'
    package = json.loads((FP_BUNDLE.parents[1] / 'package.json').read_text())
    assert package['version'] == MANIFEST['fingerprintjs']['version']
    assert hashlib.sha256((CREEP / 'docs/creep.js').read_bytes()).hexdigest() == MANIFEST['creepjs']['bundleSHA256'], 'CreepJS bundle checksum mismatch'
    assert hashlib.sha256(FP_BUNDLE.read_bytes()).hexdigest() == MANIFEST['fingerprintjs']['bundleSHA256'], 'FingerprintJS bundle checksum mismatch'
    return {'creepjsCommit': commit, 'fingerprintjsVersion': package['version'],
            'creepjsBundleSHA256': hashlib.sha256((CREEP / 'docs/creep.js').read_bytes()).hexdigest(),
            'fingerprintjsBundleSHA256': hashlib.sha256(FP_BUNDLE.read_bytes()).hexdigest()}


def validate_samples(library, samples, minimum=3):
    """Gate collection/consistency; preserve every upstream flag in raw samples."""
    checks = []
    def check(condition, label):
        checks.append({'pass': bool(condition), 'label': library + ': ' + label})
    check(len(samples) >= minimum, 'required reload samples collected')
    valid = all(isinstance(value, dict) and 'error' not in value for value in samples)
    check(bool(samples) and valid, 'upstream collection completed')
    if not samples or not valid:
        return checks
    def stable(values, label):
        check(all(value is not None for value in values), label + ' collected')
        check(len({stable_hash(value) for value in values}) == 1, label + ' reload stability')
    if library == 'fingerprintjs':
        ids = [value.get('visitorId') for value in samples]
        check(all(isinstance(value, str) and re.fullmatch('[0-9a-f]{32}', value) for value in ids), 'visitor IDs populated')
        stable(ids, 'visitor ID')
        for field in ('geometry', 'text'):
            values = [value.get('rawCanvas', {}).get(field) for value in samples]
            check(all(isinstance(value, str) and value.startswith('data:image/') for value in values), 'raw canvas ' + field)
            stable(values, 'canvas ' + field)
        audio = [value.get('components', {}).get('audio', {}).get('value') for value in samples]
        check(all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in audio),
              'audio contains real positive samples, not timeout/unsupported sentinels')
        for component in ('canvas', 'audio', 'timezone', 'platform', 'screenResolution'):
            entries = [value.get('components', {}).get(component, {}) for value in samples]
            check(all(isinstance(entry, dict) and 'error' not in entry and entry.get('value') is not None for entry in entries), component + ' successful value')
            stable([entry.get('value') for entry in entries], component)
    elif library == 'creepjs':
        fingerprints = [value.get('fingerprint', {}) for value in samples]
        for component in ('canvas2d', 'offlineAudioContext', 'cssMedia', 'screen', 'navigator', 'workerScope'):
            values = [value.get(component, {}).get('$hash') for value in fingerprints]
            check(all(isinstance(value, str) and value for value in values), component + ' collected')
            if component != 'canvas2d':
                stable(values, component)
        for field in ('dataURI', 'paintURI', 'paintCpuURI', 'textURI', 'emojiURI'):
            values = [value.get('canvas2d', {}).get(field) for value in fingerprints]
            check(all(isinstance(value, str) and value.startswith('data:image/') for value in values), field + ' image collected')
            stable(values, field)
        for value in fingerprints:
            navigator, worker = value.get('navigator', {}), value.get('workerScope', {})
            for field in ('platform', 'hardwareConcurrency'):
                check(navigator.get(field) is not None and navigator.get(field) == worker.get(field), 'window/worker ' + field + ' agree')
            css = value.get('cssMedia', {})
            a, b = css.get('mediaCSS', {}), css.get('matchMediaCSS', {})
            check(isinstance(a, dict) and isinstance(b, dict) and a == b and
                  {'color-gamut', 'device-screen', 'prefers-reduced-motion', 'forced-colors'} <= a.keys(),
                  'stylesheet and matchMedia agree')
    else:
        raise ValueError('Unknown fingerprint library')
    return checks


def validate_native_controls(first, second):
    checks = []
    for library in ('fingerprintjs', 'creepjs'):
        a, b = first[library][0], second[library][0]
        if library == 'fingerprintjs':
            equal = a['rawCanvas'] == b['rawCanvas'] and a['visitorId'] == b['visitorId']
        else:
            equal = a['fingerprint']['canvas2d']['dataURI'] == b['fingerprint']['canvas2d']['dataURI']
        checks.append({'pass': equal, 'label': library + ': master-off output ignores different container seeds'})
    return checks
