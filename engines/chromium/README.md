# Chromium companion prototype

Development-only macOS arm64 CEF companion on branch `codex/dual-engine-prototype`.
It uses real Chromium with Chrome-style browser controls, not Gecko with a Chrome UA.
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
python3 -m unittest discover -s tests/engines -p 'test_protocol_security.py' -v
python3 tests/engines/probe_cef_isolation.py --binary "$CLOAKFOX_CHROMIUM_BIN" --report /tmp/cef-isolation.json
# Use a Python environment with tests/network/requirements-wire.txt installed:
python3 tests/engines/probe_cef_transport.py --binary "$CLOAKFOX_CHROMIUM_BIN" --report /tmp/cef-transport.json
```

The probes use disposable profiles and owned loopback servers. They check real
persistent/private storage, restart behavior, private-window closure, macOS
renderer sandbox enforcement, permission denial, invalid inputs, replay rejection
and intentional renderer crash recovery.

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

Current internal APFS storage has insufficient free space for the 128 GiB
development budget. The external USB volume has space but is ExFAT. Full Xcode
is absent from the active developer directory. No drive is reformatted and no
global toolchain selection is changed by these scripts.

A dedicated APFS disk image backed by the external disk can address the
filesystem/storage requirement without reformatting it. Full Xcode and its
matching macOS SDK must also be available before starting the supported source
build. See [Chromium's Mac build requirements](https://chromium.googlesource.com/chromium/src/+/main/docs/mac_build_instructions.md).

After the prerequisites pass, pin CEF source commit `14c5a08` and its matching
Chromium revision from CEF's `CHROMIUM_BUILD_COMPATIBILITY.txt`, build an
unmodified source baseline, then implement/test deterministic native canvas
readback protection for container plus schemeful-site ownership, including
workers and OffscreenCanvas. Do not claim source patch maintainability or privacy
parity from this binary-only prototype. The native-patch gate remains open before
proceeding to Gecko launcher integration and a shared shell.

CEF is a viable embedding candidate based on the measured prototype so far;
it is not yet selected as Cloakfox's final architecture. See the roadmap and
verification report for completed and pending work.
