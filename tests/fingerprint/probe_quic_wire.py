"""Local QUIC ClientHello/transport parameters/H3 SETTINGS parity against stock."""
import base64
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import H3Fixtures, create_certificates
from probe_daily_defaults import launch
from probe_network_policy import READ


def main():
    report={}
    native=os.environ['CLOAKFOX_BIN']
    binaries={'stock':os.environ.get('FIREFOX_BIN','/Applications/Firefox.app/Contents/MacOS/firefox'),'cloakfox':native}
    hosts=['quic-wire-a.test','quic-wire-b.test','quic-wire-c.test']
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-quic-wire-') as temp:
            root=Path(temp);ca,cert,key=create_certificates(root,hosts)
            for label,binary in binaries.items():
                os.environ['CLOAKFOX_BIN']=binary
                records=[]
                # Separate browser sessions prevent legal cross-origin H3
                # connection coalescing from collapsing endpoint observations.
                for repeat in range(3):
                    fixture=H3Fixtures(cert,key,count=1)
                    profile=root/(label+str(repeat));profile.mkdir()
                    d=launch(profile,root/(label+str(repeat)+'.log'))
                    try:
                        d.set_script_timeout(25)
                        d.execute_script("""
                          Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                            .addCertFromBase64(arguments[0],'CT,,');
                          Services.prefs.setBoolPref('network.http.http3.enable',true);
                          Services.prefs.setBoolPref('network.http.http3.disable_when_third_party_roots_found',false);
                          Services.prefs.setStringPref('network.dns.localDomains',arguments[1]);
                          Services.prefs.setIntPref('network.trr.mode',5);
                          Services.prefs.setStringPref('network.http.http3.alt-svc-mapping-for-testing',arguments[2]);
                        """,base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode(),hosts[0],f'{hosts[0]};h3=:{fixture.ports[0]}')
                        response=d.execute_async_script(READ,f'https://{hosts[0]}/wire',1)
                        assert response['status']==0 and response['body']=='local-http3-ok',(label,response,fixture.observed)
                        observed=fixture.observed[0]
                        assert observed['alpn']==['h3'] and observed['handshakes'],observed
                        records.append({'hello':observed['clientHellos'][0],
                            'transportParameters':observed['transportParameters'][0],
                            'settings':observed['settings']})
                        version=d.capabilities['browserVersion']
                    finally:d.quit();fixture.close()
                def comparable(record):
                    hello={**record['hello'],'extensions':sorted(record['hello']['extensions'])}
                    return {**record,'hello':hello}
                assert comparable(records[0])==comparable(records[1])==comparable(records[2]),(label,'Unstable non-randomized structure',records)
                report[label]={'version':version,'connections':records,'extensionOrderVaries':len({tuple(r['hello']['extensions']) for r in records})>1}
            report['equal']=comparable(report['stock']['connections'][0])==comparable(report['cloakfox']['connections'][0])
            path=Path(os.environ.get('QUIC_WIRE_REPORT','/tmp/cloakfox-quic-wire.json'))
            path.write_text(json.dumps(report,indent=2))
            print(json.dumps({'equal':report['equal'],'report':str(path)}))
            assert report['equal'],'QUIC structure differs from stock Firefox; inspect the report'
            print('PASS: QUIC extension sets, ordered transport parameters and H3 SETTINGS parity; extension order remains randomized')
    finally:os.environ['CLOAKFOX_BIN']=native


if __name__=='__main__':main()
