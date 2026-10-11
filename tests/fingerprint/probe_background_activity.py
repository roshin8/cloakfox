#!/usr/bin/env python3
"""Measure real server-side heartbeats and scheduling without refocusing pages.

Requires selenium and websockets. Runs headful, with disposable profiles and
local HTTP/WebSocket endpoints. Default background observation exceeds Gecko's
normal timer-throttling startup delay; no scheduling preferences are changed.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from websockets.sync.server import serve

from probe_focus_masking import chrome, set_pref

PREF = "cloakfox.opt.focus_masking"
PAGE = """<!doctype html><meta charset=utf-8><input id=a>
<script>
const label=new URLSearchParams(location.search).get('label');
let raf=0,timer=0,worker=0;
function frame(){raf++;requestAnimationFrame(frame)}requestAnimationFrame(frame);
setInterval(()=>timer++,100);
const w=new Worker('/worker');w.onmessage=()=>worker++;
setInterval(()=>fetch('/record',{method:'POST',body:JSON.stringify({label,raf,timer,worker})}),200);
if(label==='ws') {
  const socket=new WebSocket('ws://127.0.0.1:WS_PORT');
  socket.onopen=()=>setInterval(()=>socket.send(label),200);
}
if(label==='top')for(const name of ['same','cross','ws']) {
  const f=document.createElement('iframe'),u=new URL(location.href);
  u.searchParams.set('label',name);if(name==='cross')u.hostname='localhost';
  f.src=u;document.body.append(f);
}
</script>"""


class Page(BaseHTTPRequestHandler):
    records = {}
    sockets = []
    lock = threading.Lock()
    ws_port = 0

    def do_GET(self):
        body = (b"setInterval(()=>postMessage('tick'),100)" if urlparse(self.path).path == "/worker"
                else PAGE.replace("WS_PORT", str(self.ws_port)).encode())
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript" if self.path == "/worker" else "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.lock:
            self.records.setdefault(data["label"], []).append((time.monotonic(), data))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def websocket(connection):
    for message in connection:
        with Page.lock:
            Page.sockets.append(time.monotonic())
        connection.send(message)


def observe(seconds):
    start = time.monotonic()
    time.sleep(seconds)
    end = time.monotonic()
    with Page.lock:
        records = {k: [r for r in v if start <= r[0] <= end] for k, v in Page.records.items()}
        sockets = [t for t in Page.sockets if start <= t <= end]
    summary = {}
    for label in ("top", "same", "cross", "ws"):
        rows = records.get(label, [])
        times = [start] + [r[0] for r in rows] + [end]
        span = rows[-1][0] - rows[0][0] if len(rows) > 1 else 0
        summary[label] = {"reports": len(rows), "maxHttpGap": max(b-a for a,b in zip(times,times[1:]))}
        for counter in ("raf", "timer", "worker"):
            summary[label][counter + "Hz"] = ((rows[-1][1][counter]-rows[0][1][counter])/span
                                               if span else 0)
    times = [start] + sockets + [end]
    summary["websocket"] = {"messages": len(sockets), "maxGap": max(b-a for a,b in zip(times,times[1:]))}
    return summary


def main():
    checks = []

    def check(ok, name, data):
        checks.append({"name": name, "pass": bool(ok), "data": data})
        print(("PASS" if ok else "FAIL") + " — " + name, flush=True)

    with serve(websocket, "127.0.0.1", 0) as ws_server:
        Page.ws_port = ws_server.socket.getsockname()[1]
        threading.Thread(target=ws_server.serve_forever, daemon=True).start()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix="cloakfox-heartbeat-") as temp:
                opts = Options()
                opts.binary_location = os.environ["CLOAKFOX_BIN"]
                opts.set_preference("cloakfox.enabled", True)
                driver = webdriver.Firefox(options=opts, service=Service(
                    executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
                    service_args=["--allow-system-access"], log_output=temp + "/gecko.log"))
                try:
                    driver.get(f"http://127.0.0.1:{server.server_port}/?label=top")
                    chrome(driver, "window.focus(); gBrowser.selectedBrowser.focus();")
                    # Control condition: unmasked background rAF really stops.
                    set_pref(driver, PREF, False)
                    chrome(driver, "window.__probeTab=gBrowser.selectedTab; window.__otherTab=gBrowser.addTab('about:blank',{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()}); gBrowser.selectedTab=window.__otherTab;")
                    baseline = observe(3)
                    check(baseline["top"]["rafHz"] < 2, "unmasked background animation pauses", baseline)
                    # Enable while already backgrounded to exercise the live refresh path.
                    set_pref(driver, PREF, True)
                    time.sleep(.5)
                    masked = observe(float(os.environ.get("BACKGROUND_PROBE_SECONDS", "35")))
                    for mode, data in (("background tab", masked),):
                        for label in ("top", "same", "cross", "ws"):
                            d = data[label]
                            check(d["rafHz"] >= 20 and d["timerHz"] >= 5 and d["workerHz"] >= 5,
                                  f"foreground scheduling in {mode} ({label})", d)
                            check(d["maxHttpGap"] < 1.2,
                                  f"HTTP heartbeats continue in {mode} ({label})", d)
                        check(data["websocket"]["maxGap"] < 1.2,
                              f"WebSocket heartbeats continue in {mode}", data["websocket"])
                    chrome(driver, "gBrowser.selectedTab=window.__probeTab;")
                    driver.minimize_window()
                    data = observe(5)
                    for label in ("top", "same", "cross", "ws"):
                        d = data[label]
                        check(d["rafHz"] >= 20 and d["timerHz"] >= 5 and d["workerHz"] >= 5
                              and d["maxHttpGap"] < 1.2,
                              f"scheduling and HTTP heartbeat survive minimization ({label})", d)
                    check(data["websocket"]["maxGap"] < 1.2,
                          "WebSocket heartbeat survives minimization", data["websocket"])
                    chrome(driver, "window.restore(); window.focus(); gBrowser.selectedBrowser.focus();")
                    handles = set(driver.window_handles)
                    chrome(driver, "window.__probeSecondWindow=OpenBrowserWindow();")
                    WebDriverWait(driver, 10).until(lambda d: set(d.window_handles)-handles)
                    driver.switch_to.window(next(iter(set(driver.window_handles)-handles)))
                    driver.get("about:blank")
                    data = observe(5)
                    for label in ("top", "same", "cross", "ws"):
                        d = data[label]
                        check(d["rafHz"] >= 20 and d["timerHz"] >= 5 and d["workerHz"] >= 5
                              and d["maxHttpGap"] < 1.2,
                              f"scheduling and HTTP heartbeat survive window deactivation ({label})", d)
                    check(data["websocket"]["maxGap"] < 1.2,
                          "WebSocket heartbeat survives window deactivation", data["websocket"])
                finally:
                    driver.quit()
        finally:
            server.shutdown()
            server.server_close()
    report = os.environ.get("BACKGROUND_PROBE_REPORT", "/tmp/cloakfox-background-activity-results.json")
    with open(report, "w") as f:
        json.dump(checks, f, indent=2)
    print(f"{sum(c['pass'] for c in checks)}/{len(checks)} checks passed; {report}")
    return 0 if all(c["pass"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
