"""Real BoringSSL ECH decryption via verified local DoH HTTPS records."""
import base64,http.server,json,os,ssl,struct,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from alps_fixture import ALPSFixture
from doh_fixture import DoH
from probe_daily_defaults import launch
from probe_network_policy import READ
from probe_dns_network import SET_DNS

def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-ech-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['ech-private.test','ech-public.test','resolver.test'])
        fixture=ALPSFixture(cert,key,settings='ech')
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        resolver=http.server.ThreadingHTTPServer(('127.0.0.1',0),DoH)
        resolver.socket=context.wrap_socket(resolver.socket,server_side=True)
        resolver.queries=[]
        parameter=lambda kind,value:struct.pack('!HH',kind,len(value))+value
        record=b'\x00\x01\x00'+parameter(1,b'\x02h2')+parameter(3,struct.pack('!H',fixture.port))+parameter(4,b'\x7f\x00\x00\x01')+parameter(5,fixture.ech_config)
        resolver.records={('ech-private.test',65):record,('ech-private.test',1):b'\x7f\x00\x00\x01',('ech-public.test',1):b'\x7f\x00\x00\x01'}
        threading.Thread(target=resolver.serve_forever,daemon=True).start()
        os.environ['MOZ_LOG']='nsHttp:4,TRR:4,nsHostResolver:4,sync'
        os.environ['MOZ_LOG_FILE']='/tmp/cfx-ech-network.log'
        profile=root/'profile';profile.mkdir();driver=launch(profile,root/'driver.log',accept_insecure_certs=False)
        report={}
        try:
            driver.set_script_timeout(30)
            driver.execute_script("""
              Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
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
              p.setBoolPref('network.dns.upgrade_with_https_rr',true);
              p.setBoolPref('network.dns.use_https_rr_as_altsvc',true);
              p.setBoolPref('network.dns.echconfig.enabled',true);
              p.setBoolPref('network.dns.echconfig.fallback_to_origin_when_all_failed',false);
              p.setBoolPref('cloakfox.enabled',true);
              p.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
            """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
            driver.execute_script(SET_DNS,{'mode':'only','resolver':f'https://resolver.test:{resolver.server_port}/dns-query','bootstrap':'127.0.0.1'})
            read=READ.replace('this.proxy = request.', 'this.ech = request.QueryInterface(Ci.nsIChannel).securityInfo?.QueryInterface(Ci.nsITransportSecurityInfo).isAcceptedEch; this.proxy = request.').replace('done({status, body,','done({ech:this.ech,status, body,')
            for name,chrome in [('native',False),('chrome',True)]:
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',arguments[0]);ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);",chrome)
                before=len(fixture.observed)
                result=driver.execute_async_script(read,'https://ech-private.test/',7)
                assert result['status']==0 and result['body']=='local-alps-ok' and result['ech'],(name,result,resolver.queries,fixture.observed)
                assert any(r.get('echAccepted') for r in fixture.observed[before:]),fixture.observed
                report[name]={'response':result,'handshakes':fixture.observed[before:]}
            assert ('ech-private.test',65) in resolver.queries,resolver.queries
            report['dohQueries']=resolver.queries
            destination=Path(os.environ.get('ECH_REPORT','/tmp/cloakfox-ech.json'));destination.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS: real encrypted ECH accepted by BoringSSL for native and Chrome profile;',destination)
        except Exception:
            print('ECH DNS:',resolver.queries,'handshakes:',fixture.observed,flush=True)
            raise
        finally:driver.quit();fixture.close();resolver.shutdown();resolver.server_close()
if __name__=='__main__':main()
