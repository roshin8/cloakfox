# Firefox159 local toolchain

This build uses the compiler selected by the verified Firefox159 source's own
Taskcluster toolchain alias, without modifying global compiler installations.
SDK27 remains selected; the upstream minimum SDK requirement is unchanged.

## Reproduce the isolated compiler download

From `firefox-src/.tools159`:

```sh
MOZBUILD_STATE_PATH="$PWD/../.mozbuild159" \
 /opt/homebrew/bin/python3.12 ../mach artifact toolchain \
 --from-build macosx64-aarch64-clang \
 --cache-dir ../.mozbuild159/toolchain-cache \
 --artifact-manifest mozilla-clang-artifact.json
```

Resolved artifact: Taskcluster task `cr2DfURqSoKyZFbvoYx60w`,
`public/build/clang.tar.zst`, SHA256
`baf584f563685497a5f0418567969b6035ae987ad7f8cf61e33b8b1a20c49c81`.
The resulting compiler is Clang22.1.8. Point `CC`, `CXX`, and `LIBCLANG_PATH`
at this directory's `clang/bin/clang`, `clang/bin/clang++`, and `clang/lib`.
`CBINDGEN` points at the isolated locked cbindgen0.29.4 executable in
`.tools159/bin`. No shared toolchain was upgraded.

## Why the earlier combinations failed

Apple's installed C++ standard library lacks the floating-point atomic operation
required by159. Older MozillaLLVM and HomebrewLLVM cannot read SDK27's new TAPI
architecture; HomebrewLLVM22.1.3 additionally fails the SDK's partial float-header
include protocol. The Mozilla159 compiler passes both minimal reproductions and
the two formerly failing native objects. A duplicate-cfloat experiment was
withdrawn; no Gecko arithmetic source workaround remains.

The new linker patch recognizes the current native Apple linker's strict version
banner and rejects DarwinLLD candidates that fail an actual link against the
selected SDK. Configure's subsequent compiler/link checks remain enabled.

## Resource and safety constraints

Native compilation uses two make jobs, nice10, and a2GiB free-space stop guard
that terminates only this build's owned process group. Release optimizations and
security/sandbox defaults remain enabled; debug symbols are disabled to reduce
local disk usage. Earlier build outputs and attempt logs are retained.

Runtime acceptance requires the new159 binary, forced headless mode, owned
temporary profiles, and explicit artifact paths. The headless plan records tests
that could display OS pickers or activate apps as deferred rather than passed.
The installed application and personal profiles are not used or replaced.
