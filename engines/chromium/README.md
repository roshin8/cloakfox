# Chromium companion prototype

Development-only macOS arm64 CEF companion on branch `codex/dual-engine-prototype`.
It uses real Chromium with a native Views address field and Back/Forward/Reload controls.
It is **not integrated into Cloakfox's tab bar and has no native fingerprint privacy patches**.
The existing Gecko browser and DMG are unchanged.

## Build

Requires Python 3.11+, CMake 3.21+, Ninja and an arm64 macOS compiler/SDK.
This binary-distribution client built with the installed CommandLineTools; a
supported full Chromium source build has additional prerequisites below.
The exact CEF stable release, Chromium version, archive size and SHA256 are in
`cef-lock.json`. The companion rejects a different CEF version at configure time.

From the repository root:

```sh
python3 engines/chromium/fetch_cef.py --cache-dir .cef-prototype
cmake -S engines/chromium -B engines/chromium/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCEF_ROOT="$PWD/.cef-prototype/cef_binary_154.0.34+g14c5a08+chromium-154.0.8037.98_macosarm64"
cmake --build engines/chromium/build --parallel 6
ctest --test-dir engines/chromium/build --output-on-failure
```

The build packages sandbox-enabled helpers and the CEF framework into
`engines/chromium/build/Release/CloakfoxChromium.app`. The prototype is not
notarized or a replacement for the installed Cloakfox app.

## Preview

```sh
python3 engines/chromium/launch_prototype.py --container 1 --container 2
```

This opens two independent Chromium windows in a disposable profile root.
Close the windows to exit, or interrupt the launcher. An explicitly supplied
`--profile-root=/absolute/dedicated/prototype-root` retains persistent container
data between launches; the root must be private, owned by the current user and
unused by another process.

The launcher uses Chromium's **test keychain**, avoiding access to the user's
real macOS Keychain. Its fixed test encryption key makes it unsuitable for real
accounts, passwords or sensitive browsing. Keychain mode is fixed per profile
root; switching to native keychain mode requires a fresh root.

## Control protocol

Only the parent's inherited stdin/stdout pipes carry newline-delimited JSON.
There is no listener, remote debugging port or JavaScript-to-host page binding.
The UI process owns browser creation, navigation and profile lifecycle.

Requests contain `version:1`, a positive strictly increasing integer `id`,
and `command`. Unknown versions, fields, commands, browser IDs and replayed IDs
are rejected. Container IDs are canonical decimal integers 1–2147483647.

| Command | Additional fields | Behavior |
|---|---|---|
| `open` | `container`, `url`, optional `private` | Opens a window under that container's context |
| `navigate` | `browser`, `url` | Navigates/reloads a surviving browser, including after renderer failure |
| `close` | `browser` | Closes that browser |
| `quit` | none | Closes browsers, releases contexts and shuts down |
| `cdp` | `browser`, `method`, `params` | Native DevTools call, only with explicit `--enable-probe` |

Control navigation accepts HTTP(S) and `about:blank`. CEF's browser interface
has its own native navigation behavior. `ready` includes actual engine versions,
`privacyPatched:false`, probe mode and test-keychain mode. Browser creation,
closure and renderer crashes produce events.

Persisted profiles must be immediate children of CEF's user-data directory.
The companion waits for asynchronous context initialization before creating a
window, and drops private contexts after their last window closes. Camera,
microphone and permission prompts are denied in this prototype; interactive
permission management and downloads have not been validated for release.

## Runtime checks

```sh
export CLOAKFOX_CHROMIUM_BIN="$PWD/engines/chromium/build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium"
python3 -m unittest discover -s tests/engines -p 'test_*.py' -v
python3 tests/engines/probe_cef_isolation.py --binary "$CLOAKFOX_CHROMIUM_BIN" --report /tmp/cef-isolation.json
# Use a Python environment with tests/network/requirements-wire.txt installed:
python3 tests/engines/probe_cef_transport.py --binary "$CLOAKFOX_CHROMIUM_BIN" --report /tmp/cef-transport.json
```

The probes use disposable profiles and owned loopback servers. They check real
persistent/private storage, restart behavior, private-window closure, macOS
renderer sandbox enforcement, permission denial, invalid inputs, replay rejection
intentional renderer crash recovery and popup context inheritance/lifetime.

The transport probe observes TCP and QUIC ClientHello/transport parameters and
rejects the untrusted fixture certificate. Its explicit `--test-quic-port=N`
option forces native QUIC only to `127.0.0.1:N`, requires both probe and test-keychain
mode, and does not bypass certificate checks. Authenticated H2/H3 SETTINGS,
connection/ticket isolation and production Alt-Svc discovery are **not verified**.

## Source-build prerequisite and next step

```sh
python3 engines/chromium/source_preflight.py --build-root "$PWD"
python3 engines/chromium/source_preflight.py --build-root /Volumes/Untitled
```

