# Optional rendering privacy modes

User intent: add toggleable rendering-stage canvas protection and compatible GPU
profiles, preserve privacy, and verify the installed Cloakfox with unmodified
fingerprinting libraries. Firefox/Chrome engine replacement is outside scope.

## Privacy boundary

Rendering perturbation is not proven equivalent to the current extraction guard.
Image, filter, composite, copy, transfer and WebGL paths prevent a text-only
implementation from safely disabling that guard. Therefore this release adds
experimental rendering protection while retaining extraction protection for all
canvases. The UI must say this plainly. Pixel-noise detection may remain.

Neither mode may expose real GPU model/vendor strings, turn off extraction noise,
loosen precise/PBO restrictions, change permissions, or rotate existing identity
seeds. Missing/malformed policy selects existing protection. Changes apply to new
contexts; users reload pages and restart workers. Master-off keeps native behavior.

## Settings

Two global booleans, both false by default:

- `cloakfox.opt.canvas_render_privacy` emits `canvas:render_privacy`.
- `cloakfox.opt.gpu_backend_profiles` emits `webGl:backend_profile`.

These are authoritative graphics policy fields applied after generic overrides.
Startup and preference updates change only owned fields in persisted config
objects. No persona regeneration, source GPU inventory persistence or seed reset.
Both controls appear beside existing graphics protections with bullet descriptions.

## Canvas

Freeze the optional rendering policy and owning schemeful-site/container seed on
the context, including OffscreenCanvas and workers. Add a small deterministic
variation to glyph rendering before rasterization. Preserve author transforms,
clipping, draw order, text alignment, text baseline, error behavior and state.
Inflate calculated draw bounds conservatively where variation requires it.
Retain native font/permission gates and existing extraction/metric behavior.
Unsupported drawing operations continue existing protection. Do not recognize
CreepJS inputs or claim complete render-time coverage.

## GPU

An internal context-creation policy bit is serialized to the host, where a
conservative standardized profile restricts actual context limits before use.
The host must not infer container identity through ambient MaskConfig state.
Client getters, native limits/compiler resources and allocation validation must
agree for controlled capabilities. Respect WebGL1/WebGL2 enum and minimum-capacity
differences. A backend incapable of the complete baseline must fail protected
context creation rather than expose its native GPU identity.

Shared device limits agree across WebGL1 and WebGL2: 16 attributes, 32 combined
texture units, 16 units per shader stage, 256 vertex uniform vectors, 224 fragment
uniform vectors, and 15 varying vectors. Both use 16 vertex output vectors and
15 fragment input vectors internally. Textures/cube maps/renderbuffers use 2048,
viewport 4096, line width 1 and point size 1–63 with raster clamping. WebGL2-only
limits include 256 3D texture size/layers, 24 UBO bindings and 4 draw buffers.
Unsupported whole baselines fail protected creation. Shader precision uses fixed
float 127/127/23 and integer 24/24/0 tuples, validated against native query results;
the latter matches Gecko's conservative non-GLES desktop query implementation.
Legacy precision masks remain validated and preserved, with native enum checks.
Legacy parameter, extension and precision tables use exact owning-container
lookups for windows and workers rather than an ambient worker container 0.

The profile uses generic masked vendor/renderer identities, not a borrowed card
name. Native support and permission checks precede extension/precision reporting.
Keep mutable state native and existing readback restrictions. This is compatible
normalization, not complete driver emulation; extension availability, timing and
rendered output may still distinguish backend cohorts. Do not copy detector
reference tables or persist a hardware fingerprint.

## Acceptance

Defaults preserve existing behavior. Both opt-ins persist independently, survive
restart, backfill old identities and preserve seeds/manual/network fields.
Native and wrong-type settings retain their correct protection boundaries.
HTML/window-Offscreen/worker-created/transferred canvas and worker WebGL retain
same-site reload stability and different-site/container separation. Exercise
text fill/stroke/maxWidth/RTL, paths/gradients/images, cropping/PNG/bitmap transfer,
state/reset, native controls and strict readback controls. Test actual GPU
allocation/shader limits and context loss/restoration where supported.

Build, strict patch replay, independent review, package/sign/install, then repeat
installed probes and pinned CreepJS/FingerprintJS across off/on mode combinations.
Record remaining warnings verbatim. No assessment or personal-profile mutation.
