"""Actual ws/wss upgrades, echo, reconnect and container route enforcement."""
import base64
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from websocket_fixture import Endpoint
from probe_daily_defaults import launch
from probe_network_policy import SET

CONNECT='''
const [url,ucid]=arguments,done=arguments[arguments.length-1];
const uri=Services.io.newURI(url);
const principal=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI('http://ws-fixture.test'),{userContextId:ucid});
const channel=Cc['@mozilla.org/network/protocol;1?name='+uri.scheme].getService(Ci.nsIWebSocketProtocolHandler).newWebSocketChannel();
channel.initLoadInfo(null,principal,principal,Ci.nsILoadInfo.SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL,Ci.nsIContentPolicy.TYPE_WEBSOCKET);
channel.protocol='local-echo';
let finished=false;
const finish=result=>{if(!finished){finished=true;done(result);}};
const listener={
 QueryInterface:ChromeUtils.generateQI(['nsIWebSocketListener']),
 onStart(){channel.sendMsg('local-route-probe');},
 onMessageAvailable(context,message){channel.close(1000,'done');finish({message,protocol:channel.protocol});},
 onStop(context,status){finish({status});},onServerClose(){channel.close(1000,'done');},
 onAcknowledge(){},onBinaryMessageAvailable(){}
};
try{channel.asyncOpen(uri,'http://ws-fixture.test',{userContextId:ucid},0,listener,null);}
catch(error){finish({status:error.result,name:error.name});}
'''


def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-websocket-') as temp:
        root=Path(temp);ca,cert,key=create_certificates(root,['ws-fixture.test'])
        endpoints=[Endpoint(),Endpoint(cert,key),Endpoint(),Endpoint()]
        proxy=Endpoint(proxy=True)
        profile=root/'profile';profile.mkdir()
        d=launch(profile,root/'gecko.log')
        try:
            d.set_script_timeout(20)
            d.execute_script('''
              Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                .addCertFromBase64(arguments[0],'CT,,');
              Services.prefs.setStringPref('network.dns.localDomains','ws-fixture.test');
              Services.prefs.setIntPref('network.trr.mode',5);
              Services.prefs.setBoolPref('network.proxy.allow_hijacking_localhost',true);
              Services.prefs.setIntPref('network.websocket.timeout.open',5);
              Services.prefs.setBoolPref('dom.security.https_only_mode',false);
              Services.prefs.setBoolPref('dom.security.https_first',false);
            ''',base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
            d.execute_script(SET,1,{'mode':0})
            d.execute_script(SET,2,{'mode':2})
            with socket.socket() as reserved:
                reserved.bind(('127.0.0.1',0));dead=reserved.getsockname()[1]
            d.execute_script(SET,3,{'mode':1,'proxyURL':f'http://127.0.0.1:{dead}'})
            d.execute_script(SET,4,{'mode':1,'proxyURL':f'http://127.0.0.1:{proxy.server_address[1]}'})
            def connect(endpoint,ucid,scheme='ws',path='echo'):
                return d.execute_async_script(CONNECT,f'{scheme}://ws-fixture.test:{endpoint.server_address[1]}/{path}',ucid)
            for i,scheme in [(0,'ws'),(1,'wss')]:
                for repeat in range(2):
                    result=connect(endpoints[i],1,scheme,f'direct-{repeat}')
                    print(json.dumps({'scheme':scheme,'result':result,'accepts':endpoints[i].accepts,'requests':endpoints[i].requests}),flush=True)
                    assert result.get('message')=='local-route-probe' and result.get('protocol')=='local-echo',result
                result=connect(endpoints[i],4,scheme,'proxied')
                assert result.get('message')=='local-route-probe',result
                report[scheme]={'requests':endpoints[i].requests}
            for endpoint,ucid in [(endpoints[2],2),(endpoints[3],3)]:
                result=connect(endpoint,ucid)
                assert result.get('status',0)!=0,result
                time.sleep(.5)
                assert endpoint.accepts==0,('Direct connection escaped route policy',ucid,endpoint.accepts)
                control=connect(endpoint,1)
                assert control.get('message')=='local-route-probe',control
                report[str(ucid)]={'rejected':result,'acceptsBeforeControl':0,'control':control}
            assert any(x['method']=='CONNECT' for x in proxy.requests),proxy.requests
            assert len(proxy.requests)==2 and all(x['method']=='CONNECT' for x in proxy.requests),proxy.requests
            assert {x['target'] for x in proxy.requests}=={f'ws-fixture.test:{e.server_address[1]}' for e in endpoints[:2]},proxy.requests
            report['proxy']=proxy.requests
            print(json.dumps(report,indent=2))
            print('PASS: ws/wss handshake, real echo, reconnect, proxy routing and fail-closed routes')
        finally:
            d.quit();proxy.close()
            for endpoint in endpoints:endpoint.close()


if __name__=='__main__':main()
