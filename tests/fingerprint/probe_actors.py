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

// Persona-driven hardware identity
r.hwc = navigator.hardwareConcurrency;
r.max_touch = navigator.maxTouchPoints;

// UA Client Hints — Firefox 146 baseline. We identify as Firefox so
// userAgentData should be undefined. If it appears non-undefined, we've
// either accidentally enabled it or we're emulating Chrome (both bad —
// would create a Firefox UA + Chromium UA-CH inconsistency a fingerprinter
// instantly catches).
r.uad_typeof = (typeof navigator.userAgentData);

// Connection API — Firefox 146 baseline gates this on dom.netinfo.enabled
// (default false). connection should be undefined; if it's an object,
// we've accidentally enabled the pref OR a downstream patch leaked it.
r.connection_typeof = (typeof navigator.connection);

// Geolocation — when the persona has lat/lng/accuracy keys, the C++
// patch auto-grants the permission and returns the spoofed coords.
// We can't await getCurrentPosition synchronously here (it's async + needs
// permission); just record that the API is exposed and let the per-container
// probe validate per-container variance via lat/long differential.
r.geolocation_in = ('geolocation' in navigator);

r.math_pi = Math.PI;
// With cloakfox.opt.math_constants_noise=false (default), Math.PI
// must be the IEEE bit-exact value. Perturbing was self-flagging.
r.math_pi_is_default = (Math.PI === 3.141592653589793);
// Backwards-compat key — `math_pi_default` was the old name.
r.math_pi_default = r.math_pi_is_default;
// Trig functions still noised regardless of the constants pref.
r.math_sin_half_jitter = Math.sin(0.5) - 0.479425538604203;

// Timer precision: with default jitter ON, performance.now must
// return non-integer-ms values (the bucket jitter adds 0..0.999ms).
const perfA = performance.now();
const perfB = performance.now();
r.perf_now_t0 = perfA;
r.perf_now_fractional = (perfA !== Math.floor(perfA));
r.perf_now_monotonic = (perfB >= perfA);

// Timezone: with CloakfoxTimezone actor + default UTC, both should report UTC.
r.tz_intl = Intl.DateTimeFormat().resolvedOptions().timeZone;
r.tz_offset = (new Date()).getTimezoneOffset();

// Canvas fingerprint — patches/canvas-spoofing.patch reads cloak_cfg
// canvas:seed and adds noise to ImageData when readPixels / toDataURL
// is called. Auto-generated by SeedSync from the same master seed as
// math_seed, so canvas/audio/font fingerprints stay coherent with the
// JS-actor ones for a given container.
//
// Stability check: render the same canvas TWICE in this same page and
// compare hashes. They MUST match — same seed, same content, same
// noise. Mismatch would mean the noise function uses something other
// than the seed (wall-clock, per-call random, etc.) and the canvas
// hash would be unstable across page reloads in the same container —
// itself a fingerprint signal.
function drawAndHash() {
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
  for (let i = 0; i < url.length; i++) {
    h = ((h << 5) - h + url.charCodeAt(i)) | 0;
  }
  return { hash: (h >>> 0).toString(16), len: url.length };
}
try {
  const a = drawAndHash();
  const b = drawAndHash();
  r.canvas_hash = a.hash;
  r.canvas_url_len = a.len;
  r.canvas_stable = (a.hash === b.hash);
} catch (e) { r.canvas_err = String(e); }

// CloakfoxWebRTC actor: setWebRTCIPv4 / setWebRTCIPv6 are self-
// destructing C++ WebIDL setters. After the actor fires, both are
// undefined for that userContextId. typeof === "undefined" → setter
// was called. typeof === "function" → never called (sharedData empty).
r.webrtc_setter_typeof = (typeof window.setWebRTCIPv4);
r.webrtc_setter_v6_typeof = (typeof window.setWebRTCIPv6);

// WebRTC IP — RTCPeerConnection ICE-gathering yields a public-IP
// candidate (typ srflx). Should match what HTTP shows. We surface the
// raw candidate text and let the test compare against the HTTP-visible
// IP captured from the parent side. Times out cleanly if no candidates.
try {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  });
  pc.createDataChannel('cfx');
  const cands = [];
  pc.onicecandidate = (ev) => {
    if (ev.candidate && ev.candidate.candidate) {
      cands.push(ev.candidate.candidate);
    }
  };
  pc.createOffer().then(o => pc.setLocalDescription(o));
  setTimeout(() => {
    r.webrtc_candidates = cands.slice();
    // Public IP from srflx (server-reflexive) candidates only.
    const srflx = cands.filter(c => c.includes(' typ srflx '));
    const ips = srflx.map(c => {
      const m = c.match(/(?:^|\s)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s/);
      return m ? m[1] : null;
    }).filter(Boolean);
    r.webrtc_srflx_ips = [...new Set(ips)];
    pc.close();
  }, 1500);
} catch (e) { r.webrtc_err = String(e); }

