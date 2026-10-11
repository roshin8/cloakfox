# Native container WebRTC policy

Implemented in `patches/cloakfox-webrtc-network-policy.patch`, touching only
`dom/media/webrtc/jsapi/PeerConnectionImpl.cpp` and `.h`. The corresponding
Firefox source is already edited. Add the new patch immediately after
`webrtc-ip-spoofing.patch` in `patches/order.txt`. Do not reapply it to this
already-edited source without reversing its delta first.

## Enforcement

At the start of native `Initialize`, before obtaining STS or creating the media
transport handler, the code obtains the responsible window's document and its
BrowsingContext origin attributes. Its `userContextId` selects
`cloakfox.container.<ucid>.network_mode` and `.webrtc_mode`.

- Missing preferences mean normal/inherit (zero).
- `network_mode != 0` disables WebRTC, including proxy, blocked and unknown modes.
  No claim is made that Firefox's proxy service routes arbitrary RTC UDP traffic.
- With normal networking, WebRTC mode zero permits ordinary calling, one enforces
  native relay-only ICE, and two or any unknown/negative value disables RTC.
- A configured preference with the wrong type fails closed. Missing responsible
  context also rejects initialization instead of falling back to container zero.
- This logic never reads `cloakfox.enabled`; disabling fingerprint spoofing does
  not disable the network policy.

Every native `SetConfiguration` computes the effective mode again and overrides
`SetIceConfig`'s transport policy with `Relay` when required. A page calling
`setConfiguration({iceTransportPolicy:'all'})` cannot relax it. The DOM-facing
configuration may still report the page's requested value (Firefox deliberately
hides preference configuration adjustments); the enforcement point is native
transport creation/configuration, not rewritten SDP/candidate strings.

Relay-only means TURN relay candidates. It does not proxy the connection to the
TURN server or promise that the relay operator cannot see the source IP. No
configured TURN server means calls may fail, which is the expected tradeoff.

## Existing connection lifetime

Each initialized PC registers a prefix preference callback for its exact
container, then filters exactly `network_mode`, `webrtc_mode` and `proxy_url`.
Changes to any of these close the existing PC even if they relax policy: a new
connection must be created under the new configuration. Unrelated identity
preferences and other containers do not match. The callback holds a temporary
strong reference while closing, and unregisters on `Close` and in the destructor.

Ordinary Gecko `Close` defers transport removal until final stats/call shutdown,
including an opportunity to send RTCP BYE. Policy changes additionally call
`RemoveTransportsExcept({})` immediately before normal closure, avoiding that
intentional delay. Actual socket-process work still uses asynchronous dispatch.
Parent-to-content preference propagation is asynchronous too. This does **not**
establish an instantaneous, machine-wide packet kill switch at the time the UI
writes a preference. In-flight/queued packets, direct non-RTC network paths and
unrelated browser services need separate enforcement/packet-capture evidence.

## Verification

`python3 -m unittest discover -s tests/network -v` passes. It extracts the actual
production C++ mode resolver from the maintained patch, compiles it with the
local C++ compiler and exercises normal, relay, proxy, disabled, negative and
unknown/large values. It initially failed for the missing resolver. No Gecko
build is required; the test also works before downloading Firefox source.

`git apply --numstat patches/cloakfox-webrtc-network-policy.patch` parses the new
patch. The full native translation unit has **not** been compiled by this worker;
controller build/review remains required.

`tests/fingerprint/probe_native_webrtc_policy.py` is a disposable-profile live
probe for controller execution after rebuilding:

```sh
CLOAKFOX_BIN=/absolute/path/to/cloakfox \
  python3 tests/fingerprint/probe_native_webrtc_policy.py
```

It uses two nondefault containers, disables the spoofing master switch, checks
normal construction and rejection in disabled/proxy/unknown modes, and observes
native closure after policy/route changes. A local UDP STUN listener supplies a
positive-control packet count in normal mode; relay-only must send zero packets
to a fresh listener even after the page requests `all` again. Failure to receive
normal-mode packets fails the test as inconclusive rather than treating silence
as evidence. The probe never contacts an external STUN/TURN endpoint. Existing
normal background browser traffic is outside its packet counter.

The live probe was syntax-checked but **not run** here. It does not test usable
TURN-relay calls, IPv6/external packet captures, every embedded-frame origin
combination, preference delivery races or all platform transport implementations.
Run these before making a broad no-leak claim. No native build, browser run,
production profile operation, commit or change to other patches was performed.

### Dynamic-pref IPC correction

Controller live testing found that changing only `proxy_url` did not reach the
native callback: Firefox sanitizes unknown dynamic string preferences out of
content preference IPC. Native policy now also observes numeric `network_epoch`
and `effective_webrtc_mode` supplied by the parent's NetworkPolicy module.
The resolver combines raw policy and the parent's typed effective mode using the
most restrictive result: either disabled/invalid blocks, otherwise either relay
requires relay. An absent effective pref retains the legacy raw checks.
This also handles wrong-type string raw modes that otherwise appear absent in
content. The controller owns parent mirror/observer integration.

The production resolver test now covers effective relay/disabled/invalid values
and passed after extending the native implementation. The live probe additionally
sets malformed string network/WebRTC prefs in the parent and expects existing
connection closure and constructor rejection in content. This updated probe was
syntax-checked only by the worker; controller rerun remains required.
