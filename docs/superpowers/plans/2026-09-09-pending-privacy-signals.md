# Pending Privacy Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining daily-driver fingerprinting gaps without creating internally contradictory identities or claiming protection that has not been measured at the wire and browser-runtime levels.

**Architecture:** Keep Cloakfox cpp-first. Native patches own observable web-platform behavior; privileged JSWindowActors are allowed only where the repository already uses them. Do not add MAIN-world injection. Preserve Firefox 155 behavior and generate coherent Firefox personas rather than impersonating Chromium or Safari. Broad persona fields stay container-scoped; randomized readouts stay deterministically keyed by the container secret and top-level schemeful site.

**Tech Stack:** Firefox 155.0.1, Gecko/C++, privileged JavaScript modules and JSWindowActors, Python/Selenium probes, Node `node:test`, local HTTP/HTTPS/WebRTC fixtures, NSS and Neqo only if measurement proves changes are necessary.

**Spec:** This handoff plus [CLAUDE.md](../../../CLAUDE.md), [privacy completion report](../../privacy-completion/README.md), and [font limitations](../../../bundle/fonts/README.md).

## Global Constraints

- Work in `/Users/zeus/Documents/cloakfox/.worktrees/firefox-155-compat` on `codex/firefox-155-compat`. Do not modify the original checkout.
- Start with `git status --short`. The worktree is intentionally dirty and contains a large, interdependent privacy implementation. Never reset, clean, or replace files wholesale.
- The latest pushed commits are `b576ae8443` (container-comparison IP warning) and `f57794c472` (plain punctuation fix). Most privacy-completion work is still uncommitted.
- A font-profile migration is already present in `additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs`, with tests in the currently untracked `tests/fingerprint/test_persona_version.mjs`. Preserve and finish that work rather than reimplementing it.
- `additions/` is the maintained source for copied browser files. Mirror only the touched files into `firefox-src/` for a local build; do not copy the entire tree blindly.
- Keep `privacy.resistFingerprinting=false`; Cloakfox's native per-container behavior replaces global RFP.
- Never add independent random values. Every exposed field must be sampled as part of a coherent persona or derived from the same container/site seed.
- Compare against stock Firefox 155 on the same host before changing low-level behavior. Passing public fingerprint sites is supporting evidence, not an acceptance test.
- Read the current completion report before `PENDING.md`. The lower historical sections of `PENDING.md` contain stale findings that later work already closed.

## Current Verified Baseline

- A full macOS arm64 build completed and the recorded suite passed 183 Node tests and 22 browser probes. See `docs/privacy-completion/` for logs and `verification.json`.
- Native browser probes cover current fonts, WebGL readback, media capabilities, WebRTC network policy, HTTP/2 and HTTP/3 configuration, worker lifecycle, container workflows, and identity reset behavior.
- The bundled font pack contains 31 fonts, but aliases and host rasterizers remain distinguishable across macOS, Windows, and Linux.
- WebRTC address leakage is controlled, but SDP ordering and capability shape have not been normalized against a stock Firefox baseline.
- HTTP/2 and HTTP/3 preference plumbing exists. TLS ClientHello, QUIC, and WebSocket handshakes have not been fully compared at the wire level, and cross-engine transport impersonation is not an approved goal.
- `patches/websocket-spoofing.patch` is an optional kill switch: it makes the `WebSocket` constructor throw when `webSocket:disabled` is true. It does not spoof WebSocket framing, extension negotiation, protocol choice, or timing. Existing HTTP header, proxy, and HTTP/2 policies may affect the handshake, but that inheritance lacks a dedicated end-to-end probe.
- IP conflicts are detected after an eligible request completes. That can warn and block subsequent navigation, but it cannot retract the first destination request.
- Automatic updates, downloaded Safe Browsing lists, signing/notarization, and Windows/Linux binaries remain release-security work and must not be described as complete.

---

### Task 1: Stabilize the font privacy model and finish the migration