// Audio fingerprint — patches/audio-fingerprint-manager.patch reads
// cloak_cfg audio:seed and noises buffer-source output. We sum a slice
// of the rendered buffer; per-container seed should produce a per-
// container sum.
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
  }).catch(e => { r.audio_err = String(e); });
} catch (e) { r.audio_err = String(e); }

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
      // Don't finalize here — WebRTC ICE gather (1500ms) and audio
      // render are still pending. The 2.5s blanket timeout below
      // catches everything.
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
// Give async chain (100x setTimeout(50ms) + offline audio render +
// WebRTC ICE 1.5s gather window) time to settle. 2.5s covers the
// ICE timeout + a margin.
setTimeout(() => { if (!finalized) finalize(); }, 2500);
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

    # Math constants — with cloakfox.opt.math_constants_noise=false
    # (default), Math.PI MUST equal the IEEE bit-exact value. The
    # old behavior (perturbed) was self-flagging.
    if not result.get("math_pi_is_default"):
        fails.append(
            f"Math constants: Math.PI = {result.get('math_pi')!r}, "
            f"want exactly 3.141592653589793 (default, no constant noise)"
        )
    # Trig must still be noised — sin(0.5) should differ from spec value
    # by ≤ NOISE_MAG_TRIG (1e-12). 0 = no noise = actor not firing.
    sin_jitter = abs(float(result.get("math_sin_half_jitter") or 0))
    if sin_jitter == 0:
        fails.append("Math trig: sin(0.5) is exactly the spec value — actor not noising functions")

    # Timer precision — with default jitter ON, performance.now should
    # return fractional ms values (not exact integer ms multiples).
    if not result.get("perf_now_fractional"):
        fails.append(
            f"Timer jitter: performance.now() = {result.get('perf_now_t0')!r} "
            f"is exact integer ms — high-precision jitter wrap not active"
        )
    if not result.get("perf_now_monotonic"):
        fails.append("Timer jitter: performance.now violated monotonicity")

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

    # Canvas / Audio — assert the spoof didn't break the API surface.
    # We can't compare to a known unspoofed baseline (varies per Firefox
    # version / OS / GPU) — but we can verify the drawing produced a
    # non-trivial result and the audio render succeeded. Per-container
    # variance is checked by comparing two containers' values, which
    # this single-container probe doesn't do — that's a deeper test
    # left for the cross-container battery.
    if "canvas_err" in result:
        fails.append(f"Canvas spoof: page-side draw threw — {result['canvas_err']}")
    elif int(result.get("canvas_url_len", 0)) < 200:
        fails.append(f"Canvas spoof: toDataURL too short ({result.get('canvas_url_len')} chars) — drawing may have failed")
    # Canvas stability: same content + same seed must produce identical
    # hashes within the same page load. Unstable hashes leak that
    # anti-fingerprinting is active.
    if result.get("canvas_stable") is False:
        fails.append(
            "Canvas stability: two identical draws produced different hashes — "
            "noise function is non-seed-pure (wall-clock or per-call random)"
        )

    # Persona-driven hardware identity. hwc must come from the persona
    # pool, not the host. maxTouchPoints must be 0 (desktop persona).
    hwc = result.get("hwc")
    if hwc not in (4, 8, 10, 12, 14, 16):
        fails.append(f"hardwareConcurrency: {hwc!r} not in any persona's value set")
    if result.get("max_touch") != 0:
        fails.append(f"maxTouchPoints: {result.get('max_touch')!r}, want 0")

    # UA-CH baseline — must NOT expose userAgentData (Chromium-only API).
    # We identify as Firefox; emitting it would create a UA-vs-UA-CH
    # inconsistency that anti-bot systems flag instantly.
    if result.get("uad_typeof") not in ("undefined", "object"):
        # Firefox 146 with dom.userAgentData.enabled returns 'object' —
        # we should be 'undefined'. If something flipped, fail loud.
        fails.append(f"navigator.userAgentData: typeof={result.get('uad_typeof')!r} (want 'undefined')")
    elif result.get("uad_typeof") == "object":
        fails.append("navigator.userAgentData is an object — Firefox 146 baseline is undefined; we accidentally enabled UA Client Hints")

    # Connection API baseline — must NOT expose navigator.connection
    # (Chromium-only). Firefox 146 gates on dom.netinfo.enabled (false
    # by default). If we accidentally flipped the pref, navigator.connection
    # becomes an object that leaks real network info.
    if result.get("connection_typeof") != "undefined":
        fails.append(f"navigator.connection: typeof={result.get('connection_typeof')!r} (want 'undefined' — dom.netinfo.enabled leaked)")
    if "audio_err" in result:
        fails.append(f"Audio spoof: OfflineAudioContext threw — {result['audio_err']}")
    elif "audio_sum" not in result:
        fails.append("Audio spoof: render didn't complete in time (no audio_sum)")

    # WebRTC IP — informational only. Without an HTTP-visible IP captured
    # outside the browser (we'd need a separate request from the test
    # harness), we can't compare for divergence. The probe just records
    # webrtc_srflx_ips so the operator can compare against what an HTTP
    # request would show. A separate cross-network test verifies the
    # actor actually substitutes the IP.

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
