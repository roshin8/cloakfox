"""
Per-container HTTP/2 fingerprint E2E.

STATUS (2026-07-27): currently FAILS — both containers emit the global
default (firefox) H2 hash instead of distinct per-container fingerprints.
This is the intended check for the C3 per-container read; the gap it
surfaces is documented in PENDING.md (socket-process userContextId not
reaching Http2Session::SendHello). Keep as the regression/validation
target for that fix.

test_h2_profile.py sets the GLOBAL `network.http.http2.fingerprint_profile`
and relaunches per profile. This proves the deeper property: within a
SINGLE browser session, two different containers emit DIFFERENT H2 wire
fingerprints, driven by their own `cloakfox.container.<ucid>.h2_profile`
prefs (the C3 per-container read in Http2Session).

Setup: container 1 -> "firefox", container 2 -> "chrome". We open a tab in
each container (chrome-context gBrowser.addTab; Selenium can't set
userContextId) pointed at tls.peet.ws/api/all, and assert the two
containers' `http2.akamai_fingerprint_hash` values DIFFER. Without the C3
per-container read, both connections would read the global pref and the
hashes would collapse.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_h2_per_container.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE_URL = "https://tls.peet.ws/api/all"
# Two non-default containers with deliberately different H2 profiles.
CONTAINERS = {1: "firefox", 2: "chrome"}

OPEN_CONTAINER_TAB = """
const [url, userContextId] = arguments;
const win = Services.wm.getMostRecentWindow('navigator:browser');
const tab = win.gBrowser.addTab(url, {
  userContextId,
  triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
});
win.gBrowser.selectedTab = tab;
return true;
"""


def _akamai_hash_in_container(driver, ucid: int) -> str:
    before = set(driver.window_handles)
    driver.set_context("chrome")
    try:
        driver.execute_script(OPEN_CONTAINER_TAB, PROBE_URL, ucid)
    finally:
        driver.set_context("content")

    deadline = time.time() + 15
    handle = None
    while time.time() < deadline:
        extra = set(driver.window_handles) - before
        if extra:
            handle = extra.pop()
            break
        time.sleep(0.1)
    if not handle:
        raise RuntimeError(f"container {ucid}: new tab never appeared")

    driver.switch_to.window(handle)
    deadline = time.time() + 30
    payload = None
    while time.time() < deadline:
        try:
            body = driver.execute_script(
                "return document.body ? (document.body.innerText || "
                "document.body.textContent) : ''"
            )
            if body and body.strip().startswith("{"):
                payload = json.loads(body.strip())
                break
        except Exception:
            pass
        time.sleep(0.3)
    if payload is None:
        raise RuntimeError(f"container {ucid}: no JSON from {PROBE_URL}")
    h = payload.get("http2", {}).get("akamai_fingerprint_hash") or payload.get(
        "akamai_fingerprint_hash"
    )
    if not h:
        raise RuntimeError(f"container {ucid}: no akamai_fingerprint_hash in response")
    return h


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "profile")
        Path(prof).mkdir(parents=True, exist_ok=True)
        lines = [
            'user_pref("cloakfox.enabled", true);',
            'user_pref("privacy.userContext.enabled", true);',
            # Serve tls.peet.ws JSON as raw text, not Firefox's JSON-viewer UI.
            'user_pref("devtools.jsonview.enabled", false);',
        ]
        for ucid, profile in CONTAINERS.items():
            lines.append(f'user_pref("cloakfox.container.{ucid}.h2_profile", "{profile}");')
        Path(prof, "user.js").write_text("\n".join(lines) + "\n")

        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-remote-allow-system-access")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        svc = Service(log_path=str(Path(prof) / "geckodriver.log"))
        driver = webdriver.Firefox(options=opts, service=svc)
        driver.set_page_load_timeout(30)
        try:
            hashes = {ucid: _akamai_hash_in_container(driver, ucid)
                      for ucid in CONTAINERS}
        finally:
            driver.quit()

    for ucid, profile in CONTAINERS.items():
        print(f"container {ucid} ({profile}): akamai_fingerprint_hash = {hashes[ucid]}")
    print()

    if len(set(hashes.values())) == len(hashes):
        print("PASS: each container emits a distinct H2 fingerprint (per-container "
              "read engaged)")
    else:
        print("FAIL: containers share an H2 fingerprint — the per-container read "
              "is not engaging; both fell back to the global pref")
        sys.exit(1)


if __name__ == "__main__":
    main()
