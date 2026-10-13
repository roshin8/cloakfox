"""Observe Chromium's own TCP/QUIC ClientHello; never trust the fixture CA.

These are pre-certificate handshake observations. They do not establish H2/H3
SETTINGS parity or authenticated HTTP responses.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import time
from probe_cef_isolation import Companion
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'network'))
from h3_fixture import create_certificates, H3Fixtures
from wire_fixture import TLSFixture


def run(binary):
    report = {"certificateVerificationDisabled": False, "httpSettingsVerified": False}
    with tempfile.TemporaryDirectory(prefix='cloakfox-cef-wire-') as directory:
        root = Path(directory).resolve()
        ca, certificate, key = create_certificates(root, ['localhost'])
        extensions = root / 'leaf-extensions.cnf'
        extensions.write_text(extensions.read_text().replace('DNS:localhost', 'DNS:localhost,IP:127.0.0.1'))
        subprocess.run(['openssl', 'x509', '-req', '-in', str(root / 'leaf.csr'),
            '-CA', str(ca), '-CAkey', str(root / 'ca-key.pem'), '-CAcreateserial',
            '-out', str(certificate), '-days', '1', '-extfile', str(extensions)],
            check=True, capture_output=True)
        subprocess.run(['openssl', 'verify', '-CAfile', str(ca), '-purpose', 'sslserver',
                        '-verify_ip', '127.0.0.1', str(certificate)], check=True, capture_output=True)
        tcp = TLSFixture(certificate, key, detailed=True)
        quic = H3Fixtures(certificate, key, count=1, detailed=True)
        try:
            for kind in ('tcp', 'quic'):
                profile = root / kind
                profile.mkdir(mode=0o700)
                port = tcp.server_address[1] if kind == 'tcp' else quic.ports[0]
                app = Companion(binary, profile, quic_port=port if kind == 'quic' else None)
                try:
                    browser = app.open('1', 'about:blank')
                    host = 'localhost' if kind == 'tcp' else '127.0.0.1'
                    response = app.rpc('cdp', browser=browser, method='Page.navigate',
                                       params={'url': f'https://{host}:{port}/'})
                    assert response['ok'], response
                    if kind == 'tcp':
                        assert response['result'].get('errorText') == 'net::ERR_CERT_AUTHORITY_INVALID', response
                        observed = next(x for x in tcp.observed if 'hello' in x)
                        assert observed['hello']['alpn'] == ['h2', 'http/1.1'], observed
                        report[kind] = observed
                    else:
                        observed = quic.observed[0]
                        # Chromium surfaces QUIC TLS verification failure as a
                        # QUIC error. The wire peer supplies the specific alert.
                        assert response['result'].get('errorText') == 'net::ERR_QUIC_PROTOCOL_ERROR', response
                        deadline = time.monotonic() + 5
                        while not any('CERTIFICATE_VERIFY_FAILED' in item['reason'] for item in observed['terminations']) and time.monotonic() < deadline:
                            time.sleep(.01)
                        assert any('CERTIFICATE_VERIFY_FAILED' in item['reason'] for item in observed['terminations']), observed
                        assert not observed['handshakes'] and not observed['requests'], observed
                        assert observed['datagrams'] > 0 and observed.get('clientHellos'), observed
                        assert observed['clientHellos'][0]['alpn'] == ['h3'], observed
                        assert observed.get('parameterDetails'), observed
                        report[kind] = observed
                    report[kind]['untrustedCertificateRejected'] = True
                    report[kind]['certificateErrorSurface'] = response['result']['errorText']
                    report[kind] = copy.deepcopy(report[kind])
                finally:
                    app.close()
        finally:
            quic.close()
            tcp.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.binary.resolve())
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: native TCP/QUIC ClientHello and QUIC parameters observed; untrusted fixture rejected in both transports')
