# Full fpgen GPU profile expansion — Firefox 159

The observed compatibility catalog now contains **nine Windows GPU identities**,
up from three. All 886 paired browser/platform/GPU/WebGL1/WebGL2 conditional paths
in the pinned full fpgen archive are scanned. Twenty-three matching paths produce
nine distinct executable identities; 863 paths remain excluded with explicit
reasons. The four previous protected reference profiles are unchanged, including
Apple. Source observations alone never grant executable capability admission.

## What changed

- Offline full-model import preserves actual conditional pairing, provenance,
  probabilities, incomplete observations and mismatched-owner blockers. Its
  deterministic compressed evidence is separate from the unchanged legacy corpus.
- Admission replaces the fixed identity shortlist with an exhaustive scan for
  complete execution-equivalent capability pairs. Existing three validated pairs
  provide the execution contracts. New identities are never assigned made-up
  capabilities, and incompatible pairs do not fall back to the physical GPU.
- Existing codes and descriptors remain stable. Native and JS registries agree on
  exact vendor, renderer and OS binding. Native context creation independently
  checks the canonical backend's actual support.
- The existing **Use observed GPU compatibility** toggle remains per container.
  Explicit on/off choices persist. Container/site secrets and owner checks stay
  separate; the same public capability tuple or canonical authored pixels may
  occur in different containers. No new network lookup or hardware upload occurs.
- Settings explain the expanded coverage and both fpgen/BrowserForge sources.

| Code | Windows GPU identity | Status | Source paths |
| --- | --- | --- | ---: |
| 36866 | Intel HD Graphics 400 | Existing | 1 |
| 36867 | AMD Radeon R9 200 Series | Existing | 6 |
| 36868 | NVIDIA GeForce GTX 980 | Existing | 6 |
| 36869 | Intel HD Graphics | Added | 3 |
| 36870 | NVIDIA GeForce 8800 GTX | Added | 1 |
| 36871 | AMD Radeon HD 3200 Graphics | Added | 2 |
| 36872 | Intel Arc A750 | Added | 2 |
| 36873 | AMD Radeon HD 5850 | Added | 1 |
| 36874 | NVIDIA GeForce GTX 480 | Added | 1 |

The software backend is unchanged. This is coherent execution with canonical
rendering, not physical vendor-driver emulation. Other OS/vendor observations
remain recorded evidence rather than automatically active profiles. In particular,
this does not expose the full model's raw WebGPU hardware information.

## Verification

A separate headless macOS arm64 **Firefox 159.0-beta.1** app was built successfully,
with zero compiler warnings. The installed application and personal profiles were
not changed. Final receipts are in `acceptance-summary.json`; exact raw reports are
archived under `runtime/`. Native XUL SHA256 is
`88702cd79e55344a6ac8c580952f5431defce483cab74b30a5efa8f70f930582`.

**11,948 checks across ten probes passed, with no failures or inconclusive
results.** All nine observed identities ran under two owners, with window,
classic/module worker, initial blank frame, restart and explicit-toggle checks.
Resource/shader/stencil/LOD/index operations, WebGPU budgets, timer/debug exclusions,
precise/PBO readback restrictions and existing noncanonical noise were exercised.

| Probe | Checks | Result |
| --- | ---: | --- |
| `probe_gpu_reference_backend_admission.py` | 1,052 | Passed |
| `probe_gpu_observed_profiles.py` | 8,419 | Passed |
| `probe_gpu_reference_profiles.py` | 1,707 | Passed |
| `probe_full_gpu_libraries.py` | 167 | Passed |
| `probe_container_gpu_profiles.py` | 385 | Passed |
| `probe_webgpu_canvas_owner.py` | 8 | Passed |
| `probe_canvas_owner_transfer.py` | 4 | Passed |
| `probe_graphics_privacy.py` | 60 | Passed |
| `probe_container_rendering_settings.py` | 87 | Passed |
| `probe_fpgen_personas.py` | 59 | Passed |

Unmodified pinned CreepJS and FingerprintJS completed 22 collections covering all
nine observed identities, a repeated sample and a second owner. CreepJS reported
no GPU/capability warnings for these identities. This is a result for the pinned
fixture, not a guarantee of universal fingerprinting invisibility. FingerprintJS
intentionally omits unmasked labels on Gecko; tests assert its real numeric
coverage and separately query native WebGL identity. Real canvas image evidence
is required before repeat/pixel comparisons can pass. WebGPU was enabled and
available throughout these probes.

Static suites: 440 JavaScript tests; 27 GPU Python tests; 22 targeted importer/
generator/native tests; final 15 importer/generator/library-helper tests. These
suites overlap and are not summed as independent tests. All passed without skips.

Independent review found a test-evidence issue (missing canvas data could have
been hashed); it was fixed, negatively tested and re-reviewed. No actionable
review findings remain. See `code-review.md`.

## Preserved failed attempts

Build integration required sorting existing resource lists and syncing missing
fpgen build resources. Three failed configuration receipts are retained before
the successful build. Runtime fixture corrections preserve native API contracts:
workers have `platform` but no `oscpu`; explicit observed=false must be saved via
the real override API; FingerprintJS omits unmasked Gecko labels; the UI coverage
assertion must use the expanded catalog. Initial receipts/raw reports remain in
the report directory and are named `attempt1` or `before-explicit-toggle`.
No production privacy assertion was disabled to obtain the passing results.

## Reproduction and boundaries

Use the importer commands in `importer.md` and
`python3 scripts/generate-gpu-reference-profiles.py --check` for reproducibility.
For each listed probe, set `CLOAKFOX_BIN` to the separately built159 executable,
`MOZ_HEADLESS=1`, `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1`, `REPORT_DIR` to a fresh output
directory, and `CLOAKFOX_CANONICAL_GPU_DIR` to that app's
`Contents/Resources/canonical-gpu`, then run with the runtime Python environment.
Library probes require the pinned fixtures verified by `library_audit_common.py`.

Chromium build inputs retain key
`bbc651dcf5cbe4321f5fd1728eb40f2a20f7547053009258d96764370804dfcf`. No Chromium build/process or checkpoints were changed.
Validation is on this Mac; it does not establish Windows/Linux native rendering.
