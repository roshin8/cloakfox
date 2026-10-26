"""A debugger attached before navigation must not suspend new workers forever.

Uses a disposable profile and loopback-only fixture. Run with CLOAKFOX_BIN set
and selenium/geckodriver available. No media devices or external sites are used.
"""

import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        worker = self.path == "/worker.js"
        body = (
            b'postMessage("worker-ready");'
            if worker else
            b'<!doctype html><body>waiting<script>'
            b'window.workerReady=false;const w=new Worker("/worker.js");'
            b'w.onmessage=e=>{window.workerReady=e.data==="worker-ready"};</script>'
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript" if worker else "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-worker-debugger-") as profile:
            options = Options()
            options.binary_location = os.environ["CLOAKFOX_BIN"]
            for argument in ["-headless", "-profile", profile, "-no-remote", "-purgecaches"]:
                options.add_argument(argument)
            service = Service(
                executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
                service_args=["--allow-system-access"],
                log_output=str(Path(profile, "geckodriver.log")),
            )
            driver = webdriver.Firefox(options=options, service=service)
            try:
                driver.set_script_timeout(20)
                driver.get("about:blank")
                driver.set_context("chrome")
                debugger_result = driver.execute_async_script("""
                    const done = arguments[arguments.length - 1];
                    const { require } = ChromeUtils.importESModule(
                        "resource://devtools/shared/loader/Loader.sys.mjs");
                    const { gDevTools } = require("devtools/client/framework/devtools");
                    gDevTools.showToolboxForTab(window.gBrowser.selectedTab,
                        { toolId: "jsdebugger" }).then(() => done(),
                        error => done({ error: String(error) }));
                """)
                assert debugger_result is None, debugger_result
                driver.set_context("content")
                driver.get(f"http://127.0.0.1:{server.server_port}/")
                deadline = time.monotonic() + 5
                ready = False
                while time.monotonic() < deadline:
                    ready = driver.execute_script("return window.workerReady === true")
                    if ready:
                        break
                    time.sleep(0.1)
                print(json.dumps({"workerReadyWithDebugger": ready}), flush=True)
                assert ready, "Worker did not start while DevTools debugger was attached"
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
