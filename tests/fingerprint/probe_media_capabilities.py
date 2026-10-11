"""Check decoding/encoding spoof hooks, native fallback, and input validation.

Firefox 155 moved both methods enough that the old patch applied both hooks to
EncodingInfo. Exercise each method with a valid but unsupported format, plus an
invalid configuration that must still reject. Uses only a disposable profile
and a local page. Run with CLOAKFOX_BIN; optionally set GECKODRIVER.
"""

import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>Media capabilities probe</title>")

    def log_message(self, *_args):
        pass


PROBE = """
const done = arguments[0];
(async () => {
  const result = {};
  for (const [method, type] of [['decodingInfo', 'file'], ['encodingInfo', 'record']]) {
    const info = await navigator.mediaCapabilities[method]({type, video: {
      contentType: 'video/x-cloakfox-unsupported', width: 640, height: 480,
      bitrate: 100000, framerate: 30
    }});
    let invalid = 'resolved';
    try { await navigator.mediaCapabilities[method]({type}); }
    catch (error) { invalid = error.name; }
    result[method] = {supported: info.supported, smooth: info.smooth,
      powerEfficient: info.powerEfficient, invalid};
  }
  return result;
})().then(done, error => done({error: String(error)}));
"""


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    gecko = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert gecko, "Set GECKODRIVER or install geckodriver"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for spoof in (False, True):
            with tempfile.TemporaryDirectory(prefix="cloakfox-media-probe-") as temp:
                opts = Options()
                opts.binary_location = binary
                opts.add_argument("--headless")
                opts.set_preference("cloakfox.enabled", True)
                opts.set_preference("cloakfox.s.cloak_cfg_0", json.dumps({
                    "fonts": ["Arial"], "fonts:spacing_seed": 12345,
                    "mediaCapabilities:spoof": spoof,
                }))
                driver = webdriver.Firefox(options=opts, service=Service(
                    executable_path=gecko,
                    service_args=["--allow-system-access"],
                    log_output=str(Path(temp) / "geckodriver.log")))
                try:
                    driver.set_page_load_timeout(20)
                    driver.set_script_timeout(20)
                    driver.set_context("chrome")
                    assert driver.execute_script("return Services.appinfo.name") == "Cloakfox"
                    driver.set_context("content")
                    driver.get(f"http://127.0.0.1:{server.server_port}/")
                    result = driver.execute_async_script(PROBE)
                    print(json.dumps({"spoof": spoof, "result": result}), flush=True)
                    assert "error" not in result, result
                    for method, info in result.items():
                        assert info["supported"] is spoof, (method, info)
                        if spoof:
                            assert info["smooth"] and info["powerEfficient"], (method, info)
                        assert info["invalid"] == "TypeError", (method, info)
                finally:
                    driver.quit()
    finally:
        server.shutdown()
        server.server_close()
    print("PASS — decoding and encoding spoof independently; fallback and validation remain active")


if __name__ == "__main__":
    main()
