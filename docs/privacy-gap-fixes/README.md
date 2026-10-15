# Privacy gap fixes — installed Mac acceptance

All three combined-review findings are fixed and independently re-reviewed on installed `/Applications/Cloakfox.app`, Firefox158.0-beta.26, runtime BuildID **20261015180857**. Personal profiles were not edited. Restart Cloakfox to use the new app if an older process remains running. [Artifact and raw acceptance](acceptance.json), [independent review](review.md).

## Fixes

- **Bitmaprenderer serialization:** metadata now controls extraction. Exact owner/container/site producer proof or verified ownerless authored rasters may export canonically. Unknown/foreign inputs receive the recipient's existing site-bound protection. If canonical mode cannot supply protection, extraction refuses or Gecko's null-buffer encoder returns a blank image; source pixels are not released. Conversion/noise uses straight RGBA to match2D typed readback, retaining alpha. Privileged/master-off and intentional legacy opt-out behavior remain native.
- **WebGPU ownership:** canonical configure checks a valid captured owner version, exact UCID and both site-owner halves against the device. Missing/mismatched owners raise InvalidStateError before configuration. Output metadata independently withholds canonical certification for mismatched devices, even with no imported sources.
- **IP warning accuracy:** page and notification describe matching public-IP lookup measurements associated with recorded visits, explicitly disclaiming proof of destination egress under proxy and IPv4/IPv6 differences. The same-host visit filter and network request behavior are unchanged.

## Verification

| Installed check | Result |
| --- | --- |
| Bitmap export, legacy/canonical, PNG/JPEG/WebP, HTML/Offscreen/worker |219passed |
| WebGPU owner boundary and native controls |8passed |
| Container/site GPU profiles, restart and restoration |331passed |
| Existing GPU corpus |103passed |
| Existing2D encoder corpus |31passed |
| Known-fill recovery resistance |14passed |
| IP workflow, local TLS proxy fixtures |Passed |
| Unmodified CreepJS/FingerprintJS, WebGPU enabled/disabled |464/448passed |
| Node/Python units |268/118passed;14Python cases skipped |
| Pristine native patch replay |144patches,409targets; zero drift/offset/fuzz |
| Installed package |Strict deep signature and82resource hashes verified |

RED evidence is retained: the previous installed build exports native bitmap pixels where protected typed readback differs (`bitmap-installed-red`), and accepts a same-process transferred canvas after its owner key changes (`webgpu-installed-red-repro`). New extracted-source policy tests also failed before their fixes. The IP render tests failed on the former destination-IP claim. GREEN reports and successful installed checks are separate; old failing observations were not overwritten or counted as passing.

## Privacy and evidence limits

Existing canonical rendering, producer/import provenance, precise/PBO readback restrictions, independent container/site secrets and default-off profile toggle remain. Verified same-owner canonical bitmap output stays exact, avoiding double noise; foreign-owner output receives recipient protection. Low-alpha and opaque-X8 paths pass. Zero seed cannot release unknown canonical input.

Gecko refuses cross-process cross-site OffscreenCanvas transfer before configure, so that test cannot establish the new guard's behavior. The same-process stale-owner transfer reaches the guard and establishes rejection; actual native-source unit matrices cover exact container and both owner halves. Bitmap foreign-owner coverage uses key rotation. Transparent testing covers an all-zero clear, not hidden nonzero RGB. PNG pixels match protected readback; JPEG/WebP establish route agreement. IP fixture results establish measured lookup routing/disclosure, not arbitrary websites' egress.

Independent review found no remaining concrete P0/P1/P2 in these fixes. This is not exhaustive dependency auditing, proof against every fingerprint attack, or cross-operating-system verification. Existing CreepJS profile/rotation and Gecko/Chromium mismatch warnings remain outside this fix; coherent realistic GPU capability catalogs remain in TODO.md.
