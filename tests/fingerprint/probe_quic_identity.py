"""Actual QUIC/H3 exchanges for the combined native adapter (local only)."""
import base64,json,os,ssl,sys,tempfile,shutil,time
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
            detailed=os.environ.get('NETWORK_IDENTITY_DETAILS')=='1'
            fixture=H3Fixtures(cert,key,count=1,detailed=detailed);profile=root/name;profile.mkdir()
            os.environ['MOZ_LOG']='SSLTokensCache:5,sync'
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
                initial_generation=d.execute_script("return Services.prefs.getIntPref('cloakfox.container.7.network_state',0)>>>1")
                response=d.execute_async_script(READ,'https://quic-identity.test/identity',7)
                assert response['status']==0 and response['body']=='local-http3-ok',(response,fixture.observed)
                observed=fixture.observed[0];assert observed['handshakes'] and observed['alpn']==['h3']
                record={"hello":observed['clientHellos'][0],"transportParameters":observed['transportParameters'][0],"settings":observed['settings']}
                if detailed:
                    record.update(parameterDetails=observed['parameterDetails'][0],initialPackets=observed.get('initialPackets',[]))
                report[name]=record
                if name=='chrome':
                    record['cachePolicy']=[d.execute_script("return [Services.prefs.getBoolPref('network.http.http3.enable_0rtt'),Services.prefs.getIntPref('network.ssl_tokens_cache_records_per_entry'),Services.prefs.getIntPref('cloakfox.container.7.network_state')]")]
                    if detailed:
                        path=Path(os.environ.get('QUIC_IDENTITY_REPORT','/tmp/cloakfox-quic-identity.json'))
                        path.write_text(json.dumps(report,indent=2)+'\n')
                        assert record['hello']['signatures']==[1027,2052,1025,1283,2053,1281,2054,1537,513],record
                        assert not any(kind in record['hello']['extensions'] for kind in [23,28,34,5,65281]),record
                        shape=record['hello']['shape']
                        assert shape['ciphers']==[4865,4866,4867] and shape['groups']==[4588,29,23,24],shape
                        assert shape['keyShares']==[[4588,1216],[29,32]],shape
                        assert shape['payloads']['27']=='020002' and shape['payloads']['45']=='0101',shape
                        # Real initial packets and supported versions, measured against Chrome 155.
                        assert record['initialPackets'],record
                        first=record['initialPackets'][0]
                        assert {key:first[key] for key in ['datagramLength','version','destinationIdLength','sourceIdLength','tokenLength']}=={'datagramLength':1250,'version':1,'destinationIdLength':8,'sourceIdLength':0,'tokenLength':0},first
                        assert dict(record['transportParameters'])[32]==65536,record
                        assert dict(record['transportParameters'])[17]==[1,1],record
                        assert dict(record['transportParameters'])[15]=={'opaqueLength':0},record
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
                    record['cachePolicy'].append(d.execute_script("return [Services.prefs.getBoolPref('network.http.http3.enable_0rtt'),Services.prefs.getIntPref('network.ssl_tokens_cache_records_per_entry'),Services.prefs.getIntPref('cloakfox.container.7.network_state')]") )
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
                    assert len(observed['clientHellos'])==wt_hellos+3,'Switch-back must establish a fresh Chrome generation'
                    assert observed['clientHellos'][-1]['ciphers']==[4865,4866,4867]
                    final_generation=d.execute_script("return Services.prefs.getIntPref('cloakfox.container.7.network_state',0)>>>1")
                    record['cachePolicy'].append(d.execute_script("return [Services.prefs.getBoolPref('network.http.http3.enable_0rtt'),Services.prefs.getIntPref('network.ssl_tokens_cache_records_per_entry'),Services.prefs.getIntPref('cloakfox.container.7.network_state')]") )
                    assert final_generation>initial_generation
                    requests=len(observed['requests'])
                    for mode,proxy in [(2,''),(1,'http://127.0.0.1:1')]:
                        d.execute_script(SET,7,{'mode':mode,'proxyURL':proxy})
                        response=d.execute_async_script(READ,'https://quic-identity.test/refused',7)
                        assert response['status']!=0,response
                    assert len(observed['requests'])==requests,'No direct QUIC fallback'
                    # Flush logging in every process before inspecting cache lookups.
                    d.quit()
                    # Packaged builds may run networking in a separate socket process.
                    # Collect all process logs; the parent log alone can be empty.
                    expected_keys=[f'key=cfx-gecko-generation-{generation}-profile-{profile}:quic-identity.test:443^userContextId=7'
                                   for generation,profile in [(initial_generation,1),(initial_generation+1,0),(final_generation,1)]]
                    deadline=time.monotonic()+5
                    while True:
                        cache='\n'.join(path.read_text() for path in root.glob(name+'-cache*'))
                        if all(expected in cache for expected in expected_keys) or time.monotonic()>=deadline:break
                        # Child process shutdown/log flush can trail parent shutdown.
                        time.sleep(0.1)
                    fixture_keys=[line for line in cache.splitlines() if 'quic-identity.test' in line]
                    for expected in expected_keys:
                        assert expected in cache, ('QUIC cache must partition captured generation/profile', expected, fixture_keys,record['cachePolicy'])
                    record['cacheGenerations']={'initial':initial_generation,'native':initial_generation+1,'switchBack':final_generation}


            except Exception:
                print('Failed QUIC mode:',name,'observations:',fixture.observed,flush=True)
                for log in root.glob('*.log'):shutil.copy2(log,Path('/tmp')/('cfx-quic-failure-'+log.name))
                for log in root.glob(name+'-cache*'):shutil.copy2(log,Path('/tmp')/('cfx-quic-failure-'+log.name))
                raise
            finally:
                try:d.quit()
                except Exception:pass
                fixture.close()
        def comparable(record):
            result={**record,'hello':{**record['hello'],'extensions':sorted(record['hello']['extensions'])}}
            result['hello'].pop('shape',None)
            result.pop('parameterDetails',None)
            result.pop('initialPackets',None)
            return result
        assert comparable(report['firefox'])==comparable(report['master-off']),report
        path=Path(os.environ.get('QUIC_IDENTITY_REPORT','/tmp/cloakfox-quic-identity.json'));path.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: native QUIC TLS fields, actual flow-control/stream limits and H3 SETTINGS; default/master off preserved;',path)
if __name__=='__main__':main()
