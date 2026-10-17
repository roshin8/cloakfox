"""Real ALPS TLS transcript with certificate verification left enabled."""
import base64,hashlib,os,ssl,subprocess,sys,tempfile
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from alps_fixture import ALPSFixture
from probe_evidence import ProbeEvidence
from probe_daily_defaults import launch
from probe_network_policy import READ

def main():
    with ProbeEvidence('alps','ALPS_REPORT') as evidence, tempfile.TemporaryDirectory(prefix='cloakfox-alps-') as temp:
        root=Path(temp);ca,cert,key=create_certificates(root,['alps-wire.test'])
        fixture=ALPSFixture(cert,key,settings=True,close_after_response=True)
        evidence.report.update({'referenceOnly':os.environ.get('ALPS_CHROME_REFERENCE')=='1','handshakes':fixture.observed,'responses':[],'adversarial':{}})
        try:
            if os.environ.get('ALPS_CHROME_REFERENCE')=='1':
                spki=x509.load_pem_x509_certificate(cert.read_bytes()).public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)
                pin=base64.b64encode(hashlib.sha256(spki).digest()).decode()
                binary=os.environ.get('CHROME_BIN','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                result=subprocess.run([binary,'--headless=new',f'--user-data-dir={root / "chrome"}','--no-first-run','--disable-background-networking','--disable-component-update',f'--ignore-certificate-errors-spki-list={pin}','--host-resolver-rules=MAP alps-wire.test 127.0.0.1','--no-proxy-server','--dump-dom',f'https://alps-wire.test:{fixture.port}/'],capture_output=True,timeout=25,check=True)
                assert b'local-alps-ok' in result.stdout,'Chrome fixture application exchange failed'
            else:
                profile=root/'profile';profile.mkdir();driver=launch(profile,evidence.root/'driver.log',accept_insecure_certs=False)
                try:
                    driver.set_script_timeout(25)
                    driver.execute_script("""
                      Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
                      Services.prefs.setStringPref('network.dns.localDomains','alps-wire.test');
                      Services.prefs.setIntPref('network.trr.mode',5);
                      Services.prefs.setBoolPref('cloakfox.enabled',true);
                      Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true);
                      Services.prefs.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
                      ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);
                    """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
                    result=driver.execute_async_script(READ,f'https://alps-wire.test:{fixture.port}/',7)
                    evidence.report['responses'].append(result)
                    assert result['status']==0 and result['body']=='local-alps-ok',(result,fixture.observed)
                    fresh=READ.replace('channel.loadFlags |= Ci.nsIRequest.LOAD_BYPASS_CACHE;', 'channel.loadFlags |= Ci.nsIRequest.LOAD_BYPASS_CACHE | Ci.nsIRequest.LOAD_FRESH_CONNECTION;')
                    result=driver.execute_async_script(fresh,f'https://alps-wire.test:{fixture.port}/resumed',7)
                    evidence.report['responses'].append(result)
                    assert result['status']==0 and result['body']=='local-alps-ok',(result,fixture.observed)
                    assert any(record.get('resumed') for record in fixture.observed),fixture.observed
                    for mode in ['ack','stream','truncated','forbidden','window-overflow','unadvertised-compression']:
                        invalid=ALPSFixture(cert,key,settings=mode)
                        evidence.report['adversarial'][mode]={'handshakes':invalid.observed}
                        try:
                            rejected=driver.execute_async_script(READ,f'https://alps-wire.test:{invalid.port}/',7)
                            evidence.report['adversarial'][mode]['response']=rejected
                            assert rejected['status']!=0,('Malformed ALPS accepted',mode,rejected,invalid.observed)
                        finally:invalid.close()

                finally:driver.quit()
            handshakes=[r for r in fixture.observed if 'alps' in r]
            assert handshakes and handshakes[0]['alps'],('ALPS was not actually negotiated',fixture.observed)
            headers=[record for record in fixture.observed if 'firstHeaderByte' in record]
            assert headers and headers[0]['firstHeaderByte']==32,('ALPS header-table setting was not consumed',fixture.observed)
            assert all(not record.get('earlyDataAccepted',False) for record in fixture.observed),fixture.observed
            destination=evidence.destination
            print('PASS: actual ALPS negotiation/transcript and H2 application response;',destination)
        finally:fixture.close()
if __name__=='__main__':main()
