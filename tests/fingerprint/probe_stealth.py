"""
Stealth probe — verifies the three extension-fingerprint leaks that the
stealth pass (commits 0515533ae5 + 851b809c20 + 33660849ba + 67f6ffcbce)
closed are actually gone from the built DMG.

Runs in page MAIN context. A leak would show up as a `function` type for
one of the Cloakfox setters, a non-null `data-cfx-boot` attribute after
inject ran, or a surviving `__cloakfox_configured` sessionStorage entry.

Also does a coarse "did C++ still fire" sanity check via WebGL — if
UNMASKED_VENDOR_WEBGL is the raw Apple/Mesa default, the ISOLATED-side
setter calls aren't reaching C++ and the whole stealth rework broke
spoofing. (Detailed per-spoofer verification belongs in
probe_js_spoofers.py.)

Exit codes:
  0 — all stealth assertions pass.
  1 — at least one leak is still present OR spoofing isn't firing.
  2 — couldn't run (probe didn't execute, browser didn't start).

Run:
    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_stealth.py
"""

from __future__ import annotations

import json
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


# All probes run in page MAIN — injected as a <script> tag so the code
# executes with the same permissions as any site script, not the
# content-script's ISOLATED principal. That's the whole point: this
# script should see what a fingerprinting site would see.
PROBE_SCRIPT = r"""
const s = document.createElement('script');
s.textContent = `
  const r = {};
  const safe = (name, fn) => { try { r[name] = fn(); } catch (e) { r[name] = 'ERR: ' + e.message; } };

  // ---- Func-gated setters: must be 'undefined' from MAIN ----
  // If any of these return 'function', the Func gate isn't working
  // and page scripts can both detect and call the spoofer machinery.
  safe('typeof.setCanvasSeed', () => typeof window.setCanvasSeed);
  safe('typeof.setWebGLVendor', () => typeof window.setWebGLVendor);
  safe('typeof.setWebGLRenderer', () => typeof window.setWebGLRenderer);
  safe('typeof.setScreenDimensions', () => typeof window.setScreenDimensions);
  safe('typeof.setScreenColorDepth', () => typeof window.setScreenColorDepth);
  safe('typeof.setFontList', () => typeof window.setFontList);
  safe('typeof.setFontSpacingSeed', () => typeof window.setFontSpacingSeed);
  safe('typeof.setAudioFingerprintSeed', () => typeof window.setAudioFingerprintSeed);
  safe('typeof.setSpeechVoices', () => typeof window.setSpeechVoices);
  safe('typeof.setNavigatorUserAgent', () => typeof window.setNavigatorUserAgent);
  safe('typeof.setNavigatorPlatform', () => typeof window.setNavigatorPlatform);
  safe('typeof.setNavigatorOscpu', () => typeof window.setNavigatorOscpu);
  safe('typeof.setNavigatorHardwareConcurrency', () => typeof window.setNavigatorHardwareConcurrency);
  safe('typeof.setCloakConfig', () => typeof window.setCloakConfig);
  safe('typeof.setHttp2Profile', () => typeof window.setHttp2Profile);
  safe('typeof.setHttp3Profile', () => typeof window.setHttp3Profile);
  safe('typeof.cloakfoxIsConfigured', () => typeof window.cloakfoxIsConfigured);

  // ---- Bridge cleanup: attribute must be gone by the time any
  // page script runs. Content scripts run before page scripts at
  // document_start per MV3, so inject/index.ts removes it before
  // we ever get here. ----
  safe('bridgeAttr', () => document.documentElement.getAttribute('data-cfx-boot'));
  // Also scan all documentElement attributes for anything cfx-shaped.
  safe('htmlAttrs', () => {
    const out = [];
    for (const a of document.documentElement.attributes) {
      if (/cfx|cloakfox|shield/i.test(a.name)) out.push(a.name);
    }
    return JSON.stringify(out);
  });

  // ---- Legacy leaks that the pre-stealth code used. ----
  safe('sessionStorage.__cloakfox_configured', () => {
    try { return sessionStorage.getItem('__cloakfox_configured'); } catch (e) { return 'ERR'; }
  });
  safe('sessionStorage.keys', () => {
    try {
      const keys = [];
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i);
        if (/cfx|cloakfox|shield/i.test(k)) keys.push(k);
      }
      return JSON.stringify(keys);
    } catch (e) { return 'ERR'; }
  });

  // ---- Spoofing sanity: WebGL vendor/renderer should be spoofed
  // (ISOLATED-side setWebGLVendor/Renderer calls succeeded). ----
  safe('webgl.vendor', () => {
    const c = document.createElement('canvas').getContext('webgl');
    const e = c && c.getExtension('WEBGL_debug_renderer_info');
    return e ? c.getParameter(e.UNMASKED_VENDOR_WEBGL) : 'no-ext';
  });
  safe('webgl.renderer', () => {
    const c = document.createElement('canvas').getContext('webgl');
    const e = c && c.getExtension('WEBGL_debug_renderer_info');
    return e ? c.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'no-ext';
  });

  const out = document.createElement('pre');
  out.id = '_stealth_probe';
  out.textContent = JSON.stringify(r);
  document.body.appendChild(out);
`;
document.body.appendChild(s);
"""


