#!/usr/bin/env python3
"""
Generate the Cloakfox persona pool from BrowserForge.

BrowserForge is Apify's Bayesian-network fingerprint generator, trained
on real-world browser distributions. We use it OFFLINE (build-time) to
sample N personas per OS family, map each one's fields to our MaskConfig
keys, and write the bundle to a chrome JS module that ships in omni.ja.

Why offline-not-runtime: BrowserForge is Python, and Cloakfox's persona
generator runs in a chrome JS module loaded at parent startup — no
Python or Node runtime there. Pre-computing personas keeps the runtime
zero-dependency while still drawing from the real BrowserForge
distribution.

Why a chrome JS module (not personas.json): chrome modules load via
ChromeUtils.importESModule which is synchronous and works during
BrowserGlue startup. A JSON file would need fetch + await + cache
priming, all of which complicate the SeedSync init path.

Run:
    pip install browserforge
    python3 scripts/generate-personas.py

Regenerate when:
    - Firefox version changes (UA string updates)
    - You want a new pool (better pool diversity, or fix a real-world
      detection issue surfaced by the bot battery)

Output: additions/browser/components/cloakfox/CloakfoxPersonaData.sys.mjs
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from browserforge.fingerprints import FingerprintGenerator
except ImportError:
    sys.exit("browserforge not installed. Run: pip install browserforge")

import random as _stdlib_random


# US cities for geolocation spoofing. The locale we feed BrowserForge is
# en-US, so coordinates need to land somewhere plausible-US. Top metros
# by population — picked so a fingerprinter checking lat/long ↔ IANA
# timezone consistency gets values that match (every entry below is
# inside America/Chicago | America/Denver | America/Los_Angeles |
# America/New_York | etc., all of which are subset-equivalent to
# "UTC offset somewhere in the US" for the purposes of casual checks).
#
# Each persona gets ONE city plus a ±0.04° lat/long jitter (~5 km) so
# different containers in the same city aren't pixel-perfect identical.
US_CITIES = [
    ("New York",      40.7128,  -74.0060),
    ("Los Angeles",   34.0522, -118.2437),
    ("Chicago",       41.8781,  -87.6298),
    ("Houston",       29.7604,  -95.3698),
    ("Phoenix",       33.4484, -112.0740),
    ("Philadelphia",  39.9526,  -75.1652),
    ("San Antonio",   29.4241,  -98.4936),
    ("San Diego",     32.7157, -117.1611),
    ("Dallas",        32.7767,  -96.7970),
    ("San Jose",      37.3382, -121.8863),
    ("Austin",        30.2672,  -97.7431),
    ("Jacksonville",  30.3322,  -81.6557),
    ("San Francisco", 37.7749, -122.4194),
    ("Seattle",       47.6062, -122.3321),
    ("Denver",        39.7392, -104.9903),
    ("Boston",        42.3601,  -71.0589),
    ("Miami",         25.7617,  -80.1918),
    ("Atlanta",       33.7490,  -84.3880),
    ("Portland",      45.5152, -122.6784),
    ("Minneapolis",   44.9778,  -93.2650),
]


# How many personas per OS family. Larger pool = lower per-pair collision
# rate when two random math_seeds pick the same persona, but bigger
# CloakfoxPersonaData.sys.mjs file. 100/OS = 300 total. JSON size
# observed: ~250 KB. Negligible at omni.ja scale.
PERSONAS_PER_OS = 30

# Pin the UA's Firefox version to whatever the build's milestone is.
# BrowserForge's pool sometimes returns older/newer versions which would
# diverge from what the actual browser reports.
FIREFOX_VERSION = "146.0"

# Per-OS chrome decoration heights — same values as
# CloakfoxPersonas.sys.mjs's CHROME_DECOR. We use these to derive
# coherent inner/outer/avail values when BrowserForge's screen.inner*
# fields are 0 (which they often are — that field is buggy in BF).
CHROME_DECOR = {
    "macos":   {"menuBar": 25, "taskbar": 0,  "firefoxChrome": 86},
    "windows": {"menuBar": 0,  "taskbar": 40, "firefoxChrome": 90},
    "linux":   {"menuBar": 0,  "taskbar": 32, "firefoxChrome": 80},
}

# Map BrowserForge OS labels → host-OS labels Services.appinfo.OS uses.
OS_TO_HOST = {
    "macos":   "darwin",
    "windows": "winnt",
    "linux":   "linux",
}


def normalize_ua(ua: str) -> str:
    """Replace whatever Firefox version BF generated with our build's."""
    # Match "rv:N.N" and "Firefox/N.N" pairs, replace both consistently.
    ua = re.sub(r"rv:\d+\.\d+", f"rv:{FIREFOX_VERSION}", ua)
    ua = re.sub(r"Firefox/\d+\.\d+", f"Firefox/{FIREFOX_VERSION}", ua)
    return ua


