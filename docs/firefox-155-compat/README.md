# Firefox 155.0.1 port

Worktree: `.worktrees/firefox-155-compat`  
Branch: `codex/firefox-155-compat`

## Current status

The 28 initially failing patches have been ported. Compile and link validation
required updates to additional patches that originally applied cleanly;
37 patch files now differ from the captured input. All 75 patches apply in
production order with no rejected or skipped hunks (`ported-pass-15/results.json`).
All 174 patched files in the full Firefox source match the verified stack.
Three addition files also needed module-import or About dialog compatibility
updates. The macOS arm64 build succeeds. All thirteen selected live browser
probes and four HTTP/3 preference tests pass. This work is not a validated
cross-platform release.

| Check | Result |
| --- | --- |
| Original stack on 146.0.1 | 75 applied, 0 failed |
| Original stack on 155.0.1 | 47 applied, 28 failed; 71 rejected + 1 skipped hunk |
| Ported stack on 155.0.1 | 75 applied, 0 failed; 0 rejected/skipped hunks |
| Existing Node unit tests | 23 passed |
| Python probe-scoring self-test | Passed |
| New async WebGL regression | 2 tests passed, including compiled production noise helpers |
| Font cache regression harness | Compiled and passed |
| HTTP/3 SETTINGS regression harness | 2 passed; 288 default/unknown-profile combinations checked |
| macOS configuration | Passed with cbindgen 0.29.4 |
| Full macOS build | Passed (macOS arm64) |
| Live browser probes | 13/13 passed, including all 39 actor signals and the About dialog |
| HTTP/3 preference tests | 4 passed |
| Canvas extraction policy unit tests | 2 passed |
| Worker configuration cache regression | Passed |

The focused C++/Rust harnesses use extracted production code with dependency
stubs. They supplement full compilation and browser tests, and do not replace
them. Patch application uses the system tool's default context tolerance;
individual regenerated patches were also checked with fuzz zero against their
exact pre-patch snapshots.

## Porting changes

- Fonts: updated shaping signatures and cache hashing while preserving container
  IDs through text runs, transformations, and worker origin attributes. Adapted
  the new document-free font visibility provider.
- HTTP/3: updated C++/Rust constructors, retained fast-PTO arguments and new
  upstream imports, preserved profile settings, and regenerated three vendored
  checksum entries against the new dependency version.
- Geometry: moved Range hooks into AbstractRange, used current SVG bounding-box
  flags and return APIs, updated WebGL shader handling, and adapted letterboxing
  to the current RFP size APIs.
- Worker configuration: warm the cpp-first cache during worker creation and
  read it under the existing mutex; avoid worker preference/IPC access.
- Actor registration: declare the actors safe for web-content processes under
  Firefox 155’s new registration contract; their parent actors expose no message
  handlers. Use the current ContextualIdentityService module URI so startup
  generates and shares seeds for the default container and four built-in containers.
- About dialog: migrate the AppConstants import and move inline load/close
  handlers into the script to comply with Firefox 155's chrome-document CSP.
- Async WebGL: covered the new capture-stream snapshot path. The requesting
  seed is captured before IPC and applied to copied RGBA pixels before swizzle.
- Compile validation: replaced removed OffscreenCanvas owner-global accessors,
  placed MediaCapabilities decoding/encoding hooks in their correct methods after
  validation, and explicitly included the new inline window-method definitions.
- Core APIs: updated relevant-global lookup, StorageManager ownership, D-Bus
  validation, WebRTC stats callback, startup hooks, and header/build contexts.
- Canvas exports: configured container noise supersedes Firefox155’s new
  session-keyed encoder randomization, after extraction permission checks.
  Forward the container ID in synchronous and encoded WebGL read paths.
- Letterboxing: invalidate cached iframe device-size media queries when the
  replicated top-level size changes. Reconciled the newer original-checkout
  fixes for native browser UI screen/CSS geometry, legacy orientation, and
  iframe CSS invalidation when either protection preference changes.
- Toolchains: update CI to cbindgen0.29.4 and Linux LLVM19.
- Packaging: moved optional Assets.car handling into the new MacOSBundle build
  path, with configure-time catalog detection.
- Native messaging: retained the legacy Mozilla lookup when Firefox155 chooses
  XDG profile locations.
- Error stacks: moved the cap to ErrorObject.h and updated its explanation for
  the new experimental Error.stackTraceLimit implementation.

## Evidence and review

- [Initial assessment](initial-assessment.md), including the original failed inventory.
- [Font port](font-port.md) and [independent font review](font-port-review.md).
- [HTTP/3 port](http3-port.md).
- [Geometry port](geometry-port.md) and [independent geometry review](geometry-port-review.md).
- [Core port review](core-port-review.md).
- `ported-pass-15/`: all 75 per-patch logs, return codes, and SHA256 hashes.
- `source-verification.json`: all 174 patched targets and three changed additions
  match the source used for the build.
- `unit-tests.log`, `configure.log`, `build.log`: execution evidence.
- `final-runtime-results.json` and referenced logs: browser probe results.
- `patch-manifest.json` and `build-artifact.json`: patch and binary hashes.
- [Integration review](integration-review.md), including runtime findings.
- Three new CI regression files cover async WebGL noise, canvas extraction
  policy, and the cpp-first worker configuration cache (five tests total).

The full runtime sweep passed twelve fingerprint probes and all four HTTP/3
preference cases. Focused reruns passed the About dialog after its CSP fix and
the expanded letterboxing probe after reconciliation. The About dialog,
navigator-coherence, and additional-vector probes were also rerun against the
letterboxing rebuild. `final-runtime-results.json` combines these results;
other probe results precede the letterboxing-only native changes. The probes cover actors,
window/worker container identity, fonts and metric noise, canvas/WebGL reads and
exports, letterboxing, navigator coherence, WebRTC, media capabilities, WebGL
tables, and the additional vectors enumerated in `final-untested_vectors.log`.

The independent review findings about native-messaging paths and async WebGL
coverage were corrected and rechecked. Linux and Windows builds, live QUIC SETTINGS capture, and the full asynchronous
capture-stream rendering route remain untested. Existing concerns about Safari QPACK
advertisement and container-only C++ seed resolution are documented in the
reviews; this port does not establish per-domain isolation.

## Reproduction

`upstream.sh` in this worktree targets155.0.1. Follow the normal fresh-source
setup and ordered patch application flow in the Makefile. Existing local source
is already patched, with `_READY` set after source verification: do not blindly
apply the stack a second time.

For patch-only checks on a fresh disposable extraction:

```sh
python3 docs/firefox-155-compat/check_stack.py /path/to/fresh/source 155.0.1 UNIQUE_RUN_LABEL
```

The experiment includes the six uncommitted files captured at task start, with
hashes in `input-snapshot.json`. The three later original-checkout edits listed
in `concurrent-changes.json` have now been reconciled: the letterboxing fixes
are adapted to Firefox 155, the expanded probe is retained with a navigation
wait correction, and its README coverage is combined with the new port docs.
No original working files were edited by this task. Worktree changes remain
uncommitted for review.
