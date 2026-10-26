"""Native synthetic microphone exposure and capture policy regression.

Uses no physical devices and never requests desktop capture. Screen selection is
verified separately by the user in the affected site.
"""
import os
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_camera_website_labels import Handler


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-capture-scope-') as tmp:
            options = Options()
            options.binary_location = os.environ['CLOAKFOX_BIN']
            for arg in ['-headless', '-no-remote', '-purgecaches', '-profile', tmp]:
                options.add_argument(arg)
            for key, value in {
                'media.navigator.streams.fake': True,
                'media.navigator.permission.disabled': True,
                'privacy.resistFingerprinting': False,
            }.items():
                options.set_preference(key, value)
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=['--allow-system-access'], log_output=str(Path(tmp, 'gecko.log'))))
            try:
                driver.set_script_timeout(20)
                driver.set_context('chrome')
                driver.execute_script("""
                    const key='cloakfox.s.cloak_cfg_0';
                    const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                    cfg['mediaDevices:enabled']=true;
                    Services.prefs.setStringPref(key,JSON.stringify(cfg));
                    Services.prefs.setIntPref('cloakfox.microphone.website_label_style',0);
                """)
                driver.set_context('content')
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                def capture():
                    return driver.execute_async_script("""
                        const done=arguments[arguments.length-1];
                        navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{
                          const result={microphone:s.getAudioTracks()[0].label,
                            microphone:s.getAudioTracks()[0].label};
                          s.getTracks().forEach(t=>t.stop());done(result);
                        },e=>done({error:e.name}));
                    """)
                chrome_inventory = None
                driver.set_context('chrome')
                chrome_inventory=driver.execute_script('return navigator.mediaDevices.getCloakfoxAudioDevices().then(ds=>ds.filter(d=>d.kind==="audioinput").map(d=>d.deviceId))')
                driver.set_context('content')
                actual=next(v for v in chrome_inventory if v)
                def select(raw_id,limit=1):
                    driver.set_context('chrome')
                    driver.execute_script('''ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setOverrides(0,{'mediaDevices:microphoneDevices':JSON.stringify([arguments[0]])});
                      const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k));
                      c['mediaDevices:microphoneDevices']=JSON.stringify([arguments[0]]);c['mediaDevices:micros']=arguments[1];
                      Services.prefs.setStringPref(k,JSON.stringify(c));''',raw_id,limit)
                    driver.set_context('content');driver.refresh()
                select(actual)
                assert capture().get('microphone'), 'Selected synthetic microphone should capture'
                select('disconnected-microphone')
                denied=capture();assert denied.get('error') in ['NotFoundError','OverconstrainedError'],denied
                count=driver.execute_async_script('const done=arguments[arguments.length-1];navigator.mediaDevices.enumerateDevices().then(ds=>done(ds.filter(d=>d.kind==="audioinput").length))')
                assert count==0,count
                driver.set_context('chrome')
                privileged=driver.execute_async_script('''const done=arguments[arguments.length-1];
                  navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{s.getTracks().forEach(t=>t.stop());done(true)},e=>done(e.name));''')
                assert privileged is True,privileged
                driver.set_context('content')

                select(actual,0);assert capture().get('error') in ['NotFoundError','OverconstrainedError']
                select(actual,1);assert capture().get('microphone')
                print('PASS selected microphone, disconnected selection fails closed, zero limit blocks capture, selection restores',flush=True)
            finally: driver.quit()
    finally: server.shutdown()

if __name__ == '__main__': main()