**Files:**
- Modify: `additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs`
- Modify: `bundle/fonts/font-manifest.json`
- Modify: `bundle/fonts/README.md`
- Test: `tests/fingerprint/test_persona_version.mjs`
- Test: `tests/fingerprint/test_font_manifest.mjs`
- Test: `tests/fingerprint/test_font_site_snapshot.mjs`
- Probe: `tests/fingerprint/probe_bundled_fonts.py`
- Probe: `tests/fingerprint/probe_container_fonts.py`
- Probe: `tests/fingerprint/probe_font_metric_noise.py`

- [ ] **Step 1: Capture the existing uncommitted migration behavior**

Run:

```bash
git diff -- additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs
node --test tests/fingerprint/test_persona_version.mjs
```

Expected: the test passes and shows that generated desktop Firefox personas with contradictory explicit generic-font metadata migrate to the canonical OS profile, while custom user agents and configurations without that metadata remain unchanged.

- [ ] **Step 2: Add a schema version instead of relying only on heuristics**

Add a persisted `personaSchemaVersion` to generated configurations. Make migration monotonic and idempotent:

```js
if ((config.personaSchemaVersion ?? 0) < CURRENT_PERSONA_SCHEMA_VERSION) {
  config = migrateGeneratedPersona(config);
  config.personaSchemaVersion = CURRENT_PERSONA_SCHEMA_VERSION;
}
```

Do not rewrite manually edited/custom personas unless the stored metadata identifies them as BrowserForge-generated.

- [ ] **Step 3: Standardize font inventories by target OS**

Use one common, documented font inventory per supported OS family. Remove random optional-font selection from the default generator. Keep generic serif/sans-serif/monospace values consistent with that inventory. Add tests proving two new personas for the same OS expose the same font set and different site seeds do not change inventory membership.

- [ ] **Step 4: Keep metric noise deterministic and bounded**

Verify that text metrics use the site-scoped seed, remain stable across reload and same-site iframe access, differ across unrelated top-level sites where enabled, and never turn missing fonts into present fonts. Reject values outside the current bounded-noise policy.

- [ ] **Step 5: Run font verification**

```bash
node --test tests/fingerprint/test_persona_version.mjs tests/fingerprint/test_font_manifest.mjs tests/fingerprint/test_font_site_snapshot.mjs
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_bundled_fonts.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_container_fonts.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_font_metric_noise.py
```

Expected: unit tests and probes pass; no replacement glyphs appear in Cloakfox chrome or ordinary pages.

- [ ] **Step 6: Commit only the coherent font slice**

```bash
git add additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs bundle/fonts/font-manifest.json bundle/fonts/README.md tests/fingerprint/test_persona_version.mjs tests/fingerprint/test_font_manifest.mjs tests/fingerprint/test_font_site_snapshot.mjs
git commit -m "fix: standardize generated persona font profiles"
```

---

### Task 2: Gate conflict-sensitive navigation before the destination request

**Files:**
- Modify: `additions/browser/components/cloakfox/CloakfoxIPConflicts.sys.mjs`
- Modify: `additions/browser/components/cloakfox/content/ip-warning.js`
- Modify: `additions/browser/components/cloakfox/content/ip-warning.html`
- Test: `tests/fingerprint/test_ip_conflicts.mjs`
- Probe: `tests/fingerprint/probe_ip_conflicts.py`
- Probe: `tests/fingerprint/probe_ip_conflict_settings.py`
- Add: `tests/network/test_ip_conflict_preflight.py`

- [ ] **Step 1: Write a failing first-request test**

Create a local destination server that records every request. Configure its hostname as conflict-sensitive, establish the same public-IP result in another container, then navigate from a new container.

Expected before implementation: the destination server records one request before the warning appears. The test must fail on that observation.

- [ ] **Step 2: Add a route-aware preflight state machine**

Track these explicit states per container and effective proxy route: `unknown`, `checking`, `clear`, `conflict`, `error`, and an expiry time. A cached result may be reused only for the same route and within its TTL. Proxy edits, network changes, and identity-forget actions invalidate it.

- [ ] **Step 3: Suspend eligible top-level channels before bytes leave**

