"""Loopback TLS/H2 observer. Stores structural fields, never TLS secrets.

The ClientHello parser discards randoms, key shares, SNI, tickets and GREASE
values. H2 observations come from decoded frames sent on a real TLS connection.
"""
import socket
import socketserver
import ssl
import struct
import threading
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import RequestReceived
from hyperframe.frame import Frame, SettingsFrame, WindowUpdateFrame


from tls_hello import client_hello


def peek_hello(sock):
    sock.settimeout(10)
    data=b''
    import time
    deadline=time.monotonic()+10
    # Peek retains every byte for the actual SSL handshake, including sessions
    # whose ClientHello spans multiple TLS records (e.g. PQ key shares).
    while True:
        if time.monotonic()>deadline:raise TimeoutError('Incomplete ClientHello')
        packet=sock.recv(65536,socket.MSG_PEEK)
        if not packet: raise EOFError('No ClientHello')
        offset=0; assembled=b''
        while offset+5<=len(packet):
            kind,_,size=struct.unpack('!BHH',packet[offset:offset+5])
            if offset+5+size>len(packet):break
            if kind==22:assembled+=packet[offset+5:offset+5+size]
            offset+=5+size
        if len(assembled)>=4 and len(assembled)>=4+int.from_bytes(assembled[1:4],'big'):
            return client_hello(assembled)
        if packet==data:
            import time
            time.sleep(.005)
        data=packet


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        observation={}
        self.server.observed.append(observation)
        try:
            observation['hello']=peek_hello(self.request)
            with self.server.context.wrap_socket(self.request,server_side=True) as stream:
                observation['tlsVersion']=stream.version()
                observation['cipher']=stream.cipher()[0]
                observation['protocol']=stream.selected_alpn_protocol()
                if observation['protocol']!='h2':
                    stream.recv(65536)
                    stream.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 13\r\nConnection: close\r\n\r\nlocal-wire-ok')
                    return
                conn=H2Connection(config=H2Configuration(client_side=False,header_encoding='utf-8'))
                conn.initiate_connection();stream.sendall(conn.data_to_send())
                buffer=b''; preface=True
                observation.update(settings=[],windowUpdates=[],pseudoHeaders=[])
                while True:
                    incoming=stream.recv(65536)
                    if not incoming:break
                    buffer+=incoming
                    if preface and len(buffer)>=24:
                        assert buffer[:24]==b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
                        buffer=buffer[24:];preface=False
                    while not preface and len(buffer)>=9:
                        frame,length=Frame.parse_frame_header(memoryview(buffer[:9]))
                        if len(buffer)<9+length:break
                        frame.parse_body(memoryview(buffer[9:9+length]));buffer=buffer[9+length:]
                        if isinstance(frame,SettingsFrame) and 'ACK' not in frame.flags:
                            observation['settings'].append(list(frame.settings.items()))
                        if isinstance(frame,WindowUpdateFrame) and frame.stream_id==0:
                            observation['windowUpdates'].append(frame.window_increment)
                    for event in conn.receive_data(incoming):
                        if isinstance(event,RequestReceived):
                            observation['pseudoHeaders'].append([k for k,v in event.headers if k.startswith(':')])
                            conn.send_headers(event.stream_id,[(':status','200'),('content-length','13')])
                            conn.send_data(event.stream_id,b'local-wire-ok',end_stream=True)
                    stream.sendall(conn.data_to_send())
        except (OSError,ssl.SSLError,EOFError) as error:
            observation['error']=type(error).__name__


class TLSFixture(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,certificate,key):
        self.observed=[]
        self.context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version=ssl.TLSVersion.TLSv1_2
        self.context.options|=ssl.OP_NO_TICKET
        self.context.set_alpn_protocols(['h2','http/1.1'])
        self.context.load_cert_chain(certificate,key)
        super().__init__(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.serve_forever,daemon=True);self.thread.start()
    def close(self):
        self.shutdown();self.server_close();self.thread.join(timeout=5)
