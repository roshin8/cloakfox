"""Native fake-device smoke check for the display-label scope fix.

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
                    Services.prefs.setIntPref('cloakfox.camera.website_label_style',0);
                """)
                driver.set_context('content')
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                def capture():
                    return driver.execute_async_script("""
                        const done=arguments[arguments.length-1];
                        navigator.mediaDevices.getUserMedia({video:true,audio:true}).then(s=>{
                          const result={camera:s.getVideoTracks()[0].label,
                            microphone:s.getAudioTracks()[0].label};
                          s.getTracks().forEach(t=>t.stop());done(result);
                        },e=>done({error:e.name}));
                    """)
                result=capture()
                assert result == {'camera':'Internal Camera','microphone':'Internal Microphone'},result
                print('PASS native fake camera and microphone remain generically labelled', flush=True)
                driver.set_context('chrome')
                driver.execute_script("""
                    Services.prefs.setIntPref('cloakfox.camera.website_label_style',4);
                    Services.prefs.setStringPref('cloakfox.camera.website_label_custom','Studio Camera');
                """)
                driver.set_context('content')
                driver.refresh()
                result=capture()
                assert result == {'camera':'Studio Camera','microphone':'Internal Microphone'},result
                print('PASS native custom camera label remains camera-only',flush=True)
            finally:
                driver.quit()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
