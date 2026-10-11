"""Loopback-only HTTP/3 server with per-endpoint raw UDP counters (aioquic)."""
import asyncio
import threading
from pathlib import Path
import subprocess
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, HandshakeCompleted, ConnectionTerminated, StreamDataReceived
from aioquic.buffer import Buffer
from aioquic.quic.packet import pull_quic_header, QuicPacketType


def transport_details(data):
    """Public parameter lengths/options, never connection identifiers."""
    buffer=Buffer(data=data); result=[]
    while not buffer.eof():
        kind=buffer.pull_uint_var(); size=buffer.pull_uint_var(); value=buffer.pull_bytes(size)
        detail={'length':size}
        if kind==12584: detail['publicOptions']=value.hex()
        result.append(['GREASE' if kind % 31 == 27 else kind,detail])
    return result


def transport_structure(data):
    """Retain parameter order/integers, excluding GREASE and connection IDs."""
    buffer = Buffer(data=data)
    result = []
    numeric = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 32}
    while not buffer.eof():
        kind = buffer.pull_uint_var(); size = buffer.pull_uint_var()
        value = buffer.pull_bytes(size)
        if kind % 31 == 27:  # RFC 9000 reserved GREASE parameters.
            continue
        if kind in numeric:
            parsed = Buffer(data=value).pull_uint_var()
        elif kind == 17:
            assert size % 4 == 0
            versions = [int.from_bytes(value[i:i+4], 'big') for i in range(0,size,4)]
            parsed = [v for v in versions if v & 0x0f0f0f0f != 0x0a0a0a0a]
        elif kind in (0, 2, 13, 15, 16):
            parsed = {'opaqueLength': size}
        else:
            parsed = {'length': size}
        result.append([kind, parsed])
    return result


