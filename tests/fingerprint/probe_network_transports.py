"""Local real IPv6 HTTP and TCP speculative-connection policy regression.

Speculation has an accepted-TCP positive control and independent blocked/proxy
sinks. This does not infer QUIC safety from preferences: no QUIC fixture exists,
so HTTP/3/UDP coverage lives in the separate probe_network_quic.py.
"""
import http.server
import json
from pathlib import Path
import socket
import socketserver
import tempfile
import threading
import time

SPECULATE = """
const [url,ucid]=arguments;
const uri=Services.io.newURI(url);
const principal=Services.scriptSecurityManager.createContentPrincipal(uri,{userContextId:ucid});
const callbacks={
 QueryInterface:ChromeUtils.generateQI(['nsIInterfaceRequestor','nsISpeculativeConnectionOverrider']),
 getInterface(iid){return this.QueryInterface(iid);},
 get parallelSpeculativeConnectLimit(){return 6;},
 get ignoreIdle(){return true;},
 get allow1918(){return true;}
};
try {
 Services.io.QueryInterface(Ci.nsISpeculativeConnect).speculativeConnect(uri,principal,callbacks,false);
 return {dispatched:true};
} catch(e){return {dispatched:false,error:e.name,status:e.result};}
"""


class IPv6HTTPServer(http.server.ThreadingHTTPServer):
    address_family = socket.AF_INET6


class AcceptSink(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.accepts.append(self.client_address)
        self.server.accepted.set()


class SinkServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.accepts=[]
        self.accepted=threading.Event()
        super().__init__(('127.0.0.1',0),AcceptSink)


def main():
    from probe_daily_defaults import launch
    from probe_network_policy import Origin, READ, SET, hits
    sinks=[SinkServer() for _ in range(3)]
    servers=list(sinks)
    ipv6_error=None
    try:
        v6=IPv6HTTPServer(('::1',0),Origin)
        servers.append(v6)
    except OSError as error:
        v6=None
        ipv6_error=str(error)
    for server in servers:
        threading.Thread(target=server.serve_forever,daemon=True).start()
    evidence={'quic':{'tested':False,'separateProbe':'probe_network_quic.py supplies negotiated HTTP/3 and UDP controls.'}}
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-transports-') as temp:
            root=Path(temp)
            profile=root/'profile'
            profile.mkdir()
            driver=launch(profile,root/'gecko.log')
            try:
                driver.set_script_timeout(15)
                driver.execute_script("""
                  Services.prefs.setBoolPref('dom.security.https_only_mode',false);
                  Services.prefs.setBoolPref('dom.security.https_first',false);
                  Services.prefs.setBoolPref('dom.security.https_first_schemeless',false);
                  Services.prefs.setIntPref('network.http.speculative-parallel-limit',6);
                  Services.prefs.setBoolPref('network.dns.disablePrefetch',false);
                  Services.prefs.setBoolPref('network.dns.disableIPv6',false);
                """)
                driver.execute_script(SET,1,{'mode':0})
                driver.execute_script(SET,2,{'mode':2})
                with socket.socket() as reserved:
                    reserved.bind(('127.0.0.1',0))
                    dead=reserved.getsockname()[1]
                driver.execute_script(SET,3,{'mode':1,'proxyURL':f'http://127.0.0.1:{dead}'})
                if v6:
                    base=f'http://[::1]:{v6.server_port}'
                    positive=driver.execute_async_script(READ,base+'/v6-direct-positive',1)
                    assert positive['status']==0 and positive['body']=='origin-ok',positive
                    blocked=driver.execute_async_script(READ,base+'/v6-blocked',2)
                    assert blocked['status']!=0 and '/v6-blocked' not in hits,(blocked,hits)
                    required=driver.execute_async_script(READ,base+'/v6-required-proxy',3)
                    assert required['status']!=0 and '/v6-required-proxy' not in hits,(required,hits)
                    evidence['ipv6']={'tested':True,'direct':positive,'blocked':blocked,'requiredProxy':required}
                else:
                    evidence['ipv6']={'tested':False,'gap':ipv6_error}
                dispatch=[]
                for ucid,sink in zip((1,2,3),sinks):
                    result=driver.execute_script(SPECULATE,f'http://127.0.0.1:{sink.server_address[1]}/',ucid)
                    dispatch.append(result)
                assert dispatch[0]['dispatched'],dispatch
                assert sinks[0].accepted.wait(5),'Speculative positive control never reached local TCP sink'
                # A bounded observation window starts after the positive control.
                time.sleep(2)
                assert not sinks[1].accepts,'Blocked container emitted a speculative TCP connection'
                assert not sinks[2].accepts,'Required-proxy container emitted a direct speculative TCP connection'
                evidence['speculation']={'dispatch':dispatch,'acceptedConnections':[len(s.accepts) for s in sinks],'negativeObservationSeconds':2}
                print(json.dumps(evidence,indent=2))
                print('PASS: accepted TCP speculative control; blocked/required-proxy sinks stayed empty' + ('; real IPv6 HTTP control and scope rejection' if v6 else '; IPv6 transport unavailable'))
            finally:
                driver.quit()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()

if __name__=='__main__':
    main()
