# Auto-coordinated per-container HTTP/2 & HTTP/3 fingerprint profiles

**Status:** approved design (brainstormed 2026-07-26)
**Branch:** `cpp-first-exploration`

## Problem

A container's HTTP/2 and HTTP/3 wire fingerprint (SETTINGS frame shape,
HPACK pseudo-header order, WINDOW_UPDATE, H3 SETTINGS) is controlled by two
**global** prefs — `network.http.http2.fingerprint_profile` (string) and
`network.http.http3.fingerprint_profile` (int) — read in the network/socket
process. Everything else in Cloakfox is per-container (keyed by
`userContextId` via `cloak_cfg_<ucid>`), but the HTTP transport profile is
browser-wide and unrelated to the container's persona.

That means the transport-layer identity can diverge from the JS/UA identity
(e.g. a Chrome H2 SETTINGS frame under a Firefox `navigator.userAgent`),
which is itself a detectable mismatch.

## Goal

The H2/H3 wire fingerprint of every connection should **match the persona
of the container that connection belongs to** — derived, never a user knob.
Coherence by construction.

Today all personas are normalized to a **Firefox** UA (`normalizeUA` forces
`Firefox/rv:`) and both profile prefs already default to `firefox`, so the
mechanism resolves to `firefox` everywhere — identical to current behavior.
It becomes multi-valued automatically once personas gain Chrome/Safari UAs.
This work makes the mechanism ready and correct for that; sourcing non-Firefox
personas is a separate prerequisite (out of scope here).

## Non-goals (YAGNI)

- No user-facing UI toggle — the profile is auto-derived from the persona.
- No Chrome/Safari persona *sourcing* — separate work; this is inert (but
  correct) until it lands.
- No TLS/JA3/JA4 spoofing — separate, already deferred (needs NSS patches).

## Approach (chosen)

**Per-container prefs + resolve in the network process.** The persona layer
derives the profile from the UA browser family and writes two dedicated
per-container prefs; the H2/H3 code reads them keyed by the connection's
`userContextId`, falling back to the existing global pref.

Rejected alternatives:
- *cloak_cfg overlay lookup* — would make `netwerk/` parse the JSON overlay
  and link against `dom/base` MaskConfig, a layering dependency it doesn't
  have.
- *Stamp onto `nsHttpConnectionInfo`* — fastest reads but adds fields to a
  core shared network class; most invasive.

## Data flow

```
persona UA family ──derive──▶ cloakfox.container.<ucid>.h2_profile  (string)
   (CloakfoxPersonas)          cloakfox.container.<ucid>.h3_profile  (int 0/1/2)
                                        │  (written wherever cloak_cfg is written)
                                        ▼
   H2: Http2Session reads pref by mConnInfo userContextId ─▶ SETTINGS/HPACK shape
   H3: C++ neqo glue resolves pref by conn userContextId ─▶ Http3Parameters
                                        │                     .fingerprint_profile(...)
                        fallback ▶ global network.http.http{2,3}.fingerprint_profile
                                   (default "firefox" / 0)
```

## Components

### C1 — persona → profile derivation (JS)

`additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs`

A pure function:

```
deriveHttpProfile(ua) -> { h2: "firefox"|"chrome"|"safari", h3: 0|1|2 }
```

Browser family is taken from the UA (mirrors the existing
`detectOSFromUA` / `NAV_IDENTITY` pattern). H3 int mapping matches
`cloakfox.cfg` and the test harness: `firefox=0, chrome=1, safari=2`. With
today's Firefox-only personas this always returns `{h2:"firefox", h3:0}`.
Single source of truth; unit-testable with no browser.

### C2 — per-container pref write (JS)

Every site that writes a container's `cloak_cfg` pref must also write the two
profile prefs from `deriveHttpProfile(ua)`:
- `additions/browser/extensions/cloakfox-shield/experiment-apis/cloakfox.js`
  (`regeneratePersona` / `buildCloakCfg` path)
- `additions/browser/components/cloakfox/content/settings.js` (3 write sites)

To avoid divergence, the write is done through one shared helper (e.g.
`writeHttpProfilePrefs(ucid, ua)` exported from `CloakfoxPersonas`) rather
than reimplemented per call site.

Prefs (not `cloak_cfg` JSON) are used so the network stack reads them cheaply
in-process with no dom/base coupling.

### C3 — H2 consumption (C++)

`patches/http2-fingerprint-spoofing.patch` → `Http2Session.cpp`

Replace the two global `Preferences::GetCString(
"network.http.http2.fingerprint_profile")` reads with a helper
`ResolveH2Profile(uint32_t userContextId)` that reads
`cloakfox.container.<ucid>.h2_profile` and falls back to the global pref
(which itself defaults to `firefox`).

- SETTINGS-frame site: `mConnInfo->GetOriginAttributes().mUserContextId` is
  directly available.
- HPACK pseudo-header-order site: in the header-compression path; the
  `userContextId` may need to be threaded from the `Http2Session` to the
  compression call. **Plan-time item:** confirm the exact class and thread
  the id if the compressor lacks conn info.

