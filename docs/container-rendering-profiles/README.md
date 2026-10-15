# Container GPU persona profiles — installed Mac acceptance

Implemented and installed bounded native GPU enforcement for Apple, Intel, AMD and NVIDIA BrowserForge personas. This is resource-profile enforcement on the verified canonical software backend; it is not physical driver emulation, bit-identical vendor rendering or performance parity.

## Use

Restart the installed `/Applications/Cloakfox.app`. In Cloakfox settings, enable **Use canonical software rendering**, then **Use container-specific GPU persona profiles**. The second toggle defaults off. Reload affected pages and restart workers. All existing saved containers must have supported physical-family personas and compatible overrides before activation; unsupported new personas keep their other privacy masks but GPU creation fails until a compatible persona is selected. No host renderer fallback is permitted.

Disabling the profile toggle preserves saved personas, keys and records and restores the existing protected generic GPU policy for new contexts. The toggle is global; profile records, secrets and derived identities remain independently owned by each container. No personal profile was modified during installation/testing.

## Enforced contract

Profiles bind the exact owning principal's container, the existing container secret and a canonical top-level schemeful site via a separate HMAC domain. Canvas readout exceptions do not disable profile identity. Existing contexts retain captured identity and caps through settings changes and context restoration. Offscreen transfers require matching container and site provenance.

WebGL1/2 enforce texture/cube/renderbuffer/viewport ceilings of Apple6144, Intel4096, AMD7168 or NVIDIA8192. Vertex uniform vectors are256+variant; fragment vectors224+variant. The8-bit variant is derived independently for each container/site. WebGPU enforces maxBufferSize=(256+variant)MiB and storage-buffer binding128MiB in adapter/device validation. WebGPU core texture minima are independently preserved. Existing extension, shader precision, attribute/unit and strict readback controls remain. Unsupported backend capabilities reject creation rather than raising advertised capacities or exposing host values.

Common safe caps and8-bit variants may coincide; separate ownership does not promise every reported value is globally unique. Saved BrowserForge vendor/renderer labels are retained and frozen for each context, rather than restoring physical host identity.

## Verified installed artifact

Runtime BuildID **20261015174757**, version158.0-beta.26, macOS arm64. XUL SHA256 `0b53725f4c5edce9888aea7c9760f18dee5080c7a28b2f820589ef404d944240`. Strict deep code-sign verification passed; signed GPU bundle hashes are preserved. [Installation and backup](install.json).

| Check | Result |
| --- | --- |
| Signed candidate native profile run |328pass |
| Installed final acceptance, including restart/restoration |331pass |
| Pinned unmodified FingerprintJS/CreepJS, WebGPU enabled |464pass |
| Same libraries, WebGPU disabled |448pass |
| Node policy/settings suite |266pass |
| Python/native suite |116pass,14skipped |
| Pristine patch replay |144patches,409targets; zero drift/offset/fuzz |
| Independent code review |Two P2 issues fixed and re-reviewed; no remaining concrete P1/P2 |

[Final native acceptance](installed-acceptance/result.json) covers all four families, eight real containers with identical-persona pairs, two sites, actual texture/shader/device/allocation rejection boundaries, page/worker agreement, precise/PBO readback guards, captured live/restored context policies, canvas exceptions, wrong-owner failure and persistent identities after restart.

Additional installed regressions passed:103GPU corpus checks,15image checks,14known-fill adversarial checks,17text checks, DOM geometry consistency (zero failures), and16canonical backing/privacy checks. The early backing-only probe incorrectly assumed identical noise bytes between renderer modes, then incorrectly required noise on authored solid fills. Both fail on the pre-feature implementation/design: canonical rendering intentionally keeps authored solid RGB/alpha exact. The corrected probe verifies exact author pixels, deterministic protected glyph rendering, restart persistence, native-glyph distinction and legacy off-mode masking. The separate known-fill recovery attack remains unsuccessful in pages/offscreen/workers. Original failed reports are retained for traceability; [independent review](review.md).

## Remaining detector warnings and limits

CreepJS still reports **unknown rotate dimensions**, **suspicious GPU**, and **suspicious capabilities**. Chrome-UA cases also report the existing SpiderMonkey/V8 engine mismatch. Canvas2D lied=false and capturedErrors=[] in the protected Firefox-identity library cases. All detector results are retained unmodified in [enabled warnings](warnings-enabled.json) and the library reports. This feature does not remove DOM masking or reproduce a physical GPU driver's complete arithmetic, shaders, outputs or timing to satisfy a detector's fixed profile lists.

Privacy verification demonstrates the tested guards and owner/site isolation; it is not a universal no-leak proof or cross-operating-system equivalence claim. Only installed Mac runtime verification was requested and performed. [Historical feasibility notes](feasibility-notes.md) record the initial catalog/emulation distinction.

## Subsequent combined review

A later combined source review found an untested WebGPU canvas/device ownership mismatch and a residual bitmaprenderer export gap in the broader pipeline. See [combined review](../privacy-review-2026-10-15.md) and TODO.md. The passing profile tests above do not establish protection for those routes.

The combined-review bitmap/WebGPU findings were subsequently fixed and independently reviewed; see [fix acceptance](../privacy-gap-fixes/README.md).
