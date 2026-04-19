# Fingerprint tests

Two tools for validating the H2/H3 transport-fingerprint patches land as
designed and match the browser they claim to mimic.

## 1. `test_h2_profile.py` — automated shape check

Launches the built Cloakfox binary under each H2 profile (firefox / chrome /
safari) via Playwright, hits `https://tls.peet.ws/api/all`, and asserts the
SETTINGS frame, WINDOW_UPDATE, and HPACK pseudo-header order match the
profile contract.

### Setup

```bash
pip install pytest playwright
python -m playwright install  # downloads Playwright's browser drivers
```

### Run

```bash
CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  pytest tests/fingerprint/test_h2_profile.py -v
```

Or on Linux:

```bash
CLOAKFOX_BIN=/path/to/firefox-src/obj-*/dist/bin/cloakfox \
  pytest tests/fingerprint/test_h2_profile.py -v
```

Skips cleanly when `CLOAKFOX_BIN` is unset — CI can run the test suite
without blowing up on machines without a built binary.

### What each test checks

- `test_h2_profile_shape[firefox]` — MAX_FRAME_SIZE present, MAX_HEADER_LIST_SIZE absent, HPACK order `:method, :path, :authority, :scheme`.
- `test_h2_profile_shape[chrome]` — MAX_HEADER_LIST_SIZE=262144, no MAX_FRAME_SIZE, WINDOW_UPDATE=15663105, HPACK order `:method, :authority, :scheme, :path`.
- `test_h2_profile_shape[safari]` — sparse SETTINGS (IDs 2/3/4 only), WINDOW_UPDATE=10485760, HPACK order `:method, :scheme, :path, :authority`.
- `test_h2_profiles_produce_distinct_fingerprints` — all three profiles produce distinct `akamai_fingerprint_hash` values. Collapsing hashes mean the WebIDL setter isn't firing.

### Known limitations

- `headless=False` is intentional. Cloakfox's `setHttp2Profile` WebIDL method
  is bound in the MAIN world and gets nerfed by some headless code paths.
  CI runs need a virtual display (Xvfb on Linux).
- The pref is forced via `user.js` dropped in the profile dir rather than
  through the extension UI. This tests the C++ patch directly. A second
  test that round-trips through the extension (`setHttp2Profile()` call
  from `content/index.ts`) would be a useful addition.

## 2. `mitm_h2_observer.py` — local packet-level observation

A mitmproxy addon that prints the exact H2 SETTINGS frame, WINDOW_UPDATE
value, and HPACK pseudo-header order Cloakfox emits per connection. Use
when you want to see bytes on the wire, not a remote service's interpretation.

### Setup

```bash
pip install mitmproxy  # 10+ required for H2 introspection
```

### Run

```bash
mitmproxy -s tests/fingerprint/mitm_h2_observer.py --listen-port 8080
```

Then in Cloakfox, `about:config`:

```
network.proxy.type       = 1
network.proxy.http       = 127.0.0.1
network.proxy.http_port  = 8080
network.proxy.ssl        = 127.0.0.1
network.proxy.ssl_port   = 8080
network.proxy.share_proxy_settings = true
```

Visit any `https://` site that speaks H2. mitmproxy prints a block per new
connection:

```
─── 192.0.2.1:443 ──────────────────────────────────────
SETTINGS:
  HEADER_TABLE_SIZE          (1) = 65536
  ENABLE_PUSH                (2) = 0
  MAX_CONCURRENT             (3) = 1000
  INITIAL_WINDOW_SIZE        (4) = 6291456
  MAX_HEADER_LIST_SIZE       (6) = 262144
WINDOW_UPDATE: 15663105
HPACK order on first HEADERS: :method, :authority, :scheme, :path
```

Compare against the profile contracts above. If the pref is set to `chrome`
but you see Firefox bytes, the setter isn't firing.

### HTTPS interception note

mitmproxy intercepts TLS by injecting its own CA cert. Install mitmproxy's
cert (`http://mitm.it/` from a proxied browser) so Cloakfox trusts the
intercepted connections. This is pure local observation — nothing about
the cert manipulation leaks the real fingerprint.

## What lives where

```
tests/fingerprint/
├── README.md                — this file
├── test_h2_profile.py       — Playwright E2E: launches Cloakfox, hits peetwapp
└── mitm_h2_observer.py      — mitmproxy addon: logs H2 frames locally
```

## H3 / Sec-CH-UA / Math constants

Not yet covered. Easy additions:

- **H3:** same pattern as `test_h2_profile.py` but against a quic-echoing
  endpoint (`https://cloudflare-quic.com/b/headers` returns the H3 SETTINGS
  it observed).
- **Sec-CH-UA:** visit `https://browserleaks.com/headers`, assert brands
  vary with the user-agent profile.
- **Math constants:** reload same domain in same container twice,
  `Math.PI.toPrecision(17)` should match byte-for-byte; across two containers
  the two values should differ.