### C4 — H3 consumption (C++ / Rust FFI)

`patches/http3-fingerprint-spoofing.patch` → `netwerk/socket/neqo_glue/src/lib.rs`
+ its C++ caller.

Currently neqo reads the H3 profile from `static_prefs` internally. Change so
the profile is resolved in **C++** (where the connection's origin attributes
and prefs are available), then passed to neqo via the existing
`Http3Parameters::fingerprint_profile(...)` builder — one added FFI argument.
The Rust profile logic is unchanged. **Plan-time item:** confirm the C++ call
site into neqo_glue has the connection's `userContextId` and add the FFI arg.

## Testing / validation

- **Unit (Vitest / node):** `deriveHttpProfile` for representative
  firefox/chrome/safari UAs; a coherence assertion that the derived family
  matches the UA family emitted into `cloak_cfg`.
- **End-to-end H2:** extend `tests/fingerprint/test_h2_profile.py` +
  `mitm_h2_observer.py`. Force `cloakfox.container.5.h2_profile=chrome`, open
  a tab in container 5 (chrome-context, per `probe_container_isolation.py`),
  and assert its H2 SETTINGS/HPACK emit the **Chrome** shape while a
  default-container connection stays **Firefox** — proving per-container
  selection. Analogous check for H3 SETTINGS via the H3 profile test.
- **Coherence regression:** with a Firefox persona, the derived profile is
  `firefox` (default) — confirm no behavior change from today.

## Fallback / edge cases

- No per-container pref, worker / no-container connection, or a connection
  opened before the pref is written (cold start) → global default (`firefox`).
  Coherent for Firefox personas.
- Connections are already partitioned by origin attributes (which include
  `userContextId`), so a connection binds to a single container — no
  cross-container connection reuse to reconcile.

## C4 implementation notes (execute-ready, mapped 2026-07-26)

Add `fingerprint_profile: u32` threaded from C++ (resolved per-container)
into neqo, replacing neqo's internal `static_prefs` read. Param goes
**right after `idle_timeout`** everywhere for consistency. cbindgen
regenerates `neqo_glue_ffi_generated.h` automatically.

Edits (all in `patches/http3-fingerprint-spoofing.patch` unless noted):

1. `neqo_glue/src/lib.rs` — `NeqoHttp3Conn::new` (sig ~341): add
   `fingerprint_profile: u32` after `idle_timeout: u32` (i.e. before
   `pmtud_enabled: bool, socket: Option<i64>`). Body (~453): replace
   `H3FingerprintProfile::from_pref(static_prefs::pref!("network.http.http3.fingerprint_profile"))`
   with `H3FingerprintProfile::from_pref(fingerprint_profile)`.
2. `lib.rs` — `neqo_http3conn_new` FFI (~745): add `fingerprint_profile: u32`
   after `idle_timeout: u32`; pass it to `new(...)` after `idle_timeout`
   → `new(..., idle_timeout, fingerprint_profile, pmtud_enabled, Some(socket))`.
3. `lib.rs` — `neqo_http3conn_new_use_nspr_for_io` FFI (~792): same add;
   call becomes `new(..., idle_timeout, fingerprint_profile, false, None)`.
4. NEW hunk — `netwerk/socket/neqo_glue/NeqoHttp3Conn.h`: add
   `uint32_t aFingerprintProfile` after `aIdleTimeout` to both `Init` and
   `InitUseNSPRForIO`, and pass it to the FFI call after `aIdleTimeout`.
5. NEW hunk — `netwerk/protocol/http/Http3Session.cpp` (~165, before the
   `NeqoHttp3Conn::Init*` calls): resolve
   ```
   uint32_t h3Profile = StaticPrefs::network_http_http3_fingerprint_profile();
   nsAutoCString cfxKey;
   cfxKey.AppendPrintf("cloakfox.container.%u.h3_profile",
                       mConnInfo->GetOriginAttributes().mUserContextId);
   int32_t perCtx = Preferences::GetInt(cfxKey.get(), -1);
   if (perCtx >= 0) h3Profile = static_cast<uint32_t>(perCtx);
   ```
   then pass `h3Profile` after `idleTimeout` to both `Init`/`InitUseNSPRForIO`
   calls. Add `#include "mozilla/Preferences.h"` if not already present.

Hunk headers: use the scratchpad recompute script (count body ' '/'+'/'-'),
ignore the trailing EOF empty line. Verify: `make dir` clean, then targeted
compile — `mach build netwerk/socket/neqo_glue` (Rust + cbindgen) and
`mach build netwerk/protocol/http` (Http3Session). Global fallback keeps a
partial landing safe.

## Risks

- **Network-stack change with a ~30-min build-verify loop.** Mitigation:
  land C1/C2 (JS) first with unit tests (no build), then C3 and C4 as
  separate build-verified steps; keep the global fallback so a partial
  landing never breaks the default path.
- **HPACK compressor / neqo FFI may need `userContextId` threaded** — flagged
  as plan-time confirmations above; both fall back to the global pref if the
  container id is unavailable.
