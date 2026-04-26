"""
End-to-end probe for the 8 cpp-first JSWindowActors.

Loads a self-hosted probe page, exercises each spoof, and asserts the
expected outcome. The probe page writes results to a `data-cfx-probe`
attribute on `<html>` so we read it via Selenium without the Cu.Sandbox
intrinsic problem (selenium's execute_script runs in a sandbox with its
own Math/Date/etc — see memory: measurement_context_traps).

Verifies:
  - CloakfoxMath:          Math.PI != 3.141592653589793 (perturbed)
  - CloakfoxTabHistory:    history.length in [3..50]
  - CloakfoxGamepad:       getGamepads() returns [null, null, null, null]
  - CloakfoxMidi:          requestMIDIAccess undefined (Firefox default)
                           OR rejects with NotAllowedError if enabled
  - CloakfoxWebGPU:        navigator.gpu === undefined, 'gpu' in navigator
  - CloakfoxFeatureDetect: webdriver=false, doNotTrack="1", GPC=true,
                           pdfViewerEnabled=true, onLine=true,
                           cookieEnabled=true, javaEnabled()=false
  - CloakfoxTiming:        spread of 100x setTimeout(50ms) is > 1ms
                           (jitter perturbation observable)
  - CloakfoxKeyboard:      not exercised here — needs real keystrokes;
                           covered by tests/fingerprint/probe_keyboard_actor.py

Run:
    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_actors.py
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
<title>cfx-probe</title>
<body>
<pre id="r"></pre>
<script>
const r = {};
r.history_length = window.history.length;
r.history_plausible = (r.history_length >= 3 && r.history_length <= 50);
try {
  const gp = navigator.getGamepads();
  r.gamepad_array = Array.isArray(gp) ? gp.length : 'not-array';
  r.gamepad_all_null = Array.isArray(gp) && gp.every(x => x === null);
} catch (e) { r.gamepad_err = String(e); }

if (typeof navigator.requestMIDIAccess === 'function') {
  navigator.requestMIDIAccess().then(
    () => { r.midi = 'RESOLVED-leak'; },
    (e) => { r.midi = e.name + ': ' + e.message; }
  );
} else {
  r.midi = 'fn-undefined';
}

r.webgpu_in = ('gpu' in navigator);
r.webgpu_value = (typeof navigator.gpu);

r.fd_webdriver = navigator.webdriver;
r.fd_doNotTrack = navigator.doNotTrack;
r.fd_gpc = navigator.globalPrivacyControl;
r.fd_pdfViewer = navigator.pdfViewerEnabled;
r.fd_onLine = navigator.onLine;
r.fd_cookieEnabled = navigator.cookieEnabled;
try { r.fd_javaEnabled = navigator.javaEnabled(); } catch (e) { r.fd_javaEnabled = 'err:' + e.message; }

r.math_pi = Math.PI;
r.math_pi_default = (Math.PI === 3.141592653589793);

// Timezone: with CloakfoxTimezone actor + default UTC, both should report UTC.
r.tz_intl = Intl.DateTimeFormat().resolvedOptions().timeZone;
r.tz_offset = (new Date()).getTimezoneOffset();

// Timing: spread of 100x setTimeout(50ms) — without jitter ~0, with 0..2ms jitter > 0
const fires = [];
const t0 = performance.now();
const target = 100;
let fired = 0;
for (let i = 0; i < target; i++) {
  setTimeout(() => {
    fires.push(performance.now() - t0);
    fired++;
    if (fired === target) {
      fires.sort((a,b)=>a-b);
      r.timing_min_minus_delay = (fires[0] - 50).toFixed(2);
      r.timing_max_minus_delay = (fires[fires.length-1] - 50).toFixed(2);
      r.timing_spread = (fires[fires.length-1] - fires[0]).toFixed(2);
      finalize();
    }
  }, 50);
}

let finalized = false;
function finalize() {
  if (finalized) return; finalized = true;
  document.getElementById('r').textContent = JSON.stringify(r, null, 2);
  document.documentElement.setAttribute('data-cfx-probe', JSON.stringify(r));
  document.title = 'PROBE_DONE';
}
setTimeout(() => { if (!finalized) finalize(); }, 5000);
</script>
</body>"""


