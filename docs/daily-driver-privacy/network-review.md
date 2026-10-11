# Network review and fixes — 2026-09-07

Independent source/API review found the following actionable defects. The
controller authorized fixes after review; all listed defects are now addressed
in additions and mirrored Firefox source. No browser/build was run by reviewer.

## Findings resolved

### P1 — Wrong-type configured modes silently became inherited/direct

`additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs:31`.
Original `getIntPref(name, 0)` treated a string/boolean mode as absent. Actual
Gecko `nsPrefBranch::GetIntPrefWithDefault` in `modules/libpref/Preferences.cpp`
returns its supplied fallback on type errors as well as absence. This contradicted
native RTC's fail-closed mode parsing. The getter now checks pref type first:
only absent means zero, configured noninteger type means disabled. Tests model
Gecko's real type/fallback boundary and exercise string and boolean values.

### P1 — Opt-out could start new third-party fallback requests

`additions/browser/components/cloakfox/CloakfoxWebRTCSync.sys.mjs:87` and `stopSync`.
Generation checks originally protected only publication. A pending failed ipify
request could start `icanhazip.com`/`v6.ident.me` after opt-out. An isolated VM
execution of the original module reproduced exactly those two new requests.
The fix aborts tracked active controllers on stop/superseding refresh and checks
current enabled state and generation before *every* fallback endpoint. Tests
verify abort signals, no post-opt-out fallback, and no superseded fallback.
Requests already transmitted before cancellation cannot be retracted.

### P1 — Default-container policy incorrectly captured browser services

`additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs:71`.
System-initiated channels also normally carry `userContextId: 0`; the original
undefined-only exception could proxy/block browser background services when the
default container changed, contrary to UI scope. The filter now retains the
browser route only when the loading principal is system and the triggering
principal is system or absent. A system loading principal with a content
triggering principal still receives the container policy; expanded/nonsystem
principals are not exempted. Tests cover these boundaries. Actual page/channel
probes still need to verify browser principal combinations across request types.

### P2 — A throwing success callback could be invoked twice

`additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs:100`.
The original success callback was inside the routing try/catch. A consumer
exception was misclassified as a proxy construction error, cancelling a valid
channel and invoking the callback again. The filter now computes/cancels before
its single callback invocation outside the catch. A throwing-callback regression
verifies exactly one invocation and no spurious cancellation.

## API checks and limits

The argument order to `nsIProtocolProxyService.newProxyInfo` matches the current
IDL: type, host, port, authorization, isolation key, flags, timeout, failover.
`TRANSPARENT_PROXY_RESOLVES_HOST` and `ALWAYS_TUNNEL_VIA_PROXY` are actual flags;
a null failover pointer results in `NS_ERROR_NOT_AVAILABLE` when no next proxy
exists in `GetFailoverForProxy`, rather than an invented direct entry. Extension
proxy filters register at position zero, below this filter's position. The
API explicitly permits other competing filters, so this is not protection
against hostile privileged browser code.

Initialization is called in BrowserGlue `_beforeUIStartup`, before first-window
startup, and independent native RTC enforcement covers nonzero network modes.
The BrowserGlue import catch still intentionally ignores missing modules; release
packaging/probes must gate delivery to catch registration failures. This review
does not establish fail-closed behavior under arbitrary broken installation.

The native proxy API only sees channels/protocols supporting proxy resolution.
It is not a whole-machine firewall. The UI correctly notes that existing downloads
may continue and pages must reload on route changes; native RTC closure also has
asynchronous preference/transport propagation. DNS/IPv6/QUIC/WebSocket,
service-worker, startup and route-change packet capture remain release checks.
The loopback Necko probe supplies useful HTTP routing/refusal evidence but does
not by itself cover those other paths.

## Verification

Five new regressions failed before production changes. Afterwards:

```
node --test tests/fingerprint/test_network_policy.mjs tests/fingerprint/test_webrtc_lookup.mjs
12 tests passed, 0 failed
```

Both modified modules were copied to `firefox-src/browser/components/cloakfox`.
No settings UI, BrowserGlue, native patches or other owner files changed in this
fix pass. Real Gecko routing/probe results remain the controller's responsibility.
