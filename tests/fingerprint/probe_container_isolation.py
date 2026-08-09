"""
True per-userContextId isolation probe.

This is the test probe_per_container.py can't do. probe_per_container.py
varies the *seed* across two profiles that both run as container 0, so it
proves seed variance but NOT that a non-default container reads its own
cloak_cfg_<ucid>. That gap mattered: the C++ MaskConfig getters used to
drop the container id and always read cloak_cfg_0, so every non-default
container silently reused container 0's fingerprint.

Here we run ONE browser with two TWO NON-DEFAULT containers, each with
its own overlay:

    cloakfox.s.cloak_cfg_1 = {canvas/audio seed A, navigator.userAgent A}
    cloakfox.s.cloak_cfg_2 = {canvas/audio seed B, navigator.userAgent B}

then open the probe in container 1 and container 2 via a chrome-context
gBrowser.addTab (Selenium can't set userContextId itself) and assert the
canvas, audio, AND navigator.userAgent all DIFFER.

Two axes are covered:
  - canvas/audio: the *manager* getters (they pass an explicit ucid).
  - navigator.userAgent: the *context-blind* getters that call
    MaskConfig::GetString with no ucid; these resolve the current
    container via GetContextOverlay's auto-resolve.

Using two NON-DEFAULT containers (1 and 2, not 0 and 1) is the point:
the old ctx-0 mirror could make one non-default container work, but two
simultaneously-configured non-default containers overwrote each other's
cloak_cfg_0 and leaked into one another. If the fixes regress, at least
one signal comes back identical and this test fails.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_container_isolation.py
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

# Two NON-DEFAULT containers with distinct overlays. Using 1 and 2 (not
# 0 and 1) is deliberate: the old ctx-0 mirror could make a single
# non-default container work, but two simultaneously-configured
# non-default containers overwrote each other's cloak_cfg_0. This checks
# both the manager path (canvas/audio seeds) and the context-blind path
# (navigator.userAgent, read via MaskConfig::GetString with no explicit
# ucid -> the GetContextOverlay auto-resolve).
UCID_A, UCID_B = 1, 2
CFG_A = {
    "canvas:seed": 11111,
    "audio:seed": 11111,
    "navigator.userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
}
CFG_B = {
    "canvas:seed": 99999,
    "audio:seed": 99999,
    "navigator.userAgent": "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
}

PROBE_HTML = """<!doctype html>
<title>cfx-container</title>
<body>
<script>
const r = {};
r.ua = navigator.userAgent;
try {
  const c = document.createElement('canvas');
  c.width = 200; c.height = 60;
  const ctx = c.getContext('2d');
  ctx.textBaseline = 'top';
  ctx.font = '16px Arial';
  ctx.fillStyle = '#f60';
  ctx.fillRect(0, 0, 60, 30);
  ctx.fillStyle = '#069';
  ctx.fillText('Cloakfox container probe \\u00c5\\u00da', 4, 10);
  const url = c.toDataURL();
  let h = 0;
  for (let i = 0; i < url.length; i++) h = ((h << 5) - h + url.charCodeAt(i)) | 0;
  r.canvas_hash = (h >>> 0).toString(16);
} catch (e) { r.canvas_err = String(e); }

try {
  const ac = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 4400, 44100);
  const osc = ac.createOscillator();
  osc.type = 'triangle';
  osc.frequency.value = 1000;
  const cmp = ac.createDynamicsCompressor();
  osc.connect(cmp);
  cmp.connect(ac.destination);
  osc.start(0);
  ac.startRendering().then(buf => {
    let sum = 0;
    const data = buf.getChannelData(0);
    for (let i = 4000; i < 4400; i++) sum += Math.abs(data[i]);
    r.audio_sum = sum.toFixed(8);
    finalize();
  }).catch(e => { r.audio_err = String(e); finalize(); });
} catch (e) { r.audio_err = String(e); finalize(); }

