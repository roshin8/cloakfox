#!/usr/bin/env python3
"""Live geometry regression: frozen chrome, stale persona sizes and scroll offsets.

Run with CLOAKFOX_BIN and optionally GECKODRIVER (must be an explicit executable).
Uses a disposable profile and a local HTTP server; never changes an installed app.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'''<!doctype html><style>
          html { scrollbar-width:none } body { margin:0; height:4000px }
          iframe { width:320px; height:240px; border:0 }
        </style><a href="/next">Next</a><iframe src="/frame"></iframe>'''
        if self.path == "/frame":
            body = b'<!doctype html><style>body{margin:0}</style>frame'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


READ = """
return {inner:[innerWidth,innerHeight], outer:[outerWidth,outerHeight],
  client:[document.documentElement.clientWidth,document.documentElement.clientHeight],
  body:document.body.clientWidth, visual:[visualViewport.width,visualViewport.height],
  screen:[screen.width,screen.height], avail:[screen.availWidth,screen.availHeight],
  origin:[screenX,screenY,mozInnerScreenX,mozInnerScreenY,screen.availLeft,screen.availTop],
  media:matchMedia(`(width: ${innerWidth}px) and (height: ${innerHeight}px)`).matches,
  deviceMedia:matchMedia(`(device-width: ${screen.width}px) and (device-height: ${screen.height}px)`).matches,
  dprMedia:matchMedia(`(resolution: ${devicePixelRatio}dppx)`).matches,
  orientation:screen.orientation.type, legacyOrientation:screen.mozOrientation,
  scroll:scrollY, visualScroll:visualViewport.pageTop};
