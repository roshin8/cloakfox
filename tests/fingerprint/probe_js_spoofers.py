"""
Broad JS spoofer probe — dumps the current value of ~40 fingerprint
signals from a running Cloakfox build and compares against "spoofed vs
unspoofed" heuristics, so you can tell at a glance which spoofers are
actually firing.

This exists because live testing of Math.PI surfaced four stacked bugs
(double-XOR seed cancellation, noise-below-ULP, Proxy invariant
violation, copy-before-override silent failure) that shipped for months.
The rest of the 55 spoofer files might have analogous issues that nobody
has live-verified. This script is the cheap first pass.

Output:
  - A grouped table per signal: value, heuristic verdict
  - A JSON blob for machine processing
  - An exit code: 0 if at least 90% of heuristics say "spoofed", non-zero
    otherwise (rough canary — hand-inspect the table for specifics)

Heuristics are deliberately loose — we're looking for "did the spoofer
do ANYTHING" not "did it do the right thing." A green verdict means the
signal is NOT the stock Cloakfox/Firefox default. A red verdict means
either the spoofer didn't run or it returned the default (needs
investigation).

Run:

    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_js_spoofers.py
"""

from __future__ import annotations

import json
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


# Probe runs in page context via <script> injection, collects into a
# single JSON payload written to <pre id="_probe">. Wrap each probe in
# try/catch so one failure doesn't break the whole run.
PROBE_SCRIPT = r"""
const s = document.createElement('script');
s.textContent = `
  async function probe() {
    const r = {};
    const safe = (name, fn) => { try { r[name] = fn(); } catch (e) { r[name] = 'ERR: ' + e.message; } };

    // Navigator basics
    safe('userAgent', () => navigator.userAgent);
    safe('platform', () => navigator.platform);
    safe('vendor', () => navigator.vendor);
    safe('hardwareConcurrency', () => navigator.hardwareConcurrency);
    safe('deviceMemory', () => navigator.deviceMemory);
    safe('languages', () => JSON.stringify(navigator.languages));
    safe('language', () => navigator.language);
    safe('cookieEnabled', () => navigator.cookieEnabled);
    safe('doNotTrack', () => navigator.doNotTrack);
    safe('maxTouchPoints', () => navigator.maxTouchPoints);
    safe('webdriver', () => navigator.webdriver);

    // Client hints
    safe('userAgentData.brands', () => navigator.userAgentData ? JSON.stringify(navigator.userAgentData.brands) : null);
    safe('userAgentData.platform', () => navigator.userAgentData ? navigator.userAgentData.platform : null);
    safe('userAgentData.mobile', () => navigator.userAgentData ? navigator.userAgentData.mobile : null);

    // Screen
    safe('screen.width', () => screen.width);
    safe('screen.height', () => screen.height);
    safe('screen.availWidth', () => screen.availWidth);
    safe('screen.availHeight', () => screen.availHeight);
    safe('screen.colorDepth', () => screen.colorDepth);
    safe('devicePixelRatio', () => devicePixelRatio);
    safe('screen.orientation.type', () => screen.orientation ? screen.orientation.type : null);

    // Timezone
    safe('Date.getTimezoneOffset', () => new Date().getTimezoneOffset());
    safe('Intl.timeZone', () => Intl.DateTimeFormat().resolvedOptions().timeZone);
    safe('Intl.locale', () => Intl.DateTimeFormat().resolvedOptions().locale);

    // Math (known working post-fix)
    safe('Math.PI', () => Math.PI);
    safe('Math.E', () => Math.E);
    safe('Math.sin(0.5)', () => Math.sin(0.5));

    // Canvas toDataURL
    safe('canvas.toDataURL-hash-8', () => {
      const c = document.createElement('canvas');
      c.width = 200; c.height = 60;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#f60'; ctx.fillRect(0, 0, 200, 60);
      ctx.fillStyle = '#069'; ctx.font = '20px Arial'; ctx.fillText('cloakfox', 10, 40);
      const d = c.toDataURL();
      // Take the first 8 chars after the comma, those change if toDataURL adds noise
      const comma = d.indexOf(',');
      return d.slice(comma + 1, comma + 9);
    });

    // WebGL
    safe('WebGL.vendor', () => {
      const c = document.createElement('canvas').getContext('webgl');
      const e = c && c.getExtension('WEBGL_debug_renderer_info');
      return e ? c.getParameter(e.UNMASKED_VENDOR_WEBGL) : 'no-ext';
    });
    safe('WebGL.renderer', () => {
      const c = document.createElement('canvas').getContext('webgl');
      const e = c && c.getExtension('WEBGL_debug_renderer_info');
      return e ? c.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'no-ext';
    });
    safe('WebGL.version', () => {
      const c = document.createElement('canvas').getContext('webgl');
      return c ? c.getParameter(c.VERSION) : null;
    });

    // AudioContext fingerprint — just check the sampleRate (spoofers may noise it)
    safe('AudioContext.sampleRate', () => {
      try { const a = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 44100, 44100);
            return a.sampleRate; } catch (e) { return 'n/a'; }
    });

    // Permissions
    safe('navigator.permissions', () => typeof navigator.permissions);
    // Storage estimate
    try { const e = await navigator.storage.estimate(); r['storage.estimate.quota'] = e.quota; r['storage.estimate.usage'] = e.usage; } catch (e) { r['storage.estimate'] = 'ERR'; }

    // Battery
    try { if (navigator.getBattery) { const b = await navigator.getBattery(); r['battery.level'] = b.level; r['battery.charging'] = b.charging; } else { r['battery'] = 'not-implemented'; } } catch (e) { r['battery'] = 'ERR'; }

    // Vibration
    safe('navigator.vibrate', () => typeof navigator.vibrate === 'function' ? navigator.vibrate([100]) : null);

    // MediaDevices
    try { const list = await navigator.mediaDevices.enumerateDevices(); r['mediaDevices.count'] = list.length; r['mediaDevices.kinds'] = JSON.stringify([...new Set(list.map(d => d.kind))]); } catch (e) { r['mediaDevices'] = 'ERR'; }

    // Speech voices
    safe('speechSynthesis.voices.length', () => speechSynthesis.getVoices().length);

    // WebRTC - check if createOffer leaks IP
    safe('RTCPeerConnection', () => typeof RTCPeerConnection);

    // WebGPU
    safe('navigator.gpu', () => typeof navigator.gpu);

    // Gamepad / MIDI
    safe('navigator.getGamepads', () => typeof navigator.getGamepads);
    safe('navigator.requestMIDIAccess', () => typeof navigator.requestMIDIAccess);

    // Window
    safe('window.name', () => window.name);

    // Self-destructing WebIDL markers (should be 'undefined' after inject fired)
    safe('setCanvasSeed', () => typeof setCanvasSeed);
    safe('setHttp2Profile', () => typeof setHttp2Profile);
    safe('setHttp3Profile', () => typeof setHttp3Profile);
    safe('setNavigatorUserAgent', () => typeof setNavigatorUserAgent);

    const out = document.createElement('pre');
    out.id = '_probe';
    out.textContent = JSON.stringify(r);
    document.body.appendChild(out);
  }
  probe();
`;
document.body.appendChild(s);
"""