class HTTP3(QuicConnectionProtocol):
    def __init__(self, *args, observed, detailed=False, alps=None, hold_settings=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = None
        self.hold_settings = hold_settings
        self.held_settings = []
        self.stream_prefixes = {}
        self.capacity_observed = False
        self.observed = observed
        parse = self._quic._parse_transport_parameters
        def capture_parameters(data, from_session_ticket=False):
            if not from_session_ticket:
                self.observed.setdefault('transportParameters', []).append(transport_structure(data))
                if detailed:
                    self.observed.setdefault('parameterDetails', []).append(transport_details(data))
            return parse(data, from_session_ticket=from_session_ticket)
        self._quic._parse_transport_parameters = capture_parameters
        initialize = self._quic._initialize
        def capture_initialize(*args, **kwargs):
            initialize(*args, **kwargs)
            tls = self._quic.tls
            hello = tls._server_handle_hello
            if alps is not None:
                # aioquic has no ALPS implementation. This local fixture adds
                # the draft's authenticated client EE and verifies Finished
                # over it, rather than just injecting ClientHello bytes.
                import aioquic.tls as t
                expected = {'clientEE':False,'offered':False}
                expect_finished = tls._server_expect_finished
                process_message = tls._handle_reassembled_message
                setup_keys = tls._setup_traffic_protection
                def deferred_finished(buffer):
                    if expected['offered'] and not tls.early_data_accepted:
                        expected['clientEE']=True
                        tls._set_state(t.State.SERVER_EXPECT_FINISHED)
                    else:
                        expect_finished(buffer)
                def process_alps(message_type,input_buf,output_buf):
                    if expected['clientEE']:
                        if message_type != t.HandshakeType.ENCRYPTED_EXTENSIONS:
                            raise t.AlertUnexpectedMessage('Missing ALPS client EE')
                        extension=t.pull_encrypted_extensions(input_buf)
                        if extension.alpn_protocol or extension.early_data or extension.other_extensions!=[(17613,b'')]:
                            raise t.AlertIllegalParameter('Invalid ALPS client settings')
                        tls.key_schedule.update_hash(input_buf.data)
                        expected['clientEE']=False
                        self.observed.setdefault('alpsClientEE',[]).append(True)
                        expect_finished(output_buf[t.Epoch.ONE_RTT])
                    else:
                        return process_message(message_type,input_buf,output_buf)
                def prepare_extensions(direction,epoch,label):
                    if direction==t.Direction.ENCRYPT and epoch==t.Epoch.HANDSHAKE and tls.early_data_accepted:
                        tls.handshake_extensions=[x for x in tls.handshake_extensions if x[0]!=17613]
                    return setup_keys(direction,epoch,label)
                tls._server_expect_finished=deferred_finished
                tls._handle_reassembled_message=process_alps
                tls._setup_traffic_protection=prepare_extensions
            def capture_hello(input_buf, *buffers):
                from tls_hello import client_hello
                structural = client_hello(input_buf.data_slice(input_buf.tell(), input_buf.capacity), detailed=detailed)
                self.observed.setdefault('clientHellos', []).append(structural)
                if alps is not None:
                    expected['offered']=17613 in structural['extensions']
                    self.observed.setdefault('alpsOffered',[]).append(expected['offered'])
                    if expected['offered']:
                        tls.handshake_extensions.append((17613,alps))
                return hello(input_buf, *buffers)
            tls._server_handle_hello = capture_hello
        self._quic._initialize = capture_initialize

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            self.observed['handshakes'].append({'alpn': event.alpn_protocol,
                'earlyDataAccepted': event.early_data_accepted, 'sessionResumed': event.session_resumed})
        if isinstance(event, ConnectionTerminated):
            self.observed['terminations'].append({'errorCode': event.error_code,
                'frameType': event.frame_type, 'reason': event.reason_phrase})
        if isinstance(event, ProtocolNegotiated):
            send = self._quic.send_stream_data
            def hold(stream_id,data,end_stream=False):
                # During construction the server sends stream type 0, then its
                # ordinary SETTINGS. Delay only that SETTINGS frame so a real
                # non-default ALPS QPACK effect can be observed beforehand.
                if self.hold_settings and stream_id==getattr(self.http,'_local_control_stream_id',None):
                    self.held_settings.append((stream_id,data,end_stream))
                else:
                    send(stream_id,data,end_stream)
            if self.hold_settings:
                # _local_control_stream_id exists on the H3 object while its
                # constructor invokes _init_connection.
                class DeferredSettingsH3(H3Connection):
                    def _init_connection(http):
                        self.http=http
                        return super()._init_connection()
                self._quic.send_stream_data=hold
                try:self.http=DeferredSettingsH3(self._quic)
                finally:self._quic.send_stream_data=send
            else:self.http=H3Connection(self._quic)
            self.observed['alpn'].append(event.alpn_protocol)
        if self.http:
            if isinstance(event,StreamDataReceived) and event.stream_id % 4==2:
                prefix=self.stream_prefixes.setdefault(event.stream_id,bytearray())
                prefix.extend(event.data[:max(0,32-len(prefix))])
            messages=self.http.handle_event(event)
            encoder=self.stream_prefixes.get(self.http._peer_encoder_stream_id,b'')
            if not self.capacity_observed and self.held_settings and len(encoder)>1 and encoder[0]==2 and encoder[1]&0xe0==0x20:
                value=encoder[1]&0x1f;cursor=2;shift=0
                if value==0x1f:
                    while cursor<len(encoder):
                        byte=encoder[cursor];cursor+=1;value+=(byte&0x7f)<<shift;shift+=7
                        if byte<128:break
                    else:value=None
                if value is not None:
                    self.observed.setdefault('alpsEncoderCapacityBeforeSettings',[]).append(value)
                    self.capacity_observed=True
            for message in messages:
                if isinstance(message, HeadersReceived):
                    for stream_id,data,end_stream in self.held_settings:
                        self._quic.send_stream_data(stream_id,data,end_stream)
                    self.held_settings.clear()
                    headers = dict(message.headers)
                    self.observed['requests'].append(headers.get(b':path', b'').decode())
                    body = b'local-http3-ok'
                    self.http.send_headers(message.stream_id, [(b':status', b'200'), (b'content-length', str(len(body)).encode())])
                    self.http.send_data(message.stream_id, body, end_stream=True)
                    self.transmit()
            if self.http.received_settings is not None:
                # RFC 9114 reserves 0x1f*N + 0x21 for H3 SETTINGS GREASE.
                self.observed['settings'] = [[k, v] for k, v in self.http.received_settings.items()
                                            if k < 33 or (k-33) % 31 != 0]


class H3Fixtures:
    def __init__(self, certificate, private_key, count=3, detailed=False,
                 retry=False,resumption=False,alps=None,hold_settings=False):
        self.detailed = detailed
        self.retry = retry
        self.resumption = resumption
        self.alps = alps
        self.hold_settings = hold_settings
        self.tickets = {}
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
                                 retry=self.retry,
                                 session_ticket_fetcher=self.tickets.get if self.resumption else None,
                                 session_ticket_handler=(lambda ticket:self.tickets.__setitem__(ticket.ticket,ticket)) if self.resumption else None,
                                 create_protocol=lambda *a, observed=observed, **kw: HTTP3(*a, observed=observed, detailed=self.detailed, alps=self.alps, hold_settings=self.hold_settings, **kw))
            original = server.datagram_received
            def received(data, address, original=original, observed=observed):
                observed['datagrams'] += 1
                if self.detailed:
                    try:
                        header=pull_quic_header(Buffer(data=data),host_cid_length=8)
                        if header.packet_type==QuicPacketType.INITIAL:
                            observed.setdefault('initialPackets',[]).append({
                                'datagramLength':len(data),'version':header.version,
                                'destinationIdLength':len(header.destination_cid),
                                'sourceIdLength':len(header.source_cid),'tokenLength':len(header.token)})
                    except ValueError:
                        pass
                original(data, address)
            # Count at UDP ingress, including packets that fail the QUIC handshake.
            server.datagram_received = received
            self.servers.append(server)
            self.ports.append(server._transport.get_extra_info('sockname')[1])

    def close_connections(self,index=0):
        async def disconnect():
            # A single protocol is indexed by several connection IDs.
            for protocol in set(self.servers[index]._protocols.values()):
                protocol.close(error_code=0,reason_phrase='local test reconnect')
            await asyncio.sleep(.25)
        asyncio.run_coroutine_threadsafe(disconnect(),self.loop).result(timeout=5)

    def close(self):
        async def shutdown():
            for server in self.servers:
                server.close()
            await asyncio.sleep(0.1)
        asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result(timeout=5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()


def create_certificates(directory, hosts, *, leaf_curve=None):
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
    key_args=['ec','-pkeyopt','ec_paramgen_curve:'+leaf_curve] if leaf_curve else ['rsa:2048']
    openssl('req', '-new', '-newkey', *key_args, '-nodes', '-keyout', key,
            '-out', csr, '-subj', '/CN=' + hosts[0])
    extensions = root / 'leaf-extensions.cnf'
    extensions.write_text('basicConstraints=critical,CA:FALSE\n'
        'keyUsage=critical,digitalSignature,keyEncipherment\n'
        'extendedKeyUsage=serverAuth\nsubjectAltName=' + ','.join('DNS:' + host for host in hosts) + '\n')
    openssl('x509', '-req', '-in', csr, '-CA', ca, '-CAkey', ca_key,
            '-CAcreateserial', '-out', cert, '-days', '1', '-extfile', extensions)
    openssl('verify', '-purpose', 'sslserver', '-CAfile', ca, cert)
    return ca, cert, key
