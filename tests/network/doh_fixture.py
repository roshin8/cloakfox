"""Small local RFC 1035/RFC 8484 response fixture; deliberately no recursion."""
import base64
import http.server
import ipaddress
import struct
from urllib.parse import urlsplit, parse_qs


def response(query):
    if len(query) < 12:
        raise ValueError('Truncated header')
    ident, flags, questions, _, _, _ = struct.unpack('!6H', query[:12])
    if questions != 1 or flags & 0x8000:
        raise ValueError('Expected one DNS question')
    offset = 12
    labels = []
    while True:
        if offset >= len(query):
            raise ValueError('Truncated name')
        length = query[offset]
        offset += 1
        if length == 0:
            break
        if length > 63 or offset + length > len(query):
            raise ValueError('Unsupported name')
        labels.append(query[offset:offset + length].decode('ascii'))
        offset += length
    if offset + 4 > len(query):
        raise ValueError('Truncated question')
    kind, dnsclass = struct.unpack('!HH', query[offset:offset + 4])
    end = offset + 4
    host = '.'.join(labels).lower()
    address = {1: '192.0.2.7', 28: '2001:db8::7'}.get(kind)
    valid = dnsclass == 1 and host.endswith('.dns-fixture.test') and address
    data = ipaddress.ip_address(address).packed if valid else b''
    answer = b'\xc0\x0c' + struct.pack('!HHIH', kind, 1, 0, len(data)) + data if valid else b''
    packet = struct.pack('!6H', ident, 0x8180, 1, int(bool(valid)), 0, 0) + query[12:end] + answer
    return host, kind, packet


class DoH(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def answer(self, query):
        try:
            host, kind, data = response(query)
        except (ValueError, UnicodeError):
            self.send_error(400)
            return
        self.server.queries.append((host, kind))
        self.send_response(200)
        self.send_header('Content-Type', 'application/dns-message')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        if self.path != '/dns-query' or not 0 < length <= 4096:
            self.send_error(400)
            return
        self.answer(self.rfile.read(length))

    def do_GET(self):
        values = parse_qs(urlsplit(self.path).query)
        encoded = values.get('dns', [''])[0]
        try:
            self.answer(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        except ValueError:
            self.send_error(400)

    def log_message(self, *args):
        pass
