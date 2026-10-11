"""Live regression for page setter exposure, touch coherence and chrome fonts.
Disposable profiles and localhost only. Run after a native build with CLOAKFOX_BIN.
"""
import json
import os
import tempfile
import threading
from pathlib import Path

from probe_daily_defaults import launch
from probe_container_workflows import open_site
from probe_media_capabilities import Page, ThreadingHTTPServer

READ = """
const el = document.createElement('span');
el.style.font = 'caption'; el.textContent = 'Browser font';
document.documentElement.appendChild(el);
const caption = getComputedStyle(el).fontFamily; el.remove();
const style = document.createElement('style');
style.textContent = '#touch-css-probe { opacity: 1; } @media (any-pointer: coarse) { #touch-css-probe { opacity: .5; } }';
const target = document.createElement('span'); target.id = 'touch-css-probe';
document.documentElement.append(style, target);
const cssCoarse = getComputedStyle(target).opacity === '0.5';
style.remove(); target.remove();
return {caption, cssCoarse, touch: navigator.maxTouchPoints,
  touchEvent: typeof TouchEvent, touchInterface: typeof Touch,
  legacy: 'ontouchstart' in window,
  fine: matchMedia('(pointer: fine)').matches,
  hover: matchMedia('(hover: hover)').matches,
  anyCoarse: matchMedia('(any-pointer: coarse)').matches,
  setters: Object.fromEntries(['setWebRTCIPv4', 'setWebRTCIPv6', 'setCloakConfig',
    'setFontList', 'setSpeechVoices', 'setTimezone'].map(k => [k, typeof window[k]]))};
"""


PRIVILEGED = r"""
const done = arguments[arguments.length - 1];
const mm = Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.messageManager;
const topic = 'cloakfox-upstream-' + Services.uuid.generateUUID();
const listener = message => { mm.removeMessageListener(topic, listener); done(message.data); };
mm.addMessageListener(topic, listener);
const script = `(() => {
  try {
    const win = content;
    const result = {v4: typeof win.setWebRTCIPv4, v6: typeof win.setWebRTCIPv6};
    win.setWebRTCIPv4('198.51.100.41'); win.setWebRTCIPv6('2001:db8::41');
    result.fonts = {};
    for (const family of ['Arial', 'Avenir', 'system-ui']) {
      const span = win.document.createElement('span');
      span.style.fontFamily = family; span.textContent = 'Font sample 123';
      win.document.body.appendChild(span);
      const range = win.document.createRange(); range.selectNodeContents(span);
      result.fonts[family] = Array.from(win.InspectorUtils.getUsedFontFaces(range), f => f.CSSFamilyName);
      span.remove();
    }
    sendAsyncMessage('${topic}', result);
  } catch (error) { sendAsyncMessage('${topic}', {error: String(error)}); }
})();`;
mm.loadFrameScript('data:application/javascript,' + encodeURIComponent(script), false);
"""


def check_voice_registration():
    # Exercise the real registry boundary with a sentinel voice; no audio is
    # spoken and the positive control does not depend on installed host voices.
    previous = os.environ.get('CLOAK_CONFIG_1')
    try:
        for configured in (None, [], [{}]):
            os.environ['CLOAK_CONFIG_1'] = json.dumps(
                {} if configured is None else {'voices': configured})
            with tempfile.TemporaryDirectory(prefix='cloakfox-voice-registry-') as tmp:
                profile = Path(tmp) / 'profile'; profile.mkdir()
                config = {'voices:blockIfNotDefined': False,
                          'fonts': ['Arial'], 'fonts:spacing_seed': 12345}
                (profile / 'user.js').write_text('user_pref("cloakfox.s.cloak_cfg_0", ' +
                    json.dumps(json.dumps(config)) + ');')
                driver = launch(profile, Path(tmp) / 'gecko.log')
                try:
                    result = driver.execute_script("""
const registry = Cc['@mozilla.org/synth-voice-registry;1'].getService(Ci.nsISynthVoiceRegistry);
const uri = 'urn:cloakfox-test:sentinel';
registry.addVoice(null, uri, 'Sentinel', 'en-US', true, false);
const found = Array.from({length: registry.voiceCount}, (_, i) => registry.getVoice(i)).includes(uri);
if (found) registry.removeVoice(null, uri);
return found;
""")
                    print(json.dumps({'configured_voices': configured, 'native_voice_registered': result}), flush=True)
                    assert result is (configured is None), (configured, result)
                finally:
                    driver.quit()
    finally:
        if previous is None: os.environ.pop('CLOAK_CONFIG_1', None)
        else: os.environ['CLOAK_CONFIG_1'] = previous


