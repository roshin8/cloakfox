"""Actual profile pooling/owner separation and security/routing precedence."""
import base64,ssl,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from wire_fixture import TLSFixture
from probe_daily_defaults import launch
from probe_network_policy import READ,SET
from probe_network_identity import CHROME_CIPHERS,CHROME_SETTINGS


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-profile-controls-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['profile-controls.test'])
        servers=[TLSFixture(cert,key) for _ in range(3)]
        profile=root/'profile';profile.mkdir()
        d=launch(profile,root/'driver.log',accept_insecure_certs=False)
        try:
            d.set_script_timeout(20)
            d.execute_script("""
              Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
              Services.prefs.setStringPref('network.dns.localDomains','profile-controls.test');
              Services.prefs.setIntPref('network.trr.mode',5);
              Services.prefs.setBoolPref('cloakfox.enabled',true);
              Services.prefs.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
              Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true);
              ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);
            """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
            def request(server,ucid,script=READ):
                result=d.execute_async_script(script,f'https://profile-controls.test:{server.server_address[1]}/controls',ucid)
                assert result['status']==0 and result['body']=='local-wire-ok',result
                return result
            def records(server):return [r for r in server.observed if r.get('pseudoHeaders')]
            request(servers[0],0);native=records(servers[0])[-1]
            request(servers[0],7);chrome=records(servers[0])[-1]
            assert len(records(servers[0]))==2
            assert chrome['hello']['ciphers']==CHROME_CIPHERS
            assert native['hello']['ciphers']!=CHROME_CIPHERS
            d.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',false)")
            request(servers[0],7);other=records(servers[0])[-1]
            assert len(records(servers[0]))==3 and other['hello']==native['hello']
            d.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true)")
            request(servers[0],7)
            assert len(records(servers[0]))==3,'Chrome request must reuse only its Chrome pool'
            assert len(chrome['pseudoHeaders'])==2 and len(other['pseudoHeaders'])==1
            conservative=READ.replace('let body =',"channel.QueryInterface(Ci.nsIHttpChannelInternal).beConservative=true; let body =")
            request(servers[1],0,conservative);conservative_native=records(servers[1])[-1]
            request(servers[1],7,conservative);record=records(servers[1])[-1]
            assert record['hello']==conservative_native['hello'],record
            assert record['settings']==conservative_native['settings'],record
            d.execute_script("Services.prefs.setIntPref('security.tls.version.max',3);Services.prefs.setBoolPref('security.ssl3.ecdhe_rsa_aes_128_gcm_sha256',false)")
            request(servers[2],7);restricted=[r for r in servers[2].observed if r.get('tlsVersion')][-1]
            assert restricted['tlsVersion']=='TLSv1.2',restricted
            assert 49199 not in restricted['hello']['ciphers'],restricted
            if restricted['protocol']=='h2':assert [list(map(list,s)) for s in restricted['settings']]==CHROME_SETTINGS
            before=sum(len(r['pseudoHeaders']) for r in records(servers[0]))
            d.execute_script(SET,7,{'mode':2,'proxyURL':''})
            result=d.execute_async_script(READ,f'https://profile-controls.test:{servers[0].server_address[1]}/blocked',7)
            assert result['status']!=0
            d.execute_script(SET,7,{'mode':1,'proxyURL':'http://127.0.0.1:1'})
            result=d.execute_async_script(READ,f'https://profile-controls.test:{servers[0].server_address[1]}/proxy-required',7)
            assert result['status']!=0
            assert sum(len(r['pseudoHeaders']) for r in records(servers[0]))==before,'No direct fallback allowed'
            print('PASS: owner/profile pool isolation, profile switches, conservative native traffic, TLS policy and blocked/required-proxy refusal')
        finally:
            d.quit()
            for s in servers:s.close()

if __name__=='__main__':main()
