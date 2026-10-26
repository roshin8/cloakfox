"""Native synthetic camera exposure and capture policy regression.

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
                chrome_inventory = None
                driver.set_context('chrome')
                chrome_inventory=driver.execute_script('return navigator.mediaDevices.getCloakfoxCameras().then(ds=>ds.map(d=>d.deviceId))')
                driver.set_context('content')
                actual=next(v for v in chrome_inventory if v)
                def select(raw_id,limit=1):
                    driver.set_context('chrome')
                    driver.execute_script('''ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setOverrides(0,{'mediaDevices:cameraDevice':arguments[0],'mediaDevices:cameraDevices':''});
                      const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k));
                      delete c['mediaDevices:cameraDevices'];c['mediaDevices:cameraDevice']=arguments[0];c['mediaDevices:webcams']=arguments[1];
                      Services.prefs.setStringPref(k,JSON.stringify(c));''',raw_id,limit)
                    driver.set_context('content');driver.refresh()
                select(actual)
                assert capture().get('camera'), 'Selected synthetic camera should capture'
                select('disconnected-camera')
                denied=capture();assert denied.get('error') in ['NotFoundError','OverconstrainedError'],denied
                count=driver.execute_async_script('const done=arguments[arguments.length-1];navigator.mediaDevices.enumerateDevices().then(ds=>done(ds.filter(d=>d.kind==="videoinput").length))')
                assert count==0,count
                driver.set_context('chrome')
                privileged=driver.execute_async_script('''const done=arguments[arguments.length-1];
                  navigator.mediaDevices.getUserMedia({video:true}).then(s=>{s.getTracks().forEach(t=>t.stop());done(true)},e=>done(e.name));''')
                assert privileged is True,privileged
                driver.set_context('content')

                select(actual,0);assert capture().get('error') in ['NotFoundError','OverconstrainedError']
                select(actual,1);assert capture().get('camera')
                print('PASS selected camera, disconnected selection fails closed, zero limit blocks capture, selection restores',flush=True)
                driver.get('about:cloakfox?ucid=0#cfx-camera-exposure-heading')
                assert driver.execute_script("return document.querySelectorAll('#grp-media .media-device-tabs [role=tab]').length===3"), 'Missing device category tabs'
                placement=driver.execute_script('''return [['microphone','microphones'],['camera','cameras'],['speaker','speakers']].every(([kind,label])=>{
                  const e=document.getElementById('cfx-'+kind+'-configuration');
                  return !!e?.closest('#grp-media .advanced-fields') && e.previousElementSibling.textContent.includes('Maximum exposed '+label);
                });''')
                assert placement, 'Each device configuration must immediately follow its maximum in advanced overrides'
                tabs=driver.execute_script('''const mic=document.getElementById('cfx-device-tab-microphone');mic.click();
                  const draft=document.getElementById('cfx-microphone-device-name');draft.value='Unsaved draft';
                  mic.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
                  const cameraActive=document.getElementById('cfx-device-tab-camera').getAttribute('aria-selected')==='true';
                  mic.click();const preserved=draft.value==='Unsaved draft';
                  document.getElementById('cfx-device-tab-camera').click();
                  return cameraActive&&preserved&&document.querySelectorAll('#grp-media .media-device-panel:not([hidden])').length===1;''')
                assert tabs, 'Device tabs must support keyboard navigation, preserve drafts and show one panel'

                from selenium.webdriver.support.ui import WebDriverWait
                WebDriverWait(driver,20).until(lambda _: driver.execute_script("return !document.getElementById('cfx-camera-exposure-mode').disabled"))
                driver.execute_script('''document.getElementById('cfx-camera-exposure-mode').value='choose';document.getElementById('cfx-camera-exposure-mode').dispatchEvent(new Event('change'));
                  for(const input of document.querySelectorAll('#cfx-camera-exposure-devices input')) input.checked=input.value===arguments[0];
                  document.getElementById('cfx-camera-exposure-form').requestSubmit();''',actual)
                driver.set_context('chrome')
                assert driver.execute_script('''return ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').readOverrides(0)['mediaDevices:cameraDevices'];''')=='["'+actual+'"]'
                driver.set_context('content');driver.refresh()
                WebDriverWait(driver,20).until(lambda _: driver.execute_script("return Array.from(document.querySelectorAll('#cfx-camera-exposure-devices input')).some(i=>i.checked&&i.value===arguments[0])",actual))
                print('PASS per-container camera selection UI save and reload',flush=True)
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                assert capture().get('camera'), 'Array selection should capture its selected camera'
                driver.set_context('chrome')
                driver.execute_script('''const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key));
                  cfg['mediaDevices:cameraDevices']='[]';delete cfg['mediaDevices:cameraDevice'];Services.prefs.setStringPref(key,JSON.stringify(cfg));''')
                driver.set_context('content');driver.refresh()
                assert capture().get('error') in ['NotFoundError','OverconstrainedError']
                print('PASS native camera array selection and explicit empty selection',flush=True)

                driver.get(f'http://127.0.0.1:{server.server_port}/')
                select('disconnected-camera')
                original=driver.current_window_handle;before=set(driver.window_handles)
                driver.set_context('chrome')
                other=driver.execute_script('''const {ContextualIdentityService}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
                  const id=ContextualIdentityService.create('Camera exposure fixture','fingerprint','blue').userContextId;
                  const w=Services.wm.getMostRecentWindow('navigator:browser');
                  w.gBrowser.selectedTab=w.gBrowser.addTab(arguments[0],{userContextId:id,triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});return id;''',f'http://127.0.0.1:{server.server_port}/')
                driver.set_context('content')
                WebDriverWait(driver,20).until(lambda _: len(set(driver.window_handles)-before)>0)
                driver.switch_to.window(next(iter(set(driver.window_handles)-before)))
                driver.set_context('chrome')
                driver.execute_script('''const key='cloakfox.s.cloak_cfg_'+arguments[0],c=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                  c['mediaDevices:enabled']=true;c['mediaDevices:webcams']=1;c['mediaDevices:cameraDevice']=arguments[1];
                  Services.prefs.setStringPref(key,JSON.stringify(c));''',other,actual)
                driver.set_context('content');driver.refresh();assert capture().get('camera')
                driver.switch_to.window(original);driver.refresh()
                assert capture().get('error') in ['NotFoundError','OverconstrainedError']
                print('PASS native container isolation: selected camera allowed in one container, disconnected selection denied in another',flush=True)

            finally:
                driver.quit()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
