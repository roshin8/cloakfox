"""
cloakfox.enabled master kill-switch regression probe.

cloakfox.cfg documents cloakfox.enabled=false as "disable all spoofing
globally". It regressed to only gating the JS actors while the C++ layer
(navigator/canvas/… via CloakConfigOverlay) and the H2/H3 socket-thread
fingerprints kept spoofing. Fixed by gating on a RelaxedAtomicBool
StaticPref readable on every thread.

This probe proves the switch with HOST-INDEPENDENT relative assertions —
no hardcoded fingerprints or platform strings, so it holds on any machine:

  A) enabled=true,  h2_profile=chrome  -> H2 = chrome
  B) enabled=false, h2_profile=chrome  -> H2 must NOT be chrome (the pref is
                                          ignored), and navigator is real
  C) enabled=false, h2_profile=chrome  -> second fresh profile

  * B.h2 != A.h2   — disabled ignores the chrome H2 pref (socket-thread gate)
  * B.h2 == C.h2   — disabled H2 is deterministic (stock Firefox), not spoofed
  * B.nav == C.nav — disabled navigator is the stable real host across fresh
                     profiles; a live spoofer emits a RANDOM per-profile
                     persona, so identical nav across profiles == not spoofed

Exit codes: 0 pass · 1 kill-switch regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_enabled_killswitch.py
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


def run(bin_path: str, enabled: bool, h2profile: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text(
            f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
            'user_pref("devtools.jsonview.enabled", false);\n'
            f'user_pref("network.http.http2.fingerprint_profile", "{h2profile}");\n'
        )
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(service_args=["--allow-system-access"], log_output=str(Path(prof) / "gd.log")))
        try:
            d.set_page_load_timeout(40)
            d.get("https://example.com/")
            time.sleep(1.5)
            nav = d.execute_script(
                "return [navigator.platform, navigator.oscpu, "
                "navigator.userAgent, navigator.hardwareConcurrency].join('|');"
            )
            d.get(PROBE_URL)
            deadline = time.time() + 40
            h2 = None
            while time.time() < deadline:
                try:
                    body = d.execute_script(
                        "return document.body ? document.body.innerText : ''"
                    )
                    if body and body.strip().startswith("{"):
                        h2 = (json.loads(body.strip()).get("http2", {})
                              .get("akamai_fingerprint_hash"))
                        break
                except Exception:
                    pass
                time.sleep(0.4)
            return {"nav": nav, "h2": h2}
        finally:
            d.quit()


def main(bin_path: str) -> int:
    a = run(bin_path, enabled=True, h2profile="chrome")
    b = run(bin_path, enabled=False, h2profile="chrome")
    c = run(bin_path, enabled=False, h2profile="chrome")

    for label, r in (("A enabled+chrome", a), ("B disabled", b), ("C disabled", c)):
        if not r["h2"]:
            print(f"could not read H2 fingerprint for run {label}")
            return 2
        print(f"  {label}: h2={r['h2']}  nav={r['nav']}")
    print()

    fails = []
    if b["h2"] == a["h2"]:
        fails.append("disabled H2 equals the chrome H2 — the chrome profile "
                     "pref was NOT ignored (socket-thread gate regressed)")
    if b["h2"] != c["h2"]:
        fails.append("disabled H2 differs across two fresh profiles — not "
                     "deterministic/stock (unexpected)")
    if b["nav"] != c["nav"]:
        fails.append("disabled navigator differs across fresh profiles — a "
                     "random persona is still being applied (DOM gate regressed)")

    if fails:
        print("FAIL — cloakfox.enabled kill-switch regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — enabled=false ignores the chrome H2 pref and presents a "
          "stable real identity (DOM + H2 both gated)")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
