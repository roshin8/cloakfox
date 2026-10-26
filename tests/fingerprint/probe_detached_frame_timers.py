"""Saved iframe timers must survive iframe removal when rebound to a live window.

Sentry Replay caches clean timer functions this way. Calling them after Gecko
tears down the source realm used to throw InvalidStateError in Cloakfox, including
when reCAPTCHA changed a field observed by Replay. Local HTTP fixture only; no
CAPTCHA execution, signup or external service is involved.

Run with CLOAKFOX_BIN and a Selenium-enabled Python interpreter.
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

PAGE = r"""<!doctype html><title>Detached frame timer regression</title><body>
<script>
const report = {activeMath: Math.sin(0.5) !== 0.479425538604203, results: {}};
const saved = {};
const raw = {};
for (const name of ['setTimeout', 'setInterval', 'requestAnimationFrame']) {
  const frame = document.createElement('iframe');
  frame.hidden = true;
  document.head.appendChild(frame);
  raw[name] = frame.contentWindow[name];
  saved[name] = raw[name].bind(window);
  frame.remove();
}
// The first call can succeed before teardown; exercise the retained references
// in a later task, after the source globals' chrome wrappers have been nuked.
setTimeout(async () => {
  for (const [name, fn] of Object.entries(saved)) {
    try {
      const object = {marker: 7};
      let id;
      let ticks = 0;
      await new Promise((resolve, reject) => {
        const watchdog = setTimeout(() => reject(new Error('callback did not run')), 3000);
        id = fn(function(first, second) {
          ticks++;
          if (name === 'requestAnimationFrame') {
            report.results[name] = {ok: Number.isFinite(first), receiver: this === window};
          } else {
            report.results[name] = {ok: first === object && second === 42, receiver: this === window};
          }
          if (name === 'setInterval' && ticks < 2) return;
          if (name === 'setInterval') clearInterval(id);
          clearTimeout(watchdog);
          resolve();
        }, 1, object, 42);
      });
      report.results[name].ticks = ticks;
      let receiverError;
      try { raw[name].call({}, () => {}, 1); } catch (error) { receiverError = error.name; }
      report.results[name].receiverError = receiverError;
    } catch (error) {
      report.results[name] = {ok: false, name: error.name, message: error.message};
    }
  }
  let cancelledFired = false;
  try {
    clearTimeout(saved.setTimeout(() => { cancelledFired = true; }, 10));
    await new Promise(resolve => setTimeout(resolve, 40));
    report.cancelledFired = cancelledFired;
  } catch (error) {
    report.cancellationError = {name: error.name, message: error.message};
  }
  document.documentElement.dataset.result = JSON.stringify(report);
}, 250);
</script>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def log_message(self, *args):
        pass


def run(binary, enabled, url, profile):
    options = Options()
    options.binary_location = binary
    for arg in ('-headless', '-no-remote', '-purgecaches', '-profile', str(profile)):
        options.add_argument(arg)
    options.set_preference('cloakfox.enabled', enabled)
    options.set_preference('privacy.resistFingerprinting', False)
    with webdriver.Firefox(options=options, service=Service(
            service_args=['--allow-system-access'], log_output=str(profile / 'gecko.log'))) as driver:
        driver.get(url)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script(
            'return !!document.documentElement.dataset.result'))
        result = json.loads(driver.execute_script('return document.documentElement.dataset.result'))
        print(json.dumps({'enabled': enabled, **result}), flush=True)
        assert result['activeMath'] == enabled, 'Actor activation control failed'
        assert all(x.get('ok') and x.get('receiver') for x in result['results'].values()), result
        assert result['results']['setInterval']['ticks'] == 2, result
        assert all(x.get('receiverError') == 'TypeError' for x in result['results'].values()), result
        assert result['cancelledFired'] is False, result


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-detached-timers-') as temporary:
            for enabled in (False, True):
                profile = Path(temporary) / str(enabled)
                profile.mkdir()
                run(os.environ['CLOAKFOX_BIN'], enabled,
                    f'http://127.0.0.1:{server.server_port}/', profile)
        print('PASS: detached-frame timers retain callbacks, arguments, receivers and cancellation')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
