# Independent review — toolchain and headless acceptance

Reviewed against checkpoint a8ef96501b and the uncommitted build fixes.

No actionable build/privacy regression found in native Apple linker detection,
component install-list ordering, NSS binding flags/checksum, or explicit new-build
selection in site-data probes. Both Cloakfox NSS privacy flags remain present.
The complete159-patch stack replays against verified source and matches live
patched targets.

The reviewer identified inherited xpcshell/codec/GPU artifact overrides and the
standalone GPU fixture path as harness gaps. The runner now pins these paths.
A later review of Firefox159's new privileged-automation gate found its environment
opt-in confined to owned test runs and fingerprint CI jobs; production defaults
remain unchanged.

The final runner forces MOZ_HEADLESS and LIBRARY_HEADLESS, removes HEADFUL,
forces POINTER_PROBE_INPUT=widget, strips stock-reference overrides, and pins
new-build artifacts. Two runtime-access regression tests passed independently.
No remaining desktop-input/activation path was identified under that environment.
Native permission pickers and appearance relaunch are explicitly deferred.

The review did not attest full runtime acceptance: those results are recorded
separately in headless-test-status.json. No source edits, browsers or builds were
started by the reviewer. Chromium build40544857164 was not modified.

## Cumulative review after runtime findings

The reviewer approved the four native viewport guards: system documents keep
native UI geometry, while non-system documents and null-document behavior stay
on the prior masking path. Runtime verification subsequently included an opaque
sandbox document as well as HTTP content. The source-selected Gecko compiler
workflow remains separate from Chromium's shared build setup.

The stock-reference helper was reviewed and tested for exact checksum records,
corrupt archive rejection before mount, destination preservation and detach on
copy failure. A live staging check used the retained official archive, verified
its signature and ejected the owned mount. It never installs or launches apps.
Template fixture cleanup now quits the browser before deleting its temporary
profile. Updated UI tests retain real clicks and downstream native/API assertions.

Hardware-unavailable outcomes remain exit2, with real failures taking precedence.
The complete runtime results and the explicitly corrected media-tab test are
recorded separately; review does not turn exclusions/inconclusives into passes.
