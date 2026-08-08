"""navigator identity self-coherence probe (per container).

Cross-checks navigator fields that are DERIVED from one another in every real
browser. These invariants are one line of JS to test, so breaking one is worse
than not spoofing at all — it proves the browser is lying about itself.

  appVersion === userAgent.slice(8)   (userAgent minus the leading "Mozilla/")
  platform is consistent with the OS token in the userAgent
  oscpu (Firefox-only) is consistent with the userAgent's OS

The appVersion invariant regressed in a way only visible in NON-DEFAULT
containers, which is why this probe walks several userContextIds rather than
just the default one. Navigator::GetAppVersion read the context-BLIND
MaskConfig getter (resolved via CloakConfigOverlay_CurrentUserContextId())
instead of this window's own BrowsingContext the way GetUserAgent does; when
that missed it fell through to Firefox's RFP value. Measured before the fix:

    container 1..3   userAgent  = Mozilla/5.0 (X11; Ubuntu; Linux x86_64; ...)
                     appVersion = 5.0 (Macintosh)        <- REAL host OS

i.e. both a spec violation and a host-OS leak. appVersion is now derived from
GetUserAgent() itself, so the invariant holds regardless of which path supplies
the UA.

Exit codes: 0 coherent · 1 an invariant broke · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_navigator_coherence.py
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

OPEN_TAB = """
const ucid = arguments[0];
const win = Services.wm.getMostRecentWindow('navigator:browser');
const tab = win.gBrowser.addTab('https://example.com/', {
  userContextId: ucid,
  triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
});
win.gBrowser.selectedTab = tab;
return true;
"""

READ = """
return JSON.stringify({
  ua: navigator.userAgent,
  appVersion: navigator.appVersion,
  platform: navigator.platform,
  oscpu: navigator.oscpu,
});
"""

# userAgent OS token -> the platform value Firefox reports on that OS.
OS_PLATFORM = {
    "Windows": "Win32",
    "Macintosh": "MacIntel",
    "X11": "Linux x86_64",
}


def os_of_ua(ua: str) -> str | None:
    for token in OS_PLATFORM:
        if token in ua:
            return token
    return None


def main(bin_path: str) -> int:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text(
            'user_pref("cloakfox.enabled", true);\n'
            'user_pref("privacy.userContext.enabled", true);\n')
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-remote-allow-system-access")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(log_output=str(Path(prof) / "g.log")))
        results = {}
        try:
            d.set_page_load_timeout(40)
            d.get("https://example.com/")
            time.sleep(2)
            for ucid in (0, 1, 2, 3):
                if ucid:
                    before = set(d.window_handles)
                    d.set_context("chrome")
                    d.execute_script(OPEN_TAB, ucid)
                    d.set_context("content")
                    time.sleep(2.2)
                    new = [h for h in d.window_handles if h not in before]
                    if not new:
                        continue
                    d.switch_to.window(new[-1])
                    time.sleep(0.8)
                results[ucid] = json.loads(d.execute_script(READ))
        finally:
            d.quit()

    if not results:
        print("no containers could be read")
        return 2

    fails = []
    for ucid, r in sorted(results.items()):
        ua, av = r["ua"], r["appVersion"]
        expect = ua[8:] if ua.startswith("Mozilla/") else None
        ok = av == expect
        print(f"  ucid{ucid}: appVersion {'== UA[8:]' if ok else 'MISMATCH'} | "
              f"platform={r['platform']}")
        if not ok:
            print(f"      ua       = {ua}")
            print(f"      appVer   = {av}")
            print(f"      expected = {expect}")
            fails.append(
                f"ucid{ucid}: appVersion {av!r} != userAgent.slice(8) {expect!r} "
                "— a spec invariant every real browser satisfies; when this "
                "broke before, appVersion leaked the real host OS")

        # platform must agree with the UA's OS token
        token = os_of_ua(ua)
        if token and r["platform"] != OS_PLATFORM[token]:
            fails.append(
                f"ucid{ucid}: userAgent says {token!r} but navigator.platform "
                f"is {r['platform']!r} (expected {OS_PLATFORM[token]!r})")
        # oscpu, when present, must not contradict the UA's OS
        oscpu = r.get("oscpu") or ""
        if token and oscpu:
            contradiction = (
                (token == "Macintosh" and "Windows" in oscpu) or
                (token == "Windows" and "Mac" in oscpu) or
                (token == "X11" and ("Windows" in oscpu or "Mac" in oscpu)))
            if contradiction:
                fails.append(f"ucid{ucid}: userAgent says {token!r} but oscpu is "
                             f"{oscpu!r}")

    print()
    if fails:
        print("FAIL — navigator fields contradict each other:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"PASS — appVersion/platform/oscpu are self-consistent in all "
          f"{len(results)} containers")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