At `http-on-modify-request`, identify top-level HTTP(S) loads for configured conflict-check domains. Suspend the destination channel, perform the IP lookup through the container's effective route, then resume on `clear` or cancel and open the comparison warning on `conflict`. Exclude lookup endpoints from observation to prevent recursion. Preserve POST bodies and history semantics.

If Gecko has already opened or speculatively connected the destination socket at this observer point, move the gate to the earliest native channel-creation hook and document the chosen hook. Do not call this “pre-navigation” until a packet-level test proves the destination received no connection or HTTP request.

- [ ] **Step 4: Define failure behavior in settings and tests**

Use fail-closed for strict container/proxy policies and a clearly labelled fail-open option for ordinary browsing. Timeouts must show a distinct lookup-error state, not an IP conflict. The warning's “Continue once” action must be scoped to the exact container, route, and destination.

- [ ] **Step 5: Verify behavior**

```bash
node --test tests/fingerprint/test_ip_conflicts.mjs
python -m unittest tests.network.test_ip_conflict_preflight
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_ip_conflicts.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_ip_conflict_settings.py
```

Expected: a conflict blocks the first destination request, a clear result resumes it once, lookup endpoints do not recurse, and changing the proxy invalidates the cache.

- [ ] **Step 6: Commit**

```bash
git add additions/browser/components/cloakfox/CloakfoxIPConflicts.sys.mjs additions/browser/components/cloakfox/content/ip-warning.js additions/browser/components/cloakfox/content/ip-warning.html tests/fingerprint/test_ip_conflicts.mjs tests/fingerprint/probe_ip_conflicts.py tests/fingerprint/probe_ip_conflict_settings.py tests/network/test_ip_conflict_preflight.py
git commit -m "feat: preflight conflict-sensitive container navigation"
```

---

### Task 3: Normalize WebRTC SDP to real Firefox 155 capabilities

**Files:**
- Modify: `additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxWebRTCSync.sys.mjs`
- Modify: `additions/browser/components/cloakfox/actors/CloakfoxWebRTCChild.sys.mjs`
- Modify: `patches/cloakfox-webrtc-network-policy.patch`
- Modify: `patches/webrtc-ip-spoofing.patch`
- Test: `tests/fingerprint/test_webrtc_lookup.mjs`
- Probe: `tests/fingerprint/probe_native_webrtc_policy.py`
- Probe: `tests/fingerprint/probe_webrtc_leak.py`
- Add: `tests/fingerprint/probe_webrtc_sdp.py`

- [ ] **Step 1: Record a stock Firefox baseline**

Capture offers and answers from stock Firefox 155 on the same host for audio-only, video-only, data-channel-only, and combined peer connections. Record codec order, RTP extensions, ICE options, DTLS algorithms, candidate types, and line ordering. Store normalized fixtures that remove session IDs, timestamps, ICE credentials, and certificates.

- [ ] **Step 2: Add the differential probe before code changes**

The new probe must compare Cloakfox against the normalized Firefox fixture and fail only on stable structural differences. It must separately assert that host and server-reflexive candidates remain hidden under relay-only or disabled WebRTC policy.

- [ ] **Step 3: Normalize only fields Cloakfox changes**

Keep SDP consistent with actual compiled codecs and Gecko's Firefox 155 behavior. Do not advertise unsupported codecs, reorder capabilities to resemble Chromium, or fabricate DTLS algorithms. Prefer removing persona-dependent drift at the native WebRTC serialization point.

- [ ] **Step 4: Verify calls still work**

Run a local two-peer audio/data smoke test as well as the fingerprint probes:

```bash
node --test tests/fingerprint/test_webrtc_lookup.mjs
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_native_webrtc_policy.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_webrtc_leak.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_webrtc_sdp.py
```

Expected: no forbidden address candidates, normalized structure matches stock Firefox 155, and the local peer connection succeeds.

- [ ] **Step 5: Commit**