# Each assertion: (key in probe JSON, predicate that must be TRUE for pass,
# human-readable description when it fails).
ASSERTIONS = [
    # Func-gated setter hiding
    ("typeof.setCanvasSeed",              lambda v: v == "undefined",  "setCanvasSeed is visible in MAIN"),
    ("typeof.setWebGLVendor",             lambda v: v == "undefined",  "setWebGLVendor is visible in MAIN"),
    ("typeof.setWebGLRenderer",           lambda v: v == "undefined",  "setWebGLRenderer is visible in MAIN"),
    ("typeof.setScreenDimensions",        lambda v: v == "undefined",  "setScreenDimensions is visible in MAIN"),
    ("typeof.setScreenColorDepth",        lambda v: v == "undefined",  "setScreenColorDepth is visible in MAIN"),
    ("typeof.setFontList",                lambda v: v == "undefined",  "setFontList is visible in MAIN"),
    ("typeof.setFontSpacingSeed",         lambda v: v == "undefined",  "setFontSpacingSeed is visible in MAIN"),
    ("typeof.setAudioFingerprintSeed",    lambda v: v == "undefined",  "setAudioFingerprintSeed is visible in MAIN"),
    ("typeof.setSpeechVoices",            lambda v: v == "undefined",  "setSpeechVoices is visible in MAIN"),
    ("typeof.setNavigatorUserAgent",      lambda v: v == "undefined",  "setNavigatorUserAgent is visible in MAIN"),
    ("typeof.setNavigatorPlatform",       lambda v: v == "undefined",  "setNavigatorPlatform is visible in MAIN"),
    ("typeof.setNavigatorOscpu",          lambda v: v == "undefined",  "setNavigatorOscpu is visible in MAIN"),
    ("typeof.setNavigatorHardwareConcurrency", lambda v: v == "undefined",  "setNavigatorHardwareConcurrency is visible in MAIN"),
    ("typeof.setCloakConfig",             lambda v: v == "undefined",  "setCloakConfig is visible in MAIN"),
    ("typeof.setHttp2Profile",            lambda v: v == "undefined",  "setHttp2Profile is visible in MAIN"),
    ("typeof.setHttp3Profile",            lambda v: v == "undefined",  "setHttp3Profile is visible in MAIN"),
    ("typeof.cloakfoxIsConfigured",       lambda v: v == "undefined",  "cloakfoxIsConfigured is visible in MAIN — Cloakfox presence is probeable"),
    # Bridge cleanup
    ("bridgeAttr",                         lambda v: v is None,         "data-cfx-boot attribute survived into MAIN"),
    ("htmlAttrs",                          lambda v: v == "[]",         "cfx-shaped attributes on <html> survived into MAIN"),
    # sessionStorage leaks
    ("sessionStorage.__cloakfox_configured", lambda v: v is None,        "__cloakfox_configured sessionStorage key is set"),
    ("sessionStorage.keys",                lambda v: v == "[]",         "cfx-shaped keys in sessionStorage"),
    # Spoofing still fires
    ("webgl.vendor",                       lambda v: isinstance(v, str) and "Apple" not in v and "Mesa" not in v and v != "no-ext",
                                                                         "WebGL vendor is raw default — ISOLATED->C++ spoofing broke"),
    ("webgl.renderer",                     lambda v: isinstance(v, str) and "Apple" not in v and "Mesa" not in v and v != "no-ext",
                                                                         "WebGL renderer is raw default — ISOLATED->C++ spoofing broke"),
]


def run(bin_path: str) -> int:
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    svc = Service(log_path="/tmp/probe-stealth.log")
    driver = webdriver.Firefox(options=opts, service=svc)
    try:
        driver.set_page_load_timeout(30)
        # Warm-up nav so the per-container profile is assigned and the
        # cloakfoxIsConfigured path has a populated state.
        driver.get("https://example.com/")
        time.sleep(2.0)
        # Second nav — reloaded page has handled[] populated by
        # cloakfoxIsConfigured, and self-destructing setters have already
        # fired. This is the path that regressed before; verify it now.
        driver.get("https://example.com/?probe=stealth")
        time.sleep(1.5)

        driver.execute_script(PROBE_SCRIPT)
        time.sleep(0.5)

        try:
            raw = driver.find_element("id", "_stealth_probe").text
        except Exception:
            print("ERROR: probe element not found — inline script didn't run.")
            return 2
        data = json.loads(raw)

        print(f"{'Assertion':<48} {'Observed':<40} Verdict")
        print("-" * 100)
        failed = []
        for key, predicate, msg in ASSERTIONS:
            v = data.get(key, "<missing>")
            try:
                ok = predicate(v)
            except Exception as e:
                ok = False
                v = f"ERR: {e}"
            verdict = "PASS" if ok else "FAIL"
            v_str = str(v)[:40]
            print(f"{key:<48} {v_str:<40} {verdict}")
            if not ok:
                failed.append((key, v, msg))

        print()
        if failed:
            print(f"FAILED {len(failed)} of {len(ASSERTIONS)} stealth assertions:")
            for key, v, msg in failed:
                print(f"  - {key}: {msg} (got {v!r})")
            return 1
        print(f"OK — all {len(ASSERTIONS)} stealth assertions pass.")
        return 0
    finally:
        driver.quit()


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN env var not set or binary missing")
    sys.exit(run(b))
