"""Compare actual TLS/H2 structures with matching stock Firefox on loopback.

Never disables certificate verification. A disposable profile imports only the
fixture root after proving that the untrusted certificate was rejected.
"""
import base64
import json
import os
from pathlib import Path
import ssl
import shutil
import sys
import tempfile
import time
from selenium import webdriver
from selenium.common.exceptions import InsecureCertificateException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates
from wire_fixture import TLSFixture


def launch_wire_browser(binary, profile, log, preferences=None):
    """Keep profile discovery as well as the browser profile disposable.

    Firefox initializes its profile registry before honoring -profile. On macOS,
    the user's Firefox registry can be protected by TCC even for an explicit
    test profile, so give this process independent app-data roots.
    """
    options=Options();options.binary_location=binary
    options.accept_insecure_certs=False
    options.add_argument('-headless');options.add_argument('-purgecaches')
    options.profile=str(profile)
    options.set_preference('remote.prefs.recommended',False)
    for name,value in (preferences or {}).items():options.set_preference(name,value)
    app_data=profile.parent/(profile.name+'-app-data')
    local_data=profile.parent/(profile.name+'-local-data')
    app_data.mkdir();local_data.mkdir()
    service=Service(executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
        service_args=['--allow-system-access'],log_output=str(log),
        env={**os.environ,'MOZ_APP_DATA':str(app_data),'MOZ_LOCAL_APP_DATA':str(local_data)})
    return webdriver.Firefox(options=options,service=service)


def main():
    report={}
    binaries={'stock':os.environ.get('FIREFOX_BIN','/Applications/Firefox.app/Contents/MacOS/firefox'),
              'cloakfox':os.environ['CLOAKFOX_BIN']}
    with tempfile.TemporaryDirectory(prefix='cloakfox-wire-') as temp:
        root=Path(temp)
        ca,cert,key=create_certificates(root,['wire.test'])
        servers=[TLSFixture(cert,key) for _ in range(3)]
        try:
            for label,binary in binaries.items():
                profile=root/label;profile.mkdir()
                d=launch_wire_browser(binary,profile,root/(label+'.log'),{
                    'network.dns.localDomains':'wire.test,wrong.test','network.trr.mode':5})
                d.set_page_load_timeout(15)
                try:
                    address=f'https://wire.test:{servers[0].server_address[1]}/'
                    rejected=False
                    try:d.get(address)
                    except InsecureCertificateException:rejected=True
                    assert rejected, (label,'Untrusted certificate was accepted')
                    d.set_context('chrome')
                    d.execute_script("""Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                        .addCertFromBase64(arguments[0],'CT,,');""",base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
                    d.set_context('content')
                    start=[len(s.observed) for s in servers]
                    for server in servers:
                        d.get(f'https://wire.test:{server.server_address[1]}/')
                        assert 'local-wire-ok' in d.page_source,(label,d.page_source)
                    valid=[]
                    for server,index in zip(servers,start):
                        records=[x for x in server.observed[index:] if x.get('pseudoHeaders')]
                        assert records,(label,server.observed[index:])
                        valid.append(records[0])
                    for observed in valid:
                        assert observed['tlsVersion']=='TLSv1.3',observed
                        assert observed['protocol']=='h2',observed
                    assert all(x['hello']==valid[0]['hello'] for x in valid), (label,'ClientHello structure is not repeatable',valid)
                    rejected=False
                    try:d.get(f'https://wrong.test:{servers[0].server_address[1]}/')
                    except InsecureCertificateException:rejected=True
                    assert rejected, (label,'Wrong-host certificate was accepted')
                    report[label]={'version':d.capabilities['browserVersion'],
                        'untrustedRejected':True,'wrongHostRejected':True,'connections':valid}
                finally:d.quit()
            report['comparison']={
                'tlsEqual':report['stock']['connections'][0]['hello']==report['cloakfox']['connections'][0]['hello'],
                'h2SettingsEqual':report['stock']['connections'][0]['settings']==report['cloakfox']['connections'][0]['settings'],
                'h2PseudoHeaderOrderEqual':report['stock']['connections'][0]['pseudoHeaders']==report['cloakfox']['connections'][0]['pseudoHeaders'],
                'h2WindowsEqual':report['stock']['connections'][0]['windowUpdates']==report['cloakfox']['connections'][0]['windowUpdates']}
            target=Path(os.environ.get('WIRE_REPORT','/tmp/cloakfox-network-wire.json'))
            target.write_text(json.dumps(report,indent=2))
            print(json.dumps(report['comparison'],indent=2))
            print('Report:',target)
            assert all(report['comparison'].values()),report['comparison']
            print('PASS: repeatable TLS/H2 stock Firefox parity; TLS 1.3 and certificate rejection intact')
        finally:
            for server in servers:server.close()


if __name__=='__main__':main()
