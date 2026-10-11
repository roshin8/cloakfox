"""Real local HTTP/3 success then blocked/required-proxy UDP escape regression.

Install tests/network/requirements-h3.txt into the probe environment. Uses three
independent UDP endpoints and verifies each endpoint can serve negotiated h3.
No Internet service, production certificate, packet sniffer or privileged port.
"""
import base64
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'network'))


def main():
    from h3_fixture import H3Fixtures, create_certificates
    from probe_daily_defaults import launch
    from probe_network_policy import READ, SET
    read = READ.replace('onStopRequest(request, status) {done(', """onStopRequest(request, status) {
      let protocol='',security=null;
      try {protocol=request.QueryInterface(Ci.nsIHttpChannel).protocolVersion;} catch {}
      try {const info=request.QueryInterface(Ci.nsIChannel).securityInfo;if(info){security={};for(const key of ['errorCode','errorCodeString','securityState','negotiatedNPN','protocolVersion']){try{security[key]=info[key];}catch{}}}} catch {}
      done(""").replace('status, body, proxy:this.proxy', 'status, body, protocol, security, proxy:this.proxy')
    hosts=['quic-positive.test','quic-blocked.test','quic-proxy.test']
    with tempfile.TemporaryDirectory(prefix='cloakfox-quic-') as temp:
        root=Path(temp)
        ca,cert,key=create_certificates(root,hosts)
        fixtures=H3Fixtures(cert,key)
        try:
            profile=root/'profile';profile.mkdir()
            driver=launch(profile,root/'gecko.log')
            evidence={}
            try:
                driver.set_script_timeout(25)
                driver.execute_script("""
                  Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                    .addCertFromBase64(arguments[0],'CT,,');
                  Services.prefs.setBoolPref('network.http.http3.enable',true);
                  // Firefox otherwise intentionally falls back to TCP after a
                  // valid custom-CA handshake (Http3Session::Authenticated).
                  // This disposable fixture trusts
                  // its own root; certificate verification remains enabled.
                  Services.prefs.setBoolPref('network.http.http3.disable_when_third_party_roots_found',false);
                  Services.prefs.setStringPref('network.dns.localDomains',arguments[1]);
                  Services.prefs.setBoolPref('network.dns.disableIPv6',true);
                  Services.prefs.setBoolPref('network.proxy.allow_hijacking_localhost',true);
                  Services.prefs.setIntPref('network.http.connection-timeout',5);
                """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode(),','.join(hosts))
                driver.execute_script(SET,1,{'mode':0})
                driver.execute_script(SET,2,{'mode':2})
                with socket.socket() as reserved:
                    reserved.bind(('127.0.0.1',0));dead=reserved.getsockname()[1]
                driver.execute_script(SET,3,{'mode':1,'proxyURL':f'http://127.0.0.1:{dead}'})
                def request(index,ucid,path):
                    driver.execute_script("Services.prefs.setStringPref('network.http.http3.alt-svc-mapping-for-testing',arguments[0]);",f'{hosts[index]};h3=:{fixtures.ports[index]}')
                    return driver.execute_async_script(read,f'https://{hosts[index]}/{path}',ucid)
                print(json.dumps({'prefs':driver.execute_script("return Object.fromEntries(['network.http.altsvc.enabled','network.http.http3.enable','network.http.http3.force-use-alt-svc-mapping-for-testing','network.http.http3.disable_when_third_party_roots_found'].map(k=>[k,Services.prefs.getBoolPref(k,false)]));")}),flush=True)
                positive=request(0,1,'positive')
                print(json.dumps({'positive':positive,'endpoints':fixtures.observed}),flush=True)
                assert positive['status']==0 and positive['body']=='local-http3-ok' and positive['protocol']=='h3',(positive,fixtures.observed)
                assert fixtures.observed[0]['datagrams']>0 and 'h3' in fixtures.observed[0]['alpn'],fixtures.observed
                evidence['positive']=positive
                for index,ucid,label in [(1,2,'blocked'),(2,3,'requiredProxy')]:
                    result=request(index,ucid,label)
                    assert result['status']!=0,result
                    time.sleep(2)
                    count=fixtures.observed[index]['datagrams']
                    assert count==0,(label,'UDP escaped',fixtures.observed[index])
                    # Prove the quiet endpoint is live, not a broken negative fixture.
                    control=request(index,1,label+'-endpoint-control')
                    assert control['status']==0 and control['protocol']=='h3' and control['body']=='local-http3-ok',control
                    assert fixtures.observed[index]['datagrams']>0,fixtures.observed[index]
                    evidence[label]={'request':result,'datagramsBeforeControl':count,'endpointControl':control,'observationSeconds':2}
                evidence['endpoints']=fixtures.observed
                if __import__('os').environ.get('QUIC_REPORT'):
                    Path(__import__('os').environ['QUIC_REPORT']).write_text(json.dumps(evidence,indent=2))
                print(json.dumps(evidence,indent=2))
                print('PASS: real negotiated HTTP/3 controls; blocked and required-proxy routes emitted no UDP to independent live endpoints')
            finally:
                driver.quit()
        finally:
            fixtures.close()

if __name__=='__main__':main()
