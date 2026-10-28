"""Native browser-picker nicknames with synthetic media and an owned profile.

No physical camera, OBS installation, removed settings controls or OS picker is
required. This checks browser-only naming, website separation and persistence.
"""
import json
from selenium.webdriver.support.ui import WebDriverWait
from screen_management_fixture import ScreenManagementFixture

RAW = 'Cloakfox synthetic camera'
NICKNAME = 'Desk caméra 📷'


def inspect_picker(f, expected, origin=None):
    d = f.driver
    d.get(origin or f.origin)
    f.chrome("Services.perms.removeFromPrincipal(gBrowser.selectedBrowser.contentPrincipal,'camera')")
    d.execute_script("navigator.mediaDevices.getUserMedia({video:true}).then(s=>{window.captureOutcome='stream';s.getTracks().forEach(t=>t.stop())},e=>window.captureOutcome=e.name+': '+e.message);")
    def picker_ready(_):
        return f.chrome("return document.getElementById('webRTC-selectCamera-single-device-label')?.value") == expected
    try:
        WebDriverWait(d, 20).until(picker_ready)
    except Exception:
        print('PICKER DIAGNOSTIC', f.chrome("return {label:document.getElementById('webRTC-selectCamera-single-device-label')?.value,menu:[...document.querySelectorAll('#webRTC-selectCamera-menupopup > *')].map(e=>e.getAttribute('label'))}"), flush=True)
        print('CAPTURE', d.execute_script('return window.captureOutcome'), flush=True)
        raise
    assert f.chrome("return [...document.querySelectorAll('#webRTC-selectCamera-menupopup > *')].map(e=>e.getAttribute('label')).includes(arguments[0])", expected)


def main():
    with ScreenManagementFixture() as f:
        f.set_master(False)
        f.pref('media.navigator.streams.fake', True)
        f.pref('media.navigator.permission.fake', True)
        f.pref('media.navigator.permission.disabled', False)
        f.pref('media.getusermedia.fake-camera-name', RAW)
        f.pref('cloakfox.camera.nicknames', json.dumps({RAW: NICKNAME}))
        d = f.driver
        expected = NICKNAME + ' · ' + RAW
        inspect_picker(f, expected)
        print('PASS native single-device label and menu preserve nickname plus original source', flush=True)

        # Leave the prompt without granting physical-device access. The provider
        # is synthetic throughout, including the subsequent actual stream.
        d.get(f.origin + '/?after-prompt')
        f.chrome("Services.perms.addFromPrincipal(gBrowser.selectedBrowser.contentPrincipal,'camera',Services.perms.ALLOW_ACTION)")
        observed = d.execute_async_script("""const done=arguments[0];navigator.mediaDevices.getUserMedia({video:true})
          .then(async s=>{try{done({track:s.getVideoTracks()[0].label,labels:(await navigator.mediaDevices.enumerateDevices()).filter(x=>x.kind==='videoinput').map(x=>x.label)})}finally{s.getTracks().forEach(t=>t.stop())}},e=>done({error:e.name}));""")
        assert observed == {'track': RAW, 'labels': [RAW]}, observed
        print('PASS browser nickname never replaces website track/enumeration labels', flush=True)
        f.pref('cloakfox.camera.nicknames', '{}')
        inspect_picker(f, RAW, f.origin.replace(str(f.https_port), str(f.alternate_port)))
        f.pref('cloakfox.camera.nicknames', json.dumps({RAW: NICKNAME}))
        f.chrome('Services.prefs.savePrefFile(null)')
        # Reuse only this disposable profile. Stop before relaunch; no NSWorkspace
        # appearance restart or installed application is involved.
        profile = f.chrome('return Services.dirsvc.get("ProfD",Ci.nsIFile).path')
        d.quit(); f.driver = None
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        import os, shutil
        options = Options(); options.binary_location = f.binary
        options.accept_insecure_certs = True  # Only this fixture's owned TLS origin.
        options.add_argument('-headless'); options.add_argument('-profile'); options.add_argument(profile)
        f.driver = webdriver.Firefox(options=options, service=Service(
            executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
            service_args=['--allow-system-access'], log_output=str(f.report_path/'restart.log')))
        inspect_picker(f, expected)
        print('PASS reset restores original source and saved mapping survives profile restart', flush=True)


if __name__ == '__main__':
    main()
