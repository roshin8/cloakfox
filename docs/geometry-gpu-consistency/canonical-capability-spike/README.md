# Recognition-warning investigation — throwaway configuration experiment

No product source or installed app was changed. The installed Mac build `20261015160908` was exercised in disposable profiles with canonical software GPU routing retained, WebGPU enabled, legacy WebGL overrides removed and the bounded backend profile disabled. The copy of the library runner is retained as `probe.py`; it is a throwaway experiment, not a supported product mode. Its absolute root path is specific to this workspace.

The 48 unmodified-library executions completed, with all 464 existing consistency/isolation assertions passing. This count does not assert that detector warnings are absent. Every protected CreepJS run retained the two GPU-recognition warnings and added `webgl/webgl2 mirrored params mismatch: MAX_VARYING_VECTORS`. Current production profile stays installed and unchanged.

Pinned CreepJS `src/domrect/index.ts` lines 300–317 accepts exactly the Gecko rectangle hash `e38453f0` for its fixed 100px square rotated 45 degrees. Any seeded presentation change to that reference fails this check, even when all geometry API invariants hold. Removing presentation noise for a recognizably styled test element would be a detector-specific exception and is not proposed.

Pinned CreepJS `src/webgl/index.ts` lines 454–478 uses static tables of brand+numeric-capability hashes and numeric XOR aggregates. Current protected profile: capabilities `-73919434`, OTHER brand hash `51cf5c56`; neither table recognizes it. The experimental unbounded software-renderer report: capabilities `-73894146`, OTHER hash `c2c696a0`; also unrecognized. Offline checking with the honest SWIFTSHADER brand still gives unknown hashes (`08c863fe` for the current bounded tuple; `9f9c5448` for the experiment). Relabeling alone cannot resolve the warnings. This is not an exhaustive proof that no truthful software profile can match; it rejects the tested shortcut.

The pinned sample dataset includes real SwiftShader observations, so a recognized software profile is a research possibility. However, it contains fingerprint hashes and renderer names, not a complete enforceable capability/extension/shader profile. A reference capture and actual backend enforcement would be needed before choosing it. Claiming a physical Apple/Intel/NVIDIA GPU or adjusting a single numeric parameter to hit a checksum would not establish coherence.

## Proposed direction for review

A separate opt-in canonical geometry mode would replace readout jitter with a defined layout/metrics cohort. It must standardize font selection and metrics, system controls, zoom and rounding inputs that affect DOM rectangles, and keep Element/Range/SVG/offset APIs consistent with actual layout. Exact authored rectangles may naturally match stock-engine values, while native host-dependent measurements must not become fallback outputs. This is an architectural change; existing protection remains active until that pipeline has privacy regression evidence. Shared geometry also changes the current per-site/container output variation, which needs an explicit design decision.

For GPU, capture a genuine software-renderer reference profile, intersect it with the bundled backend's supported limits, and enforce the entire advertised profile in allocations, validation, shaders, extensions, workers and context restoration. Prefer one honest software identity. If no supported profile is recognized, retain truthful protection and report the warning rather than forge a known hash.

Acceptance would include unmodified CreepJS/FPJS, adversarial geometry with text/intrinsic/system-font cases, cross-scope ownership, all relevant GPU allocation/validation checks, native controls, installed Mac reruns and code review. Passing a detector allowlist is not itself the privacy criterion. No new product implementation or new success claim is made by this experiment.

## Superseding requirement

The user rejected shared cross-container profiles. The revised [container-specific plan](../../superpowers/plans/2026-10-15-container-rendering-profiles.md) and [design](../../superpowers/specs/2026-10-15-container-rendering-profiles-design.md) supersede the shared-cohort proposal above. Keep historical experiment results unchanged.
