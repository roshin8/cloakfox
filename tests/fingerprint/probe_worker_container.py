"""Worker-vs-window identity coherence probe (per-container).

JSWindowActors cannot reach worker globals, so worker-scope spoofing runs
entirely through the C++ MaskConfig path. That path resolves "which container
am I?" via CloakConfigOverlay_CurrentUserContextId(), which returns 0 whenever
it is off the main thread:

    // Window/container resolution is main-thread only; workers fall back
    // to the ctx-0 / env overlay
    if (!NS_IsMainThread()) return 0;          // CloakConfigOverlay.cpp

So inside a NON-default container a worker may report container 0's persona
while the window reports its own. That is two problems at once:

  * a window/worker contradiction — one line of JS for a fingerprinter, and no
    real browser disagrees with itself about navigator.platform; and
  * cross-container correlation — container N can read container 0's identity,
    which is exactly what per-container isolation exists to prevent.

This probe opens a chrome-privileged tab in a non-default userContextId, spawns
a Worker there, and compares the identity fields the worker sees against the
window's. Everything is compared within one container, so the check is
host-independent.

Fields compared: navigator.platform, userAgent, appVersion, hardwareConcurrency.
(appVersion is called out separately in the audit: unlike its neighbours,
WorkerNavigator::GetAppVersion has no per-ucid NavigatorManager lookup at all.)

Exit codes: 0 coherent · 1 window/worker mismatch · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_worker_container.py
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

# Collected in the page, then again inside a Worker spawned from that page.
COMPARE = r"""
const cb = arguments[arguments.length - 1];
const win = {
  platform: navigator.platform,
  userAgent: navigator.userAgent,
  appVersion: navigator.appVersion,
  hardwareConcurrency: navigator.hardwareConcurrency,
};
const src = `postMessage({
  platform: navigator.platform,
  userAgent: navigator.userAgent,
  appVersion: navigator.appVersion,
  hardwareConcurrency: navigator.hardwareConcurrency,
});`;
try {
  const w = new Worker(URL.createObjectURL(new Blob([src])));
  const timer = setTimeout(() => cb(JSON.stringify({win, worker: 'timeout'})), 5000);
  w.onmessage = (e) => {
    clearTimeout(timer);
    cb(JSON.stringify({win, worker: e.data}));
  };
} catch (e) {
  cb(JSON.stringify({win, worker: 'ERR ' + e}));
}
"""

FIELDS = ("platform", "userAgent", "appVersion", "hardwareConcurrency")


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
            d.set_script_timeout(30)
            d.get("https://example.com/")
            time.sleep(2)

            results = {}
            # default container first, then a named one — the bug is specific to
            # non-default containers, so a default-only check would miss it.
            for ucid in (0, 2):
                if ucid:
                    before = set(d.window_handles)
                    d.set_context("chrome")
                    d.execute_script(OPEN_TAB, ucid)
                    d.set_context("content")
                    time.sleep(2.5)
                    new = [h for h in d.window_handles if h not in before]
                    if not new:
                        print(f"could not open a tab in container {ucid}")
                        return 2
                    d.switch_to.window(new[-1])
                    time.sleep(1.0)
                results[ucid] = json.loads(d.execute_async_script(COMPARE))
        finally:
            d.quit()

    fails = []
    for ucid, r in results.items():
        w, k = r["win"], r["worker"]
        label = "default" if ucid == 0 else f"container {ucid}"
        if not isinstance(k, dict):
            print(f"  {label}: worker did not report ({k})")
            fails.append(f"{label}: worker unavailable — cannot verify coherence")
            continue
        print(f"  {label}:")
        for f in FIELDS:
            match = w.get(f) == k.get(f)
            shown_w = str(w.get(f))[:52]
            shown_k = str(k.get(f))[:52]
            print(f"    {f:<20} window={shown_w}")
            print(f"    {'':<20} worker={shown_k}  {'ok' if match else 'MISMATCH'}")
            if not match:
                fails.append(
                    f"{label}: worker {f} = {k.get(f)!r} but window = {w.get(f)!r} "
                    "— the worker resolved a different container's persona "
                    "(CloakConfigOverlay returns ucid 0 off the main thread)")

    # Cross-container correlation: a non-default container's worker must not
    # echo the default container's identity.
    if 0 in results and 2 in results:
        w0, k2 = results[0].get("win"), results[2].get("worker")
        if isinstance(k2, dict) and isinstance(w0, dict):
            leaked = [f for f in FIELDS
                      if k2.get(f) == w0.get(f) and results[2]["win"].get(f) != w0.get(f)]
            if leaked:
                fails.append(
                    f"container 2's worker reported the DEFAULT container's "
                    f"{leaked} — cross-container correlation")

    print()
    if fails:
        print("FAIL — worker/window identity is incoherent:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — workers report the same identity as their own window, in the "
          "default and in a named container")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
