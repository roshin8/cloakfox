"""Verify preset and custom website camera labels using synthetic media only.

No physical camera is opened. CLOAKFOX_BIN selects the development binary.
"""
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>Neutral camera label test</title>")

    def log_message(self, *_args):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-camera-labels-") as tmp:
            prefs = {
                "cloakfox.enabled": True,
                "cloakfox.opt.mediadevices_disabled": False,
                "media.navigator.streams.fake": True,
                "media.navigator.permission.disabled": True,
                "privacy.resistFingerprinting": False,
            }
            Path(tmp, "user.js").write_text("\n".join(
                f"user_pref({json.dumps(key)}, {json.dumps(value)});"
                for key, value in prefs.items()
            ))
            options = Options()
            options.binary_location = os.environ["CLOAKFOX_BIN"]
            for arg in ["-headless", "-profile", tmp, "-purgecaches", "-no-remote"]:
                options.add_argument(arg)
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=["--allow-system-access"],
                log_output=str(Path(tmp, "gecko.log")),
            ))
            try:
                driver.set_script_timeout(20)
                driver.get("about:cloakfox#sec-media")
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return !!document.getElementById('cfx-camera-website-label')"
                ))
                assert driver.execute_script(
                    "return !!document.getElementById('cfx-camera-website-device')"
                ), 'Missing individual webcam selector'
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return !document.getElementById('cfx-camera-website-device').disabled"
                ))
                raw_camera_id = driver.execute_script(
                    "return document.getElementById('cfx-camera-website-device').value"
                )
                assert raw_camera_id
                assert driver.execute_script(
                    "return document.getElementById('cfx-camera-website-device').selectedOptions[0].textContent"
                ) == 'Default Video Device'
                print('PASS webcam selector lists the actual synthetic camera without capture', flush=True)
                # Placeholder handling now has direct controller coverage in
                # test_media_website_labels.mjs. Cross-compartment Xrays deliberately
                # ignore expando replacements of navigator.mediaDevices methods.
                driver.execute_script("""
                    const select = document.getElementById('cfx-camera-website-label');
                    if (![...select.options].some(option => option.value === '4'))
                        throw new Error('Missing custom camera label choice');
                    select.value = '2'; select.dispatchEvent(new Event('change'));
                """)
                driver.refresh()
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return document.getElementById('cfx-camera-website-label')?.value === '2'"
                ))
                print("PASS fixed website label choices and saved UI selection", flush=True)
                custom_label = 'Caméra <studio> & 東京'
                driver.execute_script("""
                    const select = document.getElementById('cfx-camera-website-label');
                    select.value = '4'; select.dispatchEvent(new Event('change'));
                    const input = document.getElementById('cfx-camera-website-custom');
                    if (!input || input.closest('[hidden]')) throw new Error('Custom editor is hidden');
                    input.value = arguments[0]; input.dispatchEvent(new Event('input'));
                    document.getElementById('cfx-camera-website-save').click();
                """, custom_label)
                driver.refresh()
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return document.getElementById('cfx-camera-website-label')?.value === '4'"
                ))
                assert driver.execute_script(
                    "return document.getElementById('cfx-camera-website-custom').value"
                ) == custom_label
                driver.quit()
                driver = webdriver.Firefox(options=options, service=Service(
                    service_args=['--allow-system-access'],
                    log_output=str(Path(tmp, 'gecko-restart.log')),
                ))
                driver.set_script_timeout(20)
                driver.get('about:cloakfox#sec-media')
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return document.getElementById('cfx-camera-website-label')?.value === '4'"
                ))
                assert driver.execute_script(
                    "return document.getElementById('cfx-camera-website-custom').value"
                ) == custom_label
                driver.execute_script("""
                    const input = document.getElementById('cfx-camera-website-custom');
                    input.value = '   '; input.dispatchEvent(new Event('input'));
                    document.getElementById('cfx-camera-website-save').click();
                    if (input.getAttribute('aria-invalid') !== 'true') throw new Error('Blank custom label accepted');
                """)
                driver.refresh()
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return document.getElementById('cfx-camera-website-custom')?.value === arguments[0]", custom_label
                ))
                driver.execute_script("""
                    const select = document.getElementById('cfx-camera-website-label');
                    select.value = '2'; select.dispatchEvent(new Event('change'));
                    if (!document.getElementById('cfx-camera-website-custom-form').hidden)
                        throw new Error('Preset did not hide custom editor');
                """)
                print("PASS custom editor save, reload/restart persistence, blank rejection and preset switching", flush=True)
                driver.get(f"http://127.0.0.1:{server.server_port}/")

                def chrome(script, *args):
                    driver.set_context("chrome")
                    try:
                        return driver.execute_script(script, *args)
                    finally:
                        driver.set_context("content")

                def capture_label():
                    result = driver.execute_async_script("""
                        const done = arguments[arguments.length - 1];
                        navigator.mediaDevices.getUserMedia({video: true}).then(stream => {
                            const label = stream.getVideoTracks()[0].label;
                            stream.getTracks().forEach(track => track.stop()); done({label});
                        }, error => done({error:error.name}));
                    """)
                    assert result.get('label'), result
                    return result['label']

                chrome("""
                    const key = 'cloakfox.s.cloak_cfg_0';
                    const cfg = JSON.parse(Services.prefs.getStringPref(key, '{}'));
                    cfg['mediaDevices:enabled'] = true;
                    cfg['mediaDevices:webcams'] = 64;
                    Services.prefs.setStringPref(key, JSON.stringify(cfg));
                """)
                original_ids = None
                for style, expected in [(1, "Camera 1"), (2, "Desk camera"), (3, "Room camera")]:
                    chrome("Services.prefs.setIntPref('cloakfox.camera.website_label_style', arguments[0])", style)
                    driver.refresh()
                    result = driver.execute_async_script("""
                        const done = arguments[arguments.length - 1];
                        (async () => {
                            const stream = await navigator.mediaDevices.getUserMedia({video: true});
                            try {
                                const track = stream.getVideoTracks()[0];
                                const cameras = (await navigator.mediaDevices.enumerateDevices())
                                    .filter(device => device.kind === 'videoinput');
                                return {track: track.label, labels: cameras.map(device => device.label), ids: cameras.map(device => device.deviceId)};
                            } finally { stream.getTracks().forEach(track => track.stop()); }
                        })().then(done, error => done({error: error.name + ': ' + error.message}));
                    """)
                    assert result.get("track") == expected, result
                    assert result.get("labels") and all(label == expected for label in result["labels"]), result
                    if original_ids is not None:
                        assert result["ids"] == original_ids, result
                    original_ids = result["ids"]
                    print(f"PASS {expected}: track, enumeration labels, unchanged device IDs", flush=True)
                for custom, expected in [('Studio Camera', 'Studio Camera'), ('Caméra 📷', 'Caméra 📷'),
                                         ('<camera> & "test"', '<camera> & "test"'),
                                         ('\u3000Studio Camera\u00a0', 'Studio Camera'), ('x' * 128, 'x' * 128)]:
                    chrome("""
                        Services.prefs.setStringPref('cloakfox.camera.website_label_custom', arguments[0]);
                        Services.prefs.setIntPref('cloakfox.camera.website_label_style', 4);
                    """, custom)
                    driver.refresh()
                    result = driver.execute_async_script("""
                        const done = arguments[arguments.length - 1];
                        (async () => {
                            const stream = await navigator.mediaDevices.getUserMedia({video: true, audio: true});
                            try {
                                const track = stream.getVideoTracks()[0];
                                const clone = track.clone();
                                const cloneLabel = clone.label; clone.stop();
                                const cameras = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'videoinput');
                                return {track: track.label, clone: cloneLabel, audio: stream.getAudioTracks()[0].label,
                                    labels: cameras.map(d => d.label), ids: cameras.map(d => d.deviceId),
                                    settings: track.getSettings(), live: track.readyState === 'live',
                                    ownLabel: Object.hasOwn(track, 'label')};
                            } finally { stream.getTracks().forEach(track => track.stop()); }
                        })().then(done, error => done({error: error.name + ': ' + error.message}));
                    """)
                    assert result.get('track') == expected and result.get('clone') == expected, result
                    assert result.get('labels') and all(label == expected for label in result['labels']), result
                    assert result['ids'] == original_ids, result
                    assert result['live'] and not result['ownLabel'] and result['audio'] != custom, result
                    assert result['settings']['deviceId'] in result['ids'], result
                    print(f"PASS custom {custom!r}: capture, clone, enumeration, IDs and native getter", flush=True)

                chrome("Services.prefs.setIntPref('cloakfox.camera.website_label_style', 0)")
                driver.refresh()
                generic_label = capture_label()
                chrome("Services.prefs.setIntPref('cloakfox.camera.website_label_style', 4)")
                for invalid_label in ['', '   ', '\u00a0', '\u3000', '\ufeff', 'x' * 129, 'Camera\nName']:
                    chrome("Services.prefs.setStringPref('cloakfox.camera.website_label_custom', arguments[0])", invalid_label)
                    driver.refresh()
                    result = capture_label()
                    assert result == generic_label, (invalid_label, result, generic_label)
                print("PASS invalid custom preferences fall back to the generic privacy label", flush=True)
                for invalid in [0, -1, 5, 999]:
                    chrome("Services.prefs.setIntPref('cloakfox.camera.website_label_style', arguments[0])", invalid)
                    driver.refresh()
                    result = capture_label()
                    assert result == generic_label, result
                print("PASS default and invalid styles retain generic privacy labels", flush=True)
                # Rename this particular webcam; preserve another disconnected camera's entry.
                chrome("""
                    Services.prefs.setStringPref('cloakfox.camera.website_label_map',
                        JSON.stringify({'disconnected-test-camera':'Other Webcam'}));
                    Services.prefs.setIntPref('cloakfox.camera.website_label_style', 2);
                """)
                driver.get('about:cloakfox#sec-media')
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return !document.getElementById('cfx-camera-website-device')?.disabled"
                ))
                driver.execute_script("""
                    const select = document.getElementById('cfx-camera-website-device');
                    select.value = arguments[0]; select.dispatchEvent(new Event('change'));
                    const input = document.getElementById('cfx-camera-device-name');
                    input.value = 'Front Caméra 📷'; input.dispatchEvent(new Event('input'));
                    document.getElementById('cfx-camera-device-save').click();
                """, raw_camera_id)
                saved_names = chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.camera.website_label_map'))")
                assert saved_names == {raw_camera_id: 'Front Caméra 📷', 'disconnected-test-camera': 'Other Webcam'}, saved_names
                driver.quit()
                driver = webdriver.Firefox(options=options, service=Service(
                    service_args=['--allow-system-access'], log_output=str(Path(tmp, 'gecko-device-restart.log')),
                ))
                driver.set_script_timeout(20)
                driver.get('about:cloakfox#sec-media')
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return document.getElementById('cfx-camera-device-name')?.value === 'Front Caméra 📷'"
                ))
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                per_device = driver.execute_async_script("""
                    const done=arguments[arguments.length-1];
                    (async()=>{
                        const stream=await navigator.mediaDevices.getUserMedia({video:true});
                        const clone=stream.getVideoTracks()[0].clone();
                        try {
                            const devices=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='videoinput');
                            return {track:stream.getVideoTracks()[0].label,clone:clone.label,
                                labels:devices.map(d=>d.label),ids:devices.map(d=>d.deviceId),
                                inventory:typeof navigator.mediaDevices.getCloakfoxCameras};
                        } finally {clone.stop();stream.getTracks().forEach(t=>t.stop());}
                    })().then(done,e=>done({error:e.name}));
                """)
                assert per_device.get('track') == per_device.get('clone') == 'Front Caméra 📷', per_device
                assert per_device['labels'] == ['Front Caméra 📷'], per_device
                assert per_device['ids'] == original_ids and raw_camera_id not in per_device['ids'], per_device
                assert per_device['inventory'] == 'undefined', per_device
                print('PASS selected webcam name survives restart, overrides fallback, preserves IDs and stays browser-only', flush=True)
                chrome("Services.prefs.setStringPref('cloakfox.camera.website_label_map', JSON.stringify({'not-the-selected-device':'Different Webcam'}))")
                driver.refresh()
                assert capture_label() == 'Desk camera'
                print('PASS names assigned to a different device do not rename the selected webcam', flush=True)
                chrome("Services.prefs.setStringPref('cloakfox.camera.website_label_map', JSON.stringify({[arguments[0]]:'Temporary name'}))", raw_camera_id)
                driver.get('about:cloakfox#sec-media')
                WebDriverWait(driver, 20).until(lambda _: driver.execute_script(
                    "return document.getElementById('cfx-camera-device-name')?.value === 'Temporary name'"
                ))
                driver.execute_script("document.getElementById('cfx-camera-device-reset').click()")
                assert raw_camera_id not in chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.camera.website_label_map'))")
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                assert capture_label() == 'Desk camera'
                print('PASS Use fallback label clears only the selected webcam override', flush=True)
                chrome("""
                    Services.prefs.setStringPref('cloakfox.camera.website_label_custom', 'Hidden Camera');
                    Services.prefs.setIntPref('cloakfox.camera.website_label_style', 4);
                    Services.prefs.setBoolPref('cloakfox.enabled', false);
                """)
                driver.refresh()
                assert capture_label() != 'Hidden Camera'
                print('PASS master off restores native capture labels', flush=True)
                chrome("""
                    Services.prefs.setBoolPref('cloakfox.enabled', true);
                    Services.prefs.setBoolPref('media.navigator.permission.disabled', false);
                    Services.prefs.setBoolPref('media.devices.enumerate.legacy.enabled', false);
                    Services.prefs.setStringPref('media.devices.enumerate.legacy.allowlist', '');
                """)
                driver.get(f'http://localhost:{server.server_port}/')
                before_permission = driver.execute_async_script("""
                    const done = arguments[arguments.length - 1];
                    navigator.mediaDevices.enumerateDevices().then(ds =>
                        done(ds.filter(d => d.kind === 'videoinput').map(d => d.label)),
                        error => done({error:error.name}));
                """)
                assert isinstance(before_permission, list) and all(label == '' for label in before_permission), before_permission
                chrome("""
                    const principal = Services.scriptSecurityManager.createContentPrincipal(
                        Services.io.newURI(arguments[0]), {});
                    Services.perms.addFromPrincipal(principal, 'camera', Services.perms.DENY_ACTION);
                """, driver.current_url)
                denied = driver.execute_async_script("""
                    const done = arguments[arguments.length - 1];
                    navigator.mediaDevices.getUserMedia({video:true}).then(stream => {
                        stream.getTracks().forEach(t => t.stop());done('unexpected capture');
                    }, error => done(error.name));
                """)
                assert denied == 'NotAllowedError', denied
                print('PASS custom labels preserve permission-gated names and denied camera access', flush=True)
            finally:
                driver.quit()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
