"""Headless canonical-layout admission diagnostic, using a disposable profile.

This is an acceptance probe, not a canonical geometry implementation. It changes
host layout inputs while retaining the same site and owner. --diagnose records
the blockers without returning a failure; otherwise unmet acceptance returns 1
(2 means these inputs passed but broader verification is still required).
Always identify the tested XUL: a source change is not tested by an older binary.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from probe_daily_defaults import launch


HTML = b'''<!doctype html><meta charset=utf-8><title>Canonical layout admission</title>
<style>
body{margin:0} #fixed{position:absolute;left:20px;top:20px;width:100px;height:80px}
#empty{position:absolute;left:0;top:0;width:0;height:0}
#wrap{position:absolute;left:20px;top:120px;width:170px}
#text{font:11px serif} #controls{position:absolute;left:240px;top:20px}
#controls>*{display:block;margin:7px;font:11px sans-serif}
#scroll{position:absolute;left:240px;top:220px;width:141.3px;height:63.3px;overflow:scroll;border:.7px solid black}
#scroll>div{width:200px;height:120px}
#round{position:absolute;left:440.3px;top:20.3px;width:101.3px;height:79.3px;border:.7px solid black}
#svg{position:absolute;left:20px;top:300px;width:420px;height:200px}
</style>
<div id=fixed></div><div id=empty></div>
<div id=wrap><span id=text>Geometry has several lines, ligatures ffi, and \xce\xa9.</span></div>
<div id=controls><button id=button>Button</button><input id=input value=Text>
<select id=select><option>Menu choice</option></select><input id=number type=number value=7>
<input id=checkbox type=checkbox checked><textarea id=textarea>Textarea</textarea></div>
<div id=scroll><div></div></div><div id=round></div>
<svg id=svg viewBox="0 0 420 200" xmlns="http://www.w3.org/2000/svg">
<defs><marker id=arrow markerWidth=8 markerHeight=8 refX=4 refY=4 orient=auto>
<path d="M0 0L8 4L0 8Z"/></marker><clipPath id=clip><rect width=105 height=105/></clipPath></defs>
<g transform="translate(13.3 17.2) rotate(13)"><path id=path d="M4 70 C30 -30 80 120 120 40"
fill=none stroke=black stroke-width=7.3 vector-effect=non-scaling-stroke
marker-start="url(#arrow)" marker-end="url(#arrow)" clip-path="url(#clip)"/>
<text id=svgtext x=130 y=40 font-size=11>SVG text ffi \xce\xa9</text></g>
<foreignObject x=130 y=80 width=200 height=100><div xmlns="http://www.w3.org/1999/xhtml"
id=foreign style="font:11px serif">Foreign object wraps its text into several lines.</div></foreignObject>
</svg>'''

READ = r'''
const rect=r=>['x','y','width','height'].map(k=>r[k]);
const matrix=m=>m&&['a','b','c','d','e','f'].map(k=>m[k]);
const output={};
for(const id of ['fixed','empty','text','button','input','select','number','checkbox','textarea','scroll','round','foreign']){
 const e=document.getElementById(id),r=e.getBoundingClientRect();
 output[id]={bounds:rect(r),fragments:[...e.getClientRects()].map(rect),
 offsets:[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight],
 client:[e.clientWidth,e.clientHeight],fontSize:getComputedStyle(e).fontSize,
 centerHit:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};
}
const text=document.getElementById('text'),range=document.createRange();
range.selectNodeContents(text);
output.range={bounds:rect(range.getBoundingClientRect()),fragments:[...range.getClientRects()].map(rect)};
range.setStart(text.firstChild,3);range.collapse(true);
output.caret={bounds:rect(range.getBoundingClientRect()),fragments:[...range.getClientRects()].map(rect)};
for(const id of ['path','svgtext']){
 const e=document.getElementById(id);
 output[id]={bounds:rect(e.getBoundingClientRect()),fill:rect(e.getBBox()),
 strokeMarkersClip:rect(e.getBBox({fill:true,stroke:true,markers:true,clipped:true})),
 ctm:matrix(e.getCTM()),screenCTM:matrix(e.getScreenCTM())};
 if(id==='path'){output[id].length=e.getTotalLength();const p=e.getPointAtLength(30);output[id].point=[p.x,p.y];}
}
return output;
'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *_):
        pass


def differences(a, b):
    return [key for key in a if a[key] != b[key]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnose', action='store_true')
    args = parser.parse_args()
    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    out = Path(os.environ.get('REPORT_DIR', '/tmp/cloakfox-canonical-geometry-readiness'))
    out.mkdir(parents=True, exist_ok=True)
    xul = binary.parent / 'XUL'
    if not xul.exists():
        xul = binary.parents[1] / 'Resources/XUL'
    with xul.open('rb') as source:
        xul_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    report = {'purpose': 'canonical geometry acceptance diagnostic; no implementation claim',
              'binary': str(binary), 'xulSHA256': xul_hash, 'samples': {}, 'blockers': []}
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-geometry-readiness-') as temp:
            profile = Path(temp) / 'profile'
            profile.mkdir()
            driver = launch(profile, out / 'gecko.log')
            try:
                def chrome(script, *arguments):
                    driver.set_context('chrome')
                    return driver.execute_script(script, *arguments)

                report['runtime'] = chrome('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID};')
                if not report['runtime']['version'].startswith('159.'):
                    raise RuntimeError('This probe requires the Firefox159 test build')
                chrome("Services.prefs.setBoolPref('dom.security.https_only_mode',false);Services.prefs.setBoolPref('cloakfox.enabled',true);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);")
                driver.set_context('content')
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                # Retain generated persona fields, but pin identity inputs for
                # every measurement. Only this disposable profile is changed.
                chrome("const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));cfg['canvas:seed']=12345;cfg['fonts:spacing_seed']=54321;cfg['fingerprint:secret']='A'.repeat(43)+'=';delete cfg['geometry:canonical'];delete cfg['rendering:geometry_profile'];Services.prefs.setStringPref(key,JSON.stringify(cfg));")

                def sample(name, *, refresh=True):
                    driver.set_context('content')
                    if refresh:
                        driver.refresh()
                    report['samples'][name] = driver.execute_script(READ)
                    report.setdefault('screenshots', {})[name] = hashlib.sha256(driver.get_screenshot_as_png()).hexdigest()

                def request(value):
                    chrome("const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key));cfg['geometry:canonical']=arguments[0];Services.prefs.setStringPref(key,JSON.stringify(cfg));", value)

                sample('protected')
                request(True)
                sample('requestedLive', refresh=False)
                sample('requested')
                sample('requestedReload')
                chrome("Services.prefs.setIntPref('font.minimum-size.x-western',50);")
                sample('minimumFont50')
                chrome("Services.prefs.setIntPref('font.minimum-size.x-western',0);")
                sample('minimumFont0')
                chrome("Services.prefs.setStringPref('layout.css.devPixelsPerPx','1.25');")
                sample('deviceScale125')
                chrome("Services.prefs.setStringPref('layout.css.devPixelsPerPx','1.0');")
                sample('deviceScale100')
                chrome("Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.browsingContext.fullZoom=1.25;")
                sample('fullZoom125', refresh=False)
                chrome("Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.browsingContext.fullZoom=1.0;")
                sample('fullZoom100', refresh=False)
                chrome("Services.prefs.setIntPref('widget.non-native-theme.scrollbar.style',1);")
                sample('scrollbarCocoa')
                chrome("Services.prefs.setIntPref('widget.non-native-theme.scrollbar.style',4);")
                sample('scrollbarWindows')
                request(False)
                sample('disabledLive', refresh=False)
                request('true')
                sample('malformed')
                chrome("Services.prefs.setBoolPref('cloakfox.enabled',false);")
                sample('masterOffControl')
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()
        samples = report['samples']
        required = {'protected', 'requested', 'requestedReload', 'minimumFont50',
                    'minimumFont0', 'deviceScale125', 'deviceScale100',
                    'fullZoom125', 'fullZoom100', 'scrollbarCocoa', 'scrollbarWindows'}
        if required.issubset(samples):
            report['requestChangedPresentation'] = differences(samples['protected'], samples['requested'])
            report['reloadChanges'] = differences(samples['requested'], samples['requestedReload'])
            report['hostDependencies'] = {
                'minimumFontPreference': differences(samples['minimumFont50'], samples['minimumFont0']),
                'devicePixelScale': differences(samples['deviceScale125'], samples['deviceScale100']),
                'fullZoom': differences(samples['fullZoom125'], samples['fullZoom100']),
                'scrollbarStyle': differences(samples['scrollbarCocoa'], samples['scrollbarWindows']),
            }
            for dependency, affected in report['hostDependencies'].items():
                if affected:
                    report['blockers'].append(f'{dependency} still changes requested canonical layout: {", ".join(affected)}')
            if samples['requested']['fixed']['bounds'] != [20, 20, 100, 80]:
                report['blockers'].append('Requested mode still presents additive geometry; canonical layout admission is not implemented')
            if report['reloadChanges']:
                report['blockers'].append('Same-owner reload changed geometry')
            report['transitions'] = {
                'requestBeforeReload': differences(samples['protected'], samples['requestedLive']),
                'disableBeforeReloadVersusMalformedAfterReload': differences(samples['disabledLive'], samples['malformed']),
            }
        report['status'] = ('INCOMPLETE DIAGNOSTIC' if not required.issubset(samples)
                            else 'BLOCKED / NOT IMPLEMENTED' if report['blockers']
                            else 'ACCEPTANCE REQUIRES BROADER CROSS-HOST AND PAINT VERIFICATION')
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key not in ('samples', 'screenshots')}, indent=2))
    return 0 if args.diagnose else 1 if report['blockers'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
