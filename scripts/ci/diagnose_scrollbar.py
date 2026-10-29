#!/usr/bin/env python3
"""Hosted-only A/B diagnostic against reused native apps; no engine rebuild."""
import argparse
import base64
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,default=Path.cwd())
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.repo))
sys.path.insert(0,str(args.repo/'tests/engines'))
from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Windowless

# Preserve the exact pre-fix fixture even if the recovery checkout has the CSS fix.
class OriginalFixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'<!doctype html><style>html,body{margin:0;background:rgb(13,37,91)}body{height:3000px}</style><title>Owned offscreen fixture</title><input id="field">'
        self.send_response(200)
        self.send_header('Content-Type','text/html')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

DOM="""({url:location.href,title:document.title,ready:document.readyState,
field:!!document.getElementById('field'),inner:[innerWidth,innerHeight],
client:[document.documentElement.clientWidth,document.documentElement.clientHeight],
scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
bodyBackground:getComputedStyle(document.body).backgroundColor,
htmlBackground:getComputedStyle(document.documentElement).backgroundColor,
scrollbarWidth:getComputedStyle(document.documentElement).scrollbarWidth,
cornerElement:document.elementFromPoint(innerWidth-1,innerHeight-1)?.tagName,
visibility:document.visibilityState,devicePixelRatio})"""
args.output.mkdir(parents=True,exist_ok=True)
report={'hypothesis':'Native scrollbar occupies the final viewport pixel','cases':[]}
preference=subprocess.run(['defaults','read','-g','AppleShowScrollBars'],capture_output=True,text=True)
report['AppleShowScrollBars']={'returncode':preference.returncode,'stdout':preference.stdout,'stderr':preference.stderr}
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),OriginalFixture)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/'

def snapshot(app,browser,label):
    # Wait for paint to settle without substituting or relaxing the acceptance check.
    deadline=time.monotonic()+3
    frame={}
    while time.monotonic()<deadline:
        frame=app.rpc('frame',browser=browser)
        if frame.get('ok'):break
        time.sleep(.025)
    time.sleep(.3)
    frame=app.rpc('frame',browser=browser)
    result={'frame':frame,'dom':app.evaluate(browser,DOM)}
    screenshot=app.rpc('cdp',browser=browser,method='Page.captureScreenshot',params={'format':'png','captureBeyondViewport':False})
    if screenshot.get('ok') and screenshot.get('result',{}).get('data'):
        path=args.output/(label+'.png')
        path.write_bytes(base64.b64decode(screenshot['result']['data']))
        result['screenshot']=str(path)
    else:result['screenshotError']=screenshot
    return result

try:
    for shared in (False,True):
        case={'sharedTexture':shared}
        report['cases'].append(case)
        with tempfile.TemporaryDirectory(prefix='cloakfox-scrollbar-diagnostic-') as folder:
            root=Path(folder)
            app=Windowless(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root,shared=shared)
            try:
                case['ready']=app.ready
                config=PersonaStore(root/'personas').get('1','chromium')
                case['config']=app.rpc('applyConfig',config=config)
                assert case['config']['ok'],case['config']
                browser=app.open('1',url,configRevision=config['revision'])
                name='iosurface' if shared else 'cpu'
                case['original']=snapshot(app,browser,name+'-original')
                app.evaluate(browser,"document.documentElement.style.scrollbarWidth='none';true")
                # The unchanged helper still requires exact [91,37,13,255].
                try:case['fixedFrame']=app.wait_frame(browser)
                except AssertionError as error:case['fixedError']=str(error)
                case['hiddenScrollbar']=snapshot(app,browser,name+'-hidden')
                case['wheel']=app.rpc('input',browser=browser,configRevision=config['revision'],kind='wheel',x=300,y=300,deltaX=0,deltaY=-200)
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    case['scrollY']=app.evaluate(browser,'window.scrollY')
                    if case['scrollY']>0:break
                    time.sleep(.025)
                case['exactColorAfterCSS']=case['hiddenScrollbar']['frame'].get('cornerBGRA')==[91,37,13,255]
                case['scrollPreserved']=case['scrollY']>0
            finally:app.close()
finally:
    server.shutdown();server.server_close()
    (args.output/'scrollbar-diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if all(c.get('exactColorAfterCSS') and c.get('scrollPreserved') for c in report['cases']) else 1)
