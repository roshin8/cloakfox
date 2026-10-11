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
CHROME_SIGNATURES=[1027,2052,1025,1283,2053,1281,2054,1537]
CHROME_SETTINGS=[[[1,65536],[2,0],[4,6291456],[6,262144]]]

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-network-identity-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['identity-wire.test'])
        untrusted_root=root/'untrusted';untrusted_root.mkdir()
        _,untrusted_cert,untrusted_key=create_certificates(untrusted_root,['identity-wire.test'])
        untrusted=TLSFixture(untrusted_cert,untrusted_key)
        detailed=os.environ.get('NETWORK_IDENTITY_DETAILS')=='1'
        servers=[TLSFixture(cert,key,detailed=detailed) for _ in range(3)]
        retry=TLSFixture(cert,key,detailed=True,curve='prime256v1') if detailed else None
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
                    if detailed:
                        target=Path(os.environ.get('NETWORK_IDENTITY_REPORT','/tmp/cloakfox-network-identity.json'))
                        target.write_text(json.dumps(report,indent=2)+'\n')
                        assert observed['hello']['signatures']==CHROME_SIGNATURES, ('Chrome signature order/policy filtering missing', observed['hello'])
                        assert 34 not in observed['hello']['extensions'] and 28 not in observed['hello']['extensions'], ('Firefox-only extensions present', observed['hello'])
                        shape=observed['hello']['shape']
                        assert shape['ciphers'][0]=='GREASE' and shape['groups'][0]=='GREASE',shape
                        assert shape['keyShares']==[['GREASE',1],[4588,1216],[29,32]],shape
                        assert shape['extensions'][0]==['GREASE',0] and shape['extensions'][-1]==['GREASE',1],shape
                        assert shape['payloads']['45']=='0101',shape
                        assert shape['payloads']['27']=='020002',shape
                        assert shape['ech']['kdf']==1 and shape['ech']['aead']==1 and shape['ech']['encLength']==32,shape
                        assert shape['ech']['payloadLength'] in [144,176,208,240],shape
                        try:d.get(url(retry))
                        except Exception:
                            print('HRR fixture observations:',retry.observed,flush=True)
                            raise
                        assert 'local-wire-ok' in d.page_source
                        retries=[r for r in retry.observed if r.get('clientHellos') and r.get('pseudoHeaders')]
                        assert retries and len(retries[0]['clientHellos'])==2,retry.observed
                        first,second=retries[0]['clientHellos']
                        assert first['keyShareGroups']==[4588,29] and second['keyShareGroups']==[23],retries
                        assert second['shape']['keyShares']==[[23,65]],retries
                        assert first['shape']['ech']==second['shape']['ech'],retries
                        assert first['shape']['extensions'][0]==second['shape']['extensions'][0]==['GREASE',0],retries
                        assert first['shape']['extensions'][-1]==second['shape']['extensions'][-1]==['GREASE',1],retries
                        # Record the real retry exchange and negotiated result.
                        report['chrome-hrr']=retries[0]
                    assert [list(map(list,settings)) for settings in observed['settings']]==CHROME_SETTINGS,observed
                    assert observed['windowUpdates'][0]==15663105,observed
                    assert observed['pseudoHeaders'][0]==[':method',':authority',':scheme',':path'],observed
                    for rejected_url in [url(untrusted),url(server,'wrong.test')]:
                        try:d.get(rejected_url);raise AssertionError('Chrome profile accepted invalid certificate')
                        except InsecureCertificateException:pass
                d.set_context('chrome')
            # ECH GREASE chooses AEAD 1 or 3 randomly in native NSS. Compare
            # deterministic native semantics, not that per-handshake choice.
            native_hello=lambda r:{k:v for k,v in r['hello'].items() if k!='shape'}
            assert native_hello(report['firefox'])==native_hello(report['master-off'])
            if detailed:
                shapes=[]
                for mode in ['firefox','master-off']:
                    shape=dict(report[mode]['hello']['shape'])
                    ech=dict(shape.pop('ech'));assert ech.pop('aead') in [1,3],ech
                    shapes.append((shape,ech))
                assert shapes[0]==shapes[1],shapes
            assert report['firefox']['settings']==report['master-off']['settings']
            d.set_context('content')
            try:d.get(url(servers[0],'wrong.test'));raise AssertionError('Wrong-host certificate accepted')
            except InsecureCertificateException:pass
            target=Path(os.environ.get('NETWORK_IDENTITY_REPORT','/tmp/cloakfox-network-identity.json'))
            target.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS: combined native TLS/H2 Chrome fields, master/default off and certificate rejection;',target)
        finally:
            d.quit()
            for server in servers+[untrusted]+([retry] if retry else []):server.close()
if __name__=='__main__':main()