def render_webgl_renderer(vendor: str, renderer: str, os: str) -> tuple[str, str]:
    """BrowserForge's videoCard.renderer is sometimes a friendly name
    like 'Intel(R) HD Graphics, or similar' — fine. But for Windows we
    want the ANGLE-prefixed form Firefox actually emits. Wrap if needed.
    """
    if os == "windows" and not renderer.startswith("ANGLE"):
        # Drop "or similar" suffix some BF renderers carry.
        clean = re.sub(r",?\s*or similar\s*$", "", renderer)
        renderer = f"ANGLE ({vendor.replace(' Inc.', '').replace(' Corporation', '')}, {clean} Direct3D11 vs_5_0 ps_5_0)"
        vendor = f"Google Inc. ({vendor.split()[0]})"
    return vendor, renderer


def fingerprint_to_persona(fp, os: str) -> dict:
    """Map a BrowserForge fingerprint object to our cloak_cfg key set."""
    nav = fp.navigator
    scr = fp.screen
    gpu = fp.videoCard
    decor = CHROME_DECOR[os]

    ua = normalize_ua(nav.userAgent)
    av = nav.appVersion or ("5.0 (Macintosh)" if os == "macos"
                            else "5.0 (Windows)" if os == "windows"
                            else "5.0 (X11)")
    lang = nav.language or "en-US"

    # Derive coherent dimensions. BF's inner* fields are unreliable —
    # compute them from outer + chrome height like our hand-rolled code.
    sw, sh, dpr = scr.width, scr.height, scr.devicePixelRatio or 1.0
    avail_top = decor["menuBar"]
    avail_h = sh - decor["menuBar"] - decor["taskbar"]
    inner_h = max(200, avail_h - decor["firefoxChrome"])

    webgl_vendor, webgl_renderer = render_webgl_renderer(
        gpu.vendor or "Intel Inc.", gpu.renderer or "Intel HD Graphics", os
    )

    # Geolocation: pick one of the city-pool entries + ±5km jitter, with
    # 50–150m accuracy (typical GPS-not-WiFi). Persistent per-persona so
    # multiple getCurrentPosition() calls in the same container return
    # consistent coords. Different containers see different cities.
    city_name, base_lat, base_lng = _stdlib_random.choice(US_CITIES)
    lat_jitter = (_stdlib_random.random() - 0.5) * 0.08
    lng_jitter = (_stdlib_random.random() - 0.5) * 0.08
    accuracy = 50.0 + _stdlib_random.random() * 100.0

    return {
        # UA + headers
        "navigator.userAgent": ua,
        "navigator.appVersion": av,
        "navigator.platform": nav.platform,
        "navigator.oscpu": nav.oscpu,
        "navigator.language": lang,
        "headers.User-Agent": ua,
        "headers.Accept-Language": f"{lang},en;q=0.5",
        "headers.Accept-Encoding": "gzip, deflate, br, zstd",

        # Locale
        "locale:language": lang.split("-")[0],
        "locale:region": (lang.split("-")[1] if "-" in lang else "US"),
        "locale:script": "Latn",

        # Hardware identity
        "navigator.hardwareConcurrency": nav.hardwareConcurrency or 8,
        "navigator:maxTouchPoints": nav.maxTouchPoints or 0,

        # Screen + window (coherent)
        "screen.width": sw,
        "screen.height": sh,
        "screen.availLeft": 0,
        "screen.availTop": avail_top,
        "screen.availWidth": sw,
        "screen.availHeight": avail_h,
        "window.innerWidth": sw,
        "window.innerHeight": inner_h,
        "window.outerWidth": sw,
        "window.outerHeight": avail_h,
        "window.devicePixelRatio": dpr,
        "window.screenX": 0,
        "window.screenY": 0,
        "window.scrollMinX": 0,
        "window.scrollMinY": 0,
        "screen.pageXOffset": 0,
        "screen.pageYOffset": 0,
        "screen:orientation:type": "landscape-primary",
        "mediaFeature:resolution": dpr,

        # WebGL
        "webGl:vendor": webgl_vendor,
        "webGl:renderer": webgl_renderer,

        # Geolocation — consumed by patches/geolocation-spoofing.patch.
        # When the keys are present, navigator.geolocation.getCurrentPosition
        # returns these coords and the permission prompt is auto-granted.
        # Per-persona values mean each container claims a different US metro.
        "geolocation:latitude":  round(base_lat + lat_jitter, 6),
        "geolocation:longitude": round(base_lng + lng_jitter, 6),
        "geolocation:accuracy":  round(accuracy, 1),

        # Audio (BF doesn't surface outputLatency; sensible per-OS default)
        "AudioContext:outputLatency": (
            0.005 if os == "macos" else 0.012 if os == "windows" else 0.010
        ),
        "AudioContext:sampleRate": 48000,
        "AudioContext:maxChannelCount": 2,

        # Spoof flags (always-on layer)
        "codecs:spoof": True,
        "mediaCapabilities:spoof": True,
        "permissions:spoof": True,
        "voices:fakeCompletion": True,
        "voices:fakeCompletion:charsPerSecond": 16,
        "voices:blockIfNotDefined": False,
        "navigator:vibrate:disabled": True,
        "navigator:webgpu:disabled": True,
        "document:lastModified:hidden": True,
        "indexedDB:databases:hidden": True,
        "mediaFeature:invertedColors": False,
        "mediaFeature:prefersReducedMotion": False,
        "mediaFeature:prefersReducedTransparency": False,
    }


