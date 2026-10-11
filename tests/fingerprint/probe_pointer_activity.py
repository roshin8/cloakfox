#!/usr/bin/env python3
"""Headful native pointer departures, frame transitions and IdleDetector exposure.

Run with CLOAKFOX_BIN pointing to a rebuilt app. Native moves use Gecko's
privileged test API; page observations arrive over HTTP without refocusing it.
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

from probe_focus_masking import chrome, set_pref

PREF = "cloakfox.opt.focus_masking"
PAGE = """<!doctype html><meta charset=utf-8>
<style>body{margin:0}#a,#b{position:absolute;top:60px;width:90px;height:70px}
#a{left:30px;background:coral}#b{left:150px;background:skyblue}
iframe{position:absolute;top:200px;width:270px;height:330px;border:0}
#same{left:20px}#cross{left:350px}#a:hover,#b:hover{outline:3px solid rgb(1,2,3)}</style><div id=a>A</div><div id=b>B</div>
<script>
const label=new URLSearchParams(location.search).get('label'), events=[];
for(const type of ['mouseout','mouseleave','mouseover','mouseenter',
                   'pointerout','pointerleave','pointerover','pointerenter',
                   'pointerdown','pointerup','click','gotpointercapture','lostpointercapture']) {
  window.addEventListener(type,e=>events.push({type,target:e.target.id||e.target.nodeName,
    related:e.relatedTarget?.id||e.relatedTarget?.nodeName||null,trusted:e.isTrusted}),true);
}
const host=document.createElement('div');host.id='menu';
Object.assign(host.style,{position:'absolute',left:'300px',top:'60px',width:'90px',height:'70px'});
document.body.append(host);const shadow=host.attachShadow({mode:'open'});
shadow.innerHTML='<style>#control{height:70px;background:plum}#submenu{display:none}#control:hover #submenu{display:block}</style><div id=control>Menu<div id=submenu>Open</div></div>';
const worker=new Worker('/worker');let workerIdle=null;
worker.onmessage=e=>workerIdle=e.data;
setInterval(()=>fetch('/record',{method:'POST',body:JSON.stringify({label,events,
  idle:typeof IdleDetector,workerIdle,hoverA:document.querySelector('#a').matches(':hover'),
  hover:Array.from(document.querySelectorAll(':hover'),e=>e.id||e.nodeName),
  outlineB:getComputedStyle(document.querySelector('#b')).outlineStyle,
  outlineA:getComputedStyle(document.querySelector('#a')).outlineStyle,
  shadowHover:shadow.querySelector('#control').matches(':hover'),
  menuVisible:getComputedStyle(shadow.querySelector('#submenu')).display==='block'})}),100);
