"""Native DoH/no-fallback + required proxy/reconnect probe, only local fixtures.

Positive and negative native DNS controls use Firefox's native-is-localhost test
pref: a native lookup would succeed, without issuing OS/external DNS packets.
DoH answers are real DNS wire messages delivered over verified fixture HTTPS.
No claim about actual QUIC packets or OS resolver packet capture is made here.
"""
import base64
import http.server
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'network'))
from doh_fixture import DoH

SET_DNS = """
const dns=ChromeUtils.importESModule('resource:///modules/CloakfoxDNS.sys.mjs');
return dns.setDNSPolicy(arguments[0]);
"""
RESOLVE = """
const [host, family] = arguments, done=arguments[arguments.length-1];
const dns=Services.dns;
let flags=Ci.nsIDNSService.RESOLVE_BYPASS_CACHE |
 (family===4 ? Ci.nsIDNSService.RESOLVE_DISABLE_IPV6 : Ci.nsIDNSService.RESOLVE_DISABLE_IPV4);
try {
 dns.asyncResolve(host,Ci.nsIDNSService.RESOLVE_TYPE_DEFAULT,flags,null,{
   onLookupComplete(request,record,status) {
     const addresses=[];
     if (Components.isSuccessCode(status)) {
       record.QueryInterface(Ci.nsIDNSAddrRecord);
       while(record.hasMore())addresses.push(record.getNextAddrAsString());
     }
     done({status,addresses});
   }
 },Services.tm.currentThread,{});
} catch(e) {done({status:e.result,addresses:[],error:e.name});}
"""


