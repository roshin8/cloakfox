# Experimental native Chromium/CEF source build

Pinned baseline: Chromium `154.0.8037.98`, CEF
`14c5a089e8452874cb1a556dc3fde26ed2d87723` (154.0.34).
This development build uses actual Apple Command Line Tools and macOS SDK paths.
It is not an official/supported Xcode build or a privacy-patched Chromium engine.

## Source and storage

Source archive:
`https://commondatastorage.googleapis.com/chromium-browser-official/chromium-154.0.8037.98.tar.xz`.
Size 4,174,095,736 bytes; published MD5 `4ae9e4fac387d9d17b7db0c65b2c0712`;
verified SHA256 `5fb963ddd71716cb21ddce52a035869e383b6f2b5dbdabe285a7ff64d0c43707`.
The matching tag points to `b859317bf11f6be47f9b7799ec690a0a42a1fb33`.

The source is under this worktree's ignored `.cef-prototype/full-source/chromium/src`.
Build output is on `/Volumes/CloakfoxChromiumBuild`, a growing 350 GiB APFS
sparsebundle stored on the existing external ExFAT disk. Nothing was reformatted.
The internal source tree avoids the external disk's slow metadata operations.
The owned stage runner preserves 15 GiB internal and 10 GiB build-volume reserves.

Git source transfer failed with connection resets. The fallback uses CEF's
supported source-tarball workflow: matching CEF `tarball_gclient.patch` against
local depot_tools `97ed77526c27c08ad80437625ffde66dcbdd3b9c`, and
`tarball_deps.patch` against the extracted source. `.gclient` custom variables:
`source_tarball=True`, `checkout_pgo_profiles=False`. Preserve the CEF source Git
history so version/API generation can determine the correct release.

Run `gclient sync --nohooks --no-history --jobs=8`, CEF `tools/patcher.py`, the
Cloakfox CLT preparer, `gclient runhooks`, then CEF
`tools/version_manager.py -u --fast-check`. Source archives nested in a separate
Git worktree need `GIT_CEILING_DIRECTORIES` at the archive workspace parent to
keep tarball patch commands from discovering the unrelated repository.

## Pinned CEF runtime repair

After the matching CEF patcher, apply
`engines/chromium/patches/macos-cef-rng-seed.patch` from the Chromium source root
using `git apply --check` followed by `git apply`. The expected before/after input
SHA256 values are in `engines/chromium/cef-runtime-patches.json`; verify them
against the two source files before applying, and against the fixed hashes after.

The pinned CEF `base_rand_util_lazy_seed.patch` moves metrics RNG seeding onto
first use. On macOS this can occur inside PartitionAlloc lock sampling; BoringSSL's
first per-thread RNG allocation re-enters the allocator. The local patch uses
macOS `getentropy` to fill the 128-bit seed on the stack, preserving lazy
construction and the all-zero retry. Allocator checks, sandboxing and lock
metrics stay enabled. The source-built startup tests reproduce the original
failure; passing runtime evidence is required before calling the repair verified.

## GN and compile

Generate `Release_GN_arm64` arguments through CEF's `tools/gn_args.py`, retaining
its release defaults. Additional local arguments:

```gn
is_official_build = false
is_component_build = false
symbol_level = 0
blink_symbol_level = 0
v8_symbol_level = 0
use_system_xcode = true
mac_use_command_line_tools = true
angle_precompile_internal_metal_shaders = false
use_remoteexec = false
use_siso = false
use_thin_lto = false
```

Prepare the pinned inputs with `engines/chromium/prepare_clt_build.py` first.
The SDK adapter reuses Chromium's own build-local SDK aliases, required by its
SDK-input no-op actions. The Metal option preserves ANGLE's renderer and uses
its existing runtime shader compilation path; it does not emulate missing Apple
tools or disable GPU support. Normal builds retain offline shader compilation.
Known prior SDK-only preparation is migrated only after verifying its exact
helper/source hashes and original backup. Unknown local edits are rejected.

With absolute `SRC` and `OUT` paths:

```sh
"$SRC/buildtools/mac/gn" gen "$OUT" --root="$SRC"
"$SRC/third_party/ninja/ninja" -C "$OUT" cef_framework -j8
```

`cef_framework` includes its native sandbox library. Nib-based CEF sample apps
need unavailable `ibtool` and are not the target. CLT also lacks the standalone
`metal` and `metallib` tools. A real runtime Metal compute probe is available as
`tests/engines/metal_runtime_check.mm`.

## Verification boundary

Successful GN generation is not a linked framework. A complete result requires
the framework, a separate native companion built using that framework and its
generated headers, matching framework SHA256 values, and passing runtime probes.
Use the matching binary SDK's CMake templates only; replace its framework,
headers and wrapper sources with the source-build outputs, then honor CEF's
`tools/distrib/transfer.cfg`. Its `net_error_list.h` mapping replaces the
source-tree include shim with the standalone Chromium header. Keep the
SDK-only `README-TRANSFER.txt` documentation template. Preserve the old SDK
and app for comparison. The source-built companion must pass the protocol,
container/popup/private storage, sandbox, permission, crash recovery and native
transport probes documented in `engines/chromium/README.md`. The graphics probe
compiles WebGL2 shaders, draws a triangle and verifies red pixel readback.

Native fingerprint protection and integration into Cloakfox's shared UI remain
separate roadmap work. Consult the recorded build status before treating this
baseline as complete.

## Recorded result — 2026-10-15

The framework, sandbox and source-linked companion now compile and pass the
native tests. See [recorded provenance and results](cef-source-build-20261015.json)
and [verification scope](cef-prototype-verification.md#full-source-baseline--2026-10-15).
The companion opts out of Chromium's compiled field-trial testing cohorts so
non-official builds use normal feature defaults and the packaged CEF helper set.
The macOS RNG repair is validated by startup and browser runtime tests.
