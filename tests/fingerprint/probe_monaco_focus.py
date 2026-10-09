#!/usr/bin/env python3
"""Real Monaco/Firepad-X focus integration, using local npm assets only.

Prepare assets with @hackerrank/firepad@0.8.6 and monaco-editor@0.18.1.
MONACO_PROBE_ASSETS contains node_modules and adapter.js (a bundled export of
the package's MonacoAdapter with monaco-editor resolved to window.monaco).
Set CLOAKFOX_HEADFUL=1 for real window activation and minimize/restore checks.
No Firebase backend or assessment platform is contacted.
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from probe_focus_masking import chrome, set_pref

PREF = "cloakfox.opt.focus_masking"
HTML = """<!doctype html><meta charset=utf-8>
<style>#editor{width:800px;height:350px}input{margin:20px}</style>
<div id=editor></div><input id=other>
<script>
const label=new URLSearchParams(location.search).get('label');
const events=[],errors=[];
window.addEventListener('error',e=>errors.push(e.message));
window.addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
function log(layer,type,data={}){events.push({layer,type,...data})}
for(const type of ['focus','blur','focusin','focusout']){
 window.addEventListener(type,e=>{if(e.isTrusted)log('dom',type,{target:e.target===window?'window':e.target.tagName})},true);
}
function report(){if(!window.probeReady)return;fetch('/record',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label,ready:true,errors,events,
 focused:document.hasFocus(),hidden:document.hidden,widgetFocus:editor.hasWidgetFocus(),textFocus:editor.hasTextFocus(),
 active:document.activeElement?.tagName,value:editor.getValue()})})}
