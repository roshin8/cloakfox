#!/usr/bin/env python3
"""Runtime smoke test for the BrowserForge browser profile picker."""
import http.server
import os
import tempfile
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class Handler(http.server.BaseHTTPRequestHandler):
    user_agent = None

    def do_GET(self):
        Handler.user_agent = self.headers.get("User-Agent")
        body = b"profile probe"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def main():
    binary = Path(os.environ["CLOAKFOX_BIN"]).resolve()
    assert binary.is_file(), binary
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="cloakfox-picker-") as profile:
        options = Options()
        options.binary_location = str(binary)
        options.add_argument("-profile")
        options.add_argument(profile)
        options.add_argument("-purgecaches")
        service = Service("/opt/homebrew/bin/geckodriver", service_args=["--allow-system-access"])
        driver = webdriver.Firefox(options=options, service=service)
        try:
            driver.get("about:cloakfox")
            WebDriverWait(driver, 15).until(lambda d: d.execute_script(
                "return document.querySelectorAll('.browser-family-tile').length === 6"))
            state = driver.execute_script("""
              const tiles = [...document.querySelectorAll('.browser-family-tile')];
              return Object.fromEntries(tiles.map(x => [x.dataset.browser, x.disabled]));
            """)
            assert state == {"firefox": False, "chrome": False, "edge": False,
                             "chromium": False, "safari": False, "custom": True}, state
            driver.execute_script("""
              const version = document.getElementById('cfx-persona-version');
              version.value = '156'; version.dispatchEvent(new Event('change'));
              const os = document.getElementById('cfx-persona-filter');
              os.value = 'Windows'; os.dispatchEvent(new Event('change'));
              document.getElementById('cfx-generate-new').click();
            """)
            WebDriverWait(driver, 20).until(lambda d: d.execute_script(
                "return document.querySelector('.profile-preview-label').textContent === 'Applied identity' "
                "&& document.getElementById('cfx-profile-preview-ua').textContent.includes(arguments[0]) "
                "&& !document.getElementById('cfx-generate-new').disabled", "Firefox/156.0"))
            driver.get(f"http://127.0.0.1:{server.server_port}/")
            ua, app_version, platform, oscpu = driver.execute_script(
                "return [navigator.userAgent,navigator.appVersion,navigator.platform,navigator.oscpu]")
            assert "Firefox/156.0" in ua and "rv:156.0" in ua, ua
            assert app_version == ua.removeprefix("Mozilla/"), (ua, app_version)
            assert Handler.user_agent == ua, (Handler.user_agent, ua)
            assert platform == "Win32" and oscpu == "Windows NT 10.0; Win64; x64", (platform, oscpu)
            driver.get("about:cloakfox")
            WebDriverWait(driver, 15).until(lambda d: d.execute_script(
                "return document.querySelector('[data-browser=chrome]')?.disabled === false"))
            driver.execute_script("""
              document.querySelector('[data-browser=chrome]').click();
              const version = document.getElementById('cfx-persona-version');
              version.value = '154'; version.dispatchEvent(new Event('change'));
              const os = document.getElementById('cfx-persona-filter');
              os.value = 'Windows'; os.dispatchEvent(new Event('change'));
              document.getElementById('cfx-generate-new').click();
            """)
            WebDriverWait(driver, 20).until(lambda d: d.execute_script(
                "return document.querySelector('.profile-preview-label').textContent === 'Applied identity' "
                "&& document.getElementById('cfx-profile-preview-ua').textContent.includes(arguments[0]) "
                "&& !document.getElementById('cfx-generate-new').disabled", "Chrome/154.0.0.0"))
            Handler.user_agent = None
            driver.get(f"http://127.0.0.1:{server.server_port}/chrome")
            chrome_ua = driver.execute_script("return navigator.userAgent")
            assert "Chrome/154.0.0.0" in chrome_ua and "Firefox/" not in chrome_ua, chrome_ua
            assert Handler.user_agent == chrome_ua, (Handler.user_agent, chrome_ua)
            print("PASS: Firefox and Chrome identity profiles are coherent and engine-independent")
        finally:
            driver.quit()
            server.shutdown()


if __name__ == "__main__":
    main()
