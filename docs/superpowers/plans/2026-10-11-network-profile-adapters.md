# Network profile adapters implementation plan

> For agentic workers: use superpowers:executing-plans inline. The user explicitly requested implementation/testing without plan-review pauses.

**Goal:** Make browser-family network intent independent of the rendering engine, implement a native opt-in Gecko transport profile, and measure every implemented field against the local Chrome reference.

**Architecture:** A parent-process registry owns a versioned profile ID and container intent. A Gecko adapter captures that ID in connection metadata; H2, NSS TCP TLS and neqo QUIC consume the captured value. Future Chromium support supplies its own adapter through the same registry contract, without inheriting Gecko preferences.

**Spec:** ../specs/2026-10-11-network-identity-toggle.md

**Constraints:** Default off; master off restores native behavior. Preserve verification, policy restrictions, proxy/DNS routing and exact owner isolation. Do not advertise unimplemented protocols. Show concrete validation gaps rather than claiming full Chrome equivalence. Local fixtures only. No user profiles or system trust-store changes.

## Review focus

- Changes while requests are queued: connection metadata must stay coherent across all protocols.
- TLS resumption and coalescing must not cross selected transport profiles or containers.
- Policy restrictions and conservative/update connections take priority over shaping.
- Unsupported identity families and future uninstalled engines must show their actual status.
- Settings from more than one window must remain container scoped and persistent.

## Task 1: Registry and container toggle

- [x] Add behavioral tests for default-off, Chrome/Firefox/unsupported identities, master off and an unavailable engine adapter.
- [x] Run the tests; verify missing profile behavior fails.
- [x] Implement `CloakfoxNetworkProfiles.sys.mjs` with `resolveNetworkProfile(ucid, ua)` and `writeNetworkProfile(ucid, ua)`; preserve the old persona helper as a delegating interface.
- [x] Bind the Identity toggle to its selected container and display the active adapter/validation status. Reconcile profile on startup, cfg changes, toggles and identity imports.
- [x] Run Node behavior tests and a live Settings test.

## Task 2: Native Gecko TCP/H2 adapter

- [x] Add a real local wire probe selecting Chrome through the production registry; assert Chrome cipher/group/key-share order, H2 settings and pseudo-header order; verify default/master off restore stock. Verify untrusted and wrong-host rejection.
- [x] Run on baseline and capture the expected mismatch.
- [x] Capture versioned profile metadata in connection/TLS provider flags, including pooling and TLS peer IDs; preserve security flag bits. Use that snapshot for H2 and NSS.
- [x] Add per-socket NSS shaping using implemented cipher/group/key-share ordering, extension permutation and GREASE. Keep unsupported negotiated extensions absent and expose that validation gap.
- [x] Correct legacy Chrome H2 settings from the measured reference and run the wire probe.

## Task 3: Native QUIC/H3 adapter

- [x] Extend the local probe to real QUIC: assert configured flow-control/stream/datagram limits and H3 SETTINGS, using the captured connection profile.
- [x] Run on baseline and capture expected mismatches.
- [x] Configure real neqo limits/decoder capacities, preserving Firefox defaults. Use the same NSS profile for QUIC TLS. Do not invent unsupported QUIC parameters.
- [x] Run QUIC tests including profile/master changes, container ownership and refusal/proxy controls. Full Chrome fallback/resumption/0-RTT acceptance remains open.

## Task 4: Verification and measured completion status

- [x] Run patch replay, Node/Python suites and relevant local runtime probes.
- [x] Rebuild/package and test the mounted DMG if native checks are green.
- [x] Dispatch one fresh whole-change reviewer and repair the three correctness findings with regression tests.
- [ ] Complete the fourth Important finding: full Chrome matching/acceptance; experimental intermediate work is not certified complete for that scope.
- [x] Record implemented fields and remaining ALPS/trust-anchor/QUIC semantics explicitly. Full Chrome equivalence remains incomplete until those protocols and resumption/ECH/0-RTT cases are implemented and verified; do not equate matching basic wire fields with full equivalence.
- [x] Commit/push verified intermediate work (`6d7253986e`) and record exact limits. Full matching remains open.


## Task 5: Continue full-protocol conformance (2026-10-11)

The user requested completion of the remaining matching requirement. Resume on
this worktree at b93259177a. This task does not redefine full matching as a
smaller measured subset.

- [x] Capture detailed real Chrome TLS/H2 and QUIC/H3 shape without secrets.
- [x] Extend real runtime checks for signatures, GREASE placement/lengths,
  compression and absent Firefox-specific extensions; observe baseline RED.
- [x] Implement per-socket NSS presentation while preserving policy filtering.
- [x] Implement measured Initial/DCID/SCID, version, receive/datagram and GREASE behavior.
- [ ] Implement full QUIC loss/migration and real H3 ORIGIN semantics.
- [x] Implement real TCP/H3 ALPS negotiation, authenticated client EE, application
  settings consumption and isolated resumption/accepted0RTT cache behavior.
- [x] Verify fresh real TCP ECH decryption through verified DoH/HTTPS records.
- [ ] Complete ECH retry/QUIC and trust-anchor behavior; do not add fake bytes.
- [x] Verify TLS1.2/1.3 resumption, HRR, QUIC Retry/accepted0RTT and ownership/security.
- [ ] Complete QPACK pressure and advanced QUIC fallback/migration acceptance.
- [x] Verify the latest packaged application (16 mounted local runtime probes).
- [x] Record the actual conformance boundary.
- [x] Commit and push the verified continuation (`cf2c058d4d`). Full-matching work above remains open.

Interfaces: the versioned Gecko connection snapshot remains authoritative;
new NSS presentation options are per socket, never global defaults. Native
Firefox mode must retain its wire behavior. Chromium remains an independent
future engine adapter.
