"""Actual QUIC/H3 exchanges for the combined native adapter (local only)."""
import base64,json,os,ssl,sys,tempfile,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import H3Fixtures,create_certificates
from probe_daily_defaults import launch
from probe_network_policy import READ,SET

def main():
    report={}
    with tempfile.TemporaryDirectory(prefix='cloakfox-quic-identity-') as tmp:
        root=Path(tmp);ca,cert,key=create_certificates(root,['quic-identity.test'])
        for name,profile_id,master in [('firefox',0,True),('chrome',1,True),('master-off',1,False)]:
            fixture=H3Fixtures(cert,key,count=1);profile=root/name;profile.mkdir()
            os.environ['MOZ_LOG']='SSLTokensCache:5'
            os.environ['MOZ_LOG_FILE']=str(root/(name+'-cache'))
            d=launch(profile,root/(name+'.log'),accept_insecure_certs=False)
            try:
                d.set_script_timeout(25)
                d.execute_script("""
                  Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB).addCertFromBase64(arguments[0],'CT,,');
                  Services.prefs.setBoolPref('network.http.http3.enable',true);
                  Services.prefs.setBoolPref('network.http.http3.enable_0rtt',true);
                  Services.prefs.setBoolPref('network.http.http3.disable_when_third_party_roots_found',false);
                  Services.prefs.setStringPref('network.dns.localDomains','quic-identity.test');
                  Services.prefs.setIntPref('network.trr.mode',5);
                  Services.prefs.setStringPref('network.http.http3.alt-svc-mapping-for-testing',arguments[1]);
                  Services.prefs.setBoolPref('cloakfox.enabled',arguments[3]);
                  Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',arguments[2]===1);
                  Services.prefs.setStringPref('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':'Mozilla/5.0 Chrome/155.0.0.0'}));
                  const selected=ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkProfiles.sys.mjs').writeNetworkProfile(7);
                  if(selected.profileId!==(arguments[3]?arguments[2]:0))throw new Error('Incorrect profile');
                """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode(),f'quic-identity.test;h3=:{fixture.ports[0]}',profile_id,master)
                response=d.execute_async_script(READ,'https://quic-identity.test/identity',7)
                assert response['status']==0 and response['body']=='local-http3-ok',(response,fixture.observed)
                observed=fixture.observed[0];assert observed['handshakes'] and observed['alpn']==['h3']
                record={"hello":observed['clientHellos'][0],"transportParameters":observed['transportParameters'][0],"settings":observed['settings']}
                report[name]=record
                if name=='chrome':
                    assert record['hello']['ciphers']==[4865,4866,4867],('Chrome QUIC TLS order missing',record)
                    assert record['hello']['groups']==[4588,29,23,24],record
                    assert record['hello']['keyShareGroups']==[4588,29],record
                    params=dict(record['transportParameters'])
                    assert {k:params[k] for k in [4,5,6,7,8,9]}=={4:15728640,5:6291456,6:6291456,7:6291456,8:100,9:103},record
                    assert record['settings']==[[1,65536],[6,262144],[7,100],[51,1]],record
                    # WebTransport deliberately keeps native negotiation:
                    # its required extensions are outside this adapter's scope.
                    before_wt=len(observed['clientHellos'])
                    wt=d.execute_async_script("""
                      const [url,ucid]=arguments,done=arguments[arguments.length-1];
                      const {NetUtil}=ChromeUtils.importESModule('resource://gre/modules/NetUtil.sys.mjs');
                      const uri=Services.io.newURI(url);
                      const principal=Services.scriptSecurityManager.createContentPrincipal(uri,{userContextId:ucid});
                      const transport=NetUtil.newWebTransport();
                      const listener={
                        QueryInterface:ChromeUtils.generateQI(['WebTransportSessionEventListener']),
                        onSessionReady(){transport.closeSession(0,'local fixture');done('ready');},
                        onSessionClosed(){done('peer rejected');},
                        onIncomingBidirectionalStreamAvailable(){},onIncomingUnidirectionalStreamAvailable(){},
                        onDatagramReceived(){},onMaxDatagramSize(){},onOutgoingDatagramOutCome(){},
                      };
                      transport.asyncConnect(uri,true,[],principal,Ci.nsILoadInfo.SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL,listener);
                      const {setTimeout}=ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
                      setTimeout(()=>{try{transport.closeSession(0,'local fixture')}catch{}done('handshake-only')},3000);
                    """,f'https://quic-identity.test:{fixture.ports[0]}/webtransport',7)
                    assert wt in ['ready','peer rejected','handshake-only']
                    assert len(observed['clientHellos'])>before_wt
                    assert all(h['ciphers']==[4865,4867,4866] for h in observed['clientHellos'][1:])
                    wt_hellos=len(observed['clientHellos'])
                    # Same origin, different owner: native profile must not
                    # reuse owner 7's Chrome QUIC session or inherit its choice.
                    response=d.execute_async_script(READ,'https://quic-identity.test/other-owner',8)
                    assert response['status']==0 and response['body']=='local-http3-ok'
                    assert observed['clientHellos'][-1]['ciphers']==[4865,4867,4866]
                    assert len(observed['clientHellos'])==wt_hellos+1
                    d.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',false)")
                    response=d.execute_async_script(READ,'https://quic-identity.test/profile-off',7)
                    assert response['status']==0 and response['body']=='local-http3-ok'
                    assert observed['clientHellos'][-1]['ciphers']==[4865,4867,4866]
                    assert len(observed['clientHellos'])==wt_hellos+2
                    d.execute_script("Services.prefs.setBoolPref('cloakfox.container.7.network_follow_identity',true)")
                    response=d.execute_async_script(READ,'https://quic-identity.test/profile-on',7)
                    assert response['status']==0 and response['body']=='local-http3-ok'
                    assert len(observed['clientHellos'])==wt_hellos+2,'Reuse only Chrome profile pool'
                    requests=len(observed['requests'])
                    for mode,proxy in [(2,''),(1,'http://127.0.0.1:1')]:
                        d.execute_script(SET,7,{'mode':mode,'proxyURL':proxy})
                        response=d.execute_async_script(READ,'https://quic-identity.test/refused',7)
                        assert response['status']!=0,response
                    assert len(observed['requests'])==requests,'No direct QUIC fallback'
                    cache=(root/(name+'-cache.moz_log')).read_text()
                    assert 'key=cfx-gecko-profile-1:quic-identity.test:443^userContextId=7' in cache, 'Chrome QUIC resumption key must include its captured profile'
                    assert 'key=quic-identity.test:443^userContextId=7' in cache, 'Native profile must retain its own cache key'


            except Exception:
                print('Failed QUIC mode:',name,'observations:',fixture.observed,flush=True)
                for log in root.glob('*.log'):shutil.copy2(log,Path('/tmp')/('cfx-quic-failure-'+log.name))
                raise
            finally:
                try:d.quit()
                except Exception:pass
                fixture.close()
        def comparable(record):
            return {**record,'hello':{**record['hello'],'extensions':sorted(record['hello']['extensions'])}}
        assert comparable(report['firefox'])==comparable(report['master-off']),report
        path=Path(os.environ.get('QUIC_IDENTITY_REPORT','/tmp/cloakfox-quic-identity.json'));path.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: native QUIC TLS fields, actual flow-control/stream limits and H3 SETTINGS; default/master off preserved;',path)
if __name__=='__main__':main()
