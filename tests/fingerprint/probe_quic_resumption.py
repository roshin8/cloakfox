"""Actual local QUIC Retry, tickets, resumption/0RTT and profile separation."""
import base64,json,os,ssl,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import H3Fixtures,create_certificates
from probe_daily_defaults import launch
from probe_network_policy import READ

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-quic-resumption-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['quic-session.test']+['quic-bad-'+label+'.test' for label in ['forbidden','truncated','duplicate-frame','duplicate-setting','invalid-setting']])
        for retry in [False,True]:
            fixture=H3Fixtures(cert,key,count=1,detailed=True,retry=retry,resumption=True,alps=b'\x04\x05\x01\x40\x40\x07\x01' if os.environ.get('QUIC_ALPS')=='1' else None,hold_settings=os.environ.get('QUIC_ALPS')=='1')
            profile=root/str(retry);profile.mkdir()
            os.environ['MOZ_LOG']='SSLTokensCache:5,nsHttp:4,sync'
            os.environ['MOZ_LOG_FILE']=str(root/(str(retry)+'-network.log'))
            driver=launch(profile,root/(str(retry)+'.log'),accept_insecure_certs=False)
            try:
                driver.set_script_timeout(30)
                driver.execute_script("""
                  Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
                  Services.prefs.setBoolPref('network.http.http3.enable',true);
                  Services.prefs.setBoolPref('network.http.http3.enable_0rtt',true);
                  Services.prefs.setBoolPref('network.http.http3.disable_when_third_party_roots_found',false);
                  Services.prefs.setStringPref('network.dns.localDomains','quic-session.test');
                  Services.prefs.setIntPref('network.trr.mode',5);
                  Services.prefs.setStringPref('network.http.http3.alt-svc-mapping-for-testing',arguments[1]);
                  Services.prefs.setBoolPref('cloakfox.enabled',true);
                  Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true);
                  Services.prefs.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
                  ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);
                """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode(),f'quic-session.test;h3=:{fixture.ports[0]}')
                observed=fixture.observed[0];records=[]
                def request(owner):
                    before=len(observed['handshakes'])
                    response=driver.execute_async_script(READ,'https://quic-session.test/request',owner)
                    assert response['status']==0 and response['body']=='local-http3-ok',(response,observed)
                    assert len(observed['handshakes'])==before+1,observed
                    records.append(observed['handshakes'][-1])
                    # LOAD_FRESH_CONNECTION intentionally disables Alt-Svc/H3.
                    # Close the client pool instead, preserving TLS tickets.
                    driver.execute_async_script("""
                      const done=arguments[arguments.length-1];
                      const {setTimeout}=ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
                      // neqo waits three PTOs for NEW_TOKEN before releasing a
                      // TLS resumption token when a server sends no NEW_TOKEN.
                      setTimeout(()=>{Services.obs.notifyObservers(null,'net:prune-all-connections');setTimeout(done,250)},1500);
                    """)
                    return records[-1]
                first=request(7);second=request(7)
                if os.environ.get('QUIC_ALPS')=='1':
                    assert observed.get('alpsOffered',[False])[0] and observed.get('alpsClientEE'),observed
                    assert observed.get('alpsEncoderCapacityBeforeSettings',[None])[0]==64,('H3 ALPS not consumed before ordinary SETTINGS',observed)
                assert not first['sessionResumed'] and second['sessionResumed'],records
                if not retry: assert second['earlyDataAccepted'],records
                other=request(8);assert not other['sessionResumed'] and not other['earlyDataAccepted'],other
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',false);ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);")
                native=request(7);assert not native['sessionResumed'] and not native['earlyDataAccepted'],native
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true);ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);")
                switched=request(7);assert not switched['sessionResumed'] and not switched['earlyDataAccepted'],switched
                if retry:
                    assert any(packet['tokenLength']>0 for packet in observed['initialPackets']),observed
                if os.environ.get('QUIC_ALPS')=='1':
                    for label,payload in [
                        ('forbidden',b'\x01\x00'),
                        ('truncated',b'\x04\x03\x01\x00'),
                        ('duplicate-frame',b'\x04\x00\x04\x00'),
                        ('duplicate-setting',b'\x04\x04\x01\x00\x01\x00'),
                        ('invalid-setting',b'\x04\x02\x33\x02')]:
                        bad=H3Fixtures(cert,key,count=1,alps=payload)
                        try:
                            host='quic-bad-'+label+'.test'
                            driver.execute_script("Services.prefs.setStringPref('network.dns.localDomains',arguments[0]);Services.prefs.setStringPref('network.http.http3.alt-svc-mapping-for-testing',arguments[1]);",host,f'{host};h3=:{bad.ports[0]}')
                            response=driver.execute_async_script(READ,f'https://{host}/bad',7)
                            assert bad.observed[0]['datagrams']>0,('Wrong fixture route',label,bad.observed)
                            assert response['status']!=0,('Malformed H3 ALPS accepted',label,response,bad.observed)
                        finally:bad.close()
                report['retry' if retry else 'direct']={'handshakes':records,'initialPackets':observed['initialPackets'],'parameters':observed['transportParameters'],'settings':observed['settings'],'alpsClientEE':observed.get('alpsClientEE',[]),'alpsEncoderCapacityBeforeSettings':observed.get('alpsEncoderCapacityBeforeSettings')}
            except Exception:
                print('QUIC ticket count:',len(fixture.tickets),flush=True)
                # Keep only public cache/handshake diagnostics, never token data.
                lines=[]
                for log in root.glob(str(retry)+'-network.log*'):
                    lines.extend(line for line in log.read_text(errors='replace').splitlines() if 'SSLTokensCache::' in line or 'ResumptionToken' in line)
                Path('/tmp/cfx-quic-resumption-cache.log').write_text('\n'.join(lines)+'\n')
                print('QUIC acceptance handshakes:',fixture.observed[0]['handshakes'],flush=True);raise
            finally:driver.quit();fixture.close()
        destination=Path(os.environ.get('QUIC_RESUMPTION_REPORT','/tmp/cloakfox-quic-resumption.json'))
        destination.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: actual QUIC Retry/resumption/0RTT; owner/profile/generation separation;',destination)
if __name__=='__main__':main()
