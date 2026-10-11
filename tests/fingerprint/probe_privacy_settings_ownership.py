"""Local fake-media ownership and live settings controls, disposable profile."""
import json
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
from probe_privacy_media_hdr import Handler


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    with tempfile.TemporaryDirectory(prefix='cloakfox-privacy-owner-') as temp:
        profile = Path(temp) / 'profile'; profile.mkdir()
        (profile / 'user.js').write_text('\n'.join([
            'user_pref("media.navigator.streams.fake", true);',
            'user_pref("media.navigator.permission.disabled", true);',
            'user_pref("dom.security.https_only_mode", false);',
        ]))
        d = launch(profile, Path(temp) / 'gecko.log'); d.set_script_timeout(20)
        def chrome(script, *args):
            d.set_context('chrome')
            try: return d.execute_script(script, *args)
            finally: d.set_context('content')
        def read(key):
            return chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'))[arguments[0]]", key)
        try:
            d.set_context('content'); d.get('about:cloakfox')
            WebDriverWait(d, 15).until(lambda x: x.execute_script("return document.querySelector('#grp-media select[data-key=\"mediaDevices:enabled\"]') !== null"))
            assert d.execute_script("return document.querySelector('[data-pref=\"cloakfox.opt.hdr_masking\"]').checked"), 'HDR control missing/default off'
            seed = chrome("return Services.prefs.getStringPref('cloakfox.container.0.math_seed')")
            d.execute_script('''const r=document.querySelector('#grp-media .k[title="mediaDevices:micros"]');
              if(!r) throw new Error('Media cap row uses the wrong key');
              r.closest('.spoof-row').querySelector('.v').click();''')
            limits = d.execute_script("const i=document.querySelector('#grp-media .row-input');return [i.min,i.max,i.step]")
            assert limits == ['0','64','1'], limits
            d.execute_script('''const i=document.querySelector('#grp-media .row-input');
              i.value='65';i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));''')
            assert read('mediaDevices:micros') != 65, 'Invalid media cap saved'
            d.execute_script('''const i=document.querySelector('#grp-media .row-input');
              i.value='2';i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));''')
            WebDriverWait(d, 10).until(lambda x: read('mediaDevices:micros') == 2)
            assert seed == chrome("return Services.prefs.getStringPref('cloakfox.container.0.math_seed')"), 'Editing a cap regenerated identity'
            d.execute_script('''const s=document.querySelector('#grp-media select[data-key="mediaDevices:enabled"]');
              s.value='false';s.dispatchEvent(new Event('change'));''')
            WebDriverWait(d, 10).until(lambda x: read('mediaDevices:enabled') is False)
            d.execute_script('''const s=document.querySelector('#grp-media select[data-key="mediaDevices:enabled"]');
              s.value='true';s.dispatchEvent(new Event('change'));''')
            WebDriverWait(d, 10).until(lambda x: read('mediaDevices:enabled') is True)
            assert chrome("return Services.prefs.getBoolPref('media.navigator.streams.fake',false)"), 'Fake hardware required'
            original = d.current_window_handle
            results = []
            chrome("Services.prefs.setBoolPref('gfx.color_management.hdr.force_enabled',true)")
            for index, enabled in enumerate((True, False, True)):
                before = set(d.window_handles)
                ucid = chrome('''const {ContextualIdentityService}=ChromeUtils.importESModule(
                  'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
                  const id=ContextualIdentityService.create('Local media owner','fingerprint','blue').userContextId;
                  Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+id,JSON.stringify({
                    'mediaDevices:enabled':arguments[0],'mediaDevices:micros':1,'mediaDevices:webcams':1,'mediaDevices:speakers':0,
                    'privacy:policy':{version:1,preset:arguments[1]?'compatibility':'standard',exceptions:[]}}));
                  const win=Services.wm.getMostRecentWindow('navigator:browser');
                  const tab=win.gBrowser.addTab('about:blank',{userContextId:id,
                    triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                  win.gBrowser.selectedTab=tab;return id;''', enabled, index==2)
                handle = (set(d.window_handles) - before).pop(); d.switch_to.window(handle)
                d.execute_script('window.location.href=arguments[0]', base)
                WebDriverWait(d, 10).until(lambda x: x.current_url.startswith(base))
                owner = chrome("return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.contentPrincipal.originAttributes.userContextId")
                assert owner == ucid, (owner, ucid)
                assert d.execute_script("return matchMedia('(video-dynamic-range:high)').matches") == (index==2), 'HDR policy read another container'
                chrome('''const p=Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.contentPrincipal;
                  for(const kind of ['camera','microphone']) Services.perms.addFromPrincipal(p,kind,Services.perms.ALLOW_ACTION);''')
                def capture():
                    return d.execute_async_script('''const done=arguments[0];
                      navigator.mediaDevices.getUserMedia({audio:true,video:true}).then(async s=>{
                        const out=(await navigator.mediaDevices.enumerateDevices()).map(d=>d.toJSON());
                        s.getTracks().forEach(t=>t.stop());done(out);
                      },e=>done({error:e.name}));''')
                devices = capture(); assert isinstance(devices, list), devices
                if not enabled:
                    assert devices == [], ('Owner false ignored', devices)
                else:
                    assert {x['kind'] for x in devices} == {'audioinput','videoinput'}, devices
                    assert {x['label'] for x in devices} == {'Internal Microphone','Internal Camera'}, devices
                    # Persisted permissions make the native principal key stable across reloads.
                    chrome('''const p=Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.contentPrincipal;
                      for(const kind of ['camera','microphone']) Services.perms.addFromPrincipal(p,kind,Services.perms.ALLOW_ACTION);''')
                    devices = capture(); d.refresh(); same = capture()
                    assert [x['deviceId'] for x in devices] == [x['deviceId'] for x in same], 'Native device IDs changed across a permitted reload'
                    d.execute_script('window.location.href=arguments[0]', base.replace('127.0.0.1','localhost'))
                    WebDriverWait(d, 10).until(lambda x: 'localhost' in x.current_url)
                    other_site = capture()
                    assert [x['deviceId'] for x in devices] != [x['deviceId'] for x in other_site], 'Media IDs linked across origins'
                    results.append({'owner':ucid,'devices':devices})
                d.close(); d.switch_to.window(original)
            assert [x['deviceId'] for x in results[0]['devices']] != [x['deviceId'] for x in results[1]['devices']], 'Media IDs linked across containers'
            print(json.dumps({'settings':True,'ownerConfig':True,'reload':True,'origins':True,'containers':True},indent=2))
            print('PASS: live media/HDR controls, owner config and native origin/container ID isolation')
        finally:
            d.quit(); server.shutdown(); server.server_close()


if __name__ == '__main__': main()
