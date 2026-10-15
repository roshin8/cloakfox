# Firefox 157 identity/privacy port verification

Verified 2026-10-14 on macOS arm64, branch `codex/firefox-157-privacy-gaps`,
starting from `24c23d478e` (`codex/firefox-157-port`). The Firefox 146 checkout
was preserved. This change is uncommitted. The initial verification used the
build output; installation was completed separately below.

## Executable and source parity

- Firefox 157.0.1 source; executable reports `157.0.1-beta.25`.
- Final BuildID: `20261013234629`.
- Final native build succeeded, with zero compiler warnings.
- XUL SHA256: `ad21b65cfbf6ab275e895625ae1718bbe66653793822e715c1511a983c68067e`.
- The original157 patch stack applied without rejected hunks. Fifteen final
  port/compatibility patches reverse and replay with exact byte parity across
  43 native files. Modified additions and runtime autoconfig also match source.
- Build: `firefox-src/obj-aarch64-apple-darwin/dist/Cloakfox.app`.

## Verified results

| Checks | Result |
| --- | --- |
| Node unit suite | 242 passed, zero failed/skipped |
| Python suite | 39 passed, one conditional skip |
| Browser runtime probes | 112 distinct probes passed, zero unresolved failures |
| Pointer/hover behavior | 145/145 widget checks and 145/145 serialized desktop checks |
| Ordered patch replay | 15 patches, 43 files, exact source parity |
| Independent follow-up code review | No remaining actionable findings in reviewed changes |

Browser probes ran in serial batches against the frozen final build. Of 112
probes, 110 passed in the initial batch runs. Two fixtures were corrected and
rerun successfully: Chrome legitimately opened multiple H3 sessions, and the
worker math probe used a file URL without a schemeful site. Every Chrome session
must still negotiate H3 and a real response must complete; all worker assertions
are retained on local HTTP. The shared math fixture was revalidated afterwards.

The Python skip is the conditional Sec-CH-UA test selecting a Firefox persona.
Explicit Chromium and Firefox Client Hints behavior is covered by the passing
`probe_user_agent_data.py` runtime test. The one-off font spike is excluded by
its existing runner policy; it requires a separately staged font.

Regression coverage includes transparent WebGL RGB, precise/PBO readback and
compute opt-out, FontFace URL/buffer/local loading, synchronous/inherited/opaque
realms, native GPU brands and webdriver policy, scoped language caches, canonical
mask storage and live parent updates, request/CONNECT/WebSocket ownership,
WebRTC startup and proxy routes, native media enforcement and consent, pointer
capture/hover/focus, settings/restart persistence, and worker startup/lifecycle.
TURN cases include supported HTTP/PAC routes, failed/late PAC, DIRECT fallback,
proxy changes, queued negotiation and ICE restart. Required-proxy negative cases
emitted no direct target traffic.

## Review and runtime findings fixed

The port preserves 157 site-derived identity, its network adapter registry,
worker cache mutex and newer ICE-operation queue behavior. It does not replace
newer source files wholesale with 146 versions.

Review repairs cover transparent-alpha nonzero RGB readback, required-proxy
DIRECT/failover paths, and scoped language invalidation for157 sanitized child
preferences. Browser verification additionally found and fixed:

- Virtual screen permission queries now initialize both browser and system
  state, keeping157 effective permission state consistent with API eligibility.
- The child-only HackerRank recovery actor explicitly opts into 157 web content
  processes, retaining its narrow HTTPS origin/path and top-level scope.
- Hover survives157 pointer-first departures while pointer targets reset
  natively. The pending mouse-entry marker preserves remote-frame reconciliation.

The untouched installed HackerRank actor registration passed a local HTTPS
fixture mapped to its matched hostname. Reconnects update the local ID/render
epoch without capture calls; wrong origin/path, child-frame and opt-out controls
remain inactive. This verifies the built registration, not a replacement actor.

Tests were also adapted to real visible settings controls, current supported
network selection, native disabled-media rejection, per-launch timing salts,
site-HMAC math expectations, and157 retirement of the legacy Feature-Policy
header. Modern Permissions-Policy denial and ancestor denial remain enforced.
Stock Firefox comparisons use disposable app-data roots because macOS TCC
blocks the normal Firefox profile registry. They preserve certificate rejection
and actual TLS/H2/QUIC/H3 response validation. Resource inventory checks the
actual loose development layout while retaining its packaged archive path.

## Scope and evidence

This verification uses disposable profiles and local fixtures. Native fake
camera/audio and screen-capture policy checks passed; a live HackerRank/Zoom
call and real macOS screen-recording consent were not exercised on this 157 build.
Windows/Linux builds and a complete MASQUE media tunnel remain unverified.

Detailed local evidence is in the ignored directory
`tests/fingerprint/reports/157-privacy-port`: `runtime-final-results.json`,
`final-probe_*.log`, `node-final.log`, `pytest-final.log`, `build-final.log`,
`build-identity.json`, `patch-replay-final.log`, `identity/findings.txt`,
`identity/production-hackerrank.log`, and `h2/pointer-*-verified.json`.

Reproduce the Python suite with a Python environment containing the documented
fixture dependencies:

```sh
CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
  python3 -m pytest --noconftest tests/fingerprint \
  --ignore=tests/fingerprint/reports -q -rs
node --test tests/fingerprint/test_*.mjs
```

The full runtime runner additionally needs `ALPS_SERVER`,
`MONACO_PROBE_ASSETS` and `CLOAKFOX_XPCSHELL` as documented in the test README.


## Installation — 2026-10-14

Packaged the verified build with `mach package`, installed a self-contained,
locally signed bundle at `/Applications/Cloakfox.app`, and verified its full
code signature and version. A packaged installation language-scope probe passed.

Opened the existing Default User profile with its saved Firefox appearance.
The running appearance copy and its child processes report version
`157.0.1-beta.25` and BuildID `20261013234629`. The settings page loads correctly;
profile registration comparison confirms no new profiles were created.

The old 146 app, coherent profile snapshot and profile registry are backed up in
`~/Library/Application Support/Cloakfox/app-backups/install-157-20261014T0036Z`.
The generated source package is
`firefox-src/obj-aarch64-apple-darwin/dist/cloakfox-157.0.1-beta.25.en-US.mac.dmg`.
