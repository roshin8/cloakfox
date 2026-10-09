#!/usr/bin/env python3
"""Exercise window/tab activity masking against real browser transitions.

Uses disposable profiles and local pages, including same- and cross-origin
frames. Background pages report to the HTTP server: selecting them to read
their state would accidentally refocus them and invalidate the test.

Run: CLOAKFOX_BIN=/path/to/cloakfox python tests/fingerprint/probe_focus_masking.py
Set CLOAKFOX_HEADFUL=1 to also exercise native window activation on a desktop.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

PREF = "cloakfox.opt.focus_masking"

PAGE = """<!doctype html><meta charset=utf-8>
<style>html{--inactive:0}html:-moz-window-inactive{--inactive:1}</style>
<input id=a><input id=b><div id=editor contenteditable=true></div>
<button id=fullscreen>Enter fullscreen</button><div id=shadowhost></div>
<script>
const label = new URLSearchParams(location.search).get('label');
const events = [];
const initial = {focused:document.hasFocus(),hidden:document.hidden,visibility:document.visibilityState};
const shadow = document.querySelector('#shadowhost').attachShadow({mode:'open'});
shadow.innerHTML = '<div id="fullscreenTarget" tabindex="0">Fullscreen target</div>';
let fullscreenResult = 'idle';
document.querySelector('#fullscreen').onclick = async () => {
  try {await shadow.firstElementChild.requestFullscreen(); fullscreenResult = 'resolved'}
  catch(e){fullscreenResult = e.name}
};
for (const type of ['fullscreenchange','mozfullscreenchange','fullscreenerror']) {
  document.addEventListener(type, e => {if(e.isTrusted) events.push({type,target:'document'})});
}
let raf = 0, timers = 0, workerTicks = 0;
const worker = new Worker('/worker');
worker.onmessage = () => workerTicks++;
for (const type of ['focus','blur','focusin','focusout']) {
  window.addEventListener(type, e => {
    if (e.isTrusted) events.push({type, target:e.target === window ? 'window' :
      e.target === document ? 'document' : e.target.id || e.target.tagName,
      active:document.activeElement?.id || document.activeElement?.tagName});
  }, true);
}
document.addEventListener('visibilitychange', e => {
  if (e.isTrusted) events.push({type:e.type,target:'document'});
});
function frame(){raf++;requestAnimationFrame(frame)}
requestAnimationFrame(frame);
setInterval(() => timers++, 20);
setInterval(async () => {
  const command = await (await fetch('/command?label=' + label)).json();
  if (command === 'b') document.querySelector('#b').focus();
  if (command === 'blur') document.activeElement.blur();
  if (command === 'a') document.querySelector('#a').focus();
  if (command === 'reentrant-focus') {
    const b = document.querySelector('#b');
    b.addEventListener('focus', () => document.querySelector('#editor').focus(), {once:true});
    b.focus();
  }
  if (command === 'removed') {
    const c = document.createElement('input'); c.id = 'removed-target'; document.body.appendChild(c);
    const b = document.querySelector('#b'); b.focus();
    b.addEventListener('blur', () => c.remove(), {once:true}); c.focus();
  }
  if (command === 'reentrant') {
    const b = document.querySelector('#b'); b.focus();
    b.addEventListener('blur', () => document.querySelector('#editor').focus(), {once:true});
    document.querySelector('#a').focus();
  }
}, 50);
setInterval(() => fetch('/record', {method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({label,initial,focused:document.hasFocus(),hidden:document.hidden,
    visibility:document.visibilityState,active:document.activeElement?.id,
    cssFocus:document.querySelector('#a').matches(':focus'),
    cssFocusB:document.querySelector('#b').matches(':focus'),
    cssFocusWithin:document.documentElement.matches(':focus-within'),
    fullscreenPosition:getComputedStyle(shadow.firstElementChild).position,
    inactive:getComputedStyle(document.documentElement).getPropertyValue('--inactive').trim(),
    fullscreen:document.fullscreen,mozFullScreen:document.mozFullScreen,
    fullscreenElement:document.fullscreenElement ? (document.fullscreenElement.id || document.fullscreenElement.tagName) : null,
    mozFullScreenElement:document.mozFullScreenElement ? (document.mozFullScreenElement.id || document.mozFullScreenElement.tagName) : null,
    shadowFullscreen:shadow.fullscreenElement?.id ?? null,
    windowFullScreen:window.fullScreen,
    cssFullscreen:shadow.firstElementChild.matches(':fullscreen'),fullscreenResult,
    cssDocumentFullscreen:document.documentElement.matches(':fullscreen'),
    raf,timers,workerTicks,events})}), 100);