```bash
git add additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs additions/browser/components/cloakfox/CloakfoxWebRTCSync.sys.mjs additions/browser/components/cloakfox/actors/CloakfoxWebRTCChild.sys.mjs patches/cloakfox-webrtc-network-policy.patch patches/webrtc-ip-spoofing.patch tests/fingerprint/test_webrtc_lookup.mjs tests/fingerprint/probe_native_webrtc_policy.py tests/fingerprint/probe_webrtc_leak.py tests/fingerprint/probe_webrtc_sdp.py
git commit -m "fix: align WebRTC SDP with Firefox capabilities"
```

---

### Task 4: Measure TLS, QUIC, and WebSocket handshakes before changing them

**Files:**
- Inspect: `patches/http2-fingerprint-spoofing.patch`
- Inspect: `patches/http3-fingerprint-spoofing.patch`
- Inspect: `patches/network-patches.patch`
- Inspect: `patches/websocket-spoofing.patch`
- Modify: `tests/fingerprint/probe_network_transports.py`
- Modify: `tests/fingerprint/probe_network_quic.py`
- Modify: `tests/fingerprint/probe_untested_vectors.py`
- Add: `tests/network/test_tls_fingerprint.py`
- Add: `tests/network/test_quic_fingerprint.py`
- Add: `tests/network/test_websocket_fingerprint.py`
- Document: `docs/privacy-completion/transport-fingerprint-baseline.md`

- [ ] **Step 1: Capture stock and Cloakfox wire fingerprints**

Use a local TLS observer to record ClientHello version, cipher suites, extensions, supported groups, signature algorithms, ALPN, GREASE positions, and ordering. Use a local QUIC endpoint or packet capture to record transport parameters, version negotiation, ALPN, and stable ordering. Hash normalized captures for repeatability.

- [ ] **Step 2: Test the intended invariant**

All ordinary Cloakfox personas currently claim Firefox 155. Therefore their TLS and QUIC handshakes should match stock Firefox 155 for the same preferences and platform. Add tests that fail on a stable Cloakfox-only difference. Do not expect different JA3/JA4 values per container.

- [ ] **Step 3: Capture real WebSocket handshakes**

Run local `ws://` and `wss://` endpoints and record the HTTP version, upgrade or extended-CONNECT request, ordered request headers, `Origin`, cookies, `User-Agent`, `Accept-Language`, `Sec-WebSocket-*` fields, negotiated subprotocol, permessage-deflate parameters, proxy route, DNS route, and reconnect behavior. Compare stock Firefox 155 with at least two Cloakfox containers. Assert that the optional kill switch prevents construction without removing the global `WebSocket` object.

The test must also verify strict-proxy fail-closed behavior for WebSockets. Do not normalize the random `Sec-WebSocket-Key`, application-selected subprotocols, or message payload/timing; those are protocol or application behavior rather than persona fields. If a stable handshake difference exists, repair it in the shared HTTP/proxy path so normal requests and WebSockets remain coherent.

- [ ] **Step 4: Decide from evidence**

If captures match stock Firefox, document the signal as controlled and make no NSS/Neqo patch. If they differ, identify the exact existing Cloakfox patch or preference responsible and repair that narrow difference. Open a separate plan before changing NSS or Neqo; those changes require protocol interoperability, resumption, 0-RTT, HTTP/3 fallback, and update-download tests.

- [ ] **Step 5: Verify and commit the measurement harness**

```bash
python -m unittest tests.network.test_tls_fingerprint tests.network.test_quic_fingerprint tests.network.test_websocket_fingerprint
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_network_transports.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_network_quic.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_untested_vectors.py
```

```bash
git add tests/network/test_tls_fingerprint.py tests/network/test_quic_fingerprint.py tests/network/test_websocket_fingerprint.py tests/fingerprint/probe_network_transports.py tests/fingerprint/probe_network_quic.py tests/fingerprint/probe_untested_vectors.py docs/privacy-completion/transport-fingerprint-baseline.md
git commit -m "test: record Firefox transport fingerprint baselines"
```

---

### Task 5: Remove optional self-identifying math behavior and make identity changes atomic