# Heuristics: for each key, declare what "unspoofed" looks like on MY
# machine (real values on macOS ARM, Cloakfox default UA). A match means
# "spoofer didn't run or returned the default." Flexible — a dict can
# also list expected-spoofed markers.
UNSPOOFED_MARKERS = {
    "userAgent": lambda v: "Cloakfox/" in v,                    # native UA leaked
    "platform": lambda v: v == "MacIntel" or v == "Linux x86_64",  # real platform
    "hardwareConcurrency": lambda v: v in (8, 10, 12, 16),       # real M-series cores
    "Math.PI": lambda v: v == 3.141592653589793,                 # IEEE default
    "Math.E": lambda v: v == 2.718281828459045,
    "Math.sin(0.5)": lambda v: abs(v - 0.479425538604203) < 1e-17,
    "WebGL.vendor": lambda v: "Apple" in str(v) or "Mesa" in str(v),
    "WebGL.renderer": lambda v: "Apple" in str(v) or "Mesa" in str(v),
    "screen.colorDepth": lambda v: v == 24,
    "Date.getTimezoneOffset": None,  # depends on real tz; skip heuristic
    "setCanvasSeed": lambda v: v == "function",  # if still present, inject never ran
}


def _verdict(key, value):
    h = UNSPOOFED_MARKERS.get(key)
    if h is None:
        return "?"
    try:
        return "UNSPOOFED" if h(value) else "spoofed"
    except Exception:
        return "?"


def run(bin_path: str) -> int:
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    svc = Service(log_path="/tmp/probe-js.log")
    driver = webdriver.Firefox(options=opts, service=svc)
    try:
        driver.set_page_load_timeout(30)
        # Warm up so active profile is assigned
        driver.get("https://example.com/")
        time.sleep(2.0)
        driver.get("https://example.com/?probe=1")  # second nav, warm
        time.sleep(1.5)
        driver.execute_script(PROBE_SCRIPT)
        time.sleep(1.5)  # async probes (storage, battery, mediaDevices)
        try:
            raw = driver.find_element("id", "_probe").text
        except Exception:
            print("Probe element missing — inline script didn't run.")
            return 2
        data = json.loads(raw)

        # Print table
        print(f"{'Signal':<40} {'Value':<40} Verdict")
        print("-" * 90)
        unspoofed = 0
        total_heuristics = 0
        for k in sorted(data.keys()):
            v = data[k]
            v_str = str(v)[:40]
            verdict = _verdict(k, v)
            print(f"{k:<40} {v_str:<40} {verdict}")
            if verdict in ("UNSPOOFED", "spoofed"):
                total_heuristics += 1
                if verdict == "UNSPOOFED":
                    unspoofed += 1

        print()
        print(f"Heuristics: {total_heuristics - unspoofed}/{total_heuristics} spoofed")
        print(f"Raw JSON: {json.dumps(data, indent=2, default=str)[:1500]}")
        return 0 if unspoofed == 0 else 1
    finally:
        driver.quit()


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN env var not set or binary missing")
    sys.exit(run(b))
