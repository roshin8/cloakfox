"""Loopback-only HTTP/3 server with per-endpoint raw UDP counters (aioquic)."""
import asyncio
import threading
from pathlib import Path
import subprocess
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, HandshakeCompleted, ConnectionTerminated


class HTTP3(QuicConnectionProtocol):
    def __init__(self, *args, observed, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = None
        self.observed = observed

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            self.observed['handshakes'].append({'alpn': event.alpn_protocol,
                'earlyDataAccepted': event.early_data_accepted, 'sessionResumed': event.session_resumed})
        if isinstance(event, ConnectionTerminated):
            self.observed['terminations'].append({'errorCode': event.error_code,
                'frameType': event.frame_type, 'reason': event.reason_phrase})
        if isinstance(event, ProtocolNegotiated):
            self.http = H3Connection(self._quic)
            self.observed['alpn'].append(event.alpn_protocol)
        if self.http:
            for message in self.http.handle_event(event):
                if isinstance(message, HeadersReceived):
                    headers = dict(message.headers)
                    self.observed['requests'].append(headers.get(b':path', b'').decode())
                    body = b'local-http3-ok'
                    self.http.send_headers(message.stream_id, [(b':status', b'200'), (b'content-length', str(len(body)).encode())])
                    self.http.send_data(message.stream_id, body, end_stream=True)
                    self.transmit()


class H3Fixtures:
    def __init__(self, certificate, private_key, count=3):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.servers = []
        self.ports = []
        self.observed = [dict(datagrams=0, alpn=[], requests=[], handshakes=[], terminations=[]) for _ in range(count)]
        asyncio.run_coroutine_threadsafe(self.start(certificate, private_key), self.loop).result(timeout=15)

    async def start(self, certificate, private_key):
        for observed in self.observed:
            configuration = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)
            configuration.load_cert_chain(certificate, private_key)
            server = await serve('127.0.0.1', 0, configuration=configuration,
                                 create_protocol=lambda *a, observed=observed, **kw: HTTP3(*a, observed=observed, **kw))
            original = server.datagram_received
            def received(data, address, original=original, observed=observed):
                observed['datagrams'] += 1
                original(data, address)
            # Count at UDP ingress, including packets that fail the QUIC handshake.
            server.datagram_received = received
            self.servers.append(server)
            self.ports.append(server._transport.get_extra_info('sockname')[1])

    def close(self):
        async def shutdown():
            for server in self.servers:
                server.close()
            await asyncio.sleep(0.1)
        asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result(timeout=5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()


def create_certificates(directory, hosts):
    """Distinct CA and end-entity leaf: NSS rejects CA:TRUE server certificates."""
    root = Path(directory)
    ca, ca_key = root / 'ca.pem', root / 'ca-key.pem'
    cert, key, csr = root / 'leaf.pem', root / 'leaf-key.pem', root / 'leaf.csr'
    def openssl(*args):
        subprocess.run(['openssl', *map(str, args)], check=True, capture_output=True)
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', ca_key,
            '-out', ca, '-days', '1', '-subj', '/CN=Cloakfox QUIC TEST ROOT ONLY',
            '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', key,
            '-out', csr, '-subj', '/CN=' + hosts[0])
    extensions = root / 'leaf-extensions.cnf'
    extensions.write_text('basicConstraints=critical,CA:FALSE\n'
        'keyUsage=critical,digitalSignature,keyEncipherment\n'
        'extendedKeyUsage=serverAuth\nsubjectAltName=' + ','.join('DNS:' + host for host in hosts) + '\n')
    openssl('x509', '-req', '-in', csr, '-CA', ca, '-CAkey', ca_key,
            '-CAcreateserial', '-out', cert, '-days', '1', '-extfile', extensions)
    openssl('verify', '-purpose', 'sslserver', '-CAfile', ca, cert)
    return ca, cert, key
