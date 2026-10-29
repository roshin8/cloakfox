"""Loopback TURN allocation traffic and browser proxy routing regression.

Positive controls prove ICE actually sends Allocate requests, and the minimal
authenticated TURN responder yields a relay candidate. HTTP CONNECT forwards only to
this fixture. No public STUN/TURN, devices or external addresses are contacted.
Uses CLOAKFOX_BIN/REPORT_DIR. These are browser-proxy checks, not OS VPN checks.
"""
from __future__ import annotations
import json
import hashlib
import hmac
import zlib
import select
import socket
import struct
from threading import Thread
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from screen_management_fixture import ScreenManagementFixture

MAGIC=0x2112a442

def attribute(kind,data):
    return struct.pack('!HH',kind,len(data))+data+b'\0'*((-len(data))%4)

def xor_address(host,port):
    return struct.pack('!BBH',0,1,port^(MAGIC>>16))+struct.pack('!I',int.from_bytes(socket.inet_aton(host),'big')^MAGIC)

def reply(data,peer,port):
    if len(data)<20: return b''
    kind,length,magic=struct.unpack('!HHI',data[:8])
    if magic!=MAGIC: return b''
    attrs={}; offset=20
    while offset+4<=len(data):
        attr,size=struct.unpack('!HH',data[offset:offset+4]);offset+=4
        attrs[attr]=data[offset:offset+size];offset+=(size+3)&~3
    if kind in (3,4,8,9):
        if 6 not in attrs:
            body=attribute(9,b'\0\0\4\1Unauthorized')+attribute(0x14,b'fixture')+attribute(0x15,b'fixture-nonce')
            response=kind|0x110
        else:
            response=kind|0x100
            body=(attribute(0x16,xor_address('127.0.0.1',port))+attribute(0x20,xor_address(*peer))+attribute(0x0d,struct.pack('!I',600))) if kind==3 else attribute(0x0d,struct.pack('!I',600)) if kind==4 else b''
            key=hashlib.md5(b'fixture:fixture:fixture').digest()
            header=struct.pack('!HHI',response,len(body)+24,MAGIC)+data[8:20]
            body+=attribute(8,hmac.new(key,header+body,hashlib.sha1).digest())
        header=struct.pack('!HHI',response,len(body)+8,MAGIC)+data[8:20]
        return header+body+attribute(0x8028,struct.pack('!I',zlib.crc32(header+body)^0x5354554e))
    return b''

class TurnFixture:
    def __init__(self):
        self.events=[];self.proxy_ports=set();self.sockets=[];self.closed=False
        self.udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.udp.bind(('127.0.0.1',0));self.port=self.udp.getsockname()[1]
        self.tcp=socket.socket();self.tcp.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);self.tcp.bind(('127.0.0.1',self.port));self.tcp.listen()
        self.sockets=[self.udp,self.tcp]
        Thread(target=self.udp_loop,daemon=True).start();Thread(target=self.tcp_loop,daemon=True).start()
    def udp_loop(self):
        self.udp.settimeout(.2)
        while not self.closed:
            try: data,peer=self.udp.recvfrom(65535)
            except socket.timeout: continue
            except OSError: break
            self.events.append(('udp',data[:2].hex()));out=reply(data,peer,self.port)
            if out: self.udp.sendto(out,peer)
    def tcp_loop(self):
        self.tcp.settimeout(.2)
        while not self.closed:
            try: conn,peer=self.tcp.accept()
            except socket.timeout: continue
            except OSError: break
            self.sockets.append(conn);Thread(target=self.tcp_connection,args=(conn,peer),daemon=True).start()
    def tcp_connection(self,conn,peer):
        conn.settimeout(.2);buffer=b''
        while not self.closed:
            try: data=conn.recv(65535)
            except socket.timeout: continue
            except OSError: break
            if not data: break
            buffer+=data
            while len(buffer)>=20:
                length=struct.unpack('!H',buffer[2:4])[0]+20
                if len(buffer)<length: break
                data,buffer=buffer[:length],buffer[length:]
                self.events.append(('proxy-tcp' if peer[1] in self.proxy_ports else 'direct-tcp',data[:2].hex()))
                out=reply(data,peer,self.port)
                if out: conn.sendall(out)
    def close(self):
        self.closed=True
        for sock in self.sockets:
            sock.close()

GATHER='''const [url,frame,done]=arguments;const realm=frame ? document.querySelector('iframe').contentWindow : window;
const pc=new realm.RTCPeerConnection({iceServers:[{urls:url,username:'fixture',credential:'fixture'}],iceTransportPolicy:'relay'});
let candidates=[],errors=[],finished=false;function finish(){if(finished)return;finished=true;pc.close();done({candidates,errors})}
pc.onicecandidate=e=>{if(e.candidate)candidates.push(e.candidate.candidate);else finish()};
pc.onicecandidateerror=e=>errors.push(e.errorCode);pc.createDataChannel('fixture');
pc.createOffer().then(o=>pc.setLocalDescription(o)).catch(e=>{errors.push(e.name);finish()});setTimeout(finish,5000);'''

