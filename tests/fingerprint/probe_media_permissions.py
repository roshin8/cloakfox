"""Verify camera/mic PermissionStatus without opening or recording devices.

Uses a disposable profile and local origin. Permission manager changes exercise
the native Permissions API and live change events; no media stream is requested.
"""
from __future__ import annotations

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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>Media permission regression</title>")

    def log_message(self, *args):
        pass


def main():
    results = []
    report = Path(os.environ.get("REPORT_DIR", tempfile.mkdtemp(prefix="cloakfox-media-permissions-")))
    report.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"

    def check(ok, name, data):
        results.append({"name": name, "pass": bool(ok), "data": data})
        print(("PASS " if ok else "FAIL ") + name, flush=True)
        assert ok, json.dumps(data)

    with tempfile.TemporaryDirectory(prefix="cloakfox-media-permissions-profile-") as tmp:
        profile = Path(tmp, "profile")
        profile.mkdir()
        Path(profile, "user.js").write_text('user_pref("cloakfox.enabled", true);\n')
        opts = Options()
        opts.binary_location = os.environ["CLOAKFOX_BIN"]
        opts.add_argument("-headless")
        opts.add_argument("-profile")
        opts.add_argument(str(profile))
        driver = webdriver.Firefox(options=opts, service=Service(
            service_args=["--allow-system-access"], log_output=str(report / "gecko.log")))
        driver.set_script_timeout(15)

        def chrome(script, *args):
            driver.set_context("chrome")
            try:
                return driver.execute_script(script, *args)
            finally:
                driver.set_context("content")

        def permission(name, action):
            chrome("""
                const [url,name,action]=arguments;
                const principal=Services.scriptSecurityManager.createContentPrincipal(
                    Services.io.newURI(url), {});
                if(action===0) Services.perms.removeFromPrincipal(principal,name);
                else Services.perms.addFromPrincipal(principal,name,action);
            """, url, name, action)

        def query(name):
            return driver.execute_async_script("""
                const [name,done]=arguments;
                navigator.permissions.query({name}).then(s=>done(s.state),e=>done({error:e.message}));
            """, name)

        try:
            driver.get(url)
            config = chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'))")
            check(config.get("permissions:spoof") is True, "regression runs with permission privacy enabled", {})
            for name in ("camera", "microphone"):
                permission(name, 1)
                check(query(name) == "granted", f"{name}: actual grant is visible", query(name))
                driver.execute_async_script("""
                    const [name,done]=arguments;
                    navigator.permissions.query({name}).then(s=>{
                        window.mediaPermissionStatus=s; window.mediaPermissionEvents=[];
                        s.onchange=()=>window.mediaPermissionEvents.push(s.state); done(s.state);
                    },e=>done({error:e.message}));
                """, name)
                permission(name, 2)
                WebDriverWait(driver, 5).until(lambda d: d.execute_script(
                    "return window.mediaPermissionStatus.state") == "denied")
                check(driver.execute_script("return window.mediaPermissionEvents.includes('denied')"),
                      f"{name}: revocation updates an existing status and fires change", {})
                permission(name, 1)
                WebDriverWait(driver, 5).until(lambda d: d.execute_script(
                    "return window.mediaPermissionStatus.state") == "granted")
                check(driver.execute_script("return window.mediaPermissionEvents.includes('granted')"),
                      f"{name}: regrant updates an existing status and fires change", {})
                permission(name, 0)
                WebDriverWait(driver, 5).until(lambda d: d.execute_script(
                    "return window.mediaPermissionStatus.state") == "prompt")
                check(driver.execute_script("return window.mediaPermissionEvents.includes('prompt')"),
                      f"{name}: removal fires a prompt change on the existing status", {})
                check(query(name) == "prompt", f"{name}: ungranted access is not reported as granted", query(name))
                # Firefox reports its persisted Always Ask choice as granted;
                # the capture request still asks before opening any device.
                permission(name, 3)
                check(query(name) == "granted", f"{name}: native Always Ask reporting is retained", query(name))
            for action in (1, 2):
                permission("desktop-notification", action)
                check(query("notifications") == "prompt", f"notification privacy retained for action {action}", query("notifications"))
            chrome("Services.prefs.setBoolPref('cloakfox.enabled', false)")
            driver.refresh()
            check(query("notifications") == "denied", "master off restores native notification state", query("notifications"))
            permission("camera", 1)
            check(query("camera") == "granted", "master off keeps native camera state", query("camera"))
        finally:
            driver.quit()
            server.shutdown()
            Path(report, "result.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
