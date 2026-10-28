# Additional Firefox159 privacy boundary tests

Test-only changes following the coherent GPU catalog checkpoint36aef7ee7f.
The same self-contained native159 acceptance app was used headlessly; no installed
application, personal profile, Chromium build input or product setting changed.
Temporary profiles contain authored local canaries only.

## New runtime coverage

- `probe_container_storage_channels.py`:70assertions. Cookies as observed by both
  document and local HTTP server, local/session storage, IndexedDB, Cache API,
  live SharedWorker state and BroadcastChannel separation. Same-owner tabs prove
  the channels work; other containers/origins must remain separate. Reload and
  restart verify persisted own data and nonpersisted tab/worker memory.
- `probe_webrtc_codec_coherence.py`:54assertions. Audio/video sender and receiver
  capabilities must be negotiable in generated SDP; mappings/parameters must
  agree across two containers, return visits and the same binary's master-off
  native control. No capture, setLocalDescription, ICE gathering or public server.
  No raw SDP, certificate fingerprint or ICE credential is saved. This does not
  compare against an independent stock Firefox binary or certify media delivery.
- `probe_graphics_settings_atomicity.py`:25assertions. Real privileged Settings
  modules reject malformed/incompatible capability tables, a missing canonical
  backend and invalid multi-field presets before writing any preference. Valid
  activation/override positive controls pass. Complete snapshots stay in chrome
  memory; secret values are not returned. This is synchronous Settings preflight,
  not a proof of atomic live propagation across all worker/frame races.

All149new assertions passed. The full browser-backed Python suite passed157tests
in79.02seconds and the Node suite passed369tests. The new probes use the normal `probe_*.py` discovery
and require `CLOAKFOX_BIN` and the existing Selenium/geckodriver setup.

Six existing probes were rerun successfully: worker lifecycle/policy updates,
site noise/third-party frames, ws/wss routes/reconnect/proxy refusal, native RTC
policy/STUN refusal, identity forgetting and bundled font rendering. Exact probe
outcomes and report hashes are recorded in `acceptance.json`.

Initial fixture failures were corrected without product changes: the shared
navigation helper finds the first tab matching a URL, so each test tab now has a
distinct query while retaining its identical origin. The first restart fixture
used a session cookie but expected persistence; the actual persistence fixture
now explicitly sets Max-Age. Those failures were not evidence of identity leaks.
Independent read-only review found no actionable defect in these three probes.

## What the CreepJS warnings actually test

Pinned source: CreepJS10aa6724cd33a1015db1574211890518cd04f0cc, recorded in
`tests/fingerprint/libraries/upstreams.json`; the upstream fixture was unchanged.

- `src/webgl/index.ts:446–478` computes a GPU-brand/capability hash and a numeric
  capability checksum and tests membership in two fixed recognized lists.
  An unrecognized but executable virtual profile can fail those checks. The
  recorded protected default case has WebGL `lied=false`, while its trash list
  contains suspicious GPU/capabilities. Those warnings do not establish actual
  native hardware identity disclosure or resource validation failure.
- `src/domrect/index.ts:300–315` hashes a known rotated element. Its Gecko branch
  recognizes one hash (`e38453f0`). Protected geometry can remain internally
  consistent and still differ from that one expected result.

To address the GPU checks behaviorally, a future profile needs a verified full
capability/precision/range combination recognizable for its declared family,
which the canonical backend can enforce in real shader/resource operations.
The new whole numeric cohorts are not reference-backed complete physical-driver
profiles. Merely copying recognized getter values would not establish execution
support or protection against other detectors.

For rectangle recognition, investigate replacing additive presentation jitter
with canonical layout/geometry behavior across relevant fonts, CSS transforms,
DOM/Range/SVG APIs and painting/hit testing. Matching a single detector hash does
not establish that larger contract. Identical standardized measurements across
containers need not share identity secrets, but changing the current per-owner
geometry presentation requires an explicit privacy/compatibility design and
regressions. No detector-specific rectangle exception, native-value fallback,
warning suppression or privacy-setting relaxation was added here.

Still unverified: exhaustive setting combinations, arbitrary worker/cache
revision races, long-term cross-device linkability, OS VPN changes, complete SDP
normalization against stock Firefox, remote media transport, and non-Mac builds.
These additions do not rerun all166currently discovered integration probes and
do not prove the absence of every privacy leak.
