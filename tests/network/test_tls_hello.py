import struct
import unittest
import ssl
import tempfile
from pathlib import Path
from tls_hello import client_hello

def hello_with(extensions, ciphers=b'\x0a\x0a\x13\x01', session=b''):
    body = (b'\x03\x03' + bytes(32) + bytes([len(session)]) + session
            + len(ciphers).to_bytes(2, 'big') + ciphers + b'\x01\x00'
            + len(extensions).to_bytes(2, 'big') + extensions)
    return b'\x01' + len(body).to_bytes(3, 'big') + body

def extension(kind, value):
    return struct.pack('!HH', kind, len(value)) + value

class TLSHelloParser(unittest.TestCase):
    def test_grease_alpn_is_structural_noise_not_an_ascii_protocol(self):
        protocols=b'\x02h2\x02\xaa\xaa'
        alpn=struct.pack('!H',len(protocols))+protocols
        extensions=struct.pack('!HH',16,len(alpn))+alpn
        body=b'\x03\x03'+bytes(32)+b'\x00\x00\x02\x13\x01\x01\x00'+struct.pack('!H',len(extensions))+extensions
        hello=b'\x01'+len(body).to_bytes(3,'big')+body
        assert client_hello(hello)['alpn']==['h2']

    def test_detailed_capture_retains_grease_shape_without_secret_bytes(self):
        extensions = (extension(0x2a2a, b'\x00')
            + extension(10, b'\x00\x04\x3a\x3a\x00\x1d')
            + extension(51, b'\x00\x0c\x3a\x3a\x00\x01\x00\x00\x1d\x00\x03key')
            + extension(17613, b'\x00\x03\x02h2')
            + extension(51764, b'\x00\x00'))
        report = client_hello(hello_with(extensions, session=b'SECRET'), detailed=True)
        shape = report['shape']
        self.assertEqual(shape['ciphers'], ['GREASE', 4865])
        self.assertEqual(shape['groups'], ['GREASE', 29])
        self.assertEqual(shape['keyShares'], [['GREASE', 1], [29, 3]])
        self.assertEqual(shape['sessionIdLength'], 6)
        self.assertEqual(shape['extensions'], [['GREASE', 1], [10, 6], [51, 14], [17613, 5], [51764, 2]])
        self.assertEqual(shape['payloads'], {'17613': '0003026832', '51764': '0000'})
        self.assertNotIn('SECRET', str(report))
        self.assertNotIn('6b6579', str(report))

    def test_rejects_truncated_extension_vector(self):
        malformed = extension(23, b'') + b'\x00'
        with self.assertRaises(ValueError):
            client_hello(hello_with(malformed), detailed=True)

    def test_fixture_observes_real_hello_retry_without_recording_key_material(self):
        from h3_fixture import create_certificates
        from wire_fixture import TLSFixture
        import socket
        with tempfile.TemporaryDirectory() as temp:
            ca,cert,key=create_certificates(Path(temp), ['localhost'])
            fixture=TLSFixture(cert,key,detailed=True,curve='prime256v1')
            try:
                context=ssl.create_default_context(cafile=str(ca))
                context.minimum_version=ssl.TLSVersion.TLSv1_3
                with socket.create_connection(fixture.server_address) as raw:
                    with context.wrap_socket(raw,server_hostname='localhost') as stream:
                        stream.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
                        self.assertIn(b'local-wire-ok',stream.recv(65536))
                records=[r for r in fixture.observed if 'tlsVersion' in r]
                self.assertEqual(len(records[0]['clientHellos']),2)
                self.assertEqual(records[0]['clientHellos'][1]['keyShareGroups'],[23])
                self.assertEqual(records[0]['tlsVersion'],'TLSv1.3')
            finally:
                fixture.close()

    def test_fixture_observes_real_resumption_in_both_tls_versions(self):
        from h3_fixture import create_certificates
        from wire_fixture import TLSFixture
        import socket
        with tempfile.TemporaryDirectory() as temp:
            ca,cert,key=create_certificates(Path(temp), ['localhost'])
            for version in [ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3]:
                fixture=TLSFixture(cert,key,resumption=True,maximum_version=version)
                try:
                    context=ssl.create_default_context(cafile=str(ca))
                    context.minimum_version=context.maximum_version=version
                    session=None
                    for _ in range(2):
                        with socket.create_connection(fixture.server_address) as raw:
                            with context.wrap_socket(raw,server_hostname='localhost',session=session) as stream:
                                stream.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
                                self.assertIn(b'local-wire-ok',stream.recv(65536))
                                session=stream.session
                    records=[r for r in fixture.observed if 'tlsVersion' in r]
                    self.assertEqual([r['sessionReused'] for r in records],[False,True])
                finally:fixture.close()
