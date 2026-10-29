# fpgen model and sampler

The default persona provider uses the pinned Scrapfly Fingerprint Generator
`model-2/2026` archive. `fpgen-model-reference.zip` is the complete, byte-identical
source archive, including all 120 Bayesian nodes and 12,256 indexed values. Its
SHA-256 is `6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936`.
The packaged source manifest records compressed/decompressed member hashes,
upstream URLs, Apache-2.0 license, attribution and modified projection details.

The runtime projection is 534,087 bytes. It retains every possible value and
conditional probability for nine ancestor-closed nodes: `browser`,
`platformInfo`, `navigator.userAgent`, `screen`,
`matchMedia.mediaCss.orientation`, `window`, `gpu`,
`navigator.deviceMemory` and `navigator.hardwareConcurrency`. It includes all
98 UA values, 501 screens, 1,409 windows and 401 GPU observations. It is neither
a hand-picked persona list nor a small collection of GPU labels. The larger
211 MB decoded value store remains compressed in the packaged reference ZIP;
runtime sampling needs no decompression, Python, network request or new library.

`sampleFPGenFingerprint(prng, {os, hardware, browser, version})` consumes only
the caller's seeded PRNG. Its immutable model and derived branch tables retain
all projected observations, but never retain a sampled identity, container ID,
secret or random state. Each returned result is detached from those tables.

The supported browser model labels are Firefox, Chrome, Edge and Safari.
Chromium has no distinct source observation and requests for it fail visibly.
The three OS filters are Windows, macOS and Linux. GPU families use observed
renderer/vendor labels: Apple, Intel, NVIDIA, AMD, software and other. `auto`
retains the complete supported probability mass. Unsupported browser/OS/GPU
combinations fail before consuming randomness; there is no provider fallback.
Browser version is validated presentation metadata for the existing Cloakfox UA
normalizer, not a claim that the source model observed that version.

Sampling conditions jointly on browser/platform/GPU and includes the probability
mass of complete descendant branches. The original archive has nine
screen/orientation paths without a window distribution; the manifest enumerates
them. They remain in reference and projection data but cannot be selected.
The sampler neither invents a uniform distribution nor splices a window from an
unrelated owner. Apple GPU observations outside macOS and non-desktop platforms
are excluded from the executable projection's sampling domain.

The adapter outputs exactly `userAgent`, `hardwareConcurrency`, `screen` and
`videoCard`. It allowlists nested geometry and GPU label fields, validates numeric
ranges and clamps captured work areas/window dimensions to their selected screen.
The existing native mapper derives inner window geometry, coherent navigator
identity and its other supported keys. The model's device-memory and orientation
nodes condition dependent observations without becoming configuration keys.

Captured permissions, media device identifiers/counts, locations, languages,
fonts, audio signatures, feature/codec support, WebRTC, TLS and HTTP fingerprints
are reference data only. They cannot enter the adapter. Existing privacy policy,
permission decisions, font/canvas/audio controls, site isolation, WebRTC/proxy
policy and native executable GPU admission remain authoritative. GPU labels are
observations and do not certify native driver capability.

## Verification

Tests were written and observed failing before implementation (missing sampler
and importer), then passed after implementation. An initial conditional-path
failure exposed the nine incomplete source paths and drove complete-path
conditioning. A later failing metadata assertion drove the explicit path report.

Commands run successfully:

```sh
node --test tests/fingerprint/test_fpgen_sampler.mjs
python3 tests/fingerprint/test_fpgen_import.py
python3 scripts/generate-fpgen-network.py additions/browser/components/cloakfox/fpgen-model-reference.zip --check
```

The seven Node tests cover determinism, distinct seeds, browser/OS/GPU filtering,
unsupported-input failures, malformed PRNGs, unsafe-field exclusion, detached
outputs, immutable source data and full-model/projection integrity. Their complete
matrix exercises 4,800 samples across 48 supported filter combinations and rejects
the other 36 combinations. The three Python tests verify byte-for-byte artifact
reproducibility, archive-tamper rejection and invalid dependency/probability
rejection. Browser runtime and packaging acceptance are recorded separately.
