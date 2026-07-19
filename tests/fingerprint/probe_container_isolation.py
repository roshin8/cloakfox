"""
True per-userContextId isolation probe.

This is the test probe_per_container.py can't do. probe_per_container.py
varies the *seed* across two profiles that both run as container 0, so it
proves seed variance but NOT that a non-default container reads its own
cloak_cfg_<ucid>. That gap mattered: the C++ MaskConfig getters used to
drop the container id and always read cloak_cfg_0, so every non-default
container silently reused container 0's fingerprint.

Here we run ONE browser with two different per-container overlays:

    cloakfox.s.cloak_cfg_0 = {"canvas:seed": SEED_0, "audio:seed": SEED_0}
    cloakfox.s.cloak_cfg_1 = {"canvas:seed": SEED_1, "audio:seed": SEED_1}

then open the probe page once in the default container (userContextId=0)
and once in container 1 (userContextId=1), via a chrome-context
gBrowser.addTab (Selenium can't set userContextId itself). We assert the
canvas + audio fingerprints DIFFER between the two containers.

Without the getter fix, GetSeed(1) resolves cloak_cfg_0 and the two
containers produce identical hashes -> this test fails. With the fix,
GetSeed(1) resolves cloak_cfg_1 -> hashes differ -> pass.

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

# Two clearly-distinct seeds. The C++ canvas/audio noise is a function of
# the seed, so different seeds must yield different fingerprints.
SEED_0 = 11111
SEED_1 = 99999

PROBE_HTML = """<!doctype html>
<title>cfx-container</title>
<body>
<script>
const r = {};
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
    cfg0 = json.dumps({"canvas:seed": SEED_0, "audio:seed": SEED_0})
    cfg1 = json.dumps({"canvas:seed": SEED_1, "audio:seed": SEED_1})
    Path(profile_dir, "user.js").write_text(
        'user_pref("cloakfox.enabled", true);\n'
        'user_pref("privacy.userContext.enabled", true);\n'
        f'user_pref("cloakfox.s.cloak_cfg_0", {json.dumps(cfg0)});\n'
        f'user_pref("cloakfox.s.cloak_cfg_1", {json.dumps(cfg1)});\n'
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
        opts.add_argument("-remote-allow-system-access")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        svc = Service(log_path=str(Path(prof) / "geckodriver.log"))
        driver = webdriver.Firefox(options=opts, service=svc)
        try:
            res0 = _read_probe_in_container(driver, probe_url, 0)
            res1 = _read_probe_in_container(driver, probe_url, 1)
        finally:
            driver.quit()

    print("=== container 0 (cloak_cfg_0, seed %d) ===" % SEED_0)
    print(json.dumps(res0, indent=2))
    print("\n=== container 1 (cloak_cfg_1, seed %d) ===" % SEED_1)
    print(json.dumps(res1, indent=2))
    print()

    fails: list[str] = []
    for key in ("canvas_hash", "audio_sum"):
        a, b = res0.get(key), res1.get(key)
        if a is None or b is None:
            fails.append(f"{key}: missing (c0={a!r} c1={b!r}) — probe error?")
        elif a == b:
            fails.append(
                f"{key}: IDENTICAL across containers ({a!r}) — non-default "
                f"container is reading cloak_cfg_0, the getter fix is not engaging"
            )
        else:
            print(f"OK  {key}: c0={a!r} != c1={b!r} (per-container ✓)")

    if fails:
        print("\nFAIL:")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("\nPASS: non-default container reads its own cloak_cfg_<ucid>")


if __name__ == "__main__":
    main()