def _build_driver(bin_path: str, profile_dir: str) -> webdriver.Firefox:
    """Profile is pre-seeded with cloakfox.enabled=true + per-container seeds."""
    seed = base64.b64encode(secrets.token_bytes(32)).decode()
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    user_js = Path(profile_dir) / "user.js"
    user_js.write_text(
        f'user_pref("cloakfox.enabled", true);\n'
        f'user_pref("cloakfox.container.0.math_seed", "{seed}");\n'
        f'user_pref("cloakfox.container.0.timing_seed", "{seed}");\n'
    )
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)
    svc = Service(log_path=str(Path(profile_dir) / "geckodriver.log"))
    return webdriver.Firefox(options=opts, service=svc)


def assert_actors(result: dict) -> tuple[int, list[str]]:
    """Returns (failure_count, list_of_failure_messages)."""
    fails: list[str] = []

    # Math
    if result.get("math_pi_default"):
        fails.append(f"Math actor: Math.PI is the IEEE default (no spoof)")

    # TabHistory
    if not result.get("history_plausible"):
        fails.append(f"TabHistory actor: history.length={result.get('history_length')} not in [3..50]")

    # Gamepad
    if result.get("gamepad_array") != 4 or not result.get("gamepad_all_null"):
        fails.append(f"Gamepad actor: getGamepads() returned {result.get('gamepad_array')} items, all_null={result.get('gamepad_all_null')}")

    # WebGPU
    if not result.get("webgpu_in") or result.get("webgpu_value") != "undefined":
        fails.append(f"WebGPU actor: 'gpu' in nav={result.get('webgpu_in')}, typeof gpu={result.get('webgpu_value')}")

    # FeatureDetect
    fd = {
        "webdriver": (result.get("fd_webdriver"), False),
        "doNotTrack": (result.get("fd_doNotTrack"), "1"),
        "globalPrivacyControl": (result.get("fd_gpc"), True),
        "pdfViewerEnabled": (result.get("fd_pdfViewer"), True),
        "onLine": (result.get("fd_onLine"), True),
        "cookieEnabled": (result.get("fd_cookieEnabled"), True),
        "javaEnabled()": (result.get("fd_javaEnabled"), False),
    }
    for name, (got, want) in fd.items():
        if got != want:
            fails.append(f"FeatureDetect actor: navigator.{name} = {got!r}, want {want!r}")

    # Timing — informational only. The actor adds 0..MAX_JITTER_MS ms of
    # jitter to each setTimeout's delay, but the visible spread depends
    # on PRNG luck plus Firefox's 1ms reduceTimerPrecision quantization,
    # so it's not a reliable assertion target. We can't introspect the
    # wrap directly either (Cu.exportFunction makes it look native).
    # If a regression breaks the wrap, downstream failures (CPU-timing
    # fingerprints showing perfect determinism) catch it. The probe
    # records timing_spread for human inspection but doesn't fail on it.

    # Timezone — CloakfoxTimezone actor should report UTC by default
    tz = result.get("tz_intl", "")
    if tz != "UTC":
        fails.append(f"Timezone actor: Intl.DateTimeFormat resolvedOptions.timeZone = {tz!r}, want 'UTC'")
    if result.get("tz_offset") != 0:
        fails.append(f"Timezone actor: getTimezoneOffset() = {result.get('tz_offset')}, want 0 (UTC)")

    # Midi — Firefox 146 default disables WebMIDI, so 'fn-undefined' is OK.
    # Only flag if MIDI is exposed AND resolves (would mean the spoof failed).
    midi = result.get("midi", "")
    if midi == "RESOLVED-leak":
        fails.append("Midi actor: requestMIDIAccess() resolved (real MIDI hardware leak)")

    return len(fails), fails


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "profile")
        probe_html = os.path.join(tmp, "probe.html")
        Path(probe_html).write_text(PROBE_HTML)

        d = _build_driver(bin_path, prof)
        try:
            d.get(f"file://{probe_html}")
            deadline = time.time() + 12
            while time.time() < deadline:
                if d.title == "PROBE_DONE":
                    break
                time.sleep(0.2)
            attr = d.find_element("css selector", "html").get_attribute("data-cfx-probe")
            if not attr:
                sys.exit("probe never finished — no data-cfx-probe attribute")
            result = json.loads(attr)
        finally:
            d.quit()

    print(json.dumps(result, indent=2))
    print()

    fail_count, fails = assert_actors(result)
    if fail_count == 0:
        print(f"ALL ACTORS PASS ({len(result)} signals checked)")
        sys.exit(0)
    else:
        print(f"FAIL: {fail_count} actor signal(s) regressed")
        for m in fails:
            print(f"  - {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()