if(label==='top')for(const name of ['same','cross']) {
  const f=document.createElement('iframe');f.id=name;
  const u=new URL(location.href);u.searchParams.set('label',name);
  if(name==='cross')u.hostname='localhost';f.src=u;document.body.append(f);
}
if(label==='cross') {
  const f=document.createElement('iframe');f.id='nested';f.style.left='20px';
  const u=new URL(location.href);u.searchParams.set('label','nested');u.hostname='127.0.0.1';
  f.src=u;document.body.append(f);
}
</script>"""


class Page(BaseHTTPRequestHandler):
    records = {}
    lock = threading.Lock()

    def do_GET(self):
        body = (b"postMessage(typeof IdleDetector)" if self.path == "/worker"
                else PAGE.encode())
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript" if self.path == "/worker" else "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.lock:
            self.records[data["label"]] = (time.monotonic(), data)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def snapshot(label):
    after = time.monotonic()
    deadline = after + 8
    while time.monotonic() < deadline:
        with Page.lock:
            record = Page.records.get(label)
        if record and record[0] > after:
            return record[1]
        time.sleep(.025)
    raise AssertionError(f"No fresh report: {label}")


def native_move(driver, x, y, toolbar=False, message="MOVE"):
    widget_input = os.environ.get("POINTER_PROBE_INPUT") == "widget"
    driver.set_context("chrome")
    try:
        # macOS warps the cursor and dispatches a native move independently.
        # The first move into an OOP descendant can finish with a stale APZ
        # ancestor exit. A second move at the same position settles the actual
        # hover target. Never repeat presses/releases or fabricate DOM events.
        for attempt in range(2 if message == "MOVE" and not widget_input else 1):
            if attempt:
                time.sleep(.12)
            geometry = driver.execute_async_script("""
          const [x,y,toolbar,message,widget,done]=arguments,b=gBrowser.selectedBrowser;
          const r=b.getBoundingClientRect(),u=window.windowUtils;
          const scale=window.devicePixelRatio;
          if(!Number.isFinite(scale)||scale<=0)throw new Error("Invalid native pixel scale");
          if(widget) {
            const type={MOVE:'mousemove',BUTTON_DOWN:'mousedown',BUTTON_UP:'mouseup'}[message];
            window.synthesizeMouseEvent(type,r.left+x,r.top+(toolbar?-20:y),
              {button:0,clickCount:1,inputSource:1},
              {isDOMEventSynthesized:true,isWidgetEventSynthesized:false,isAsyncEnabled:true});
            done({input:'Gecko widget',left:r.left,top:r.top});return;
          }
          const screen=u.toScreenRect(r.left+x,r.top+(toolbar?-20:y),1,1);
          const sx=screen.x,sy=screen.y;
          u.sendNativeMouseEvent(Math.round(sx),Math.round(sy),
            u["NATIVE_MOUSE_MESSAGE_"+message],0,0,b,{onCompleteDispatch(){done({sx,sy,scale,left:r.left,top:r.top,width:r.width,height:r.height})}});
        """, x, y, toolbar, message, widget_input)
    finally:
        driver.set_context("content")
    if os.environ.get("POINTER_PROBE_DEBUG"):
        print("Native position", geometry, flush=True)
    time.sleep(.35)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks = []
    input_mode = "Gecko widget/APZ" if os.environ.get("POINTER_PROBE_INPUT") == "widget" else "desktop native"

    def check(ok, name, data=None):
        checks.append({"name": name, "pass": bool(ok), "data": data, "inputMode": input_mode})
        print(("PASS" if ok else "FAIL") + " — " + name, flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-pointer-") as temp:
            opts = Options()
            opts.binary_location = os.environ["CLOAKFOX_BIN"]
            if os.environ.get("POINTER_PROBE_INPUT") == "widget":
                opts.add_argument("-headless")
            opts.set_preference("cloakfox.enabled", True)
            driver = webdriver.Firefox(options=opts, service=Service(
                executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
                service_args=["--allow-system-access"], log_output=temp + "/gecko.log"))
            try:
                driver.set_window_size(1280, 1000)
                driver.get(f"http://127.0.0.1:{server.server_port}/?label=top")
                chrome(driver, "window.focus(); gBrowser.selectedBrowser.focus();")
                for label in ("top", "same", "cross", "nested"):
                    d = snapshot(label)
                    check(d["idle"] == "undefined" and d["workerIdle"] == "undefined",
                          f"IdleDetector absent in page and worker ({label})", d)
                for masked, master in ((False, True), (True, True), (True, False)):
                    set_pref(driver, "cloakfox.enabled", master)
                    set_pref(driver, PREF, masked)
                    enabled = masked and master
                    mode = f"option={masked},master={master}"
                    for label in ("top", "same", "cross", "nested"):
                        d = snapshot(label)
                        check(d["idle"] == "undefined" and d["workerIdle"] == "undefined",
                              f"IdleDetector remains absent ({label}, {mode})", d)
                    native_move(driver, 60, 85)
                    before = snapshot("top")["events"]
                    native_move(driver, 180, 85)
                    fresh = snapshot("top")["events"][len(before):]
                    check(all(any(e["type"] == t and e["target"] == "a" for e in fresh)
                              for t in ("mouseout", "mouseleave", "pointerout", "pointerleave")),
                          f"in-page mouse/pointer transitions survive ({mode})", fresh)
                    for label, x, y in (("top", 180, 85), ("same", 80, 285), ("cross", 410, 285), ("nested", 430, 485)):
                        native_move(driver, x, y)
                        hover_before = snapshot(label)["hover"]
                        check(("b" if label == "top" else "a") in hover_before,
                              f"trusted input reaches intended hover target ({label}, {mode})", hover_before)
                        before = snapshot(label)["events"]
                        parent_before = snapshot("top")["events"] if label != "top" else before
                        native_move(driver, 80, 0, toolbar=True)
                        departed_state = snapshot(label)
                        departed = departed_state["events"][len(before):]
                        check(departed_state["hover"] == hover_before if enabled else not departed_state["hover"],
                              f"CSS hover {'retained' if enabled else 'cleared'} on departure ({label}, {mode})", departed_state["hover"])
                        check(departed_state["outlineB" if label == "top" else "outlineA"] == ("solid" if enabled else "none"),
                              f"CSS hover styling follows departure policy ({label}, {mode})", departed_state)
                        parent_departed = snapshot("top")["events"][len(parent_before):]
                        native_move(driver, x, y)
                        returned_state = snapshot(label)
                        returned = returned_state["events"][len(before)+len(departed):]
                        check(returned_state["hover"] == hover_before,
                              f"CSS hover restored on return ({label}, {mode})", returned_state["hover"])
                        parent_returned = snapshot("top")["events"][len(parent_before)+len(parent_departed):]
                        if label != "top":
                            # Parent boundary mirroring can arrive after the child's
                            # report. An event with a related element in this page
                            # describes a normal frame transition, not departure.
                            private_departures = [e for e in parent_departed if e["related"] is None]
                            private_returns = [e for e in parent_returned if e["related"] is None]
                            check(not private_departures if enabled else any(e["type"] == "mouseout" for e in private_departures),
                                  f"parent departure {'private' if enabled else 'observable'} while inside {label} ({mode})",
                                  parent_departed)
                            check(not private_returns if enabled else any(e["type"] == "mouseover" for e in private_returns),
                                  f"parent return {'private' if enabled else 'observable'} into {label} ({mode})",
                                  parent_returned)
                        leave_types = {e["type"] for e in departed if e["trusted"]}
                        enter_types = {e["type"] for e in returned if e["trusted"]}
                        check(not leave_types if enabled else
                              {"mouseout", "mouseleave", "pointerout", "pointerleave"} <= leave_types,
                              f"native departure {'private' if enabled else 'observable'} ({label}, {mode})",
                              departed)
                        check(not enter_types if enabled else
                              {"mouseover", "mouseenter", "pointerover", "pointerenter"} <= enter_types,
                              f"native return {'private' if enabled else 'observable'} ({label}, {mode})",
                              returned)
                    # APZ routes pointer input directly to the deepest OOP
                    # frame. Its ancestor may only receive mirrored mouse
                    # events, so test each frame while it owns the pointer.
                    nested_before = snapshot("nested")["events"]
                    parent_before = snapshot("top")["events"]
                    native_move(driver, 180, 85)
                    nested_fresh = snapshot("nested")["events"][len(nested_before):]
                    check(any(e["type"] == "pointerleave" for e in nested_fresh),
                          f"nested iframe-to-parent transition survives ({mode})", nested_fresh)
                    fresh_parent = snapshot("top")["events"][len(parent_before):]
                    check(any(e["type"] == "pointerenter" and e["target"] == "b" for e in fresh_parent),
                          f"parent receives iframe-to-element entry ({mode})", fresh_parent)
                    native_move(driver, 410, 285)
                    before = snapshot("cross")["events"]
                    native_move(driver, 180, 85)
                    fresh = snapshot("cross")["events"][len(before):]
                    check(any(e["type"] == "pointerleave" for e in fresh),
                          f"iframe-to-parent transition survives ({mode})", fresh)
                    # Return elsewhere: the departed frame must stop matching :hover.
                    for departed_label, x, y in (("same",80,285),("cross",410,285),("nested",430,485)):
                        native_move(driver, x, y)
                        native_move(driver, 80, 0, toolbar=True)
                        native_move(driver, 180, 85)
                        departed_hover = snapshot(departed_label)["hover"]
                        check(not departed_hover and "b" in snapshot("top")["hover"],
                              f"return elsewhere reconciles {departed_label} hover ({mode})", departed_hover)
                    native_move(driver, 330, 85)
                    d = snapshot("top")
                    check(d["shadowHover"] and d["menuVisible"], f"shadow hover opens menu ({mode})", d)
                    native_move(driver, 80, 0, toolbar=True)
                    d = snapshot("top")
                    check(d["shadowHover"] == enabled and d["menuVisible"] == enabled,
                          f"shadow hover follows departure policy ({mode})", d)
                    native_move(driver, 330, 85)
                    d = snapshot("top")
                    check(d["shadowHover"] and d["menuVisible"], f"shadow menu works after return ({mode})", d)
                    native_move(driver, 60, 85)
                    d = snapshot("top")
                    check(not d["shadowHover"] and not d["menuVisible"], f"normal movement closes shadow menu ({mode})", d)
                set_pref(driver, "cloakfox.enabled", True)
                set_pref(driver, PREF, True)
                for switch in (PREF, "cloakfox.enabled"):
                    native_move(driver, 180, 85)
                    native_move(driver, 80, 0, toolbar=True)
                    check("b" in snapshot("top")["hover"], "hover retained before live switch " + switch)
                    set_pref(driver, switch, False)
                    check(not snapshot("top")["hover"], "live switch clears retained hover " + switch)
                    set_pref(driver, switch, True)
                native_move(driver, 60, 85)
                driver.execute_script("document.querySelector('#a').addEventListener('pointerdown',e=>e.target.setPointerCapture(e.pointerId))")
                before = snapshot("top")["events"]
                native_move(driver, 60, 85, message="BUTTON_DOWN")
                native_move(driver, 180, 85)
                native_move(driver, 180, 85, message="BUTTON_UP")
                fresh = snapshot("top")["events"][len(before):]
                check(all(any(e["type"] == t and e["target"] == "a" for e in fresh)
                          for t in ("pointerdown", "pointerup", "gotpointercapture", "lostpointercapture")),
                      "native pointer capture, drag and release survive masking", fresh)
                before = snapshot("top")["events"]
                driver.execute_script("document.querySelector('#a').dispatchEvent(new PointerEvent('pointerleave'))")
                fresh = snapshot("top")["events"][len(before):]
                check(any(e["type"] == "pointerleave" and not e["trusted"] for e in fresh),
                      "script-dispatched boundary events remain unchanged", fresh)
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()
    report = os.environ.get("POINTER_PROBE_REPORT", "/tmp/cloakfox-pointer-activity-results.json")
    with open(report, "w") as f:
        json.dump(checks, f, indent=2)
    print(f"{sum(c['pass'] for c in checks)}/{len(checks)} checks passed; {report}")
    return 0 if all(c["pass"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
