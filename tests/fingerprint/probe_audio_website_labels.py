"""Native/UI audio label probe; synthetic microphone capture only, no real capture."""
import os
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from probe_camera_website_labels import Handler


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-audio-labels-') as tmp:
            options = Options()
            options.binary_location = os.environ['CLOAKFOX_BIN']
            for arg in ['-headless', '-no-remote', '-purgecaches', '-profile', tmp]:
                options.add_argument(arg)
            for k,v in {'media.navigator.streams.fake':True,
                        'media.navigator.permission.disabled':True,
                        'privacy.resistFingerprinting':False}.items():
                options.set_preference(k,v)
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=['--allow-system-access'],log_output=str(Path(tmp,'gecko.log'))))
            try:
                driver.set_script_timeout(20)
                def chrome(code,*args):
                    driver.set_context('chrome')
                    try: return driver.execute_script(code,*args)
                    finally: driver.set_context('content')
                assert chrome('''const p=Services.prefs.getDefaultBranch('');
                  return ['microphone','speaker'].every(k=>
                    p.getIntPref('cloakfox.'+k+'.website_label_style')===0 &&
                    p.getStringPref('cloakfox.'+k+'.website_label_custom')==='' &&
                    p.getStringPref('cloakfox.'+k+'.website_label_map')==='{}');'''), 'Missing defaults: string prefs must mirror to content processes'
                inventory = chrome('''return navigator.mediaDevices.getCloakfoxAudioDevices().then(ds=>
                  ds.map(d=>({deviceId:d.deviceId,label:d.label,kind:d.kind})));''')
                assert any(d['kind']=='audioinput' for d in inventory), 'No synthetic microphone'
                assert all(d['kind'] in ['audioinput','audiooutput'] for d in inventory)
                print('PASS chrome-only audio inventory without capture',flush=True)
                chrome('''const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k,'{}'));
                  c['mediaDevices:enabled']=true;c['mediaDevices:micros']=64;c['mediaDevices:speakers']=64;
                  Services.prefs.setStringPref(k,JSON.stringify(c));''')
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                assert driver.execute_script('return typeof navigator.mediaDevices.getCloakfoxAudioDevices')=='undefined'
                def capture():
                    return driver.execute_async_script('''const done=arguments[arguments.length-1];
                      (async()=>{const s=await navigator.mediaDevices.getUserMedia({audio:true,video:true});
                        try {const ds=await navigator.mediaDevices.enumerateDevices();return {
                          mic:s.getAudioTracks()[0].label,camera:s.getVideoTracks()[0].label,
                          devices:ds.map(d=>({kind:d.kind,label:d.label,id:d.deviceId})),
                          ownLabel:Object.hasOwn(s.getAudioTracks()[0],'label')};}
                        finally{s.getTracks().forEach(t=>t.stop())}})().then(done,e=>done({error:e.name}));''')
                baseline=capture();assert baseline.get('mic')=='Internal Microphone',baseline
                for kind,name in [('microphone','Studio Mic'),('speaker','Desk Speakers')]:
                    chrome('''Services.prefs.setIntPref('cloakfox.'+arguments[0]+'.website_label_style',4);
                      Services.prefs.setStringPref('cloakfox.'+arguments[0]+'.website_label_custom',arguments[1]);''',kind,name)
                driver.refresh();result=capture()
                assert result.get('mic')=='Studio Mic',result
                outputs=[d for d in result['devices'] if d['kind']=='audiooutput']
                assert outputs and all(d['label'].startswith('Desk Speakers') for d in outputs),outputs
                assert result['camera']==baseline['camera'] and not result['ownLabel']
                assert [(d['kind'],d['id']) for d in result['devices']]==[(d['kind'],d['id']) for d in baseline['devices']]
                print('PASS custom fallbacks, native track labels, stable IDs and camera isolation',flush=True)
                # Per-device maps override the fallback independently for each kind.
                mic=next(d for d in inventory if d['kind']=='audioinput' and d['deviceId'])
                chrome('''Services.prefs.setStringPref('cloakfox.microphone.website_label_map',
                  JSON.stringify({[arguments[0]]:'Interview Mic'}));''',mic['deviceId'])
                driver.refresh();assert capture()['mic']=='Interview Mic'
                print('PASS per-device microphone override',flush=True)
                speakers=[d for d in inventory if d['kind']=='audiooutput' and d['deviceId']]
                assert speakers, 'No physical output available for map regression'
                chrome('''Services.prefs.setStringPref('cloakfox.speaker.website_label_map',
                  JSON.stringify(Object.fromEntries(arguments[0].map(id=>[id,'Meeting Speakers']))));''',
                  [d['deviceId'] for d in speakers])
                driver.refresh();mapped=capture()
                output_labels=[d['label'] for d in mapped['devices'] if d['kind']=='audiooutput']
                assert 'Meeting Speakers' in output_labels, output_labels
                assert all(v=='Meeting Speakers' or v.startswith('Desk Speakers') for v in output_labels), output_labels
                assert [(d['kind'],d['id']) for d in mapped['devices']]==[(d['kind'],d['id']) for d in baseline['devices']]
                print('PASS physical speaker overrides and stable output IDs',flush=True)
                driver.get('about:cloakfox#sec-media')
                for kind,noun in [('microphone','microphone'),('speaker','speaker')]:
                    driver.execute_script("document.getElementById('cfx-device-tab-'+arguments[0]).click()",kind)
                    assert driver.execute_script('return !!document.getElementById(arguments[0])',f'cfx-{kind}-website-device')
                    WebDriverWait(driver,20).until(lambda _: driver.execute_script(
                      'return !document.getElementById(arguments[0]).disabled',f'cfx-{kind}-website-device'))
                    driver.execute_script('document.getElementById(arguments[0]).scrollIntoView({block:"center"})',f'cfx-{kind}-website-device')
                    driver.execute_async_script('const done=arguments[arguments.length-1];requestAnimationFrame(()=>requestAnimationFrame(done))')
                    assert driver.find_element('id',f'cfx-{kind}-website-device').is_displayed(), driver.execute_script("let e=document.getElementById(arguments[0]),a=[];for(;e;e=e.parentElement)a.push({tag:e.tagName,id:e.id,hidden:e.hidden,open:e.open,display:getComputedStyle(e).display,height:e.getBoundingClientRect().height});return a",f'cfx-{kind}-website-device')
                    selected=driver.execute_script('return document.getElementById(arguments[0]).value',f'cfx-{kind}-website-device')
                    driver.execute_script('''const k=arguments[0];document.getElementById('cfx-'+k+'-device-name').value='UI '+k;
                      document.getElementById('cfx-'+k+'-device-form').requestSubmit();''',kind)
                    assert chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.'+arguments[0]+'.website_label_map'))[arguments[1]]",kind,selected)=='UI '+kind
                    driver.execute_script("document.getElementById('cfx-'+arguments[0]+'-device-reset').click()",kind)
                    assert chrome("return !Object.hasOwn(JSON.parse(Services.prefs.getStringPref('cloakfox.'+arguments[0]+'.website_label_map')),arguments[1])",kind,selected)
                    driver.execute_script('''const k=arguments[0];document.getElementById('cfx-'+k+'-website-label').value='4';
                      document.getElementById('cfx-'+k+'-website-label').dispatchEvent(new Event('change'));
                      document.getElementById('cfx-'+k+'-website-custom').value='Saved '+k;
                      document.getElementById('cfx-'+k+'-website-custom-form').requestSubmit();''',kind)
                    assert chrome("return Services.prefs.getStringPref('cloakfox.'+arguments[0]+'.website_label_custom')",kind)=='Saved '+kind
                    driver.execute_script('''const k=arguments[0];document.getElementById('cfx-'+k+'-website-custom').value='  ';
                      document.getElementById('cfx-'+k+'-website-custom-form').requestSubmit();''',kind)
                    assert chrome("return Services.prefs.getStringPref('cloakfox.'+arguments[0]+'.website_label_custom')",kind)=='Saved '+kind
                driver.refresh()
                for kind in ['microphone','speaker']:
                    assert driver.execute_script('return document.getElementById(arguments[0]).value',f'cfx-{kind}-website-custom')=='Saved '+kind
                print('PASS settings per-device save/reset, fallback save, blank validation and reload persistence',flush=True)
                driver.execute_script("document.getElementById('cfx-device-tab-microphone').click()")
                WebDriverWait(driver,20).until(lambda _: driver.execute_script("return !document.getElementById('cfx-microphone-exposure-mode').disabled"))
                selected=driver.execute_script("return document.querySelector('#cfx-microphone-exposure-devices input').value")
                driver.execute_script("""const mode=document.getElementById('cfx-microphone-exposure-mode');
                  mode.value='choose';mode.dispatchEvent(new Event('change'));
                  document.querySelector('#cfx-microphone-exposure-devices input').click();
                  document.getElementById('cfx-microphone-exposure-form').requestSubmit();""")
                assert chrome("return ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').readOverrides(0)['mediaDevices:microphoneDevices']")==__import__('json').dumps([selected],separators=(',',':'))
                driver.refresh()
                WebDriverWait(driver,20).until(lambda _: driver.execute_script("return !document.getElementById('cfx-microphone-exposure-mode').disabled"))
                assert driver.execute_script("return document.getElementById('cfx-microphone-exposure-mode').value")=='choose'
                assert driver.execute_script("return document.querySelector('#cfx-microphone-exposure-devices input:checked').value")==selected
                print('PASS microphone access selection save and reload',flush=True)
            finally: driver.quit()
    finally: server.shutdown()


if __name__=='__main__': main()
