"""Catch settings edits being stored as pins but omitted from the active config.

Exercises the real about:cloakfox editor, per-container isolation, regeneration,
reload/restart persistence, HTTP User-Agent and the native navigator identity.
Run with CLOAKFOX_BIN and optionally REPORT_DIR; uses disposable profiles.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select

CHROME = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = ("<!doctype html><title>Identity probe</title><script>window.httpUA="
                + json.dumps(self.headers.get("User-Agent")) + ";</script>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    results = []
    report = Path(os.environ.get("REPORT_DIR", tempfile.mkdtemp(prefix="cloakfox-settings-report-")))
    report.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"

    def check(ok, name, data):
        results.append({"name": name, "pass": bool(ok), "data": data})
        print(("PASS " if ok else "FAIL ") + name, flush=True)
        assert ok, json.dumps(data, indent=2)

    with tempfile.TemporaryDirectory(prefix="cloakfox-settings-") as tmp:
        profile = Path(tmp, "profile")
        profile.mkdir()
        Path(profile, "user.js").write_text(
            'user_pref("cloakfox.enabled", true);\n'
            'user_pref("cloakfox.opt.clipboard_masking", true);\n'
            'user_pref("cloakfox.opt.focus_masking", true);\n')

        def launch():
            opts = Options()
            opts.binary_location = os.environ["CLOAKFOX_BIN"]
            opts.add_argument("-headless")
            opts.add_argument("-profile")
            opts.add_argument(str(profile))
            return webdriver.Firefox(options=opts, service=Service(
                service_args=["--allow-system-access"], log_output=str(report / "gecko.log")))

        driver = launch()

        def chrome(script, *args):
            driver.set_context("chrome")
            try:
                return driver.execute_script(script, *args)
            finally:
                driver.set_context("content")

        def snapshot(ucid):
            return chrome("""
                const id=arguments[0], {readOverrides}=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
                return {pins:readOverrides(id),cfg:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id)),
                    h2:Services.prefs.getStringPref('cloakfox.container.'+id+'.h2_profile','')};
                """, ucid)

        def settings(ucid):
            driver.get("about:cloakfox")
            WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, ".spoof-row.dyn"))
            selector = driver.find_element(By.ID, "cfx-container-select")
            choices = [option.get_attribute("value") for option in selector.find_elements(By.TAG_NAME, "option")]
            check(str(ucid) in choices, f"settings lists container {ucid}", choices)
            Select(selector).select_by_value(str(ucid))
            selection = driver.execute_script("const s=document.getElementById('cfx-container-select');return {value:s.value,options:Array.from(s.options,o=>o.value)}")
            check(selection["value"] == str(ucid), f"settings selects requested container {ucid}", selection)

        def row(key):
            return driver.find_element(By.CSS_SELECTOR, f'.k[title="{key}"]').find_element(By.XPATH, "..")

        def edit(key, value):
            driver.execute_script("arguments[0].click()", row(key).find_element(By.CSS_SELECTOR, ".v"))
            field = row(key).find_element(By.CSS_SELECTOR, ".row-input")
            field.send_keys(Keys.COMMAND, "a")
            field.send_keys(value)
            driver.execute_script("document.activeElement.blur()")
            WebDriverWait(driver, 5).until(lambda d: not row(key).find_elements(By.CSS_SELECTOR, ".row-input"))

        try:
            for id, ua in ((0, CHROME), (2, EDGE)):
                settings(id)
                for key, value in (("navigator.userAgent", ua), ("headers.User-Agent", ua),
                                   ("navigator.hardwareConcurrency", "41")):
                    edit(key, value)
                    state = snapshot(id)
                    expected = 41 if key.endswith("hardwareConcurrency") else value
                    check(state["pins"].get(key) == expected and state["cfg"].get(key) == expected,
                          f"container {id}: {key} edit reaches active config", state)
                driver.execute_script("document.getElementById('cfx-regenerate').click()")
                state = snapshot(id)
                check(state["cfg"]["navigator.userAgent"] == ua and state["cfg"]["headers.User-Agent"] == ua
                      and state["cfg"]["navigator.hardwareConcurrency"] == 41 and state["h2"] == "chrome",
                      f"container {id}: new persona preserves overrides and HTTP profile", state)
                driver.refresh()
                WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, ".spoof-row.dyn"))
                Select(driver.find_element(By.ID, "cfx-container-select")).select_by_value(str(id))
                check(row("navigator.userAgent").find_element(By.CSS_SELECTOR, ".v").get_attribute("title") == ua,
                      f"container {id}: settings reload retains UA", snapshot(id))
            check(snapshot(0)["cfg"]["navigator.userAgent"] == CHROME,
                  "editing container 2 preserves default container", snapshot(0))
            driver.quit()
            driver = launch()
            for id, ua in ((0, CHROME), (2, EDGE)):
                state = snapshot(id)
                check(state["cfg"]["navigator.userAgent"] == ua and state["cfg"]["navigator.hardwareConcurrency"] == 41,
                      f"container {id}: overrides survive restart", state)
            driver.get(url)
            identity = driver.execute_script("return {ua:navigator.userAgent,http:window.httpUA,cores:navigator.hardwareConcurrency,brands:navigator.userAgentData?.brands}")
            check(identity["ua"] == CHROME and identity["http"] == CHROME and identity["cores"] == 41
                  and any(b["brand"] == "Google Chrome" for b in identity.get("brands", [])),
                  "default website receives edited UA, HTTP header, cores and Chrome hints", identity)
            settings(0)
            persona_cores = chrome("""
                const {fillPersonaKeys}=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
                return fillPersonaKeys(Services.prefs.getStringPref('cloakfox.container.0.math_seed'),0)['navigator.hardwareConcurrency'];
                """)
            driver.execute_script("arguments[0].click()", row("navigator.hardwareConcurrency").find_element(By.CSS_SELECTOR, ".row-reset-x"))
            state = snapshot(0)
            check("navigator.hardwareConcurrency" not in state["pins"]
                  and state["cfg"]["navigator.hardwareConcurrency"] == persona_cores
                  and state["cfg"]["navigator.userAgent"] == CHROME,
                  "resetting one field retains other overrides", state)
            driver.execute_script("document.getElementById('cfx-clear-overrides').click()")
            state = snapshot(0)
            check(not state["pins"] and "Firefox/" in state["cfg"]["navigator.userAgent"]
                  and snapshot(2)["cfg"]["navigator.userAgent"] == EDGE,
                  "clear overrides restores persona only in selected container", state)
        finally:
            driver.quit()
            server.shutdown()
            Path(report, "result.json").write_text(json.dumps(results, indent=2))
    print(f"{len(results)} checks passed; report: {report}")


if __name__ == "__main__":
    main()
