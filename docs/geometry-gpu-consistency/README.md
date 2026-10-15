# DOM geometry and GPU consistency — installed Mac verification

The DOM geometry fixes are installed in `/Applications/Cloakfox.app`. Empty nodes no longer acquire phantom rectangles, zero-width carets remain zero-width, small extents cannot become negative, and Element/Range bounding rectangles agree with the union of their protected client rectangles. Protection remains active for ordinary, authored, transformed and text geometry.

## Privacy and implementation

`CloakfoxGeometry.hpp` shares the existing owner-seeded additive presentation across Element and Range APIs. The original ±0.2 float coefficients remain; fragments use the same coefficients rather than advancing noise by fragment index. Existing integer offset jitter remains, with guards for truly empty dimensions. No exact-text or authored-geometry exemption was introduced. Native-off and privileged handling remain native.

Bounding unions use double property setters because `DOMRect::SetRect` narrows to float. This preserves sums of values already exposed by protected client rectangles; it does not read extra native precision. The installed regression initially found this float narrowing; its failing development report is retained as `dom-dev.json`, followed by the corrected passing report.

The GPU investigation found no additional API inconsistency in the tested profiles. Both CreepJS GPU warnings originate in static recognition tables: the protected generic brand/capability hashes are absent. No GPU product change was made to imitate a known hardware label or regain access to host capabilities. Actual allocation, shader validation, mutable state and reported limits passed 103 GPU checks plus 42 profile checks. Existing backend and conservative capability enforcement remain enabled.

## Installed verification

- Runtime BuildID `20261015160908`, Firefox `158.0-beta.26`.
- Installed XUL SHA256 `0dd811a063e878eb03d8d19a5510fe09ab77de33f56732985bf9749cf11a7b56`.
- DOM regression passes with the canonical renderer both off and on, across reloads, changed seeds, two actual containers and different sites.
- Core renderer corpus: **940 checks pass**; additional exact SVG goldens: **29 pass**; additional GPU profile checks: **42 pass**.
- Unmodified pinned CreepJS and FingerprintJS: **448 checks across 48 executions pass**. These assertions cover consistency and isolation, not a claim of zero detector warnings.
- Unit suites: **261 Node tests, 115 Python tests pass**; 14 unrelated runtime-dependent Python cases skipped.
- Native replay: **144 patches / 408 pristine targets**, no drift, offsets or fuzz.
- Installed deep/strict signature verification passes; all **82** GPU manifest files match.

Machine-readable summary: [acceptance.json](acceptance.json). Individual probes and the initial failed observations are retained rather than overwritten. All browser probes used disposable local profiles. Personal profiles were unchanged; app backup is recorded in [install.json](install.json).

## Font regression correction

The initial corpus's unconditional SVG-versus-Canvas exact-pixel assertion failed twice. Matching seeds reproduce identical corresponding output in the previous verified build, and native rendering also differs across these APIs at fractional sizes. This was an overstrict cross-API assertion, not a new geometry regression. The original 100-check report remains under `installed/probe_canvas_canonical_fonts`.

The revised corpus has 96 strict checks, including exact same-SVG data/blob comparisons and exact OffscreenCanvas/worker transfers. Cross-API differences remain visible diagnostics. An additional 29-check test pins explicit font bytes, owner identities and raw SVG pixel hashes from the previous build. Both revised probes were independently rerun against the installed app. No arbitrary anti-aliasing tolerance or product rendering change was introduced. See [diagnosis](svg-bidi-diagnosis/README.md).

## Remaining warnings and limits

CreepJS no longer reports the ghost-rectangle inconsistency. It still reports `unknown rotate dimensions`, `suspicious gpu` and `suspicious capabilities`. The first compares geometry against known engine hashes; the others compare protected GPU values against known-profile hashes. Matching those values by returning native measurements would change the privacy model. Full per-run warnings remain in [detector-observations.json](detector-observations.json). Chromium UA cases also retain the separately deferred Gecko/Chromium engine mismatch.

This verifies macOS arm64 only, not cross-operating-system pixel equality or undetectability. The bounding-rectangle path now allocates a client-rectangle list proportional to fragment count; no broad performance claim is made. No screen-sharing/camera session or external assessment was started for these tests.

Independent code review and final test review found no remaining actionable findings; see [review.md](review.md).

Follow-up: [WebGPU-enabled library verification](webgpu-enabled.md) passes 464 library checks and 103 direct GPU checks. This supplements the earlier default-blocked library run.