The standard preflight reports insufficient internal APFS space for its 128 GiB
development budget, external ExFAT storage and no full Xcode. A source baseline
now builds using the experimental CLT path and an external APFS disk image; see
[the source-build record](../../docs/dual-engine/cef-source-build.md). No drive is reformatted and no
global toolchain selection is changed by these scripts.

A dedicated APFS disk image backed by the external disk can address the
filesystem/storage requirement without reformatting it. Full Xcode and its
matching macOS SDK must also be available before starting the supported source
build. See [Chromium's Mac build requirements](https://chromium.googlesource.com/chromium/src/+/main/docs/mac_build_instructions.md).

The pinned source baseline now compiles and passes the native runtime probes.
It includes build compatibility adaptations and a macOS CEF RNG startup repair.
The next source milestone is deterministic native canvas readback protection for
container plus schemeful-site ownership, including workers and OffscreenCanvas.
The native privacy gate remains open before Gecko launcher integration and a
shared shell.

CEF is a viable embedding candidate based on the measured prototype so far;
it is not yet selected as Cloakfox's final architecture. See the roadmap and
verification report for completed and pending work.

## Experimental Command Line Tools source configuration

An opt-in adaptation is available for Chromium **154.0.8037.98**. It uses the
installed CLT receipt, compiler and SDK paths; it does not create a fake
`Xcode.app`, replace `xcodebuild`, accept licenses, or alter system settings.
Prepare an existing pinned Chromium source checkout:

```sh
python3 engines/chromium/prepare_clt_build.py --source-root /absolute/path/to/chromium/src
# Include these in that checkout's GN arguments:
# mac_use_command_line_tools=true
# use_system_xcode=true
# is_official_build=false
# angle_precompile_internal_metal_shaders=false
```

The preparer checks both upstream GN file SHA256 hashes before writing, preserves
the originals beside them and refuses changed input or conflicting helper files. Repeating preparation
is supported. To undo it, restore `build/config/mac/mac_sdk.gni.cloakfox-original`
over `mac_sdk.gni`, restore the matching `metal_backend.gni.cloakfox-original`
under `third_party/angle/src/libANGLE/renderer/metal/`, and remove the installed
`build/config/apple/clt_sdk_info.py`.
Normal GN builds still use upstream Xcode detection unless explicitly opted in.
Official builds, non-system toolchains and explicit `mac_sdk_path` overrides
reject CLT mode. The discovered SDK must satisfy Chromium's `mac_sdk_min`.

Legacy GN `xcode_version` fields encode the installed **CLT toolset** version in
this mode for existing build consumers. `xcode_build` is explicitly `CLT-<receipt
version>`; no actual Xcode installation or release metadata is claimed. The
native helper is macOS-only. Missing `ibtool`, `actool`, `metal` and `momc` remain
unavailable. `angle_precompile_internal_metal_shaders=false` uses ANGLE's existing
runtime Metal shader compilation path instead of requiring `metal`/`metallib`;
Metal rendering remains enabled. The option defaults to true, preserving normal
builds. This mode does not emulate missing tools or establish support for targets
that need them (including CEF's nib-based sample applications).

Measured on this machine: the real patched GN configuration works in an isolated
fixture, rejects official builds, leaves default Xcode behavior intact, and its
returned compiler/SDK paths compile and run Cocoa/Metal code. The fixture supplies
minimal surrounding GN imports; it is **not the complete Chromium build graph**.
The complete CEF framework and source-built companion now pass native runtime
checks: see [verification](../../docs/dual-engine/cef-prototype-verification.md)
and [source-build evidence](../../docs/dual-engine/cef-source-build-20261015.json).
Targets requiring unavailable resource compilers and native privacy patches
remain outside this verified baseline. The normal `source_preflight.py` still
reports standard Xcode prerequisites and storage budget; it is not a validator
for this experimental mode.

To repeat the configuration probe, use a public standalone GN executable and a
small source tree containing the pinned upstream `mac_sdk.gni`, `sdk_info.py` and
`find_sdk.py` at their upstream paths:

```sh
python3 tests/engines/probe_clt_toolchain.py --gn /absolute/path/to/gn \
  --upstream-root /absolute/path/to/pinned-source-files --report /tmp/clt-probe.json
```

The pinned upstream fixture in `tests/engines/fixtures/mac_sdk_154.gni` is covered
by `THIRD_PARTY_LICENSES/Chromium-LICENSE.txt`.

The pinned ANGLE fixture and build patch are covered by
`THIRD_PARTY_LICENSES/ANGLE-LICENSE.txt`.

The companion disables Chromium's compiled-in field-trial testing configuration.
Non-official source builds otherwise enable experimental test cohorts, including
Aperitif helpers absent from the pinned CEF distribution. Normal feature defaults
preserve the existing supported helper set, GPU rendering and sandbox enforcement.
Apply the pinned macOS runtime repair described in
[the source-build instructions](../../docs/dual-engine/cef-source-build.md)
after CEF's upstream patches and before building the framework.
