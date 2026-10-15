# Firefox 158 port progress

Branch: `codex/firefox-158-port`. Source snapshot: current uncommitted157 privacy checkout at commit24c23d478e. `157-input-manifest.json` records every copied tracked/untracked file hash. Installed157 and all existing profiles are preserved.

Mozilla158.0 source and stockmacOSDMG both match officialSHA256SUMS. Stock158 measured TLS/H2/H3 references have been captured independently with disposable profiles; structural protocol fields match157 and Chrome155 oracle remains unchanged.

Native adaptation decisions:

- Retain158 SBOM/license declarations while adding Cloakfox build directories/includes.
- Retain158 network-geolocation URL validation and request logging; keep existing per-document location/privacy policy rather than reintroduce process-global configuration.
- Adapt Navigator user-agent interfaces to158 UTF8 types; preserve own-container identity and native internal caller behavior.
- Retain158 unified SVG/text bounding-box path and TextContentBounds with owning-document noise, exact zero-box handling and CTM noise.
- Keep comprehensive Cloakfox container restore pruning, including closed/saved groups and deferred restore records. Upstream158 also prunes closed windows, already included in the broader Cloakfox implementation.

Validation pending: full patch replay, native build, unit/runtime suite, package and independent review.

Test harness maintenance: three explicit runtime version checks now require158; strict replay uses configured upstream version and verbose patch output to expose otherwise silent offsets on macOS. Stock158 native feature probe confirms JPEGXL decoding/bitmap/canvas/PNG paths and actual CSS calc typed arithmetic dimensions; default probe will test master-on and master-off in the Cloakfox build. Baseline source-dependent unit checks were intentionally run before all native patches and are not claimed passing.


First full build reached C++/Rust compilation after selecting installedSDK26.5 (14.4 correctly rejected by158; defaultSDK27 uses unsupported new TAPI architecture in installed LLVM19). First source compiler issue: ClientWebGLContext no longer inherits dom namespace imports; qualify owning WorkerPrivate/CanvasFingerprintManager/WebGLParamsManager references in final158compat patch. No behavior changed. Node242/242 and source-only Python24/24 pass;16 binary tests await158. Release28/28, network13/13, blocker6/6, icon preservation/font rename checks pass. Staging-idempotence fixture needed required helper stubs; production staging was unchanged and both calls now required to succeed. Corrected patch replay passed128/128 and335 file hash comparisons. Native source compile warnings remain to classify at completion.

Fresh strict replay also passed128 patches,297 pristine targets and335 final hashes, zero offsets/fuzz/drift. Node242/242 and source-only Python24/24 passed after formatting normalization; binary checks still pending.

Adapted canvas and dom/base native target builds both exited0, proving the WebGL namespace and UTF8 Navigator/ScreenAccess conversions compile. Full first Rust link remains in progress; full-build success is not yet claimed.

Coverage correction found while build runs: screen-management/media-HDR probes used the retired featurePolicy.header pref. Updated to158 permissionsPolicy.header.enabled so native parsing-on and parsing-off controls exercise the real158 preference. Production settings had no stale pref; native policy migration was already using the new name. Existing behavior assertions unchanged.

Full native build4 passed in14m31s after initial Rust compilation. Buildidentity/XUL hash recorded.113 browser probes running serially with stock158 and Chrome155 references, real localTLS/H2/H3 fixtures, copied Monaco assets and widget pointer input. No installedapp/profile changes.

Runtime first environmental failure: background_activity exited at import because isolated network venv lacked websockets. Installed15.0.1 locally in that venv; full suite continues, background probe must rerun serially after suite. Import inventory otherwise only flags optional mitm observer/embedded mozbuild imports.

Reviewer P2 reproduced in new158-feature probe: exact protected DOMRect40px assertion failed at39.9748268px, while CSS.supports/computedwidth were correct. This is intended existing geometry noise, not a layout regression. Test now keeps exact parser/computedwidth proof and exact disabled/stock geometry, checks protectedDOMRect within native±0.2px and offsetWidth within±1px, and asserts seed12345/valid32byte secret/standard-or-strict policy with no exceptions. No native protection changed. Serial rerun pending after full suite.

All113 runtime probes passed after3 explicit reruns (110 initialpasses; missingwebsockets dependency, correctedgeometrytest expectation, personaUI click not reproduced with diagnostics). Binary-enabledPython initial38pass/1failure/1skip exposed the WebGL owner-method teststub missing its new dom namespace; addedmatchingnamespacealias without changing real method/assertions. Targetedsource testpassed, freshfullPython39passed/1conditionalFirefox-UA skip. Desktop/headful checks and package pending.

Final: additional desktop probes5/5 after pointer145/145 isolated rerun (initial142/145 transient retained in report). Independent final review: no remaining actionable findings. Package succeeded; actual DMG-mounted app passed12/12 representative checks; executable/XUL UUIDs match development build; no escaping app symlinks. Source hashes freshly reverified335/335. See verification.md for final status and limits. No install/commit/push.
