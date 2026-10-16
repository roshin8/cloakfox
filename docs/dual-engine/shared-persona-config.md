# Shared persona/config foundation

The maintained Gecko158 branch now contains a portable v1 snapshot model and
Chromium companion adapter. This is infrastructure for subsequent native persona
vectors and UI integration. It does not yet connect the Gecko settings page,
implement BrowserForge generation in Chromium, or claim complete privacy parity.

## Ownership and lifecycle

`engines/shared/persona_config.py` owns validation, generation, revisions and
atomic storage. A snapshot contains:

```json
{
  "schemaVersion": 1,
  "engine": "chromium",
  "containerId": "1",
  "private": false,
  "revision": 1,
  "enabled": true,
  "persona": {
    "seed": "<64 lowercase hexadecimal characters / 32 random bytes>",
    "options": {"canvas": true, "blockWebGPUReadback": false},
    "overrides": {}
  }
}
```

The seed example is deliberately a placeholder, not a valid snapshot. `gecko` is
also a schema engine identifier; no Gecko adapter consumes this schema yet.
Engines have separate records. Container IDs are canonical decimal 1–2147483647;
revisions are integers in the same positive range. Unknown fields and options,
nonboolean flags, invalid seeds and ownership mismatches fail validation.

`PersonaStore.get()` creates or loads a snapshot. `update()` checks the entire
previous snapshot under a filesystem lock and increments its revision.
`regenerate(clear_overrides=False)` rotates the seed, retaining explicit
choices; `clear_overrides=True` clears them. `options` hold defaults;
`overrides` take precedence. The master switch gates implemented native policies.
Fixed prototype permission denials are separate and remain in effect.

Persistent records live in private `personas/<engine>-<container>.json` files
beside the companion profiles. Updates use private temp files, fsync and atomic
rename. Unsafe modes, links, nonregular files (including FIFOs), corrupt data and conflicting revisions are rejected. Directory permissions are checked again on each persistent operation.
Private snapshots remain memory-only. The production controller owns a
`PersonaStore` (or accepts it via `store=`). It automatically retires a private
snapshot on native `configDiscarded` or process shutdown. That native event is
emitted only when the entire context closes, including its popups. A new private
session samples a fresh seed. `close_browser()` waits for native closure before
returning. The native backend also rejects replay of a retired private seed in
the same process. Direct low-level store/protocol callers must explicitly end
their private ownership using `forget_private()`; the owned probes do so.

## Native protocol

The production controller `engines/chromium/controller.py` launches a dedicated
test-Keychain companion and uses only inherited stdin/stdout pipes. It validates
`configSchemaVersion:1` and `supportedPersonaOptions` before applying a config.

1. Send `{version:1,id:N,command:"applyConfig",config:<snapshot>}`.
2. Wait for successful `event:"configApplied"`, matching engine, container,
   private ownership and `configRevision`.
3. Send `open` with that container/private flag and matching `configRevision`.

The native adapter independently validates the complete snapshot. During request
context initialization it sets the native container secret and effective policy
preferences before any browser window is created. Existing native plumbing owns
site partitioning and delivers the resulting key/policies to frames and workers.
Acknowledgements report effective policy/revision, never the seed. Configuration
capability is distinct from `privacyPatched:false`.

Only `canvas` and `blockWebGPUReadback` are supported in v1; both native hooks must
report version 1. This rejects older/unpatched SDKs. `canvas` controls the existing
partial canvas/WebGL/Metal pixel transforms and GPU identifier reduction; it does
not implement the Gecko158 canonical renderer or full graphics masking.

Reapplying an identical initialized snapshot is idempotent. A changed/stale config
or a legacy context cannot be reconfigured in place: restart the companion first.
This deliberately preserves immutable page/worker ownership. Revision checks are
session-local in the backend; cross-restart controller authority is the persistent
store. The backend does not accept arbitrary on-disk files or prove that a trusted
controller did not intentionally submit an older snapshot on a new process.
Private contexts discard their snapshot after their final browser closes.
Legacy unversioned `open` remains available to existing regression tooling; it
cannot open an already-versioned context without its acknowledged revision.

## Development launcher

The normal development launcher now uses the shared store/controller. Existing
`--disable-canvas-privacy` and `--block-webgpu-readback` flags write explicit
portable overrides. Additional controls:

```sh
python3 engines/chromium/launch_prototype.py --regenerate-persona \
  --clear-overrides-when-generating
python3 engines/chromium/launch_prototype.py --disable-privacy
```

Use a dedicated `--profile-root` to retain personas across launches. The default
root remains disposable. Changing an existing profile's effective config takes
effect on the new companion session. The test-Keychain limitation remains; this
is not the normal-account release configuration.

## Verification

Runtime tests exercise native first-script page/frame/dedicated/shared/service
worker canvas identity, same-seed agreement, persistent restart and regeneration,
master-off and overrides, stale/malformed snapshot rejection without mutation,
revision-bound opens, idempotence and private/persistent separation/destruction.
Controller tests use the real production adapter and inherited CEF pipes.
The existing graphics, compute correctness, protocol and sandbox checks remain
part of the complete engine suite. The concurrent Gecko158 probe accepts
`--require-persona-config` to exercise versioned Chromium configs alongside Gecko.

The source inventory is refreshed by `engines/chromium/update_inventory.py`; it
uses the canonical patch resolver and hashes maintained158 patches/modules/UI.
The unit test detects subsequent source drift. Dynamic settings and individual
semantics still require manual parity review; collected names are not coverage.

Independent review found and reproduced private-session seed retention and a FIFO
read hang. Regression tests failed before fixes and pass afterward. The controller
now retires private ownership automatically, the backend rejects retired private
seeds, record reads are nonblocking before file-type validation, and reopened store
directories are revalidated. Popup lifetime and process-only shutdown are covered.

## Final run — 2026-10-15

All 86 engine Python tests passed without skips (including unpatched-SDK denial),
and the C++ test passed. Gecko158/Chromium ran concurrently with versioned
Chromium configs; their owned storage/lifecycle checks passed. TCP and QUIC
untrusted-certificate rejection still pass; authenticated H2/H3 isolation remains
unverified. The local companion now contains the rebuilt client; its framework
hash matches the unchanged verified SDK and prior app. Launcher regeneration,
clear-overrides, disable/re-enable and orderly interruption passed with retained
profile revisions. [Result and evidence](persona-config-20261015/result.json).
