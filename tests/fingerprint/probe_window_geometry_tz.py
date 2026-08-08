"""mozInnerScreen derivation + default-container timezone integrity.

Two independent regressions, both only visible once more than one container is
involved — which is why they survived checks that only looked at the default
container.

1. window.mozInnerScreenX / mozInnerScreenY
   Firefox-specific and read directly by CreepJS. Unspoofed they leak the real
   window placement, the real browser-chrome height and the multi-monitor
   layout, and they contradict the spoofed screenX/screenY beside them. They are
   now DERIVED from values we already report, so the pair cannot drift:
       mozInnerScreenX == screenX                (no horizontal chrome)
       mozInnerScreenY == screenY + (outerHeight - innerHeight)
   Asserting the relationship rather than absolute numbers keeps this valid on
   any host.

2. Default-container timezone integrity
   TimezoneManager::SetTimezone unconditionally called DisableFunction(ucid),
   and nsGlobalWindowInner::SetTimezone additionally wrote a ucid-0 "fallback"
   for shared/service workers. Together those meant a NAMED container setting
   its timezone permanently disabled the DEFAULT container's own setter and
   overwrote its zone — the default container then reported that container's
   timezone forever, a cross-container correlation signal that also contradicted
   its own persona geolocation. The fallback is now store-only and only fires
   when ctx 0 has no zone of its own.

   Tested behaviourally: read the default container's timezone, open other
   containers, then read the default container again. It must not have changed.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_window_geometry_tz.py
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
  screenX: window.screenX,
  screenY: window.screenY,
  mozInnerX: window.mozInnerScreenX,
  mozInnerY: window.mozInnerScreenY,
  outerH: window.outerHeight,
  innerH: window.innerHeight,
  tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
  tzOffset: new Date().getTimezoneOffset(),
});
"""


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
        try:
            d.set_page_load_timeout(40)
            d.get("https://example.com/")
            time.sleep(2)
            default_before = json.loads(d.execute_script(READ))
            default_handle = d.current_window_handle

            others = {}
            for ucid in (1, 2):
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
                others[ucid] = json.loads(d.execute_script(READ))

            # back to the default container — its timezone must be unchanged
            d.switch_to.window(default_handle)
            time.sleep(0.8)
            default_after = json.loads(d.execute_script(READ))
        finally:
            d.quit()

    fails = []
    print(f"  default before: tz={default_before['tz']} "
          f"screen=({default_before['screenX']},{default_before['screenY']}) "
          f"mozInner=({default_before['mozInnerX']},{default_before['mozInnerY']})")
    for ucid, r in others.items():
        print(f"  container {ucid}: tz={r['tz']} "
              f"screen=({r['screenX']},{r['screenY']}) "
              f"mozInner=({r['mozInnerX']},{r['mozInnerY']})")
    print(f"  default after : tz={default_after['tz']}")
    print()

    # 1. mozInnerScreen derivation, in every container we saw
    for label, r in [("default", default_before)] + \
                    [(f"container {u}", v) for u, v in others.items()]:
        if r["mozInnerX"] != r["screenX"]:
            fails.append(f"{label}: mozInnerScreenX={r['mozInnerX']} != "
                         f"screenX={r['screenX']} — the pair drifted, so one of "
                         "them is the real host value")
        chrome = r["outerH"] - r["innerH"]
        expect_y = r["screenY"] + (chrome if chrome >= 0 else 0)
        if r["mozInnerY"] != expect_y:
            fails.append(
                f"{label}: mozInnerScreenY={r['mozInnerY']} != screenY + "
                f"(outerHeight - innerHeight) = {expect_y} — chrome height or "
                "window origin is leaking the real window")

    # 2. the default container's timezone must survive other containers
    if default_after["tz"] != default_before["tz"]:
        fails.append(
            f"default container timezone changed from {default_before['tz']!r} "
            f"to {default_after['tz']!r} after other containers were opened — "
            "a named container hijacked ctx 0 (TimezoneManager ucid-0 fallback)")
    if default_after["tzOffset"] != default_before["tzOffset"]:
        fails.append(
            f"default container getTimezoneOffset changed "
            f"({default_before['tzOffset']} -> {default_after['tzOffset']})")

    if fails:
        print("FAIL — window geometry / timezone integrity regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — mozInnerScreen is derived from the spoofed screen origin and "
          "chrome height, and the default container's timezone is not hijacked")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
