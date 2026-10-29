# GPU reference and canonical geometry readiness —2026-10-28

**Status: BLOCKED / NOT IMPLEMENTED.** This is an honest preparatory checkpoint,
not a completed feature or a new Firefox build. No active GPU-reference or
canonical-geometry toggle was added, and no native privacy protection was removed.

## Implemented preparation

- Offline, bounded importer for a pinned fpgen model, with exact archive/member/
  decompressed SHA256 checks, conditional GPU→GL1→GL2 pairing and model/license
  provenance. No automatic package import, unchecked download or network call.
-106Firefox paired reference paths and118deduplicated contexts. Full original
  observations, static capability subsets and mutable state remain distinct.
- A comparison against previously measured real canonical-backend scalar bounds,
  retaining every required value unchanged. This is a necessary support screen,
  never executable admission or physical-driver certification.
- A headless canonical-geometry acceptance probe across fonts, controls, borders,
  Element/Range/caret, SVG transforms/strokes/markers/clips/foreignObject, zoom,
  request transitions and reload. It explicitly fails admission rather than
  silently certifying the current implementation.
- CI wiring and an exact zstandard0.25.0 dependency pin for importer tests.

Source: Camoufox commitb6205b0ee1e4c2e8e4bb9eb0e084472028a9c6a3 uses
fpgen model2/2026. The pinned model originates from
https://github.com/scrapfly/fingerprint-generator/releases/tag/model-2/2026 .
The model observations carry Firefox146/coarse GPU labels, not complete verified
Firefox159 physical-model execution. Version adaptation and actual operations
must be validated separately before activation. Apache-2.0 text/attribution are
in `additions/cloakcfg/gpu-reference-source.json`.

## Why activation is blocked

Every available recorded pair exceeds at least one measured scalar capacity:

| Family | Examples of a required backend change |
| --- | --- |
| Apple |77uniform-buffer bindings versus72available; some records require80combined texture units versus64available. |
| Intel | A closest Linux record requires32GL1varying vectors versus31available, and128GL2varying components versus124available. |
| AMD | A closest record requires16384texture dimensions versus8192available and8samples versus4available. |
| NVIDIA | A closest Windows GTX980record requires8samples versus4available. |

The full matrix is `additions/cloakcfg/gpu-reference-matrix.json`. These are
necessary scalar failures only: precision, ranges, extensions, formats, real
allocation/compilation/rasterization, error semantics and WebGPU agreement still
need validation. Increasing a returned limit or silently clamping a reference
would not implement the requested protection. Supporting these records needs
real changes to the software backend and its validation, not relabelling it or
switching to host drivers.

Geometry also fails admission with the existing canonical font pipeline: changing
minimum font size, physical device-pixel rounding or full zoom changes actual
text/control/Range/SVG geometry under the same container/site identity. Simply
removing additive presentation would reveal those unnormalized values.
`geometry-negative-acceptance.json` records the expected failing acceptance
(exit1); `geometry-diagnostic.json` preserves the detailed run. See the complete
[implementation dependency map](../../superpowers/verification/2026-10-28-canonical-geometry-blockers.md).
The diagnostic uses the prior159baseline XUL, not newly compiled native changes.

## Review and preservation

Independent review covered import parsing/pairing/bounds, provenance, CI changes
and readiness-test truthfulness. A proposed zstd-units concern was checked with
real pinned0.25.0 C-extension frames: the parameter is enforced as bytes in this
runtime. The added64MiB-window fixture must be rejected by the16MiB guard, even
when its output would fit the ordinary byte bound. No guard was weakened.

`status.json` records unchanged Chromium build inputs, preserved checkpoints,
source/data hashes and zero admitted references. Existing runtime protections,
installed applications, personal profiles, previous builds and test evidence
are unchanged. A full implementation and its new native159build/test/review
remain outstanding; these preparatory results must not be called completion.

Final verification:166Python tests passed in74.82seconds;369Node tests passed.
The targeted importer/native-helper set passed10tests. The deliberately failing
canonical-geometry acceptance remains exit1; it is not included in those unit
pass counts. Independent review found no remaining actionable issue in the
preparatory importer/diagnostics, not in a completed native implementation.
