# HTTP/3 fingerprint patch port to Firefox 155.0.1

Ported `patches/http3-fingerprint-spoofing.patch` against its ordered Firefox
155.0.1 pre-patch snapshot. Only this patch and this report were edited in the
worktree; the shared Firefox source was not modified.

## Compatibility changes

- Preserved Firefox 155's `fast_pto` / `aFastPto` constructor parameter and added
  the fingerprint profile immediately after it in both native-socket and NSPR
  paths. `Http3Session`, the C++ wrappers, the Rust FFI functions, and
  `NeqoHttp3Conn::new` use the same argument order.
- Kept the upstream removal of `provider_flags` from the Neqo constructor.
  Existing Firefox 155 TLS setup and fast-PTO handling remain intact.
- Retained the new `connect_udp::ClientSession` and
  `webtransport::ClientSession` trait imports while importing the profile enum.
- Kept Firefox 155's new congestion-control preferences, includes, QPACK
  settings structure, and SETTINGS decoder. The profile additions use the
  current `Http3Parameters` accessor API.
- Rebuilt the vendored checksum manifest from the Firefox 155 baseline, changing
  only hashes for `src/conn_params.rs`, `src/lib.rs`, and `src/settings.rs`.
  The complete current file inventory, other hashes, and package metadata are
  preserved.

The master switch still forces the Firefox profile when disabled. When enabled,
the container preference overrides the global profile; unknown profile numbers
fall back to Firefox. Chrome and Safari retain the original patch's SETTINGS
ordering and values, with decoder blocked-stream capacity raised to at least
100. Profile zero preserves the Firefox 155 SETTINGS behavior.

## Validation

- `python3 /tmp/cloakfox-port-patch.py generate http3-fingerprint-spoofing.patch`
  passed: the patch applies with fuzz zero to its Firefox 155 snapshot and all
  resulting files match the resolved working files byte for byte.
- All four modified Rust files parse with `rustfmt --emit stdout --config
  skip_children=true --edition 2024`. An initial formatting check using edition
  2021 rejected an upstream let-chain; the corrected edition parses it.
  Existing unrelated formatting differences were left untouched.
- An isolated Rust harness compiled the extracted production profile enum and
  SETTINGS conversion alongside the unpatched Firefox 155 conversion. Both
  tests passed: 288 combinations of default/unknown profiles, QPACK capacities,
  and feature flags matched the upstream conversion, and Chrome/Safari produced
  the preserved ordered setting/value pairs. The harness uses parameter/type
  stubs, so this is a mapping regression check, not a full Neqo integration test.
- Verified that the checksum manifest changes exactly the three expected
  entries, and each matches SHA-256 of the ported source.
- Inspected both C++ initialization call sites and both Rust FFI forwarding
  paths for matching parameter names, order, and types. Existing `u32`/`u64`
  QPACK table-size widening at the C++/Rust boundary remains unchanged.

The temporary regression harness is at
`/var/folders/ft/76f9yg5n45x3bvcrbb7kp6yc0000gn/T/cloakfox-155-port-7aslxcji/http3-port-settings-regression.rs`.

## Remaining integration checks and inherited risks

Full Gecko/Neqo compilation, generated FFI headers, and live HTTP/3 traffic were
not tested by this isolated port. The integrating task must compile the complete
ordered stack and test both I/O modes, container profile selection, master-off
fallback, QPACK-heavy responses, and connection reuse/resumption.

The original Safari profile advertises a fixed QPACK table capacity of 4096,
while the actual decoder retains the configured global table size. A configured
capacity below 4096 can therefore disagree with the advertised capacity. The
port preserves that existing behavior. Alternate profiles also preserve their
original sparse feature advertisements; compatibility with WebTransport and
CONNECT-UDP needs runtime validation. No claim is made that the inherited
Chrome/Safari shapes match current external browser versions.

The shared patch helper initially omitted missing-final-newline markers, which
would break checksum-file diffs. This was reported to the integrating task and
fixed centrally before generation succeeded.
