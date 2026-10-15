"""
Cross-container variance probe.

Runs a local HTTP page in the default container and a freshly created named
container in one disposable profile. Verifies default-container reload stability
and asserts:
  - canvas_hash differs between the two containers
  - audio_sum differs between the two containers
  - Math.sin(0.5) differs between the two containers

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
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from probe_focus_masking import chrome


PROBE_HTML = """<!doctype html>
<title>cfx-percontainer</title>
<body>
<pre id="r"></pre>
<script>
const r = {};
r.math_pi = Math.PI;
// Math.sin is the per-container canary now: with cloakfox.opt.
// math_constants_noise=false (default), Math.PI is bit-exact across
// all containers (3.141592653589793). The trig FUNCTIONS still get
// per-call noise from the site-derived Math seed, so Math.sin(0.5) varies per
// container and serves as the strict-differential signal.
r.math_sin_jitter = Math.sin(0.5);
r.tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
r.history_length = window.history.length;
r.ua = navigator.userAgent;
r.platform = navigator.platform;
r.oscpu = navigator.oscpu;
r.hwc = navigator.hardwareConcurrency;
r.lang = navigator.language;
r.inner = window.innerWidth + "x" + window.innerHeight;
r.outer = window.outerWidth + "x" + window.outerHeight;
r.screen = screen.width + "x" + screen.height;
r.avail = screen.availWidth + "x" + screen.availHeight;
r.dpr = window.devicePixelRatio;
// Coherence check: avail dimensions must fit within screen, inner
// must fit within outer, outer must fit within avail.
r.dim_coherent = (
  screen.availWidth <= screen.width &&
  screen.availHeight <= screen.height &&
  window.outerWidth <= screen.availWidth &&
  window.outerHeight <= screen.availHeight &&
  window.innerWidth <= window.outerWidth &&
  window.innerHeight <= window.outerHeight
);
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

// Geolocation — coords come from C++ when persona has the keys.
// Async (callback). Fire it; finalize() is gated on completion below.
r.geo_pending = true;
try {
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      r.geo_lat = pos.coords.latitude;
      r.geo_lng = pos.coords.longitude;
      r.geo_acc = pos.coords.accuracy;
      r.geo_pending = false;
    },
    (err) => {
      r.geo_err = err.code + ": " + err.message;
      r.geo_pending = false;
    },
    { timeout: 1000 }
  );
} catch (e) { r.geo_err = String(e); r.geo_pending = false; }

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
    // Don't finalize here — geo callback may still be pending. Single
    // 4000ms blanket below captures everything.
  }).catch(e => { r.audio_err = String(e); });
} catch (e) { r.audio_err = String(e); }

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


def _profile(profile_dir: str) -> str:
    """Seed a disposable default container; named container uses SeedSync."""
    seed = base64.b64encode(secrets.token_bytes(32)).decode()
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    Path(profile_dir, "user.js").write_text(
        f'user_pref("cloakfox.enabled", true);\n'
        f'user_pref("cloakfox.container.0.math_seed", "{seed}");\n'
        f'user_pref("cloakfox.container.0.timing_seed", "{seed}");\n'
        f'user_pref("cloakfox.container.0.keyboard_seed", "{seed}");\n'
    )
    return seed


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    class Page(BaseHTTPRequestHandler):
        def do_GET(self):
            body = PROBE_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-container-") as tmp:
            profile = str(Path(tmp, "profile"))
            _profile(profile)
            opts = Options()
            opts.binary_location = bin_path
            opts.add_argument("--headless")
            opts.add_argument("-profile")
            opts.add_argument(profile)
            d = webdriver.Firefox(options=opts, service=Service(
                service_args=["--allow-system-access"],
                log_output=str(Path(tmp, "geckodriver.log"))))
            try:
                url = f"http://127.0.0.1:{server.server_port}/"
                def collect():
                    d.get(url)
                    deadline = time.monotonic() + 15
                    while d.title != "PROBE_DONE" and time.monotonic() < deadline:
                        time.sleep(.1)
                    attr = d.find_element("css selector", "html").get_attribute("data-cfx-probe")
                    assert attr, "page did not finish collecting fingerprints"
                    return json.loads(attr)
                result_a = collect()
                repeated_a = collect()
                for key in ("math_sin_jitter", "canvas_hash", "audio_sum"):
                    assert result_a[key] == repeated_a[key], f"same-container reload changed {key}"
                before = set(d.window_handles)
                chrome(d, """
                  const {ContextualIdentityService: cis} = ChromeUtils.importESModule(
                    'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
                  const id=cis.create('Variance control','fingerprint','green').userContextId;
                  gBrowser.selectedTab=gBrowser.addTab(arguments[0],{userContextId:id,
                    triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                """, url)
                d.switch_to.window(next(handle for handle in d.window_handles if handle not in before))
                result_b = collect()
                configs = chrome(d, """
                  return [0,gBrowser.selectedBrowser.browsingContext.originAttributes.userContextId].map(id=>
                    JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id)));
                """)
                assert configs[0]["fingerprint:secret"] != configs[1]["fingerprint:secret"], "container secrets collided"
            finally:
                d.quit()
    finally:
        server.shutdown()
        server.server_close()

    print("=== default container ===")
    print(json.dumps(result_a, indent=2))
    print("\n=== named container ===")
    print(json.dumps(result_b, indent=2))
    print()

    fails: list[str] = []
    # Strict differential: separate containers have different master secrets.
    # Math.PI is no longer the canary — it's intentionally bit-exact in
    # the new default (math_constants_noise=false). Use Math.sin(0.5)
    # which gets per-call noise from the site-derived Math seed.
    STRICT = ("math_sin_jitter", "canvas_hash", "audio_sum")
    # Persona-derived: with only 3 personas per OS, two container math_seeds may
    # land on the same persona ~33% of the time. Treat as "diverse-aware" —
    # report whether they varied without failing on a collision.
    SOFT = ("ua", "platform", "hwc", "inner", "outer", "screen", "avail", "dpr", "webgl_renderer", "webgl_vendor", "geo_lat", "geo_lng")
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
    print()
    # Hard requirement: dimensions must be internally coherent in BOTH
    # profiles. Without sync, fpscanner-style consistency checks reject.
    for k, name in [("dim_coherent", "screen/window dim coherence")]:
        for label, res in [("A", result_a), ("B", result_b)]:
            v = res.get(k)
            if v is not True:
                fails.append(f"{name} ({label}): screen={res.get('screen')} avail={res.get('avail')} outer={res.get('outer')} inner={res.get('inner')} — geometry not nested correctly")

    if not fails:
        print("\nALL PER-CONTAINER VARIANCE CHECKS PASS")
        sys.exit(0)
    print("\nFAIL:")
    for m in fails:
        print(f"  - {m}")
    sys.exit(1)


if __name__ == "__main__":
    main()