"""


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    gecko = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert gecko, "Install geckodriver or set GECKODRIVER"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    failures = []

    def check(condition, label, data):
        if not condition:
            failures.append(f"{label}: {data}")

    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-letterbox-probe-") as temp:
            opts = Options()
            opts.binary_location = binary
            opts.add_argument("-headless")
            opts.set_preference("cloakfox.enabled", True)
            opts.set_preference("privacy.resistFingerprinting", False)
            # Do not set the letterboxing pref: also test the shipped default.
            driver = webdriver.Firefox(options=opts, service=Service(
                executable_path=gecko, service_args=["--allow-system-access"],
                log_output=os.path.join(temp, "geckodriver.log")))
            try:
                driver.set_context("chrome")
                identity = driver.execute_script("return Services.appinfo.name")
                assert identity == "Cloakfox", f"Wrong browser launched: {identity}"
                driver.set_context("content")
                driver.get(f"http://127.0.0.1:{server.server_port}/")
                sizes = []
                for width, height in [(1100, 850), (1500, 1000), (900, 1100)]:
                    driver.set_window_size(width, height)
                    # Wait for layout + the asynchronous letterboxing paint to settle.
                    driver.execute_async_script("""
                      const done=arguments[0]; let n=0;
                      function tick(){if(++n===12) done(); else requestAnimationFrame(tick)}
                      requestAnimationFrame(tick);
                    """)
                    data = driver.execute_script(READ)
                    sizes.append(data["inner"])
                    print(json.dumps({"window": [width, height], "page": data}), flush=True)
                    check(data["inner"] == data["client"] == data["visual"], "viewport agreement", data)
                    check(data["body"] == data["inner"][0], "body width", data)
                    check(data["media"] and data["deviceMedia"] and data["dprMedia"], "CSS agreement", data)
                    check(data["screen"] == data["avail"] == data["outer"] == data["inner"], "protected screen", data)
                    check(data["origin"] == [0] * 6, "protected origin", data)
                    orientation = "landscape-primary" if data["screen"][0] > data["screen"][1] else "portrait-primary"
                    check(data["orientation"] == orientation, "screen orientation", data)
                    check(data["legacyOrientation"] == orientation, "legacy screen orientation", data)
                    check(data["inner"][0] % 200 == 0 and data["inner"][1] % 100 == 0, "shared buckets", data)
                    driver.set_context("chrome")
                    chrome = driver.execute_script("""
                      const manager = Cc['@mozilla.org/gfx/screenmanager;1'].getService(Ci.nsIScreenManager);
                      const native = manager.screenForRect(screenX, screenY, 1, 1);
                      const x={}, y={}, w={}, h={}; native.GetRect(x,y,w,h);
                      return {width:innerWidth, root:document.documentElement.clientWidth,
                        toolbar:document.getElementById('nav-bar').getBoundingClientRect().width,
                        screen:[screen.width,screen.height],
                        nativeScreen:[w.value/native.defaultCSSScaleFactor,h.value/native.defaultCSSScaleFactor],
                        deviceMedia:matchMedia(`(device-width: ${screen.width}px)`).matches,
                        cursor:!!document.getElementById('cursor-highlighter')};
                    """)
                    check(abs(chrome["root"] - width) <= 2 and abs(chrome["toolbar"] - width) <= 2, "chrome fills window", chrome)
                    check(not chrome["cursor"], "cursor overlay disabled", chrome)
                    check(chrome["screen"] == chrome["nativeScreen"] and chrome["deviceMedia"], "chrome uses native monitor geometry", chrome)
                    if width == 1500 and os.environ.get("CLOAKFOX_PROBE_SCREENSHOT"):
                        driver.save_screenshot(os.environ["CLOAKFOX_PROBE_SCREENSHOT"])
                    driver.set_context("content")
                check(len({tuple(size) for size in sizes}) == 3, "viewport responds to resizing", sizes)
                top = driver.execute_script(READ)
                driver.switch_to.frame(0)
                frame = driver.execute_script(READ)
                check(frame["inner"] == [320, 240] and frame["media"], "iframe own layout", frame)
                check(frame["screen"] == top["screen"] and frame["outer"] == top["outer"], "iframe top screen", frame)
                driver.switch_to.default_content()
                driver.execute_script("document.querySelector('iframe').src = arguments[0]",
                                      f"http://localhost:{server.server_port}/frame")
                driver.switch_to.frame(0)
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return location.hostname") == "localhost")
                frame = driver.execute_script(READ)
                check(frame["inner"] == [320, 240] and frame["screen"] == top["screen"] and frame["deviceMedia"], "cross-origin iframe", frame)
                driver.execute_script("""
                  window.savedQuery = matchMedia(`(device-width: ${screen.width}px)`);
                  const style = document.createElement('style');
                  style.textContent = `body{--screen-match:0} @media(device-width:${screen.width}px){body{--screen-match:1}}`;
                  document.head.appendChild(style);
                """)
                driver.switch_to.default_content()
                driver.set_window_size(1300, 950)
                driver.execute_async_script("const done=arguments[0]; setTimeout(done, 400)")
                top = driver.execute_script(READ)
                driver.switch_to.frame(0)
                cached = driver.execute_script("return [savedQuery.matches, getComputedStyle(document.body).getPropertyValue('--screen-match')]")
                check(cached == [False, "0"], "iframe cached CSS updates after top resize", cached)
                driver.switch_to.default_content()
                driver.execute_script("scrollTo(0, 500)")
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.documentElement.scrollTop") == 500)
                data = driver.execute_script(READ)
                check(data["scroll"] == data["visualScroll"] == 500, "real scrolling", data)
                driver.refresh()
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return innerWidth") == top["inner"][0])
                check(driver.execute_script(READ)["inner"] == top["inner"], "reload geometry", top)
                driver.get(f"http://127.0.0.1:{server.server_port}/next")
                check(driver.execute_script(READ)["inner"] == top["inner"], "navigation geometry", top)
                driver.back()
                check(driver.execute_script(READ)["inner"] == top["inner"], "back geometry", top)
                original = driver.current_window_handle
                for container in (1, 2):
                    handles = set(driver.window_handles)
                    driver.set_context("chrome")
                    driver.execute_script("""
                      const tab = gBrowser.addTab(arguments[0], {
                        userContextId: arguments[1],
                        triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()
                      });
                      gBrowser.selectedTab = tab;
                    """, f"http://127.0.0.1:{server.server_port}/", container)
                    driver.set_context("content")
                    handle = WebDriverWait(driver, 5).until(
                        lambda d: next(iter(set(d.window_handles) - handles), None))
                    driver.switch_to.window(handle)
                    WebDriverWait(driver, 5).until(
                        lambda d: d.execute_script("return document.readyState") == "complete")
                    data = driver.execute_script(READ)
                    check(data["inner"] == data["screen"] == top["inner"] and data["media"],
                          f"container {container} uses protected viewport", data)
                    driver.close()
                    driver.switch_to.window(original)
                driver.execute_script("document.querySelector('iframe').src = arguments[0]",
                                      f"http://localhost:{server.server_port}/frame")
                driver.switch_to.frame(0)
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return location.hostname") == "localhost")
                driver.execute_script("""
                  window.savedWidth = screen.width;
                  window.savedDPR = devicePixelRatio;
                  window.savedQuery = matchMedia(`(device-width: ${savedWidth}px)`);
                  window.savedResolution = matchMedia(`(resolution: ${savedDPR}dppx)`);
                  const style = document.createElement('style');
                  style.textContent = `body{--screen-match:0} @media(device-width:${savedWidth}px){body{--screen-match:1}}`;
                  document.head.appendChild(style);
                """)
                driver.switch_to.default_content()

                def check_cached_frame(label):
                    driver.set_context("content")
                    driver.switch_to.frame(0)
                    try:
                        WebDriverWait(driver, 5).until(lambda d: d.execute_script("""
                          const expected = screen.width === savedWidth;
                          return savedQuery.matches === expected &&
                            savedResolution.matches === (devicePixelRatio === savedDPR) &&
                            getComputedStyle(document.body).getPropertyValue('--screen-match').trim() === (expected ? '1':'0');
                        """))
                    except TimeoutException:
                        check(False, label, driver.execute_script(READ))
                    finally:
                        driver.switch_to.default_content()
                        driver.set_context("chrome")

                driver.set_context("chrome")
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.enabled', false)")
                try:
                    WebDriverWait(driver, 5).until(lambda d: d.execute_script("return !gBrowser.tabpanels.classList.contains('letterboxing')"))
                except TimeoutException:
                    check(False, "master switch detaches letterboxing", {})
                check_cached_frame("master off updates iframe CSS")
                driver.execute_script("Services.prefs.setBoolPref('cloakfox.enabled', true)")
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return gBrowser.tabpanels.classList.contains('letterboxing')"))
                check_cached_frame("master on updates iframe CSS")
                driver.execute_script("Services.prefs.setBoolPref('privacy.resistFingerprinting.letterboxing', false)")
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return !gBrowser.tabpanels.classList.contains('letterboxing')"))
                check_cached_frame("letterboxing opt-out updates iframe CSS")
                driver.execute_script("Services.prefs.setBoolPref('privacy.resistFingerprinting.letterboxing', true)")
                WebDriverWait(driver, 5).until(lambda d: d.execute_script("return gBrowser.tabpanels.classList.contains('letterboxing')"))
                check_cached_frame("letterboxing opt-in updates iframe CSS")
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()
    for failure in failures:
        print("FAIL", failure)
    if failures:
        return 1
    print("PASS — responsive chrome, letterboxed geometry, scrolling, reload and master switch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
