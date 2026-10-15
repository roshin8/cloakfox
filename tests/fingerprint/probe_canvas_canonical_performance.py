"""Mac-only installed compatibility/load measurements, not a speed guarantee.

Uses disposable profiles and loopback content; records wall-clock timings outside
the page's protected clock. Large surfaces have a bounded 4096-pixel side.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<!doctype html><title>Canvas load check</title><label for="edit">Editor</label><textarea id="edit"></textarea><canvas id="canvas" width="512" height="512" aria-label="Rendered preview"></canvas>'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


ANIMATE = r'''
const done=arguments[arguments.length-1], c=document.getElementById('canvas'), x=c.getContext('2d');
let frames=0;
function draw(){
 x.fillStyle='#234567';x.fillRect(0,0,512,512);
 x.font='20px sans-serif';x.fillStyle='#fedcba';
 for(let j=0;j<32;j++){x.save();x.translate((j*37+frames*3)%480,j*15);x.rotate(frames/50);x.fillText('Canvas Ω مرحبا 😀',0,0);x.restore();}
 if(++frames===30)done({frames,pixel:Array.from(x.getImageData(510,510,1,1).data)});
 else requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
'''
LARGE = r'''
const done=arguments[arguments.length-1];
(async()=>{
 const c=new OffscreenCanvas(4096,4096),x=c.getContext('2d');
 x.fillStyle='rgb(41,103,179)';x.fillRect(0,0,c.width,c.height);
 const corner=Array.from(x.getImageData(4095,4095,1,1).data);
 const blob=await c.convertToBlob({type:'image/png'});
 const bitmap=await createImageBitmap(blob);
 const dest=new OffscreenCanvas(2,2),d=dest.getContext('2d');d.drawImage(bitmap,4094,4094,2,2,0,0,2,2);
 const copied=Array.from(d.getImageData(0,0,1,1).data);bitmap.close();
 c.width=c.height=0;
 done({corner,copied,bytes:blob.size,type:blob.type});
})().catch(e=>done({error:String(e)}));
'''


class ResidentSampler:
    """Sum disposable WebDriver process-tree RSS; shared pages can be counted twice."""
    def __init__(self, root_pid):
        self.root_pid = root_pid
        self.peak_kib = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        while not self.stop.is_set():
            rows = [list(map(int, row.split())) for row in subprocess.check_output(
                ['ps', '-axo', 'pid=,ppid=,rss='], text=True).splitlines() if row.strip()]
            descendants = {self.root_pid}
            while True:
                expanded = descendants | {pid for pid, parent, _ in rows if parent in descendants}
                if expanded == descendants:
                    break
                descendants = expanded
            self.peak_kib = max(self.peak_kib, sum(rss for pid, _, rss in rows if pid in descendants))
            self.stop.wait(.1)


def main():
    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    out = Path(os.environ.get('REPORT_DIR', '/tmp/cloakfox-canvas-load'))
    out.mkdir(parents=True, exist_ok=True)
    report = {'binary': str(binary), 'xulSHA256': hashlib.sha256(binary.with_name('XUL').read_bytes()).hexdigest(),
              'scope': 'single Mac; observed timings only, no universal performance or accessibility claim', 'cases': []}
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for mode in [False, True]:
            with tempfile.TemporaryDirectory(prefix='cloakfox-canvas-load-') as profile:
                options = Options()
                options.binary_location = str(binary)
                for arg in ['-headless', '-purgecaches', '-profile', profile]:
                    options.add_argument(arg)
                options.set_preference('cloakfox.experimental.canvas_pipeline', mode)
                case_out = out / ('canonical' if mode else 'legacy')
                case_out.mkdir(exist_ok=True)
                driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access'], log_output=str(case_out / 'gecko.log')))
                resident = ResidentSampler(driver.service.process.pid)
                resident.thread.start()
                try:
                    driver.set_script_timeout(60)
                    driver.set_context('chrome')
                    runtime = driver.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
                    driver.set_context('content')
                    driver.switch_to.new_window('tab')
                    driver.get(f'http://127.0.0.1:{server.server_port}/')
                    edit = driver.find_element('id', 'edit')
                    edit.send_keys('ordinary editing 123')
                    editing = driver.execute_script("return document.getElementById('edit')?.value") == 'ordinary editing 123'
                    start = time.monotonic()
                    animation = driver.execute_async_script(ANIMATE)
                    animation_seconds = time.monotonic() - start
                    start = time.monotonic()
                    large = driver.execute_async_script(LARGE)
                    large_seconds = time.monotonic() - start
                    passed = editing and animation.get('frames') == 30 and 'error' not in large and large['bytes'] > 0
                    if mode:
                        passed = passed and large['corner'] == large['copied'] == [41, 103, 179, 255]
                    report['cases'].append({'canonical': mode, 'runtime': runtime, 'editing': editing, 'animation': animation,
                                            'animationSeconds': animation_seconds, 'large': large,
                                            'largeSeconds': large_seconds,
                                            'peakProcessTreeRSSKiB': resident.peak_kib,
                                            'memoryAccounting': 'summed RSS, includes shared pages more than once', 'pass': passed})
                    print(json.dumps(report['cases'][-1]), flush=True)
                    (out / 'result.json').write_text(json.dumps(report, indent=2))
                finally:
                    driver.quit()
                    resident.stop.set()
                    resident.thread.join()
    finally:
        server.shutdown()
    return 0 if all(case['pass'] for case in report['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