**Files:**
- Modify: `additions/browser/components/cloakfox/actors/CloakfoxMathChild.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs`
- Modify: `additions/browser/components/cloakfox/CloakfoxIdentityActions.sys.mjs`
- Modify: `additions/browser/components/cloakfox/content/settings.js`
- Test: `tests/fingerprint/test_persona_version.mjs`
- Test: `tests/fingerprint/test_worker_config_snapshot.mjs`
- Probe: `tests/fingerprint/probe_actor_stealth.py`
- Probe: `tests/fingerprint/probe_worker_lifecycle.py`
- Probe: `tests/fingerprint/probe_identity_forget.py`

- [ ] **Step 1: Add exact Math invariants**

Test that `Math` constants and function descriptors equal stock Firefox bit-for-bit under default settings. If `cloakfox.opt.math_constants_noise` still exists, test that it cannot be enabled through ordinary UI or migrated configuration.

- [ ] **Step 2: Remove the optional constant-noise path**

Retain deterministic noise only for functions already covered by native policy, if required. Do not alter ECMAScript constants or their descriptor flags. Remove or permanently ignore the preference and update docs.

- [ ] **Step 3: Define an atomic identity transition**

Generating a candidate persona must not apply it. Applying a selected persona must persist exactly that selection, increment a configuration revision, close/recreate affected worker contexts, clear or invalidate identity-derived caches, and reload tabs in that container. Existing cookie/site data remains unless the user chooses “Forget container data.”

- [ ] **Step 4: Prove no mixed identity remains**

Extend the worker lifecycle probe to create dedicated/shared/service workers and same-site/cross-site iframes before applying a new persona. After application, no surviving context may report the prior revision. The UI must show progress, success, and actionable failure states.

- [ ] **Step 5: Verify and commit**

```bash
node --test tests/fingerprint/test_persona_version.mjs tests/fingerprint/test_worker_config_snapshot.mjs
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_actor_stealth.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_worker_lifecycle.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_identity_forget.py
```

```bash
git add additions/browser/components/cloakfox/actors/CloakfoxMathChild.sys.mjs additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs additions/browser/components/cloakfox/CloakfoxIdentityActions.sys.mjs additions/browser/components/cloakfox/content/settings.js tests/fingerprint/test_persona_version.mjs tests/fingerprint/test_worker_config_snapshot.mjs tests/fingerprint/probe_actor_stealth.py tests/fingerprint/probe_worker_lifecycle.py tests/fingerprint/probe_identity_forget.py
git commit -m "fix: make persona transitions atomic"
```

---

### Task 6: Characterize GPU, audio, and device residuals without adding arbitrary noise

**Files:**
- Inspect: `patches/webgl-spoofing.patch`
- Inspect: `patches/webgl-readback-noise.patch`
- Inspect: `patches/audio-context-spoofing.patch`
- Inspect: `patches/audio-fingerprint-manager.patch`
- Inspect: `patches/media-device-spoofing.patch`
- Inspect: `patches/media-capabilities-spoofing.patch`
- Modify: `tests/fingerprint/probe_webgl_readback.py`
- Modify: `tests/fingerprint/probe_media_capabilities.py`
- Modify: `tests/fingerprint/probe_untested_vectors.py`
- Add: `docs/privacy-completion/gpu-audio-device-matrix.md`

- [ ] **Step 1: Build a differential matrix**

For stock Firefox and each Cloakfox OS persona, record WebGL strings/limits/extensions/readback hashes, OfflineAudioContext hashes, `enumerateDevices()` pre/post permission behavior, supported media constraints, codec/media capabilities, speech voices, and WebGPU exposure. Run each case twice in the same site and once under a different top-level site.

- [ ] **Step 2: Assert coherence, stability, and scope**

Add probe assertions for: same-site stability; container separation only where the design requires it; site-scoped differences only for protected noisy surfaces; no capability claims unsupported by the binary; permission-gated labels and stable device IDs; WebGL parameters coherent with renderer/vendor and operating-system persona.

- [ ] **Step 3: Fix only demonstrated contradictions**

Prefer a common Firefox-supported capability floor or disabling an unusually identifying API over inventing hardware. Any new noise must be deterministic, bounded, consistent across synchronous and asynchronous readback paths, and backed by a regression probe.

