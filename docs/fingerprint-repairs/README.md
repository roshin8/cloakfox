# Installed Cloakfox fingerprint repairs — 2026-10-15

The five confirmed audit gaps are repaired in the installed `/Applications/Cloakfox.app` (158.0-beta.26, runtime build `20261015004136`). The previous app is backed up; personal profiles were not changed. Quit and reopen the installed application to replace any already-running older appearance copy.

| Confirmed gap | Final behavior | Installed verification |
| --- | --- | --- |
| Raw AudioWorklet graph readback | Site/container-bound protection covers normal input copies and graph signals connected through AudioParams. Intrinsic automation, constants, silence and source graph buffers retain native behavior. | Distinct protected hashes across containers/sites; repeat/reload stability; native master-off and site-exception controls; numerical bounds and pure automation controls pass. |
| CSS color depth exposes physical screen depth | Content CSS and `screen.colorDepth`/`pixelDepth` use the owning document's configuration. Browser UI retains native handling. | Protected 24-bit depth agrees with `(color: 8)` and stylesheet rules; master-off reports native depth. |
| CSS gamut and JS media queries disagree or use another container | Native media-query evaluation is authoritative; conflicting actor overrides are removed. | 22 observations cover stylesheet/matchMedia agreement, explicit gamut/preference changes, multiple containers, frames, asynchronous evaluation and native opt-out. |
| Chromium JavaScript identity lacks matching HTTP hints | First secure content requests receive the three default low-entropy hints from their actual final UA; Chromium vendor reporting and UA parsing agree. Explicit per-hint edits/removal and site denial are respected. | 90 real local TLS/HTTP header checks pass, including redirects, workers, policy inheritance, initial-empty/srcdoc/blob frames, trust gates, native opt-outs and malformed UA values. BrowserLeaks independently receives matching Chrome/Windows headers. |
| WebCodecs hardware-preference support oracle | The existing media-capability privacy flag normalizes preference in both support queries and actual configure paths, using the owning window/worker's container. | Eight cases cover window/worker, native per-container opt-out/master-off, invalid/unsupported configurations, preference-independent results and real VP8 encoding. |

A configured User-Agent containing CRLF or NUL is now rejected safely rather than becoming an extra HTTP header or a truncated identity.

## Verification

- Native build and final incremental dependency check: passed.
- Pristine Firefox replay: **133 patches, 307 pristine targets, 346 target hashes, no fuzz, offsets or source drift**.
- **247 JavaScript unit tests** and **38 Python tests** passed.
- **27 probes passed against the installed app**, covering the four new repair probes and related media, network, worker, screen, settings and IP-warning behavior.
- The packaged app is self-contained and its local signature verifies with `codesign --verify --deep --strict`.
- Independent source review found no remaining actionable defects after the AudioParam and policy-inheritance corrections.

Raw local results are under `tests/fingerprint/reports/158-fingerprint-repairs/installed/`. The installed binary, package/hash, backup path, exact probe results and reduced raw-audio hashes are retained in [results.json](results.json), with installation identity in [install.json](install.json). The earlier failing installed-browser cases are retained beside the final results.

## External website retest

Twenty-one distinct case/site combinations were captured using the installed application in disposable profiles: a generated default identity, generated Windows Firefox and Windows Chrome identities, and a protection-off control. The ten URLs cover BrowserLeaks JavaScript, canvas, WebGL, fonts, WebRTC, Client Hints and TLS, plus CreepJS, Fingerprint's demo and tls.peet.ws. Four repeat/reload checks preserve the selected identity and hashes.

BrowserLeaks confirms matching CSS/JS screen depth and gamut; its Client Hints page receives Chrome 155/Windows headers matching JavaScript. Its WebRTC page reports **No Leak**, with no local/public candidate address. The default Fingerprint demo resolves to the generated Linux/Firefox identity in the completed follow-up. These observations do not establish that the browser cannot be tracked.

Fonts, TLS and the Fingerprint demo were revisited after their asynchronous results finished. An initial font readiness selector missed the checkmark before its hash; the corrected selector completes successfully. The final summary selects the completed observations, retaining initial captures and follow-ups separately. Raw pages/screenshots are in `installed-sites/`, `installed-sites-async/` and `installed-sites-fonts/` under the report directory. The reproducible external auditor is `tests/fingerprint/audit_installed_fingerprint_sites.py`.

Marionette has a separate Intl realm; its timezone is explicitly marked diagnostic metadata. Website-rendered and worker timezone results, together with the local owning-page tests, are authoritative.

## Remaining limits

- **Gecko remains distinguishable from Chromium.** CreepJS still reports `chromium: false` for the Chrome identity. UA/header coherence does not replace the rendering engine.
- HTTP high-entropy Client Hints, Accept-CH persistence, Critical-CH and full origin allowlist delegation remain unsupported. BrowserLeaks explicitly lists those optional headers as not received. See the [request-hint policy](../fingerprint-audits/2026-10-15-client-hints-policy.md).
- WebCodecs still validates real codec availability and uses real execution performance. This repair closes the preference-dependent query difference; it does not fabricate codecs.
- Worklet attenuation mitigates exact raw readback. It is not a proof against arbitrary averaging or quantization attacks, and cross-device uniqueness was not quantified.
- Dedicated/nested workers inherit the owning snapshot. Existing shared workers retain their first creator's policy; independent service workers have their own policy rather than inheriting every controlling page's restrictions.
- Real camera/microphone permissions, live interview calls and personal browsing profiles were not used. Related capture checks use test-profile fake media devices. No live assessment was opened or submitted.

The follow-up local library validation adds **48 executions and 449 passing checks**, with **247 JavaScript and 43 Python checks** passing on the final tree. See [library validation](library-validation.md). Commit and push are authorized for this work.