def main():
    failures=[];results={};turns=[];proxy_connects=[]
    class Proxy(BaseHTTPRequestHandler):
        def do_CONNECT(self):
            host,port=self.path.rsplit(':',1);port=int(port)
            target=next((t for t in turns if t.port==port),None)
            if host!='127.0.0.1' or not target: self.send_error(403);return
            upstream=socket.create_connection((host,port));target.proxy_ports.add(upstream.getsockname()[1]);proxy_connects.append(port)
            self.send_response(200);self.end_headers()
            sockets=[self.connection,upstream]
            try:
                while True:
                    ready,_,_=select.select(sockets,[],[],5)
                    if not ready: break
                    for s in ready:
                        data=s.recv(65535)
                        if not data: return
                        (upstream if s is self.connection else self.connection).sendall(data)
            finally: upstream.close()
        def log_message(self,*_): pass
    proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy);Thread(target=proxy.serve_forever,daemon=True).start()
    try:
        with ScreenManagementFixture() as f:
            d=f.driver;d.set_script_timeout(12)
            f.pref('media.peerconnection.ice.loopback',True)
            f.pref('media.peerconnection.ice.tcp',True)
            f.pref('media.peerconnection.ice.proxy_only_if_behind_proxy',False)
            f.pref('network.proxy.allow_hijacking_localhost',True)
            f.pref('network.proxy.no_proxies_on','')
            f.pref('network.proxy.http','127.0.0.1');f.pref('network.proxy.http_port',proxy.server_port)
            f.pref('network.proxy.ssl','127.0.0.1');f.pref('network.proxy.ssl_port',proxy.server_port)
            f.routes['/pac.js']=(f'''function FindProxyForURL(url,host){{return host==='127.0.0.1' ? 'PROXY 127.0.0.1:{proxy.server_port}' : 'DIRECT';}}''',{})
            f.routes['/direct-pac.js']=("function FindProxyForURL(url,host){return 'DIRECT';}",{})
            f.routes['/changing-pac.js']=(f'''var calls={{}};function FindProxyForURL(url,host){{
              if(host!=='127.0.0.1')return 'DIRECT';
              calls[url]=(calls[url]||0)+1;
              return calls[url]===1 ? 'PROXY 127.0.0.1:{proxy.server_port}' :
                'DIRECT; PROXY 127.0.0.1:{proxy.server_port}';}}''',{})
            d.get(f.origin)
            d.execute_script("const f=document.createElement('iframe');f.srcdoc='<p>blank frame</p>';document.body.append(f)")
            def run(name,mode,protect,transport,expect,enabled=True,frame=False):
                f.pref('network.proxy.type',mode);f.pref('cloakfox.webrtc.protect_proxy',protect);f.set_master(enabled)
                t=TurnFixture();turns.append(t)
                value=d.execute_async_script(GATHER,f'turn:127.0.0.1:{t.port}?transport={transport}',frame)
                time.sleep(.2);events=list(t.events);t.close()
                allocated=any(kind=='0003' for _,kind in events)
                direct=any(route in ('udp','direct-tcp') for route,_ in events)
                via=any(route=='proxy-tcp' for route,_ in events)
                relay=any(' typ relay ' in candidate for candidate in value['candidates'])
                ok= allocated and direct and relay if expect=='direct' else allocated and via and not direct and relay if expect=='proxy' else not events
                value.update(events=events,connects=t.port in proxy_connects)
                results[name]=value;print(('PASS ' if ok else 'FAIL ')+name+': '+json.dumps(value),flush=True)
                if not ok: failures.append(name)
            run('direct UDP allocation control',0,True,'udp','direct')
            run('direct TCP allocation control',0,True,'tcp','direct')
            run('manual proxy protected UDP blocked',1,True,'udp','blocked')
            run('manual proxy protected TCP CONNECT',1,True,'tcp','proxy')
            run('manual proxy iframe UDP blocked',1,True,'udp','blocked',frame=True)
            run('manual proxy opt-out UDP native',1,False,'udp','direct')
            run('manual proxy master-off UDP native',1,True,'udp','direct',enabled=False)
            f.pref('network.proxy.autoconfig_url',f.origin+'/pac.js')
            run('PAC target proxy protected UDP blocked',2,True,'udp','blocked')
            run('PAC target proxy TCP CONNECT',2,True,'tcp','proxy')
            f.pref('network.proxy.autoconfig_url',f.origin+'/changing-pac.js')
            run('PAC changed DIRECT failover list TCP closed',2,True,'tcp','blocked')
            f.pref('network.proxy.autoconfig_url',f.origin+'/direct-pac.js')
            run('PAC DIRECT UDP native',2,True,'udp','direct')
            f.pref('network.proxy.autoconfig_url',f.origin+'/missing-pac.js')
            run('PAC lookup failure UDP closed',2,True,'udp','blocked')
            f.pref('network.proxy.http_port',1);f.pref('network.proxy.ssl_port',1)
            run('unavailable manual proxy UDP closed',1,True,'udp','blocked')
            run('unavailable manual proxy TCP closed',1,True,'tcp','blocked')
            f.pref('network.proxy.http_port',proxy.server_port);f.pref('network.proxy.ssl_port',proxy.server_port)
            # The host system may intentionally have a proxy; this control is
            # conditional and records actual traffic rather than guessing it.
            run('system mode UDP route control',5,True,'udp','direct')
            (f.report_path/'turn-proxy-results.json').write_text(json.dumps(results,indent=2))
    finally:
        for t in turns:t.close()
        proxy.shutdown();proxy.server_close()
    assert not failures,failures

if __name__=='__main__':main()
