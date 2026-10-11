import struct
from tls_hello import client_hello

def test_grease_alpn_is_structural_noise_not_an_ascii_protocol():
    protocols=b'\x02h2\x02\xaa\xaa'
    alpn=struct.pack('!H',len(protocols))+protocols
    extensions=struct.pack('!HH',16,len(alpn))+alpn
    body=b'\x03\x03'+bytes(32)+b'\x00\x00\x02\x13\x01\x01\x00'+struct.pack('!H',len(extensions))+extensions
    hello=b'\x01'+len(body).to_bytes(3,'big')+body
    assert client_hello(hello)['alpn']==['h2']