let finalized = false;
function finalize() {
  if (finalized) return; finalized = true;
  document.documentElement.setAttribute('data-cfx-probe', JSON.stringify(r));
  document.title = 'PROBE_DONE';
}
setTimeout(finalize, 4000);
</script>
</body>"""

# Chrome-scope script: open `url` in a tab with the given userContextId
# and return the new tab's linked browser's outer window id so we can find
# its content window handle. We use the system principal as the
# triggering principal (required by addTab for file:// loads from chrome).
OPEN_CONTAINER_TAB = """
const [url, userContextId] = arguments;
const win = Services.wm.getMostRecentWindow('navigator:browser');
const gBrowser = win.gBrowser;
const tab = gBrowser.addTab(url, {
  userContextId,
  triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
});
gBrowser.selectedTab = tab;
return true;
"""


def _read_probe_in_container(driver, probe_url: str, ucid: int) -> dict:
    """Open probe_url in a tab bound to userContextId=ucid, wait for the
    probe to finish, and return its result dict."""
    before = set(driver.window_handles)

    driver.set_context("chrome")
    try:
        driver.execute_script(OPEN_CONTAINER_TAB, probe_url, ucid)
    finally:
        driver.set_context("content")

    # Wait for the new content tab handle to appear, then switch to it.
    deadline = time.time() + 10
    new_handle = None
    while time.time() < deadline:
        extra = set(driver.window_handles) - before
        if extra:
            new_handle = extra.pop()
            break
        time.sleep(0.1)
    if not new_handle:
        raise RuntimeError(f"container {ucid}: new tab handle never appeared")

    driver.switch_to.window(new_handle)
    deadline = time.time() + 12
    while time.time() < deadline:
        if driver.title == "PROBE_DONE":
            break
        time.sleep(0.2)
    attr = driver.find_element("css selector", "html").get_attribute("data-cfx-probe")
    return json.loads(attr) if attr else {}


def _profile(profile_dir: str) -> None:
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    # "fonts"/"fonts:spacing_seed" are required for these overlays to SURVIVE
    # startup: CloakfoxSeedSync.needsCfgRebuild() regenerates any cloak_cfg
    # missing them. Without these, BOTH containers get random personas — which
    # still differ from each other, so the isolation assertion passes while
    # testing nothing it injected. Distinct spacing seeds keep the two
    # containers distinguishable for the right reason.
    cfg_a = json.dumps({"fonts": ["Arial", "Verdana", "Georgia"],
                        "fonts:spacing_seed": 0xA11CE, **CFG_A})
    cfg_b = json.dumps({"fonts": ["Arial", "Verdana", "Georgia"],
                        "fonts:spacing_seed": 0xB0B, **CFG_B})
    Path(profile_dir, "user.js").write_text(
        'user_pref("cloakfox.enabled", true);\n'
        'user_pref("privacy.userContext.enabled", true);\n'
        f'user_pref("cloakfox.s.cloak_cfg_{UCID_A}", {json.dumps(cfg_a)});\n'
        f'user_pref("cloakfox.s.cloak_cfg_{UCID_B}", {json.dumps(cfg_b)});\n'
    )


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    with tempfile.TemporaryDirectory() as tmp:
        probe_html = os.path.join(tmp, "probe.html")
        Path(probe_html).write_text(PROBE_HTML)
        probe_url = f"file://{probe_html}"

        prof = os.path.join(tmp, "profile")
        _profile(prof)

        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        # Required so Marionette will switch to chrome context (needed to
        # open a tab bound to a specific userContextId).
        opts.add_argument("-profile")
        opts.add_argument(prof)
        svc = Service(service_args=["--allow-system-access"], log_path=str(Path(prof) / "geckodriver.log"))
        driver = webdriver.Firefox(options=opts, service=svc)
        try:
            res_a = _read_probe_in_container(driver, probe_url, UCID_A)
            res_b = _read_probe_in_container(driver, probe_url, UCID_B)
        finally:
            driver.quit()

    print(f"=== container {UCID_A} (cloak_cfg_{UCID_A}) ===")
    print(json.dumps(res_a, indent=2))
    print(f"\n=== container {UCID_B} (cloak_cfg_{UCID_B}) ===")
    print(json.dumps(res_b, indent=2))
    print()

    # canvas_hash / audio_sum: manager path (explicit ucid). ua: context-blind
    # path (MaskConfig::GetString with no ucid -> GetContextOverlay auto-resolve).
    fails: list[str] = []
    for key in ("canvas_hash", "audio_sum", "ua"):
        a, b = res_a.get(key), res_b.get(key)
        if a is None or b is None:
            fails.append(f"{key}: missing (c{UCID_A}={a!r} c{UCID_B}={b!r}) — probe error?")
        elif a == b:
            path = "context-blind auto-resolve" if key == "ua" else "manager getter"
            fails.append(
                f"{key}: IDENTICAL across two non-default containers ({a!r}) — "
                f"the {path} is not isolating per container"
            )
        else:
            print(f"OK  {key}: c{UCID_A}={a!r} != c{UCID_B}={b!r} (per-container ✓)")

    if fails:
        print("\nFAIL:")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("\nPASS: non-default container reads its own cloak_cfg_<ucid>")


if __name__ == "__main__":
    main()