- [ ] **Step 4: Verify and commit**

```bash
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_webgl_readback.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_media_capabilities.py
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/probe_untested_vectors.py
```

```bash
git add tests/fingerprint/probe_webgl_readback.py tests/fingerprint/probe_media_capabilities.py tests/fingerprint/probe_untested_vectors.py docs/privacy-completion/gpu-audio-device-matrix.md
git commit -m "test: characterize residual hardware fingerprint signals"
```

---

### Task 7: Verify Windows and Linux and separate release security from fingerprint work

**Files:**
- Modify: `.github/workflows/build.yml`
- Modify: `.github/workflows/release-security.yml`
- Modify: `docs/privacy-completion/README.md`
- Modify: `README.md`
- Test: `tests/release/`
- Test: `tests/network/`

- [ ] **Step 1: Add a three-platform verification matrix**

Build macOS arm64, Windows x64, and Linux x64. On every platform run Node tests, Python unit tests, patch/source verification, and the daily-driver browser suite. Store per-platform results rather than treating source-level success as runtime parity.

- [ ] **Step 2: Add cross-platform persona assertions**

For each host platform, generate macOS, Windows, and Linux personas. Assert coherent high-level fields and record the residual rasterizer/graphics differences. A foreign-OS persona may remain distinguishable because Gecko still uses CoreText, DirectWrite, or FreeType; document this limit rather than hiding it.

- [ ] **Step 3: Keep release blockers explicit**

Do not mark the browser release-ready until CI demonstrates authenticated update metadata/MAR verification, downloaded Safe Browsing list operation with a working provider key, platform signing/notarization, and install/update rollback tests. Credentials and signing material belong in owner-controlled CI secrets.

- [ ] **Step 4: Run the full suite on the built binary**

```bash
node --test tests/fingerprint/test_*.mjs
python -m unittest discover -s tests/release
python -m unittest discover -s tests/blocker
python -m unittest discover -s tests/network
CLOAKFOX_BIN="$PWD/firefox-src/obj-cloakfox/dist/Cloakfox.app/Contents/MacOS/cloakfox" python tests/fingerprint/run_daily_driver.py --output /tmp/cloakfox-daily-results
```

Expected: all suites pass on each supported platform, with environment-dependent H3 tests reported as explicit skips only when their documented dependencies are unavailable.

- [ ] **Step 5: Update the authoritative completion report**

Record the exact commit, build identifiers, platform, test counts, output paths, known limitations, and outstanding owner-supplied release requirements in `docs/privacy-completion/README.md`. Remove or mark superseded matching entries in the top active section of `PENDING.md`; do not rewrite the historical record.

---

## Final Review Gate

- [ ] Run `git diff --check` and inspect `git status --short`.
- [ ] Confirm every modified `additions/` file that participates in the build has an identical staged copy in `firefox-src/` or is applied by a listed patch.
- [ ] Apply the full ordered patch stack to a fresh Firefox 155.0.1 source tree and compare copied sources with the working build tree.
- [ ] Run the full test command from Task 7 against a fresh full build, not an artifact from before the changes.
- [ ] Review the result against these failure conditions: cross-engine UA claims, per-read randomness, site-visible container IDs, leaked WebRTC addresses, a first conflict-sensitive destination request escaping the gate, foreign-OS fonts changing inventory per identity, mixed old/new identity contexts, or release-security claims without end-to-end evidence.
- [ ] Use `superpowers:requesting-code-review` before merge.
- [ ] Push only after all new commits and the authoritative verification report are present on `codex/firefox-155-compat`.

## Definition of Done

The work is complete when the font inventory is standardized and migrated safely; conflict-sensitive navigation is blocked before the destination receives a request; WebRTC SDP matches real Firefox 155 capabilities; TLS, QUIC, and WebSocket handshakes have reproducible wire-level baselines; Math constants remain exact; persona application cannot leave live contexts on mixed revisions; GPU/audio/device residuals have evidence-backed policies; all supported platforms have full-build runtime results; and remaining release-security dependencies are accurately reported.
