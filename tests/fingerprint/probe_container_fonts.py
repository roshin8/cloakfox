"""
Per-container font-set regression probe (#4).

FontListManager narrows font enumeration per userContextId at resolution time
(AutoFontListContext at gfxTextRun), reading each container's cloak_cfg "fonts"
overlay. Before this was wired, every container inherited the default (ucid 0)
persona's font set — a cross-container linkage — because the process-global
font whitelist is parent-authoritative and content-process per-container writes
are overridden.

Deterministic proof (no reliance on random personas): inject two known overlays
via prefs — ctx 0 includes the Mac fonts Menlo/Monaco/Tahoma, ctx 1 excludes
them — then render in each container (chrome-privileged tab in the target
userContextId) and enumerate. Because both containers share one process-global
whitelist, the ONLY way ctx 1 can hide fonts ctx 0 shows is per-container
narrowing from its own overlay.

  ctx 0 overlay "fonts" ⊇ {Menlo, Monaco, Tahoma}  -> must be visible in ctx 0
  ctx 1 overlay "fonts" ∌ {Menlo, Monaco, Tahoma}  -> must be hidden in ctx 1

PASS iff ctx 0 shows Menlo+Monaco AND ctx 1 hides both. (Arial can read as
absent via the classic detect-vs-default-sans-serif artifact; the Mac-font
discriminators are unambiguous.)

Requires containers, so it drives a chrome-privileged tab open — needs
-remote-allow-system-access (already used by the other probes).

Exit codes: 0 pass · 1 per-container narrowing regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_container_fonts.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PANEL = ["Arial", "Georgia", "Verdana", "Menlo", "Monaco", "Tahoma",
         "Impact", "Geneva"]
# "fonts:spacing_seed" is REQUIRED for these overlays to survive startup.
# CloakfoxSeedSync.needsCfgRebuild() regenerates any cloak_cfg missing it, so
# an overlay without it is replaced by a RANDOM persona before the probe
# reads anything — measured as: ctx 0 did not expose its overlay's Mac fonts
# (Menlo/Monaco missing) — overlay not applied: [].
#
# Worse than a plain failure, it made this probe non-deterministic: when the
# regenerated persona happened to be a Mac one, Menlo/Monaco were present and
# the probe PASSED without ever testing the injected overlay.
CFG0 = json.dumps({"fonts": ["Arial", "Georgia", "Verdana", "Impact", "Tahoma",
                             "Menlo", "Monaco", "Courier New", "Times New Roman",
                             "Geneva"],
                   "fonts:spacing_seed": 0xC0FFEE})
CFG1 = json.dumps({"fonts": ["Arial", "Georgia", "Verdana"],
                   "fonts:spacing_seed": 0xBADF00D})

FONT_PROBE = """
const P = arguments[0];
function present(f){
  const b = ['monospace','sans-serif','serif'];
  const s = document.createElement('span');
  s.style.cssText = 'position:absolute;left:-9999px;font-size:72px';
  s.textContent = 'mmmmmwwwwiiil'; document.body.appendChild(s);
  let d = false;
  for (const g of b){
    s.style.fontFamily = g; const w = s.offsetWidth, h = s.offsetHeight;
    s.style.fontFamily = '"' + f + '",' + g;
    if (s.offsetWidth !== w || s.offsetHeight !== h){ d = true; break; }
  }
  document.body.removeChild(s); return d;
}
return JSON.stringify(P.filter(present));
"""

OPEN_TAB = """
const ucid = arguments[0];
const win = Services.wm.getMostRecentWindow('navigator:browser');
const tab = win.gBrowser.addTab('https://example.com/', {
  userContextId: ucid,
  triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
});
win.gBrowser.selectedTab = tab; return true;
"""


def main(bin_path: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text(
            'user_pref("cloakfox.enabled", true);\n'
            'user_pref("privacy.userContext.enabled", true);\n'
            f'user_pref("cloakfox.s.cloak_cfg_0", {json.dumps(CFG0)});\n'
            f'user_pref("cloakfox.s.cloak_cfg_1", {json.dumps(CFG1)});\n'
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
            time.sleep(2)
            ctx0 = set(json.loads(d.execute_script(FONT_PROBE, PANEL)))
            before = set(d.window_handles)
            d.set_context("chrome")
            d.execute_script(OPEN_TAB, 1)
            d.set_context("content")
            time.sleep(2.5)
            new = [h for h in d.window_handles if h not in before]
            if not new:
                print("could not open a container tab")
                return 2
            d.switch_to.window(new[-1])
            time.sleep(1)
            ctx1 = set(json.loads(d.execute_script(FONT_PROBE, PANEL)))
        finally:
            d.quit()

    print(f"  ctx 0 (overlay incl Menlo/Monaco/Tahoma): {sorted(ctx0)}")
    print(f"  ctx 1 (overlay excl them)               : {sorted(ctx1)}")
    print()

    fails = []
    if not ({"Menlo", "Monaco"} <= ctx0):
        fails.append(f"ctx 0 did not expose its overlay's Mac fonts "
                     f"(Menlo/Monaco missing) — overlay not applied: {sorted(ctx0)}")
    if {"Menlo", "Monaco"} & ctx1:
        fails.append(f"ctx 1 exposed Menlo/Monaco that its overlay excludes — "
                     f"it is NOT narrowing to its own container (inherited ctx 0): "
                     f"{sorted(ctx1)}")

    if fails:
        print("FAIL — per-container font narrowing regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — each container narrows to its own overlay 'fonts' set; "
          "ctx 1 hides fonts ctx 0 shows despite sharing the process whitelist")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
