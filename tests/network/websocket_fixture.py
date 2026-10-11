"""Loopback RFC 6455 echo and forwarding proxy for routing acceptance."""
import base64
import hashlib
import select
import socket
import socketserver
import ssl
import threading
from wire_fixture import peek_hello


def read_exact(stream, count):
    data=b''
    while len(data)<count:
        chunk=stream.recv(count-len(data))
        if not chunk:raise EOFError()
        data+=chunk
    return data


def headers(stream):
    data=b''
    while not data.endswith(b'\r\n\r\n'):
        data+=read_exact(stream,1)
        assert len(data)<32768
    return data


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.accepts+=1
        stream=self.request
        try:
            stream.settimeout(10)
            if self.server.context:
                self.server.hellos.append(peek_hello(stream))
                stream=self.server.context.wrap_socket(stream,server_side=True)
            data=headers(stream);lines=data.decode().split('\r\n')
            fields=dict(line.split(': ',1) for line in lines[1:] if ': ' in line)
            fields={k.lower():v for k,v in fields.items()}
            assert fields['upgrade'].lower()=='websocket' and fields['sec-websocket-version']=='13'
            self.server.requests.append({'path':lines[0].split()[1],
                'origin':fields.get('origin'),'protocol':fields.get('sec-websocket-protocol')})
            accept=base64.b64encode(hashlib.sha1((fields['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
            stream.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\nSec-WebSocket-Protocol: local-echo\r\n\r\n')
            while True:
                first,size=read_exact(stream,2)
                assert size&128,'Client frames must be masked'
                n=size&127
                if n==126:n=int.from_bytes(read_exact(stream,2),'big')
                assert n<65536
                mask=read_exact(stream,4);payload=read_exact(stream,n)
                body=bytes(value^mask[i%4] for i,value in enumerate(payload))
                encoded=bytes([first,n]) if n<126 else bytes([first,126])+n.to_bytes(2,'big')
                stream.sendall(encoded+body)
                if first&15==8:return
        except (OSError,EOFError,ssl.SSLError):pass
        finally:
            if stream is not self.request:stream.close()


class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        stream=self.request;stream.settimeout(10)
        try:
            data=headers(stream);first,*rest=data.split(b'\r\n')
            method,target,version=first.decode().split(' ')
            self.server.requests.append({'method':method,'target':target})
            if method=='CONNECT':host,port=target.rsplit(':',1);initial=None
            else:
                from urllib.parse import urlsplit
                uri=urlsplit(target);host,port=uri.hostname,uri.port
                initial=('GET '+(uri.path or '/')+' '+version).encode()+b'\r\n'+b'\r\n'.join(rest)
            assert host=='ws-fixture.test'
            with socket.create_connection(('127.0.0.1',int(port)),timeout=5) as upstream:
                if initial:upstream.sendall(initial)
                else:stream.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                while True:
                    ready,_,_=select.select([stream,upstream],[],[],10)
                    if not ready:return
                    for source in ready:
                        data=source.recv(65536)
                        if not data:return
                        (upstream if source is stream else stream).sendall(data)
        except (OSError,EOFError):pass


class Endpoint(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,certificate=None,key=None,proxy=False):
        self.requests=[];self.accepts=0;self.hellos=[];self.context=None
        if certificate:
            self.context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.context.minimum_version=ssl.TLSVersion.TLSv1_2
            self.context.load_cert_chain(certificate,key)
        super().__init__(('127.0.0.1',0),Forward if proxy else Echo)
        self.thread=threading.Thread(target=self.serve_forever,daemon=True);self.thread.start()
    def close(self):self.shutdown();self.server_close();self.thread.join(timeout=5)
