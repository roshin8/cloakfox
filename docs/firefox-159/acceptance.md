# Firefox159 build and headless acceptance

The native Mac build completed successfully with Mozilla Clang22.1.8, isolated
cbindgen0.29.4 and the native Apple linker. The follow-up privileged-viewport fix
also rebuilt successfully. The tested self-contained app is recorded in
`acceptance-app-viewport.json`; its executable, XUL, renderer libraries and
manifest match the build outputs byte for byte. Existing application installs
were not replaced, and no Cloakfox installer was created in this continuation.

| Verification | Result |
| --- | --- |
| Complete privacy patch replay |160/160, matching live patched targets |
| Headless runtime probes |150 passed;4 GPU hardware probes inconclusive |
| Pinned CreepJS/FingerprintJS audits |Both legacy and canonical modes passed |
| Browser-backed Python tests |144 passed |
| JavaScript regression tests |363 passed |
| CI helper unit tests |169 passed with bounded fixture capacity described below |
| Release Python tests |31 passed |
| Official release-freshness gate |Passed for159.0 on2026-10-27; no offline fixture |
| Independent source/build/harness review |No actionable finding |

`acceptance.json` contains the resolved results and precise exclusions. The raw
complete run remains in `headless-test-status.json`, including its one stale
media-control selector failure. `headless-final-rerun.json` records the successful
rerun after selecting the actual Microphones tab; its source hash matches the
current test. No functional or privacy assertion was waived. The old attempts,
logs and app copies remain available.

All four GPU inconclusives reflect a missing WebGPU adapter in the headless
native control. Native/protected mismatches and all actual WebGL, ownership,
capacity, integrity and readback failures still fail. No hardware blocklist or
sandbox was disabled. Nine additional probes were deferred because they can
interact with native pickers/relaunch, or exercise historical/other-engine
artifacts rather than this Firefox build. These are exclusions, not passes.

The real regression found during testing was privileged settings documents
receiving masked viewport dimensions. The native fix exempts only system-principal
documents; ordinary HTTP and opaque sandbox documents still receive the configured
masks. A red/green runtime test verifies both sides. Strict canonical-library
integrity checks remain unchanged: development symlinks are correctly rejected,
and the acceptance copy supplies real, verified files.

The raw CI helper run hit its existing10GiB host storage reserve. The bounded
unit fixtures then ran with an explicit simulated20GiB capacity; nested low-disk
rejection tests still execute. The real build's2GiB stop guard and all production
storage guards remain unchanged. Raw capacity failures are retained separately.

The original158 checkout's saved HEAD and dirty tracked status still match the
preservation receipt. No Chromium build inputs were changed, and run40544857164
was not cancelled, restarted or altered. The Gecko-only workflow now obtains the
source-selected compiler, preserves its provenance and stages a verified matching
stock reference privately. No shared Chromium toolchain script was modified.
