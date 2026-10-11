#!/usr/bin/env python3
"""Check page-facing fullscreen gates against independently observed native state.

Uses a local page/disposable profile. DOM fullscreen uses Gecko's widget-ignore
test mode; this does not test macOS fullscreen animation or a vendor assessment.
"""
import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from probe_focus_masking import PREF, chrome, set_pref

HTML = """<!doctype html><meta charset=utf-8><button id=enter>Enter</button>
<div id=host></div><script>
const shadow=document.querySelector('#host').attachShadow({mode:'open'});
shadow.innerHTML='<div id=target>Target</div>';
const events=[];
const detached=document.implementation.createHTMLDocument('detached');
document.addEventListener('fullscreenchange',()=>events.push('change'));
document.addEventListener('fullscreenerror',()=>events.push('error'));
let result='idle';
document.querySelector('#enter').onclick=async()=>{
 try{await shadow.firstElementChild.requestFullscreen();result='resolved'}
 catch(e){result=e.name}
};
function observe(){return {result,events:[...events],fullscreen:document.fullscreen,
 mozFullScreen:document.mozFullScreen,windowFullScreen:window.fullScreen,
 element:document.fullscreenElement?.tagName??null,
 alias:document.mozFullScreenElement?.tagName??null,
 root:document.documentElement.matches(':fullscreen'),
 target:shadow.firstElementChild.matches(':fullscreen'),
 shadow:shadow.fullscreenElement?.id??null,shadowAlias:shadow.mozFullScreenElement?.id??null,
 layout:getComputedStyle(shadow.firstElementChild).position,
 detached:{element:detached.fullscreenElement,flag:detached.fullscreen,css:detached.documentElement.matches(':fullscreen')},
 gate:Boolean(document.fullscreenElement)&&document.fullscreen}}
</script>"""


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    checks = []

    def check(ok, label, state):
        checks.append({'pass': bool(ok), 'name': label, 'evidence': state})
        print(('PASS' if ok else 'FAIL') + ' — ' + label + ': ' + json.dumps(state), flush=True)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    driver = None
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-fullscreen-gate-') as temp:
            opts = Options()
            opts.binary_location = os.environ['CLOAKFOX_BIN']
            if not os.environ.get('CLOAKFOX_HEADFUL'):
                opts.add_argument('-headless')
            opts.set_preference('cloakfox.enabled', True)
            opts.set_preference('full-screen-api.ignore-widgets', True)
            driver = webdriver.Firefox(options=opts, service=Service(
                executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
                service_args=['--allow-system-access'], log_output=str(Path(temp)/'gecko.log')))

            def state():
                data = driver.execute_script('return observe()')
                data['nativeWindow'] = chrome(driver, 'return window.fullScreen')
                data['nativeDocument'] = chrome(driver, "return document.documentElement.hasAttribute('inDOMFullscreen')")
                return data

            def virtual(data):
                return data['gate'] and data['windowFullScreen'] and data['mozFullScreen'] and data['root'] and data['element']=='HTML' and data['alias']=='HTML'

            driver.get(f'http://127.0.0.1:{server.server_port}/')
            set_pref(driver, PREF, False)
            data = state()
            check(not data['gate'] and not data['nativeWindow'] and not data['nativeDocument'], 'baseline windowed gate rejected', data)
            set_pref(driver, PREF, True)
            WebDriverWait(driver, 5).until(lambda _: driver.execute_script('return document.hasFocus()'))
            data = state()
            check(virtual(data) and not data['nativeWindow'] and not data['nativeDocument'], 'masked windowed gate accepted', data)
            check(data['shadow'] is None and data['shadowAlias'] is None and not data['target'], 'virtual root does not invent shadow fullscreen target', data)
            check(data['detached']=={'element':None,'flag':False,'css':False}, 'detached document retains native fullscreen state', data)
            driver.find_element(By.ID, 'enter').click()
            WebDriverWait(driver, 10).until(lambda _: driver.execute_script("return observe().result!=='idle'"))
            data = state()
            check(data['result']=='resolved' and data['nativeWindow'] and data['nativeDocument'], 'native DOM fullscreen still enters', data)
            check(data['gate'] and data['element']=='DIV' and data['shadow']=='target' and data['shadowAlias']=='target' and data['target'], 'real fullscreen target and shadow retargeting exposed consistently', data)
            check(data['layout']=='fixed' and not data['events'], 'native fullscreen layout retained and transitions private', data)
            set_pref(driver, PREF, False)
            data = state()
            check(data['gate'] and data['shadow']=='target' and data['target'], 'live disabling exposes real fullscreen', data)
            set_pref(driver, PREF, True)
            driver.execute_async_script('document.exitFullscreen().then(arguments[0])')
            data = state()
            check(virtual(data) and not data['nativeWindow'] and not data['nativeDocument'] and not data['events'], 'masked gate remains accepted after real exit', data)
            for pref in (PREF, 'cloakfox.enabled'):
                set_pref(driver, pref, False)
                data = state()
                check(not data['gate'] and not data['root'] and data['element'] is None, pref+' live off restores windowed state', data)
                set_pref(driver, pref, True)
                data = state()
                check(virtual(data) and not data['nativeWindow'], pref+' live on restores virtual fullscreen', data)
    finally:
        if driver:
            driver.quit()
        server.shutdown()
        Path(os.environ.get('FULLSCREEN_PROBE_REPORT','/tmp/cloakfox-fullscreen-gate-results.json')).write_text(json.dumps(checks, indent=2))
    failures = sum(not c['pass'] for c in checks)
    print(f'{len(checks)-failures}/{len(checks)} checks passed', flush=True)
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
