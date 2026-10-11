"""Real local TLS/H2/QUIC profile adapter test; keeps cert verification enabled."""
import base64,json,os,ssl,sys,tempfile
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import InsecureCertificateException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from wire_fixture import TLSFixture

CHROME_CIPHERS=[4865,4866,4867,49195,49199,49196,49200,52393,52392,49171,49172,156,157,47,53]
CHROME_GROUPS=[4588,29,23,24]
CHROME_SHARES=[4588,29]
CHROME_SETTINGS=[[[1,65536],[2,0],[4,6291456],[6,262144]]]

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-network-identity-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['identity-wire.test'])
        servers=[TLSFixture(cert,key) for _ in range(3)]
        options=Options();options.binary_location=os.environ['CLOAKFOX_BIN'];options.accept_insecure_certs=False
        options.add_argument('-headless');options.add_argument('-purgecaches')
        profile=root/'profile';profile.mkdir();options.add_argument('-profile');options.add_argument(str(profile))
        options.set_preference('remote.prefs.recommended',False)
        options.set_preference('network.dns.localDomains','identity-wire.test,wrong.test')
        options.set_preference('network.trr.mode',5)
        d=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(root/'driver.log')))
        d.set_page_load_timeout(15)
        try:
            url=lambda s,host='identity-wire.test':f'https://{host}:{s.server_address[1]}/'
            try:d.get(url(servers[0]));raise AssertionError('Untrusted certificate accepted')
            except InsecureCertificateException:pass
            d.set_context('chrome')
            d.execute_script("Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');",base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
            for name,profile_id,master,server in zip(['firefox','chrome','master-off'],[0,1,1],[True,True,False],servers):
                selected=d.execute_script("""
                  Services.prefs.setBoolPref('cloakfox.enabled',arguments[1]);
                  Services.prefs.setBoolPref('cloakfox.container.0.network_follow_identity',arguments[0]===1);
                  Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
                  return ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(0).profileId;
                """,profile_id,master)
                assert selected==(profile_id if master else 0)
                d.set_context('content');start=len(server.observed);d.get(url(server));assert 'local-wire-ok' in d.page_source
                observed=[r for r in server.observed[start:] if r.get('pseudoHeaders')][0]
                report[name]=observed
                assert observed['tlsVersion']=='TLSv1.3' and observed['protocol']=='h2',observed
                if name=='chrome':
                    assert observed['hello']['ciphers']==CHROME_CIPHERS,('Chrome cipher order missing',observed)
                    assert observed['hello']['groups']==CHROME_GROUPS,observed
                    assert observed['hello']['keyShareGroups']==CHROME_SHARES,observed
                    assert [list(map(list,settings)) for settings in observed['settings']]==CHROME_SETTINGS,observed
                    assert observed['windowUpdates'][0]==15663105,observed
                    assert observed['pseudoHeaders'][0]==[':method',':authority',':scheme',':path'],observed
                d.set_context('chrome')
            assert report['firefox']['hello']==report['master-off']['hello']
            assert report['firefox']['settings']==report['master-off']['settings']
            d.set_context('content')
            try:d.get(url(servers[0],'wrong.test'));raise AssertionError('Wrong-host certificate accepted')
            except InsecureCertificateException:pass
            target=Path(os.environ.get('NETWORK_IDENTITY_REPORT','/tmp/cloakfox-network-identity.json'))
            target.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS: combined native TLS/H2 Chrome fields, master/default off and certificate rejection;',target)
        finally:
            d.quit()
            for server in servers:server.close()
if __name__=='__main__':main()