def main():
    errors = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for touch in (0, 5):
            with tempfile.TemporaryDirectory(prefix='cloakfox-upstream-') as tmp:
                profile = Path(tmp) / 'profile'; profile.mkdir()
                config = {'navigator.platform': 'Win32', 'navigator:maxTouchPoints': touch,
                          'fonts': ['Arial', 'Segoe UI', 'Times New Roman'],
                          'fonts:spacing_seed': 12345}
                prefs = {'cloakfox.enabled': True, 'cloakfox.s.cloak_cfg_0': json.dumps(config)}
                (profile / 'user.js').write_text('\n'.join(
                    f'user_pref({json.dumps(k)}, {json.dumps(v)});' for k, v in prefs.items()))
                driver = launch(profile, Path(tmp) / 'gecko.log')
                try:
                    driver.set_context('chrome')
                    chrome = driver.execute_script(READ)
                    # Chrome must use native host fonts even when content claims Windows.
                    if 'Segoe UI' in chrome['caption']:
                        errors.append(('chrome persona font leak', touch, chrome))
                    driver.set_context('content')
                    driver.get(f'http://127.0.0.1:{server.server_port}/')
                    result = driver.execute_script(READ)
                    print(json.dumps({'touch': touch, 'chrome': chrome, 'content': result}), flush=True)
                    for name, value in result['setters'].items():
                        if value != 'undefined': errors.append(('page setter', name, value))
                    if result['touch'] != touch: errors.append(('touch count', result))
                    if result['anyCoarse'] != (touch > 0) or result['cssCoarse'] != (touch > 0):
                        errors.append(('coarse pointer JS/CSS', result))
                    for key in ('touchEvent', 'touchInterface'):
                        if result[key] != ('function' if touch else 'undefined'):
                            errors.append((key, result))
                    if result['legacy'] or not result['fine'] or not result['hover']:
                        errors.append(('desktop touch shape', result))
                    if 'Segoe UI' not in result['caption']: errors.append(('content persona font', result))
                    driver.set_context('chrome')
                    privileged = driver.execute_async_script(PRIVILEGED)
                    print(json.dumps({'privileged': privileged}), flush=True)
                    if privileged.get('v4') != 'function' or privileged.get('v6') != 'function':
                        errors.append(('privileged setters', privileged))
                    if 'error' in privileged: errors.append(('font inspection', privileged))
                    else:
                        if any('avenir' in f.lower() for f in privileged['fonts']['Avenir']):
                            errors.append(('hidden font resolved', privileged))
                        if not privileged['fonts']['Arial']:
                            errors.append(('allowed font missing', privileged))
                    driver.set_context('content')
                    driver.execute_script("document.body.innerHTML = '<iframe></iframe>'")
                    driver.switch_to.frame(0)
                    frame = driver.execute_script(READ)
                    if any(v != 'undefined' for v in frame['setters'].values()):
                        errors.append(('iframe setters', frame))
                    driver.switch_to.default_content()
                    driver.set_context('chrome')
                    other_touch = 0 if touch else 5
                    driver.execute_script('''Services.prefs.setStringPref('cloakfox.s.cloak_cfg_2',
                        JSON.stringify({'navigator.platform': 'MacIntel',
                          'navigator:maxTouchPoints': arguments[0],
                          fonts: ['Helvetica', 'Arial', 'Times'], 'fonts:spacing_seed': 12345}));''', other_touch)
                    open_site(driver, f'http://127.0.0.1:{server.server_port}/', 2)
                    other = driver.execute_script(READ)
                    print(json.dumps({'other_container': other}), flush=True)
                    if 'Helvetica' not in other['caption'] or other['touch'] != other_touch:
                        errors.append(('container persona', other))
                    if other['anyCoarse'] != (other_touch > 0) or other['cssCoarse'] != (other_touch > 0):
                        errors.append(('container touch CSS', other))
                    driver.set_context('chrome')
                    driver.execute_script("""Services.prefs.setStringPref('cloakfox.s.cloak_cfg_3',
                      JSON.stringify({'navigator.platform': 'Win32', fonts: ['Arial'], 'fonts:spacing_seed': 12345}));""")
                    open_site(driver, f'http://127.0.0.1:{server.server_port}/', 3)
                    driver.set_context('chrome')
                    restricted = driver.execute_async_script(PRIVILEGED)
                    print(json.dumps({'restricted_container': restricted}), flush=True)
                    if 'error' in restricted or any(not faces or any(f != 'Arial' for f in faces)
                       for faces in restricted.get('fonts', {}).values()):
                        errors.append(('restrictive font fallback', restricted))

                finally:
                    driver.quit()
    finally:
        server.shutdown(); server.server_close()
    assert not errors, json.dumps(errors, indent=2)
    check_voice_registration()
    print('PASS — setters hidden and privileged calls work; touch JS/CSS and fonts isolated; voice registration fails closed')


if __name__ == '__main__':
    main()
