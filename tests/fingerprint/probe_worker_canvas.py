"""Compare window/worker OffscreenCanvas noise in distinct containers.

Uses a local HTTP page and disposable profile. Both realms draw the same
font-free pixels, so differences identify canvas seed resolution, not fonts.
Run with CLOAKFOX_BIN and selenium/geckodriver, as for the other live probes.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


DRAW = r"""
async function draw() {
  function hash(bytes) {
    let h = 0;
    for (const b of bytes) h = (h * 31 + b) >>> 0;
    return h.toString(16);
  }
  async function blobHash(canvas) {
    const blob = await canvas.convertToBlob();
    return hash(new Uint8Array(await blob.arrayBuffer()));
  }
  const canvas = new OffscreenCanvas(64, 64);
  const gl = canvas.getContext('webgl');
  if (!gl) throw new Error('WebGL unavailable');
  gl.clearColor(0.2, 0.4, 0.7, 1);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.enable(gl.SCISSOR_TEST);
  gl.scissor(8, 12, 32, 24);
  gl.clearColor(0.8, 0.3, 0.1, 1);
  gl.clear(gl.COLOR_BUFFER_BIT);
  const pixels = new Uint8Array(64 * 64 * 4);
  gl.readPixels(0, 0, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  const glerror = gl.getError();
  if (glerror) throw new Error('WebGL error ' + glerror);
  const canvas2d = new OffscreenCanvas(64, 64);
  const ctx = canvas2d.getContext('2d');
  ctx.fillStyle = '#369'; ctx.fillRect(0, 0, 64, 64);
  ctx.fillStyle = '#c51'; ctx.fillRect(8, 12, 32, 24);
  return {
    webglPixels: hash(pixels), webglBlob: await blobHash(canvas),
    canvas2dPixels: hash(ctx.getImageData(0, 0, 64, 64).data),
    canvas2dBlob: await blobHash(canvas2d),
  };
}
"""

COMPARE = r"""
const done = arguments[arguments.length - 1];
const source = arguments[0];
(async () => {
  const windowResult = await (new Function(source + '; return draw();'))();
  const workerResult = await new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([
      source + '; draw().then(result => postMessage({result}), '
      + 'error => postMessage({error: String(error)}));'
    ], {type: 'text/javascript'}));
    const worker = new Worker(url);
    const cleanup = () => { worker.terminate(); URL.revokeObjectURL(url); };
    const timer = setTimeout(() => {
      cleanup(); reject(new Error('worker timeout'));
    }, 15000);
    worker.onmessage = ({data}) => {
      clearTimeout(timer); cleanup();
      if (data.error) reject(new Error(data.error)); else resolve(data.result);
    };
    worker.onerror = (event) => {
      clearTimeout(timer); cleanup(); reject(new Error(event.message));
    };
  });
  return {window: windowResult, worker: workerResult};
})().then(result => done(JSON.stringify(result)),
          error => done(JSON.stringify({error: String(error)})));
"""

OPEN_TAB = """
const win = Services.wm.getMostRecentWindow('navigator:browser');
const tab = win.gBrowser.addTab(arguments[0], {
  userContextId: arguments[1],
  triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
});
win.gBrowser.selectedTab = tab;
"""

SIGNALS = ('webglPixels', 'webglBlob', 'canvas2dPixels', 'canvas2dBlob')
SEEDS = {0: 333333, 1: 111111, 2: 999999, 3: 0}


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<!doctype html><title>Worker canvas probe</title>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def main(binary: str) -> int:
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    results = {}
    try:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory, 'profile')
            profile.mkdir()
            prefs = ['user_pref("cloakfox.enabled", true);',
                     'user_pref("privacy.userContext.enabled", true);']
            for ucid, seed in SEEDS.items():
                cfg = {'canvas:seed': seed, 'fonts': ['Arial', 'Verdana'],
                       'fonts:spacing_seed': 0x5EED}
                prefs.append(f'user_pref("cloakfox.s.cloak_cfg_{ucid}", '
                             f'{json.dumps(json.dumps(cfg))});')
            (profile / 'user.js').write_text('\n'.join(prefs) + '\n')
            options = Options()
            options.binary_location = binary
            options.set_preference('cloakfox.experimental.canvas_pipeline',os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE','0')=='1')
            options.add_argument('--headless')
            options.add_argument('-profile')
            options.add_argument(str(profile))
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=['--allow-system-access'],
                log_output=str(Path(directory, 'geckodriver.log'))))
            try:
                driver.set_page_load_timeout(30)
                driver.set_script_timeout(30)
                wait = WebDriverWait(driver, 20)
                driver.get(url)
                for ucid in SEEDS:
                    if ucid:
                        before = set(driver.window_handles)
                        driver.set_context('chrome')
                        driver.execute_script(OPEN_TAB, url, ucid)
                        driver.set_context('content')
                        wait.until(lambda d: len(set(d.window_handles) - before) == 1)
                        driver.switch_to.window(next(iter(set(driver.window_handles) - before)))
                    wait.until(lambda d: d.current_url == url and
                               d.execute_script('return document.readyState') == 'complete')
                    samples = []
                    for _ in range(2):
                        samples.append(json.loads(driver.execute_async_script(COMPARE, DRAW)))
                        driver.refresh()
                        wait.until(lambda d: d.current_url == url and
                               d.execute_script('return document.readyState') == 'complete')
                    results[ucid] = samples
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()

    print(json.dumps(results, indent=2))
    failures = []
    for ucid, samples in results.items():
        if any('error' in sample for sample in samples):
            failures.append(f'container {ucid}: collection error')
            continue
        for signal in SIGNALS:
            values = [sample[realm][signal] for sample in samples
                      for realm in ('window', 'worker')]
            if len(set(values)) != 1:
                failures.append(f'container {ucid}: {signal} window/worker or reload mismatch {values}')
    if not failures:
        for signal in SIGNALS:
            for realm in ('window', 'worker'):
                values = [results[ucid][0][realm][signal] for ucid in SEEDS]
                if len(set(values)) != len(values):
                    failures.append(f'{realm} {signal}: different container seeds collapsed {values}')
    if failures:
        print('FAIL: ' + '\n'.join(failures))
        return 1
    print('PASS: window/worker canvas pixels and blobs agree, survive reloads, '
          'and differ across container seeds including zero')
    return 0


if __name__ == '__main__':
    binary = os.environ.get('CLOAKFOX_BIN')
    if not binary or not Path(binary).exists():
        sys.exit('CLOAKFOX_BIN not set or binary missing')
    sys.exit(main(binary))
