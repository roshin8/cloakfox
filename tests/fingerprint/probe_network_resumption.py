"""Local real TLS 1.2/1.3 resumption and owner/profile separation."""
import base64,json,os,ssl,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from wire_fixture import TLSFixture
from probe_daily_defaults import launch
from probe_network_policy import READ

FRESH_READ=READ.replace("channel.loadFlags |= Ci.nsIRequest.LOAD_BYPASS_CACHE;", "channel.loadFlags |= Ci.nsIRequest.LOAD_BYPASS_CACHE | Ci.nsIRequest.LOAD_FRESH_CONNECTION;")

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-tls-resumption-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['session-wire.test'])
        servers=[TLSFixture(cert,key,detailed=True,resumption=True,close_after_response=True,maximum_version=version) for version in [ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3]]
        profile=root/'profile';profile.mkdir();driver=launch(profile,root/'driver.log',accept_insecure_certs=False)
        try:
            driver.set_script_timeout(25)
            driver.execute_script("""
              Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
              Services.prefs.setStringPref('network.dns.localDomains','session-wire.test');
              Services.prefs.setIntPref('network.trr.mode',5);
              Services.prefs.setBoolPref('cloakfox.enabled',true);
              Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true);
              Services.prefs.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
              ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);
            """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
            for server in servers:
                records=[]
                def request(owner):
                    start=len(server.observed)
                    response=driver.execute_async_script(FRESH_READ,f'https://session-wire.test:{server.server_address[1]}/request',owner)
                    assert response['status']==0 and response['body']=='local-wire-ok',(response,server.observed)
                    successful=[record for record in server.observed[start:] if record.get('pseudoHeaders')]
                    assert len(successful)==1,server.observed
                    records.append(successful[0]);return successful[0]
                first=request(7);second=request(7)
                assert not first['sessionReused'] and second['sessionReused'],records
                assert second['hello']['signatures']==[1027,2052,1025,1283,2053,1281,2054,1537],second
                other=request(8);assert not other['sessionReused'],other
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',false);ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);")
                native=request(7);assert not native['sessionReused'],native
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true);ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);")
                switched=request(7);assert not switched['sessionReused'],switched
                report[first['tlsVersion']]=records
            destination=Path(os.environ.get('TLS_RESUMPTION_REPORT','/tmp/cloakfox-tls-resumption.json'))
            destination.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS: actual TLS1.2/1.3 resumption; container/profile/generation separation;',destination)
        finally:
            driver.quit()
            for server in servers:server.close()
if __name__=='__main__':main()
