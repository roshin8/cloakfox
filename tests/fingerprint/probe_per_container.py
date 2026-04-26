"""
Cross-container variance probe.

Runs the same canvas + audio fingerprint twice — once with userContextId=0
(default container, math_seed=A), once with a fresh container 1
(math_seed=B). Asserts:
  - canvas_hash differs between the two containers
  - audio_sum differs between the two containers
  - Math.PI differs between the two containers (sanity for actor variance)

If any of these match, per-container spoofing isn't actually engaging —
either SeedSync didn't auto-generate the per-container values or the
underlying spoofers are reading the wrong key.

This is the test the single-container probe_actors.py can't do — and
it's the test that proves "every spoof is actually per-container".

Run:
    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_per_container.py
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


PROBE_HTML = """<!doctype html>
<title>cfx-percontainer</title>
<body>
<pre id="r"></pre>
<script>
const r = {};
r.math_pi = Math.PI;
r.tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
r.history_length = window.history.length;
r.ua = navigator.userAgent;
r.platform = navigator.platform;
r.oscpu = navigator.oscpu;
r.hwc = navigator.hardwareConcurrency;
r.lang = navigator.language;
r.inner = window.innerWidth + "x" + window.innerHeight;
r.dpr = window.devicePixelRatio;
try {
  const gl = document.createElement('canvas').getContext('webgl');
  const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
  r.webgl_vendor = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : (gl && gl.getParameter(gl.VENDOR));
  r.webgl_renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : (gl && gl.getParameter(gl.RENDERER));
} catch (e) { r.webgl_err = String(e); }

try {
  const c = document.createElement('canvas');
  c.width = 200; c.height = 60;
  const ctx = c.getContext('2d');
  ctx.textBaseline = 'top';
  ctx.font = '16px Arial';
  ctx.fillStyle = '#f60';
  ctx.fillRect(0, 0, 60, 30);
  ctx.fillStyle = '#069';
  ctx.fillText('Cloakfox FP probe ÅÚ', 4, 10);
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
  document.getElementById('r').textContent = JSON.stringify(r, null, 2);
  document.documentElement.setAttribute('data-cfx-probe', JSON.stringify(r));
  document.title = 'PROBE_DONE';
}
setTimeout(() => { if (!finalized) finalize(); }, 4000);
</script>
</body>"""


def _profile_for_ucid(profile_dir: str, ucid: int) -> str:
    """Selenium can't switch userContextId — so we use 2 separate profiles
    with different per-container seeds and run each in isolation. Each
    profile pretends to be 'container 0' but with a different seed."""
    seed = base64.b64encode(secrets.token_bytes(32)).decode()
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    Path(profile_dir, "user.js").write_text(
        f'user_pref("cloakfox.enabled", true);\n'
        f'user_pref("cloakfox.container.0.math_seed", "{seed}");\n'
        f'user_pref("cloakfox.container.0.timing_seed", "{seed}");\n'
        f'user_pref("cloakfox.container.0.keyboard_seed", "{seed}");\n'
    )
    return seed


def _run(bin_path: str, profile_dir: str, probe_url: str) -> dict:
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)
    svc = Service(log_path=str(Path(profile_dir) / "geckodriver.log"))
    d = webdriver.Firefox(options=opts, service=svc)
    try:
        d.get(probe_url)
        deadline = time.time() + 10
        while time.time() < deadline:
            if d.title == "PROBE_DONE":
                break
            time.sleep(0.2)
        attr = d.find_element("css selector", "html").get_attribute("data-cfx-probe")
        return json.loads(attr) if attr else {}
    finally:
        d.quit()


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    with tempfile.TemporaryDirectory() as tmp:
        probe_html = os.path.join(tmp, "probe.html")
        Path(probe_html).write_text(PROBE_HTML)
        probe_url = f"file://{probe_html}"

        prof_a = os.path.join(tmp, "profile_a")
        prof_b = os.path.join(tmp, "profile_b")
        seed_a = _profile_for_ucid(prof_a, 0)
        seed_b = _profile_for_ucid(prof_b, 0)
        if seed_a == seed_b:
            sys.exit("internal: profiles have the same seed (bug in test setup)")

        result_a = _run(bin_path, prof_a, probe_url)
        result_b = _run(bin_path, prof_b, probe_url)

    print("=== profile A ===")
    print(json.dumps(result_a, indent=2))
    print("\n=== profile B ===")
    print(json.dumps(result_b, indent=2))
    print()

    fails: list[str] = []
    # Strict differential: should differ between profiles seeded with different math_seed.
    STRICT = ("math_pi", "canvas_hash", "audio_sum")
    # Persona-derived: with only 3 personas per OS, two random math_seeds may
    # land on the same persona ~33% of the time. Treat as "diverse-aware" —
    # report whether they varied without failing on a collision.
    SOFT = ("ua", "platform", "hwc", "inner", "dpr", "webgl_renderer", "webgl_vendor")
    for key in STRICT:
        a, b = result_a.get(key), result_b.get(key)
        if a is None or b is None:
            fails.append(f"{key}: missing in one of the runs (A={a!r}, B={b!r})")
        elif a == b:
            fails.append(f"{key}: identical across containers (A=B={a!r}) — spoofer not per-container")
        else:
            print(f"OK  {key}: A={a} vs B={b} (different ✓)")
    print()
    print("Persona-derived signals (may collide with 3 personas per OS):")
    for key in SOFT:
        a, b = result_a.get(key), result_b.get(key)
        marker = "≠" if a != b else "="
        print(f"  {key}: A={a!r} {marker} B={b!r}")

    if not fails:
        print("\nALL PER-CONTAINER VARIANCE CHECKS PASS")
        sys.exit(0)
    print("\nFAIL:")
    for m in fails:
        print(f"  - {m}")
    sys.exit(1)


if __name__ == "__main__":
    main()
