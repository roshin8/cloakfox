# Shared persona/config foundation

User requested implementation and tests without plan review. Execute inline.

## Design

A backend-neutral Python snapshot model owns schema version, engine, container,
revision, cryptographic persona seed, master switch, default options and explicit
overrides. Chromium consumes validated complete snapshots over its inherited
control pipes. Its capability report lists only settings implemented natively.
Snapshots are applied before creating a browser/renderer, acknowledged by revision,
and immutable for the lifetime of a request context. Changes require companion
restart; existing realms are never silently mixed with a different seed/policy.
The Gecko158 adapter/settings UI and additional masking vectors are subsequent work.

The controller persists only persistent personas in private atomic JSON files;
private personas stay in memory and use fresh seeds per private session. Generation
can preserve or clear overrides. Unsupported fields/options, invalid IDs/seeds,
stale revisions, mismatched engines and live changes must fail closed. No seed is
returned in protocol acknowledgements. Legacy open remains available for existing
owned regression probes; versioned contexts require their acknowledged revision.

## Implementation and checks

- [x] Add shared snapshot/store with tests for strict validation, regeneration,
  revision advancement, persistence, private ownership and unsafe files.
- [x] Add native applyConfig and revision-bound opens; wire the development launcher
  through a shared controller. Test first-page/worker seed ownership, master and
  overrides, rejection paths, process restart and current graphics regressions.
- [x] Regenerate patch/preference/UI inventory from maintained158 sources, explicitly
  distinguish partial graphics/config coverage and remaining backend/UI work.
- [x] Build companion, run complete engine suite and concurrent158 probe, inspect
  evidence, review, commit and push changes.

## Review focus

Initialization/config races; rejected snapshots leaving accepted state unchanged;
private snapshots accidentally persisted; file links/permissions; unsupported
settings appearing enabled. Test these at the owning model/backend boundaries.

## Execution record

- Model, native apply/open and production controller tests were observed failing
  before implementation. Initial complete engine suite: 80/80; C++ test: 1/1.
- Source inventory: 144 active canonical patches, 21 optional/WebRTC preferences,
  124 HTML bindings and 13 actors from maintained158, with drift-test hashes.
- Fresh review found private store lifetime retention and blocking FIFO reads;
  both reproduced. Regression tests also cover reopened directory permissions.
  Fixes retire private ownership using the native context lifecycle (including
  popups), reject retired seeds, use nonblocking file validation and revalidate
  directory descriptors. Expanded focused suite including unpatched-SDK denial:
  17/17. Final full suite and concurrent-engine evidence are recorded separately.
- Scope decision: v1 exposes only the existing native graphics options; future
  vectors and the Gecko settings adapter remain pending. Live config changes
  require a companion restart to preserve immutable page/worker ownership.

Final verification: engine Python86/86 with no skips; C++1/1; concurrent
Gecko158 plus versioned Chromium; TCP/QUIC certificate rejection; local bundle
framework hash unchanged; launcher lifecycle/persistence smoke passed. No
Gecko source/config changes or additional privacy-parity claims. Evidence is
in docs/dual-engine/persona-config-20261015. Review findings fixed; none deferred.