def generate_pool(os: str, count: int) -> list[dict]:
    """Generate N personas for one OS family.

    No dedup — BrowserForge's per-OS distribution has a narrow set of
    unique screens (≤ ~10 per OS), and tight dedup spins past
    max_attempts. Natural variation across the other ~30 fields (UA
    minor version, audio output latency, GPU model variant, font
    list, etc.) keeps the pool diverse enough.

    Skip mobile-ish screens (BF can return tiny dims for some niche
    desktop configs); keep everything else.
    """
    import time
    fg = FingerprintGenerator(browser="firefox", os=os, device="desktop", locale="en-US")
    pool = []
    attempts = 0
    max_attempts = count * 5
    t0 = time.time()
    while len(pool) < count and attempts < max_attempts:
        attempts += 1
        fp = fg.generate()
        if fp.screen.width < 1024 or fp.screen.height < 600:
            continue
        pool.append(fingerprint_to_persona(fp, os))
        if len(pool) % 10 == 0:
            print(f"  {os}: {len(pool)}/{count}, {attempts} attempts, {time.time()-t0:.1f}s", flush=True)
    if len(pool) < count:
        print(f"  WARN: hit max_attempts ({max_attempts}); accepting {len(pool)} of {count}", flush=True)
    return pool


def write_module(pools: dict[str, list[dict]], out_path: Path) -> None:
    """Render the chrome JS module that ships the persona data."""
    payload = json.dumps(
        {OS_TO_HOST[os]: pools[os] for os in pools},
        indent=2,
        sort_keys=True,
    )
    body = f'''/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* GENERATED — do not edit by hand.
 *
 * Persona pools sampled from BrowserForge's real-world Bayesian-
 * network fingerprint distribution. Each persona is a pre-computed
 * cloak_cfg subset (the MaskConfig keys our C++ patches consume).
 *
 * Regenerate with:
 *   pip install browserforge
 *   python3 scripts/generate-personas.py
 *
 * {sum(len(v) for v in pools.values())} personas total ({"/".join(str(len(v)) for v in pools.values())} per OS).
 */

export const PERSONAS = {payload};
'''
    out_path.write_text(body)
    sizes = {os: len(pools[os]) for os in pools}
    print(f"Wrote {out_path} — {sum(sizes.values())} personas: {sizes}")


def main() -> None:
    out = Path(__file__).parent.parent / "additions" / "browser" / "components" / \
          "cloakfox" / "CloakfoxPersonaData.sys.mjs"
    pools = {}
    for os in ("macos", "windows", "linux"):
        print(f"Generating {PERSONAS_PER_OS} {os} personas …", flush=True)
        pools[os] = generate_pool(os, PERSONAS_PER_OS)
    write_module(pools, out)


if __name__ == "__main__":
    main()
