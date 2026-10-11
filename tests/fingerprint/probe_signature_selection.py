"""Authenticated P-521 selection against an actual Chrome/native offer."""
import base64,hashlib,json,os,ssl,subprocess,sys,tempfile
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from alps_fixture import ALPSFixture
from probe_daily_defaults import launch
from probe_network_policy import READ

def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-signature-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['signature-wire.test'],leaf_curve='secp521r1')
        report={}
        if os.environ.get('SIGNATURE_CHROME_REFERENCE')=='1':
            fixture=ALPSFixture(cert,key,settings='unadvertised-signature')
            try:
                spki=x509.load_pem_x509_certificate(cert.read_bytes()).public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)
                pin=base64.b64encode(hashlib.sha256(spki).digest()).decode()
                binary=os.environ.get('CHROME_BIN','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                result=subprocess.run([binary,'--headless=new',f'--user-data-dir={root / "chrome"}','--no-first-run','--disable-background-networking','--disable-component-update',f'--ignore-certificate-errors-spki-list={pin}','--host-resolver-rules=MAP signature-wire.test 127.0.0.1','--no-proxy-server','--dump-dom',f'https://signature-wire.test:{fixture.port}/'],capture_output=True,timeout=25,check=True)
                assert b'local-alps-ok' not in result.stdout,('Chrome accepted unadvertised P-521',fixture.observed)
                assert any(r.get('handshakeFailed') for r in fixture.observed),fixture.observed
                report['chromeReference']=fixture.observed
            finally:fixture.close()
        else:
            profile=root/'profile';profile.mkdir();driver=launch(profile,root/'driver.log',accept_insecure_certs=False)
            try:
                driver.set_script_timeout(25)
                driver.execute_script("""
                  Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
                  Services.prefs.setStringPref('network.dns.localDomains','signature-wire.test');
                  Services.prefs.setIntPref('network.trr.mode',5);
                  Services.prefs.setBoolPref('cloakfox.enabled',true);
                  Services.prefs.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
                """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
                for name,chrome in [('native',False),('chrome',True)]:
                    fixture=ALPSFixture(cert,key,settings='unadvertised-signature')
                    try:
                        driver.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',arguments[0]);ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);",chrome)
                        result=driver.execute_async_script(READ,f'https://signature-wire.test:{fixture.port}/',7)
                        if chrome:
                            assert result['status']!=0,('Chrome profile accepted an unadvertised handshake signature',result,fixture.observed)
                        else:
                            assert result['status']==0 and result['body']=='local-alps-ok',(result,fixture.observed)
                            assert any(r.get('signature')==1539 for r in fixture.observed),fixture.observed
                        report[name]={'response':result,'handshakes':fixture.observed}
                    finally:fixture.close()
            finally:driver.quit()
        destination=Path(os.environ.get('SIGNATURE_REPORT','/tmp/cloakfox-signature.json'))
        destination.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: authenticated signature selection matches the advertised profile;',destination)
if __name__=='__main__':main()