def main():
    from probe_daily_defaults import launch
    from probe_network_policy import READ, SET, Origin, Proxy, hits, tunnels
    servers = []
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-dns-network-') as temp:
            root = Path(temp)
            cert, key = root / 'cert.pem', root / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=resolver.test', '-addext', 'subjectAltName=DNS:resolver.test'],
                           check=True, capture_output=True)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            doh = http.server.ThreadingHTTPServer(('127.0.0.1', 0), DoH)
            doh.queries = []
            doh.socket = context.wrap_socket(doh.socket, server_side=True)
            origin = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Origin)
            proxy = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
            servers.extend([doh, origin, proxy])
            for server in servers:
                threading.Thread(target=server.serve_forever, daemon=True).start()
            profile = root / 'profile'
            profile.mkdir()
            driver = launch(profile, root / 'gecko.log')
            evidence = {}
            try:
                driver.set_script_timeout(20)
                der = ssl.PEM_cert_to_DER_cert(cert.read_text())
                driver.execute_script("""
                  const cert=Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                    .constructX509FromBase64(arguments[0]);
                  Cc['@mozilla.org/security/certoverride;1'].getService(Ci.nsICertOverrideService)
                    .rememberValidityOverride('resolver.test',arguments[1],{},cert,true);
                  const p=Services.prefs;
                  p.setBoolPref('network.dns.native-is-localhost',true);
                  p.setBoolPref('network.trr.allow-rfc1918',true);
                  p.setBoolPref('network.trr.temp_blocklist',false);
                  p.setBoolPref('network.trr.retry_on_recoverable_errors',false);
                  p.setBoolPref('network.trr.wait-for-portal',false);
                  p.setBoolPref('network.trr.wait-for-confirmation',false);
                  p.setStringPref('network.trr.confirmationNS','skip');
                  p.setStringPref('network.trr.excluded-domains','');
                  p.setStringPref('network.trr.builtin-excluded-domains','');
                  p.setIntPref('network.trr.request_timeout_ms',1500);
                  p.setIntPref('network.trr.request_timeout_mode_trronly_ms',1500);
                  p.setBoolPref('dom.security.https_only_mode',false);
                  p.setBoolPref('network.dns.disableIPv6',false);
                """, base64.b64encode(der).decode(), doh.server_port)
                resolver = f'https://resolver.test:{doh.server_port}/dns-query'
                driver.execute_script(SET_DNS, {'mode':'system'})
                native = driver.execute_async_script(RESOLVE, 'native-control.test', 4)
                assert native['status'] == 0 and '127.0.0.1' in native['addresses'], native
                evidence['nativePositiveControl'] = native
                driver.execute_script(SET_DNS, {'mode':'only','resolver':resolver,'bootstrap':'127.0.0.1'})
                for family, address in [(4,'192.0.2.7'),(6,'2001:db8::7')]:
                    host = f'positive-v{family}.dns-fixture.test'
                    result = driver.execute_async_script(RESOLVE, host, family)
                    assert result['status'] == 0 and address in result['addresses'], result
                    assert (host, 1 if family == 4 else 28) in doh.queries, doh.queries
                    evidence[f'encryptedIPv{family}'] = result
                # Exclusions would otherwise bypass TRR even in mode 3.
                driver.execute_script("Services.prefs.setStringPref('network.trr.excluded-domains','excluded.test'); Services.dns.clearCache(true);")
                excluded = driver.execute_async_script(RESOLVE, 'excluded.test', 4)
                assert excluded['status'] != 0 and not excluded['addresses'], excluded
                evidence['excludedFailsClosed'] = excluded
                with socket.socket() as held:
                    held.bind(('127.0.0.1',0))
                    dead = held.getsockname()[1]
                failed = f'https://resolver.test:{dead}/dns-query'
                driver.execute_script(SET_DNS, {'mode':'only','resolver':failed,'bootstrap':'127.0.0.1'})
                for family in (4,6):
                    result=driver.execute_async_script(RESOLVE,f'failed-v{family}.dns-fixture.test',family)
                    assert result['status'] != 0 and not result['addresses'], result
                    evidence[f'failedResolverIPv{family}'] = result
                # Explicit fallback mode must actually recover via the same native test path.
                driver.execute_script(SET_DNS, {'mode':'fallback','resolver':failed,'bootstrap':'127.0.0.1'})
                fallback=driver.execute_async_script(RESOLVE,'fallback-control.dns-fixture.test',4)
                assert fallback['status'] == 0 and '127.0.0.1' in fallback['addresses'], fallback
                evidence['explicitFallbackPositiveControl']=fallback
                driver.execute_script(SET_DNS, {'mode':'only','resolver':failed,'bootstrap':'127.0.0.1'})
                driver.execute_script(SET,2,{'mode':1,'proxyURL':f'http://127.0.0.1:{proxy.server_port}'})
                url=f'http://origin.test:{origin.server_port}'
                proxied=driver.execute_async_script(READ,url+'/proxy-with-dead-dns',2)
                assert proxied['body']=='origin-ok' and proxied['proxy']=='127.0.0.1', proxied
                assert any(t.startswith('origin.test:') for t in tunnels), tunnels
                assert not any(h=='origin.test' for h,t in doh.queries), doh.queries
                # Refused proxy cannot leak directly; restoring a route recovers.
                driver.execute_script(SET,2,{'mode':1,'proxyURL':f'http://127.0.0.1:{dead}'})
                refused=driver.execute_async_script(READ,url+'/proxy-refused',2)
                assert refused['status'] != 0 and '/proxy-refused' not in hits, (refused,hits)
                driver.execute_script(SET,2,{'mode':1,'proxyURL':f'http://127.0.0.1:{proxy.server_port}'})
                recovered=driver.execute_async_script(READ,url+'/proxy-recovered',2)
                assert recovered['body']=='origin-ok', recovered
                evidence['proxy']={'success':proxied,'refused':refused,'recovered':recovered,'tunnels':tunnels}
                # Restore strict resolver and prove recovery clears failed-resolution state.
                driver.execute_script(SET_DNS, {'mode':'only','resolver':resolver,'bootstrap':'127.0.0.1'})
                recovery=driver.execute_async_script(RESOLVE,'recovery.dns-fixture.test',4)
                assert recovery['addresses']==['192.0.2.7'], recovery
                evidence['resolverRecovery']=recovery
                evidence['dohQueries']=doh.queries
                print(json.dumps(evidence,indent=2))
                print('PASS: real HTTPS DoH A/AAAA, strict failure/exclusion, explicit native fallback control, required-proxy remote DNS, refusal/recovery')
            finally:
                driver.quit()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()

if __name__=='__main__':
    main()
