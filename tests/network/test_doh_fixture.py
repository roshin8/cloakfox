import ipaddress
import struct
import unittest
from doh_fixture import response
class DNSFixture(unittest.TestCase):
    def query(self, kind):
        labels = b''.join(bytes([len(p)]) + p for p in b'positive.dns-fixture.test'.split(b'.')) + b'\0'
        return struct.pack('!6H', 41, 0x0100, 1, 0, 0, 0) + labels + struct.pack('!HH', kind, 1)
    def test_ipv4_and_ipv6(self):
        for kind, address in [(1, '192.0.2.7'), (28, '2001:db8::7')]:
            host, actual_kind, packet = response(self.query(kind))
            self.assertEqual((host, actual_kind), ('positive.dns-fixture.test', kind))
            self.assertEqual(struct.unpack('!6H', packet[:12]), (41, 0x8180, 1, 1, 0, 0))
            self.assertTrue(packet.endswith(ipaddress.ip_address(address).packed))
    def test_invalid_and_no_answer(self):
        for query in [b'', b'\0' * 12, self.query(1)[:-2]]:
            with self.assertRaises(ValueError): response(query)
        self.assertEqual(struct.unpack('!6H', response(self.query(65))[2][:12])[3], 0)
