"""Local HDR and real-backed media enumeration regression, disposable profile.

Fake hardware is enabled only in this test profile. Production must preserve
the raw MediaDevice backing, including exact-device capture constraints.
"""
import json
import sys
import time
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from probe_daily_defaults import launch


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        if self.path == '/denied':
            self.send_header('Permissions-Policy', 'camera=(), microphone=(), speaker-selection=()')
            self.send_header('Feature-Policy', "camera 'none'; microphone 'none'; speaker-selection 'none'")
        self.end_headers()
        self.wfile.write(b'''<!doctype html><title>Local media privacy fixture</title>
          <style>body { color:rgb(1,2,3) } @media (video-dynamic-range:high) { body { color:rgb(4,5,6) } }</style>''')

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    report = {}
    with tempfile.TemporaryDirectory(prefix='cloakfox-media-hdr-') as temp:
        profile = Path(temp) / 'profile'; profile.mkdir()
        (profile / 'user.js').write_text('\n'.join([
            'user_pref("dom.security.permissionsPolicy.header.enabled", true);',
            'user_pref("media.navigator.streams.fake", true);',
            'user_pref("media.navigator.permission.disabled", true);',
            'user_pref("dom.security.https_only_mode", false);',
        ]))
        d = launch(profile, Path(temp) / 'gecko.log')
        d.set_script_timeout(20)
        def chrome(script, *args):
            d.set_context('chrome')
            try: return d.execute_script(script, *args)
            finally: d.set_context('content')
        def devices():
            return d.execute_async_script('''const done=arguments[0];
                navigator.mediaDevices.enumerateDevices().then(ds=>done(ds.map(d=>d.toJSON())),e=>done({error:e.name}));''')
        def configure(cfg, enabled=True):
            chrome('''Services.prefs.setBoolPref('cloakfox.enabled',arguments[1]);
                Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',JSON.stringify(arguments[0]));''', cfg, enabled)
        cfg = {'mediaDevices:enabled': True, 'mediaDevices:micros': 3,
               'mediaDevices:webcams': 2, 'mediaDevices:speakers': 1,
               'fingerprint:secret': 'A'*43+'='}
        try:
            assert chrome("return Services.prefs.getBoolPref('media.navigator.streams.fake',false)"), 'Capture probe must use fake hardware'
            if "--media-only" not in sys.argv:
                chrome("Services.prefs.setBoolPref('gfx.color_management.hdr.force_enabled',true);")
                d.get(url+'/')
                def hdr():
                    state=d.execute_script("return [matchMedia('(video-dynamic-range: high)').matches,getComputedStyle(document.body).color]")
                    assert state[1] == ('rgb(4, 5, 6)' if state[0] else 'rgb(1, 2, 3)'), ('CSS/matchMedia HDR mismatch',state)
                    return state[0]
                configure(cfg, False); d.refresh()
                assert hdr(), 'Forced-HDR positive control failed'
                report['hdrNative'] = hdr()
                configure(cfg); d.refresh()
                report['hdrProtected'] = hdr()
                assert not hdr(), 'Cloakfox still exposes actual HDR display capability'
                configure({**cfg, 'privacy:policy': {'version':1,'preset':'compatibility','exceptions':[]}})
                d.refresh(); assert hdr(), 'Compatibility policy must preserve native HDR'
                configure({**cfg, 'privacy:policy': {'version':1,'preset':'standard','exceptions':[
                    {'site':'http://127.0.0.1','vectors':['geometry'],'expiresAt':int(time.time()*1000)+60000}]}})
                d.refresh(); assert hdr(), 'Live geometry site exception must preserve native HDR'
                configure(cfg); chrome("Services.prefs.setBoolPref('cloakfox.opt.hdr_masking',false)")
                d.refresh(); assert hdr(), 'HDR option-off must preserve native display capability'
                chrome("Services.prefs.setBoolPref('cloakfox.opt.hdr_masking',true)")
            configure(cfg,False)
            d.get(url+'/denied')
            native_denied=devices(); report['nativeDenied']=native_denied
            assert native_denied == [], ('Native Permissions-Policy positive control failed',native_denied)
            configure(cfg); d.refresh()
            denied = devices(); report['denied'] = denied
            assert denied == [], ('Permissions-Policy leaked media devices', denied)
            configure({'mediaDevices:enabled': False}); d.get(url+'/')
            disabled = devices(); report['disabled'] = disabled
            assert disabled == [], ('Disable mediaDevices did not return empty', disabled)
            strict_labels=d.execute_async_script('''const done=arguments[0];
              navigator.mediaDevices.getUserMedia({audio:true,video:true}).then(s=>{
                const labels=s.getTracks().map(t=>t.label);s.getTracks().forEach(t=>t.stop());done(labels);
              },e=>done({error:e.name}));''')
            assert strict_labels=={'error':'NotAllowedError'},('Disabled media capture accessed device hardware',strict_labels)
            report['strictLabels']=strict_labels
            configure(cfg); d.refresh()
            captured = d.execute_async_script('''const done=arguments[0];
              navigator.mediaDevices.getUserMedia({audio:true,video:true}).then(async s=>{
                const ds=(await navigator.mediaDevices.enumerateDevices()).map(d=>d.toJSON());
                s.getTracks().forEach(t=>t.stop()); done(ds);
              },e=>done({error:e.name}));''')
            assert isinstance(captured, list), captured
            report['granted'] = captured
            for kind in ('audioinput','videoinput'):
                entries = [x for x in captured if x['kind']==kind]
                assert len(entries)==1, ('One fake hardware device must not become multiple invented devices',kind,captured)
                for entry in entries:
                    assert entry['label'] in ('Internal Microphone','Internal Camera','Internal Speaker'), entry
                    result = d.execute_async_script('''const [kind,id,done]=arguments;
                      navigator.mediaDevices.getUserMedia({[kind==='audioinput'?'audio':'video']:{deviceId:{exact:id}}})
                        .then(s=>{const t=s.getTracks()[0]; const id=t.getSettings().deviceId;
                          s.getTracks().forEach(t=>t.stop()); done({id,label:t.label});}, e=>done({error:e.name}));''',kind,entry['deviceId'])
                    assert result.get('label')==entry['label'],('Track/enumeration labels disagree',entry,result)
                    assert result.get('id') == entry['deviceId'], ('Listed device lost its capture backing',entry,result)
            print(json.dumps(report,indent=2))
            print('PASS: HDR controls, permission gating and real-backed media device selection')
        finally:
            d.quit(); server.shutdown(); server.server_close()


if __name__=='__main__': main()
