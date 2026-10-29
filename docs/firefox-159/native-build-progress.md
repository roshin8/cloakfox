# Native Firefox159 build continuation —2026-10-27

User requested fixing the toolchain and completing the159 build/tests, headless only. Original Chromium run40544857164 and all existing checkpoints/source trees must remain untouched. Local target uses2 make jobs and nice10 with a2GiB minimum-free-space guard; no checkpoint deletion or profile/application replacement.

## Toolchain fixes

- Native Apple Clang21 and SDK27 are installed. LLVM19 and22 TAPI readers reject the SDK's arm64e.x1 architecture; SDK14.4 is correctly below Firefox159 minimum26.5.
- New cloakfox-apple-linker-detection.patch keeps old diagnostics, adds strict same-selected-linker Apple version recognition when LD_PRINT_OPTIONS is absent, and requires a real Darwin SDK link smoke check before selecting LLD for host or target. It does not weaken compiler/SDK/security constraints.
- Six tests exercise legacy/new Apple banners, malformed banners, execution failure, incompatible/compatible LLD and non-Darwin behavior. Red failures observed before fixes, green afterward.
- Built locked cbindgen0.29.4 under firefox-src/.tools159, not the shared toolchain install.
- Canonical component moz.build lists were unsorted; sorted them while preserving exact membership. Added regression for ordering, duplicates and file presence.

## Attempts

First native configuration passed after these initial fixes. First actual build failed linking nsinstall because automatic host selection still chose incompatible LLD. Failure log preserved at/tmp/cloakfox159-native-build-attempt1.log and receiptbuild-attempt1.json. Added the Darwin LLD real-link check to address this, rather than forcing unknown tools or disabling checks.

The next configure/build result is recorded in build-status.json and subsequent evidence. This progress file does not attest build/runtime completion. Headful appearance/IME and OS permission prompts must not be invoked during testing. Set MOZ_HEADLESS=1 and unset CLOAKFOX_HEADFUL for owned disposable tests.

## Matched-toolchain continuation

Attempts2–4 are retained with their failure logs. They exposed upstream159's
sorted NSS-variable requirement, missing floating-point atomics in the installed
Apple headers, and HomebrewLLVM22.1.3's SDK27 partial-float-header incompatibility.
Both Cloakfox NSS flags remain present; ordering and the vendor checksum were
corrected. No Gecko arithmetic workaround remains.

The verified Firefox159 taskgraph supplied isolated Clang22.1.8, which passes
both small toolchain reproductions and native mfbt/PerfStats object compilation.
Attempt5 uses that compiler and the native Apple linker. Its live status is in
build-status.json; this paragraph does not claim that the full build has passed.

Current static evidence:

-159/159 whole patches replayed, with no differences from live patched targets.
-363 JavaScript fingerprint tests passed.
-130 Python fingerprint tests and13 subtests passed;14 browser-backed tests
 deferred until the binary exists.
-31 Python release tests and the release Node test passed.
-17 Gecko CI regression tests passed.
-160 bounded CI helper tests passed with a test-only20GiB disk-capacity fixture.
 Raw host runs hit the existing10GiB Chromium storage reserve; those failures
 are retained, and production/build guards were not reduced.
-94 engine source/helper tests completed,35 runtime-dependent tests skipped.
-Independent review found no build/privacy regression. Runner artifact overrides
 were explicitly pinned to the new source/object directory in response to review.

The headless plan accounts for153 selected probes plus9 explicit deferrals.
Runtime tests and pinned library audits must still execute after a successful
native build. Historical evidence outputs are preserved by routing new screenshots
and codec reports through REPORT_DIR.

## Native result

Attempt5 completed successfully, exit0, in66m07s. The new binary reports
Cloakfox159.0-beta.1. It has not been installed or packaged. The raw compiler log
is retained, including warnings; a quoted source line containing the word
"error" was classified as a diagnostic source excerpt rather than a compiler
failure in the final receipt.

Initial runtime attempts are retained. Firefox159 now requires
MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1 for privileged Marionette access; this opt-in
is confined to test environments. CI-pinned Python dependencies, the source-built
ALPS loopback fixture and Monaco/Firepad assets are installed only under the
owned .tools159 directory. The final run forces widget/APZ pointer input so it
cannot move the desktop cursor. Its full results are still pending.

## Final acceptance

See acceptance.md and acceptance.json. The native system-document viewport guard
was verified red/green, including ordinary and opaque web documents. Build7
completed successfully after build6's priority-setting failure before compilation;
all logs remain. Source-selected Clang setup is now in the Gecko-only workflow.
The verified matching stock159 reference and its staging helper are confined to
owned test directories. No installed app or shared Chromium setup was replaced.

Final resolved results:150 headless probes passed,4 native-hardware probes
inconclusive; both pinned library modes and144 browser-backed Python tests passed.
169 CI fixture tests,363 JavaScript tests and31 release tests passed. Nine probes
remain explicitly deferred. The raw full run and the corrected media-tab rerun
are both retained; no failing privacy assertion was waived.