if (label === 'top') {
  for (const name of ['same','cross']) {
    const frame = document.createElement('iframe'); frame.id = name;
    const url = new URL(location.href); url.searchParams.set('label', name);
    if (name === 'cross') url.hostname = 'localhost';
    frame.src = url; document.body.appendChild(frame);
  }
}
</script>"""


class Page(BaseHTTPRequestHandler):
    records = {}
    commands = {}
    lock = threading.Lock()

    def do_GET(self):
        if urlparse(self.path).path == "/command":
            label = parse_qs(urlparse(self.path).query)["label"][0]
            with self.lock:
                body = json.dumps(self.commands.pop(label, None)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = (b"setInterval(() => postMessage('tick'),20);"
                if urlparse(self.path).path == "/worker" else PAGE.encode())
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript" if self.path == "/worker"
                         else "text/html; charset=utf-8")
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


def snapshot(label, after=0):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with Page.lock:
            record = Page.records.get(label)
        if record and record[0] > after:
            return record[1]
        time.sleep(0.05)
    raise AssertionError(f"No fresh report from {label}")


def await_snapshot(label, predicate, after=0):
    deadline = time.monotonic() + 8
    data = snapshot(label, after)
    while not predicate(data) and time.monotonic() < deadline:
        data = snapshot(label, time.monotonic())
    return data


def chrome(driver, script, *args):
    driver.set_context("chrome")
    try:
        return driver.execute_script(script, *args)
    finally:
        driver.set_context("content")


def set_pref(driver, name, value):
    chrome(driver, "Services.prefs.setBoolPref(arguments[0],arguments[1]);", name, value)


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    gecko = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert gecko, "Install geckodriver or set GECKODRIVER"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    failures = []

    def check(ok, description, data):
        if not ok:
            failures.append(f"{description}: {json.dumps(data)}")
            print("FAIL — " + failures[-1], flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-focus-probe-") as temp:
            opts = Options()
            opts.binary_location = binary
            if not os.environ.get("CLOAKFOX_HEADFUL"):
                opts.add_argument("-headless")
            else:
                # Exercise DOM fullscreen without an OS widget transition.
                # This is Gecko's fullscreen test mode: requests still require
                # trusted activation and run the native DOM/permission path.
                # Native window activation/minimization are tested separately.
                opts.set_preference("full-screen-api.ignore-widgets", True)
            opts.set_preference("cloakfox.enabled", True)
            # Shorten only the time until throttling starts; keep actual
            # background timer/rAF policies at their shipped values.
            opts.set_preference("dom.timeout.throttling_delay", 100)
            driver = webdriver.Firefox(options=opts, service=Service(
                executable_path=gecko, service_args=["--allow-system-access"],
                log_output=os.path.join(temp, "geckodriver.log")))
            try:
                check(chrome(driver, "return Services.appinfo.name") == "Cloakfox",
                      "Cloakfox binary launched", driver.capabilities)
                check(chrome(driver, "return Services.prefs.getBoolPref(arguments[0],false)", PREF)
                      is False, "mask is opt-in", {})
                driver.get("about:cloakfox")
                toggle = WebDriverWait(driver, 8).until(lambda d: d.find_element(
                    By.CSS_SELECTOR, f'input[data-pref="{PREF}"]'))
                check(not toggle.is_selected(), "settings checkbox is off by default", {})
                # Exercise the settings change handler directly; headful
                # automation can use spoofed geometry for click scrolling.
                driver.execute_script("arguments[0].click()", toggle)
                check(chrome(driver, "return Services.prefs.getBoolPref(arguments[0])", PREF),
                      "settings checkbox enables native pref", {})
                driver.get(f"http://127.0.0.1:{server.server_port}/?label=top")
                for label in ("top", "same", "cross"):
                    data = snapshot(label)
                    check(data["focused"] and not data["hidden"] and data["visibility"] == "visible",
                          f"masked foreground API agreement ({label})", data)
                chrome(driver, "gBrowser.addTab(arguments[0], {triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});",
                       f"http://127.0.0.1:{server.server_port}/?label=born-background")
                before = snapshot("born-background")
                time.sleep(1)
                data = snapshot("born-background", time.monotonic())
                check(data["initial"]["focused"] and not data["initial"]["hidden"] and
                      data["initial"]["visibility"] == "visible" and
                      data["raf"] - before["raf"] > 10 and
                      data["workerTicks"] - before["workerTicks"] > 10,
                      "background-created page is masked from parser-time through worker scheduling", data)
                a, b = driver.find_element(By.ID, "a"), driver.find_element(By.ID, "b")
                a.click()
                a.send_keys("alpha")
                b.click()
                b.send_keys("beta")
                data = snapshot("top", time.monotonic())
                for event in (("blur", "a"), ("focusout", "a"), ("focus", "b"), ("focusin", "b")):
                    check(any((e["type"], e["target"]) == event for e in data["events"]),
                          f"ordinary element event {event} survives", data)
                check(a.get_attribute("value") == "alpha" and b.get_attribute("value") == "beta",
                      "typing and field switching work", data)
                a.click()
                baseline = {label: snapshot(label, time.monotonic()) for label in ("top", "same", "cross")}
                chrome(driver, """
                  window.__focusProbeTab = gBrowser.selectedTab;
                  window.__focusProbeOther = gBrowser.addTab(arguments[0], {
                    triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                  gBrowser.selectedTab = window.__focusProbeOther;
                """, f"http://127.0.0.1:{server.server_port}/?label=other")
                WebDriverWait(driver, 8).until(lambda _: bool(Page.records.get("other")))
                started = time.monotonic()
                time.sleep(2)
                for label, before in baseline.items():
                    data = snapshot(label, started + 1)
                    new_events = data["events"][len(before["events"]):]
                    check(data["focused"] and not data["hidden"] and data["visibility"] == "visible",
                          f"background APIs stay masked ({label})", data)
                    check(not new_events, f"background transition events stay private ({label})", new_events)
                    check(data["raf"] - before["raf"] > 15,
                          f"background animation callbacks continue ({label})", data)
                    check(data["timers"] - before["timers"] > 15,
                          f"background timers continue ({label})", data)
                    check(data["workerTicks"] - before["workerTicks"] > 15,
                          f"background worker timers continue ({label})", data)
                    if label == "top":
                        check(data["active"] == "a" and data["cssFocus"] and data["inactive"] == "0",
                              "logical focused element and CSS stay consistent", data)
                # Let the background page change focus itself, without a
                # WebDriver command that might activate its browsing context.
                for command in ("b", "blur", "a"):
                    before_events = snapshot("top", time.monotonic())["events"]
                    with Page.lock:
                        Page.commands["top"] = command
                    time.sleep(0.3)
                    data = snapshot("top", time.monotonic())
                    check((data["active"] == command and
                           data["cssFocus"] == (command == "a") and
                           data["cssFocusB"] == (command == "b")) if command != "blur"
                          else not data["cssFocus"] and not data["cssFocusB"] and
                          not data["cssFocusWithin"],
                          f"background scripted {command} keeps activeElement/CSS consistent", data)
                    expected = (("focus", "b"), ("focusin", "b")) if command == "b" else (
                        (("blur", "b"), ("focusout", "b")) if command == "blur" else
                        (("focus", "a"), ("focusin", "a")))
                    fresh = data["events"][len(before_events):]
                    check(all(e.get("active") == "BODY" for e in fresh if e["type"] == "blur"),
                          f"background scripted {command} blur sees cleared activeElement", fresh)
                    check(all(any((e["type"], e["target"]) == pair for e in fresh) for pair in expected),
                          f"background scripted {command} retains ordinary trusted element events", fresh)
                with Page.lock:
                    Page.commands["top"] = "reentrant"
                time.sleep(0.3)
                data = snapshot("top", time.monotonic())
                check(data["active"] == "editor" and not data["cssFocus"] and not data["cssFocusB"],
                      "background blur handler can redirect focus without being overwritten", data)
                with Page.lock:
                    Page.commands["top"] = "a"
                time.sleep(0.3)

                for command in ("reentrant-focus", "removed"):
                    before_events = snapshot("top", time.monotonic())["events"]
                    with Page.lock:
                        Page.commands["top"] = command
                    time.sleep(0.3)
                    data = snapshot("top", time.monotonic())
                    fresh = data["events"][len(before_events):]
                    if command == "reentrant-focus":
                        check(data["active"] == "editor" and not any(
                              e["type"] == "focusin" and e["target"] == "b" for e in fresh),
                              "redirected background focus skips obsolete focusin", data)
                    else:
                        check(not any(e["type"] in ("focus", "focusin") and
                              e["target"] == "removed-target" for e in fresh),
                              "blur handler removing target prevents detached focus events", fresh)
                    with Page.lock:
                        Page.commands["top"] = "a"
                    time.sleep(0.3)
                for label in ("same", "cross"):
                    old_parent = snapshot("top", time.monotonic())
                    with Page.lock:
                        Page.commands[label] = "a"
                    time.sleep(0.3)
                    parent = snapshot("top", time.monotonic())
                    child = snapshot(label, time.monotonic())
                    check(parent["active"] == label and not parent["cssFocus"] and child["cssFocus"],
                          f"background focus into {label} frame clears parent field state", [parent, child])
                    check(any(e["type"] == "blur" and e["target"] == "a"
                              for e in parent["events"][len(old_parent["events"]):]),
                          f"focus into {label} frame dispatches actual parent field blur", parent)
                    old_child = child
                    with Page.lock:
                        Page.commands["top"] = "a"
                    time.sleep(0.3)
                    child = snapshot(label, time.monotonic())
                    check(not child["cssFocus"] and not child["cssFocusB"],
                          f"background focus out of {label} frame clears descendant state", child)
                    check(any(e["type"] == "blur" and e["target"] == "a"
                              for e in child["events"][len(old_child["events"]):]),
                          f"focus out of {label} frame dispatches actual child field blur", child)
                for label in ("same", "cross"):
                    with Page.lock:
                        Page.commands[label] = "a"
                    time.sleep(0.3)
                with Page.lock:
                    Page.commands["same"] = "blur"
                time.sleep(0.3)
                parent = snapshot("top", time.monotonic())
                child = snapshot("cross", time.monotonic())
                check(parent["active"] == "cross" and child["cssFocus"],
                      "blurring an abandoned sibling preserves current frame focus", [parent, child])
                with Page.lock:
                    Page.commands["top"] = "a"
                time.sleep(0.3)
                # Live changes while the target page remains backgrounded.
                for name in (PREF, "cloakfox.enabled"):
                    set_pref(driver, name, False)
                    changed = time.monotonic()
                    data = await_snapshot("top", lambda d: d["hidden"] and not d["focused"] and
                                          not d["cssFocus"], changed)
                    check(data["hidden"] and data["visibility"] == "hidden" and not data["focused"] and
                          not data["cssFocus"],
                          f"{name}=false restores native background APIs", data)
                    set_pref(driver, name, True)
                    changed = time.monotonic()
                    before = await_snapshot("top", lambda d: d["focused"] and not d["hidden"], changed)
                    for label in ("same", "cross"):
                        child = snapshot(label, changed)
                        check(not child["cssFocus"] and not child["cssFocusB"],
                              f"{name}=true doesn't resurrect abandoned {label} focus", child)
                    time.sleep(1)
                    data = snapshot("top", changed + 0.8)
                    check(data["focused"] and not data["hidden"] and data["raf"] - before["raf"] > 10,
                          f"{name}=true resumes masking and background animation", data)
                before = snapshot("top", time.monotonic())
                chrome(driver, "gBrowser.selectedTab = window.__focusProbeTab")
                data = snapshot("top", time.monotonic())
                check(not data["events"][len(before["events"]):],
                      "returning to the page doesn't leak reactivation events", data)
                # A real second window exercises activation separately from
                # tab visibility. No synthetic focus events are used.
                if os.environ.get("CLOAKFOX_HEADFUL"):
                    target = driver.current_window_handle
                    before = snapshot("top", time.monotonic())
                    handles = set(driver.window_handles)
                    # Marionette's new-window endpoint hardcodes the Firefox
                    # application name. Use the native chrome entry point in
                    # this branded fork, then attach to its real window.
                    chrome(driver, "window.__focusProbeSecondWindow = OpenBrowserWindow();")
                    WebDriverWait(driver, 10).until(lambda d: set(d.window_handles) - handles)
                    driver.switch_to.window(next(iter(set(driver.window_handles) - handles)))
                    driver.get(f"http://127.0.0.1:{server.server_port}/?label=window")
                    data = snapshot("top", time.monotonic())
                    check(data["focused"] and data["inactive"] == "0" and
                          not data["events"][len(before["events"]):],
                          "native window deactivation is masked", data)
                    driver.close()
                    driver.switch_to.window(target)
                    driver.find_element(By.ID, "a").send_keys(" resumed")
                    check(driver.find_element(By.ID, "a").get_attribute("value") == "alpha resumed",
                          "typing resumes after native window activation", {})
                    chrome(driver, "window.focus(); gBrowser.selectedBrowser.focus();")
                    before = snapshot("top", time.monotonic())
                    driver.find_element(By.ID, "fullscreen").click()
                    WebDriverWait(driver, 10).until(lambda _: snapshot("top")["fullscreenResult"] != "idle")
                    data = snapshot("top", time.monotonic())
                    check(data["fullscreenResult"] == "resolved", "native fullscreen request succeeds", data)
                    check(chrome(driver, "return window.fullScreen"),
                          "browser chrome retains real fullscreen state", {})
                    def masked_fullscreen(data):
                        return data["fullscreen"] and data["mozFullScreen"] and data["windowFullScreen"]
                    check(masked_fullscreen(data) and data["fullscreenElement"] == "shadowhost" and
                          data["mozFullScreenElement"] == "shadowhost" and
                          data["shadowFullscreen"] == "fullscreenTarget" and data["cssFullscreen"],
                          "real fullscreen getters, aliases, shadow root and CSS agree", data)
                    check(data["fullscreenPosition"] == "fixed", "native fullscreen layout survives masking", data)
                    check(not any(e["type"] in ("fullscreenchange", "mozfullscreenchange")
                                  for e in data["events"][len(before["events"]):]),
                          "fullscreen entry events stay private", data)
                    set_pref(driver, PREF, False)
                    data = await_snapshot("top", lambda d: d["fullscreen"] and d["cssFullscreen"],
                                          time.monotonic())
                    check(data["fullscreen"] and
                          data["fullscreenElement"] == "shadowhost" and
                          data["shadowFullscreen"] == "fullscreenTarget" and data["cssFullscreen"],
                          "disabling restores native fullscreen getters and CSS", data)
                    set_pref(driver, PREF, True)
                    before = snapshot("top", time.monotonic())
                    driver.execute_async_script("document.exitFullscreen().then(arguments[0]);")
                    data = snapshot("top", time.monotonic())
                    check(masked_fullscreen(data) and data["fullscreenElement"] == "HTML" and
                          data["mozFullScreenElement"] == "HTML" and data["shadowFullscreen"] is None and
                          data["cssDocumentFullscreen"] and not data["cssFullscreen"] and
                          not any(e["type"] == "fullscreenchange"
                          for e in data["events"][len(before["events"]):]),
                          "native fullscreen exit succeeds without exposing a transition", data)
                    before = snapshot("top", time.monotonic())
                    driver.minimize_window()
                    data = snapshot("top", time.monotonic())
                    check(data["focused"] and not data["hidden"] and data["inactive"] == "0" and
                          not data["events"][len(before["events"]):],
                          "minimized window remains logically focused and visible", data)
                    chrome(driver, "gBrowser.selectedTab = window.__focusProbeTab; window.restore(); window.focus(); gBrowser.selectedBrowser.focus();")
                    WebDriverWait(driver, 8).until(lambda _: chrome(driver,
                        "return window.windowState !== window.STATE_MINIMIZED"))
                for name in (PREF, "cloakfox.enabled"):
                    set_pref(driver, name, False)
                    driver.find_element(By.ID, "a").click()
                    before = snapshot("top", time.monotonic())
                    chrome(driver, "gBrowser.selectedTab = window.__focusProbeOther")
                    data = await_snapshot("top", lambda d: d["hidden"] and not d["focused"],
                                          time.monotonic())
                    fresh = data["events"][len(before["events"]):]
                    check(data["hidden"] and not data["focused"] and
                          any(e["type"] == "visibilitychange" for e in fresh) and
                          any(e["type"] == "blur" and e["target"] == "a" for e in fresh),
                          f"{name}=false restores native transition events", data)
                    chrome(driver, "gBrowser.selectedTab = window.__focusProbeTab")
                    snapshot("top", time.monotonic())
                    set_pref(driver, name, True)
                print("Native window activation: " + ("exercised" if os.environ.get("CLOAKFOX_HEADFUL")
                                                       else "not exercised (set CLOAKFOX_HEADFUL=1)"))
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()
    if failures:
        return 1
    print("PASS — focus/visibility masking, native element focus, frames, scheduling and live switches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
