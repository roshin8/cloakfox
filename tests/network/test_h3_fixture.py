"""Real loopback aioquic client/server fixture self-test; optional dependency."""
import asyncio
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

@unittest.skipUnless(importlib.util.find_spec('aioquic'), 'Install requirements-h3.txt for actual QUIC fixture self-test')
class QUICFixture(unittest.TestCase):
    def test_parameter_details_keep_public_options_and_discard_connection_ids(self):
        from aioquic.buffer import Buffer
        from h3_fixture import transport_details
        wire=Buffer(capacity=100)
        for kind,value in [(15,b'private-cid'),(12584,b'INAK'),(58,b'abc')]:
            wire.push_uint_var(kind);wire.push_uint_var(len(value));wire.push_bytes(value)
        result=transport_details(wire.data)
        self.assertEqual(result, [[15,{'length':11}], [12584,{'length':4,'publicOptions':'494e414b'}], ['GREASE',{'length':3}]])

    def test_real_http3_exchange_counts_datagrams(self):
        from aioquic.asyncio import QuicConnectionProtocol, connect
        from aioquic.h3.connection import H3Connection, H3_ALPN
        from aioquic.h3.events import DataReceived
        from aioquic.quic.configuration import QuicConfiguration
        from h3_fixture import H3Fixtures, create_certificates
        class Client(QuicConnectionProtocol):
            def __init__(self,*a,**kw):
                super().__init__(*a,**kw)
                self.http=H3Connection(self._quic)
                self.response=asyncio.get_running_loop().create_future()
                self.body=b''
            def quic_event_received(self,event):
                for value in self.http.handle_event(event):
                    if isinstance(value,DataReceived):
                        self.body+=value.data
                        if value.stream_ended and not self.response.done(): self.response.set_result(self.body)
        with tempfile.TemporaryDirectory() as temp:
            ca,cert,key=create_certificates(Path(temp),['localhost'])
            from cryptography import x509
            leaf=x509.load_pem_x509_certificate(cert.read_bytes())
            authority=x509.load_pem_x509_certificate(ca.read_bytes())
            self.assertFalse(leaf.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
            self.assertTrue(authority.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
            self.assertEqual(leaf.issuer,authority.subject)
            fixture=H3Fixtures(cert,key,1)
            try:
                async def exchange():
                    config=QuicConfiguration(is_client=True,alpn_protocols=H3_ALPN,server_name='localhost')
                    config.load_verify_locations(cafile=str(ca))
                    async with connect('127.0.0.1',fixture.ports[0],configuration=config,create_protocol=Client) as client:
                        stream=client._quic.get_next_available_stream_id()
                        client.http.send_headers(stream,[(b':method',b'GET'),(b':scheme',b'https'),(b':authority',b'localhost'),(b':path',b'/fixture-control')],end_stream=True)
                        client.transmit()
                        return await asyncio.wait_for(client.response,5)
                self.assertEqual(asyncio.run(exchange()),b'local-http3-ok')
                self.assertGreater(fixture.observed[0]['datagrams'],0)
                self.assertEqual(fixture.observed[0]['requests'],['/fixture-control'])
                self.assertIn('h3',fixture.observed[0]['alpn'])
                self.assertTrue(fixture.observed[0]['handshakes'])
            finally:fixture.close()
