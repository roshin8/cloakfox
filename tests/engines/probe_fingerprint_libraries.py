"""Required pinned CreepJS/FingerprintJS audit against the native CEF companion.

Uses only disposable profiles and owned loopback pages. DevTools is test-only;
no upstream detector code or detection flags are changed.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/fingerprint'))
from library_audit_common import CREEP, Handler, stable_hash, validate_samples, validate_native_controls, verify_fixtures
from probe_cef_isolation import Companion


LIBRARIES = (
    ('fingerprintjs', '/fp.html', '!!window.libraryResult', 'window.libraryResult'),
    ('creepjs', '/index.html', '!!window.Fingerprint && !!window.Creep',
     '({fingerprint:window.Fingerprint,creep:window.Creep})'),
)


def snapshot(container, seed, enabled):
    # Minimal v1 intentionally works before and after the identity increment.
    # Audio/OS/font masking is not claimed by the current Chromium capability.
    return {'schemaVersion': 1, 'engine': 'chromium', 'containerId': container,
            'private': False, 'revision': 1, 'enabled': enabled,
            'persona': {'seed': seed * 32,
                        'options': {'canvas': True, 'blockWebGPUReadback': False}, 'overrides': {}}}


def frame(app, browser):
    response = app.rpc('cdp', browser=browser, method='Page.getFrameTree', params={})
    assert response.get('ok'), response
    return response['result']['frameTree']['frame']['loaderId']


def collect(app, browser, url, ready, expression, timeout=75):
    previous = frame(app, browser)
    response = app.rpc('navigate', browser=browser, url=url)
    assert response.get('ok'), response
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        document = frame(app, browser)
        if document != previous and app.evaluate(browser, 'location.href') == url:
            value = app.evaluate(browser, 'document.readyState === "complete" && (' + ready + ')')
            if value:
                return document, app.evaluate(browser, 'JSON.parse(JSON.stringify(' + expression + '))')
        time.sleep(.1)
    raise TimeoutError('New document/library did not complete: ' + url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    if not args.binary.is_file():
        parser.error('Required source-built Chromium companion is missing')
    out = args.report_dir
    out.mkdir(parents=True, exist_ok=True)
    provenance = {**verify_fixtures(), 'binary': str(args.binary), 'engine': 'chromium',
                  'contract': 'collection, reload stability, native window/worker agreement, canvas/site/container separation',
                  'notCoveredIsolation': ['audio', 'fonts', 'screen', 'WebRTC', 'cross-OS persona masking']}
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(CREEP / 'docs')))
    server.requests = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {'success': False, 'provenance': provenance, 'cases': [], 'checks': [], 'requests': server.requests}
    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    def check(ok, label):
        report['checks'].append({'pass': bool(ok), 'label': label})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)
    app = None
    profile = tempfile.TemporaryDirectory(prefix='cloakfox-library-audit-')
    try:
        app = Companion(args.binary.resolve(), Path(profile.name))
        provenance['runtime'] = app.ready
        for container, seed, enabled in [('91', '11', True), ('92', '22', True), ('93', '33', False), ('94', '44', False)]:
            accepted = app.rpc('applyConfig', config=snapshot(container, seed, enabled))
            assert accepted.get('ok') and accepted.get('configRevision') == 1, accepted
        # The native shell exits after its last window closes. Keep a blank
        # owner window until quit; audit pages themselves are still closed.
        anchor = app.open('91', 'about:blank', configRevision=1)
        provenance['anchorBrowser'] = anchor
        definitions = [('A', '91', '127.0.0.1'), ('B', '92', '127.0.0.1'),
                       ('A-other-site', '91', 'localhost'), ('A-return', '91', '127.0.0.1'),
                       ('native', '93', '127.0.0.1'), ('native-B', '94', '127.0.0.1')]
        for label, container, host in definitions:
            browser = app.open(container, 'about:blank', configRevision=1)
            case = {'case': label, 'container': container, 'host': host, 'libraries': {}, 'documentIds': {}}
            report['cases'].append(case)
            for library, path, ready, expression in LIBRARIES:
                samples, documents = [], []
                case['libraries'][library] = samples
                case['documentIds'][library] = documents
                for repeat in range(3):
                    print(f'RUN {label}/{library}/{repeat}', flush=True)
                    document, value = collect(app, browser, f'http://{host}:{server.server_port}{path}', ready, expression)
                    samples.append(value)
                    documents.append(document)
                    (out / f'{label}-{library}-{repeat}.json').write_text(json.dumps(value, indent=2) + '\n')
                    save()
                check(len(set(documents)) == 3, label + '/' + library + ': three distinct document loads')
                for result in validate_samples(library, samples):
                    check(result['pass'], label + '/' + result['label'])
            response = app.rpc('close', browser=browser)
            assert response.get('ok'), response
        by_name = {case['case']: case for case in report['cases']}
        def canvas(name, library):
            sample = by_name[name]['libraries'][library][0]
            return sample['rawCanvas'] if library == 'fingerprintjs' else sample['fingerprint']['canvas2d']['dataURI']
        for left, right in [('A', 'B'), ('A', 'A-other-site'), ('A', 'native')]:
            for library in ('fingerprintjs', 'creepjs'):
                check(canvas(left, library) != canvas(right, library), f'{left}/{right}: {library} canvas separation')
            check(by_name[left]['libraries']['fingerprintjs'][0]['visitorId'] != by_name[right]['libraries']['fingerprintjs'][0]['visitorId'],
                  f'{left}/{right}: FingerprintJS visitor ID separation')
        for library in ('fingerprintjs', 'creepjs'):
            check(canvas('A', library) == canvas('A-return', library), library + ': return restores original site canvas')
        check(by_name['A']['libraries']['fingerprintjs'][0]['visitorId'] == by_name['A-return']['libraries']['fingerprintjs'][0]['visitorId'],
              'FingerprintJS: return restores original visitor ID')
        for result in validate_native_controls(by_name['native']['libraries'], by_name['native-B']['libraries']):
            check(result['pass'], result['label'])
        report['success'] = bool(report['checks']) and all(item['pass'] for item in report['checks'])
        assert report['success'], 'Required library assertions failed; inspect raw results and detector warnings'
    except BaseException as error:
        report['error'] = str(error)
        report['success'] = False
        raise
    finally:
        try:
            if app is not None:
                app.close()
        except BaseException as error:
            report['success'] = False
            report['shutdownError'] = str(error)
            raise
        finally:
            profile.cleanup()
            server.shutdown()
            server.server_close()
            save()
            (out / 'summary.json').write_text(json.dumps({key: report[key] for key in ('success', 'provenance', 'checks')}, indent=2) + '\n')


if __name__ == '__main__':
    main()
