# Probe baseline — green DMG on 2026-04-20

Output of `probe_js_spoofers.py` (variant `probe_split.py` with sync-only
probes, on `https://example.com/?warm`) against the green CI-built DMG at
commit `13228a92bc` (first Cloakfox build where the extension actually
loaded). Use this as a baseline for post-fix regressions.

The extension was assigned a Chrome/macOS Chromium profile automatically —
not a forced pick. Re-running would likely pick a different random profile.

## Signal table (Chrome/macOS profile)

```
Signal                         Value                                     Verdict
---------------------------------------------------------------------------------
userAgent                      Chrome/123.0.0.0 Mac OS X 10_15_7         spoofed (UA matches Chrome)
platform                       MacIntel                                  consistent (Chrome/Mac → MacIntel)
vendor                         Google Inc.                               spoofed (Firefox default is "")
hardwareConcurrency            16                                        spoofed (real machine has 12)
languages                      ["en-US","en"]                            default
maxTouchPoints                 0                                         default (non-touch Mac)
webdriver                      false                                     spoofed (selenium → true normally)
uaData_brands                  Chrome 123, Not:A-Brand 8, Chromium 123   spoofed (Firefox has no UA-CH)
uaData_platform                macOS                                     consistent
uaData_mobile                  false                                     consistent
screen_wh                      1728x1117                                 spoofed
screen_avail                   1728x1092                                 spoofed
screen_colorDepth              30                                        spoofed (real = 24, Mac HDR would be 30)
dpr                            2                                         real (Mac Retina)
screen_orientation             landscape-primary                         default
tz_offset                      240                                       spoofed (America/New_York; real is PST)
tz_intl                        America/New_York                          spoofed
locale_intl                    en-US                                     default
Math_PI                        3.1415926535897767                        spoofed (real = 3.141592653589793)
Math_E                         2.718281828459019                         spoofed
Math_sin_0.5                   0.4794255386044774                        spoofed
webgl_vendor                   Apple Inc.                                consistent-with-Mac (untested: cross-platform)
webgl_renderer                 Apple M1 (varies — Apple M2 Pro in 1st run) spoofed within Apple family
webgl_version                  WebGL 1.0                                  default
audio_sampleRate               44100                                      default
speech_voices_count            4                                          varies per session (2 in 1st run)
gpu                            object (WebGPU enabled)                    present
gamepads                       function                                   default
midi                           function                                   default
window_name                    ""                                         default empty
rtc_peer                       function                                   present
vibrate_result                 true                                       default
setCanvasSeed                  undefined                                  ✓ self-destructed (inject ran)
setHttp2Profile                function                                   waiting for call (pref doesn't persist anyway)
setHttp3Profile                function                                   waiting for call
setNavigatorUserAgent          undefined                                  ✓ self-destructed (inject ran)
nav_storage_type               object                                     present in secure context
nav_mediaDevices_type          object                                     present in secure context
nav_permissions_type           object                                     present
nav_getBattery_type            undefined                                  ✓ disabled by pref (dom.battery.enabled=false)
```

## Takeaways

- **Most spoofing works end-to-end.** UA, UA-CH, screen dimensions, timezone,
  Math, WebGL rotation, and the self-destructing WebIDL markers all show
  correct behavior.
- **False alarm corrected:** my first pass flagged `navigator.storage` and
  `navigator.mediaDevices` as `undefined` — that was because the probe ran
  on `http://` (non-secure context). On HTTPS both APIs appear correctly.
- **Untested:** cross-platform WebGL (Chrome/Windows UA + real Mac → does
  webgl_renderer still leak Apple?). See PENDING.md.
- **Known limits carried forward:** WebIDL setters are still bound but
  don't persist prefs (content-process → parent-process IPC gap documented
  in PENDING.md P0).

## How to regenerate

```bash
# Download the latest green DMG
gh api repos/roshin8/cloakfox/actions/artifacts/<id>/zip > /tmp/cloakfox.zip
unzip -q /tmp/cloakfox.zip -d /tmp/cf-probe
hdiutil attach /tmp/cf-probe/Cloakfox-macos-arm64.dmg
cp -R /Volumes/Cloakfox/Cloakfox.app /tmp/cf-probe/
hdiutil detach /Volumes/Cloakfox

# Set up venv
cd /tmp/cf-probe
python3 -m venv venv && source venv/bin/activate
pip install -q selenium
brew install geckodriver  # or download from github

# Run probe
CLOAKFOX_BIN=/tmp/cf-probe/Cloakfox.app/Contents/MacOS/cloakfox \
    python /path/to/cloakfox/tests/fingerprint/probe_js_spoofers.py
```

If the probe times out, check that the page you're probing allows inline
scripts (no strict CSP). Use a no-CSP page like `http://httpbin.org/html`
for non-secure tests, or `https://example.com/?warm` for secure-context
probes (storage, mediaDevices, etc.).