setInterval(report,100);
</script>
<script src=/node_modules/monaco-editor/min/vs/loader.js></script>
<script>
require.config({paths:{vs:'/node_modules/monaco-editor/min/vs'}});
require(['vs/editor/editor.main'],()=>{
 const script=document.createElement('script');script.src='/adapter.js';
 script.onload=()=>{
  window.editor=monaco.editor.create(document.querySelector('#editor'),{value:'',language:'plaintext',minimap:{enabled:false}});
  window.adapter=new firepadProbe.MonacoAdapter(editor,false);
  adapter.setInitiated(true);
  for(const type of ['focus','blur','change','cursorActivity','error'])adapter.on(type,(op)=>log('adapter',type,{operation:type==='change'?op.toString():undefined}));
  editor.onDidFocusEditorWidget(()=>log('monaco','focus'));
  editor.onDidBlurEditorWidget(()=>log('monaco','blur'));
  editor.onDidFocusEditorText(()=>log('monaco-text','focus'));
  editor.onDidBlurEditorText(()=>log('monaco-text','blur'));
  editor.onDidChangeModelContent(e=>log('model','change',{sizes:e.changes.map(c=>c.text.length)}));
  editor.onDidChangeCursorPosition(()=>log('monaco','cursor'));
  window.probeReady=true;
  report();
 };document.head.appendChild(script);
});
</script>"""


class Handler(SimpleHTTPRequestHandler):
    records = {}
    lock = threading.Lock()

    def do_GET(self):
        if urlparse(self.path).path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.lock:
            self.records[data["label"]] = (time.monotonic(), data)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def snapshot(label, after=0):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        with Handler.lock:
            row = Handler.records.get(label)
        if row and row[0] > after and row[1]["ready"]:
            return row[1]
        time.sleep(.05)
    raise AssertionError(f"No fresh ready report: {label}; records={Handler.records}")


def main():
    assets = Path(os.environ["MONACO_PROBE_ASSETS"])
    versions = {name: json.loads((assets / "node_modules" / name / "package.json").read_text())["version"]
                for name in ("monaco-editor", "@hackerrank/firepad")}
    assert versions == {"monaco-editor": "0.18.1", "@hackerrank/firepad": "0.8.6"}, versions
    # Bundle the unmodified published adapter, sharing the real AMD Monaco
    # instance. No mock editor methods or adapter callback overrides are used.
    (assets / "adapter-entry.js").write_text("export {MonacoAdapter} from './node_modules/@hackerrank/firepad/es/monaco-adapter.js';")
    (assets / "monaco-global.js").write_text("module.exports = window.monaco;")
    subprocess.run(["node", "-e", "require('esbuild').buildSync({entryPoints:['adapter-entry.js'],bundle:true,format:'iife',globalName:'firepadProbe',outfile:'adapter.js',alias:{'monaco-editor':'./monaco-global.js'}})"], cwd=assets, check=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(assets)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    root = f"http://127.0.0.1:{server.server_port}/"
    checks = []
    observations = []
    driver = None

    def check(ok, name, evidence):
        checks.append({"pass": bool(ok), "name": name, "evidence": evidence})
        print(("PASS" if ok else "FAIL") + " — " + name, flush=True)

    def settle(label):
        # Monaco's DOM focus tracker defers blur with setTimeout. Allow it to run
        # before inspecting reports, without selecting the background tab.
        time.sleep(1.2)
        return snapshot(label, time.monotonic())

    def delta(before, after):
        return after["events"][len(before["events"]):]

    def callback(rows, layer, kind):
        return any(e["layer"] == layer and e["type"] == kind for e in rows)

    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-monaco-profile-") as profile:
            opts = Options()
            opts.binary_location = os.environ["CLOAKFOX_BIN"]
            headful = bool(os.environ.get("CLOAKFOX_HEADFUL"))
            if not headful:
                opts.add_argument("-headless")
            opts.set_preference("cloakfox.enabled", True)
            driver = webdriver.Firefox(options=opts, service=Service(
                executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
                service_args=["--allow-system-access"], log_output=str(Path(profile) / "gecko.log")))
            check(chrome(driver, "return Services.appinfo.name") == "Cloakfox", "built Cloakfox launched", driver.capabilities)
            for masked in (False, True):
                set_pref(driver, PREF, masked)
                label = "masked" if masked else "baseline"
                driver.get(root + "?label=" + label)
                snapshot(label)
                driver.execute_script("editor.focus()")
                before = settle(label)
                check(before["widgetFocus"] and before["textFocus"], label + " editor initially focused", before)
                tab = chrome(driver, "return gBrowser.selectedTab.linkedPanel")
                chrome(driver, "window.__monacoTargetTab=gBrowser.selectedTab; window.__monacoOtherTab=gBrowser.addTab('about:blank',{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});gBrowser.selectedTab=window.__monacoOtherTab;")
                away = settle(label)
                check(chrome(driver, "return gBrowser.selectedTab !== window.__monacoTargetTab"), label + " actual tab changed", tab)
                chrome(driver, "gBrowser.selectedTab=window.__monacoTargetTab;gBrowser.removeTab(window.__monacoOtherTab)")
                back = settle(label)
                for layer in ("monaco", "monaco-text", "adapter"):
                    rows = delta(before, back)
                    ok = not callback(rows, layer, "blur") and not callback(rows, layer, "focus") if masked else callback(delta(before, away), layer, "blur") and callback(delta(away, back), layer, "focus")
                    check(ok, label + " tab switch/return " + layer + " callbacks", rows)
                check(away["widgetFocus"] == masked and away["textFocus"] == masked,
                      label + " background editor focus state", away)
                if headful:
                    driver.execute_script("editor.focus()")
                    chrome(driver, "window.focus();gBrowser.selectedBrowser.focus()")
                    before = settle(label)
                    target = driver.current_window_handle
                    handles = set(driver.window_handles)
                    chrome(driver, "OpenBrowserWindow()")
                    WebDriverWait(driver, 12).until(lambda d: set(d.window_handles) - handles)
                    second = next(iter(set(driver.window_handles) - handles))
                    driver.switch_to.window(second)
                    chrome(driver, "window.focus();gBrowser.selectedBrowser.focus()")
                    WebDriverWait(driver, 8).until(lambda _: chrome(driver, "return Services.focus.activeWindow === window"))
                    away = settle(label)
                    driver.close()
                    driver.switch_to.window(target)
                    chrome(driver, "window.focus();gBrowser.selectedBrowser.focus()")
                    back = settle(label)
                    for layer in ("monaco", "monaco-text", "adapter"):
                        rows = delta(before, back)
                        ok = not callback(rows, layer, "blur") and not callback(rows, layer, "focus") if masked else callback(delta(before, away), layer, "blur") and callback(delta(away, back), layer, "focus")
                        check(ok, label + " native window departure/return " + layer, rows)
                    before = settle(label)
                    driver.minimize_window()
                    check(chrome(driver, "return window.windowState === window.STATE_MINIMIZED"), label + " actual native minimize", {})
                    away = settle(label)
                    chrome(driver, "window.restore();window.focus();gBrowser.selectedBrowser.focus()")
                    WebDriverWait(driver, 8).until(lambda _: chrome(driver, "return window.windowState !== window.STATE_MINIMIZED"))
                    back = settle(label)
                    for layer in ("monaco", "monaco-text", "adapter"):
                        rows = delta(before, back)
                        if masked:
                            check(not callback(rows, layer, "blur") and not callback(rows, layer, "focus"), label + " minimize/restore " + layer, rows)
                        else:
                            # macOS minimization need not deactivate DOM focus.
                            # Record the control instead of demanding events the
                            # unmodified browser itself does not generate.
                            observations.append({"name": label + " minimize/restore " + layer, "events": rows, "away": away})
                            print("INFO — baseline minimize/restore " + layer + ": " + json.dumps(rows), flush=True)
                    check(away["hidden"] != masked, label + " minimized visibility state", away)
                before = settle(label)
                driver.execute_script("document.querySelector('#other').focus()")
                away = settle(label)
                driver.execute_script("editor.focus()")
                back = settle(label)
                for layer in ("monaco", "monaco-text", "adapter"):
                    check(callback(delta(before, away), layer, "blur") and callback(delta(away, back), layer, "focus"), label + " ordinary field focus preserved " + layer, delta(before, back))
                before = back
                driver.execute_script("document.activeElement.blur()")
                away = settle(label)
                driver.execute_script("editor.focus()")
                back = settle(label)
                for layer in ("monaco", "monaco-text", "adapter"):
                    check(callback(delta(before, away), layer, "blur") and callback(delta(away, back), layer, "focus"), label + " explicit blur/focus preserved " + layer, delta(before, back))
                driver.find_element(By.CSS_SELECTOR, ".monaco-editor textarea").send_keys("abc")
                typed = settle(label)
                check(typed["value"] == "abc" and callback(delta(back, typed), "adapter", "change"), label + " typing and adapter model updates preserved", typed)
                check(not typed["errors"] and not callback(typed["events"], "adapter", "error"), label + " no editor/adapter errors", typed["errors"])
    finally:
        if driver:
            driver.quit()
        server.shutdown()
        report = {"versions": versions, "headful": bool(os.environ.get("CLOAKFOX_HEADFUL")), "binary": os.environ["CLOAKFOX_BIN"], "checks": checks, "observations": observations}
        Path(os.environ.get("MONACO_PROBE_REPORT", "/tmp/cloakfox-monaco-focus-results.json")).write_text(json.dumps(report, indent=2))
    failed = [c for c in checks if not c["pass"]]
    print(f"{len(checks)-len(failed)}/{len(checks)} checks passed", flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
