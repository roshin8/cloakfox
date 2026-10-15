# Canvas and GPU consistency audit

Worktree: `codex/firefox-158-port`, based on `a35115c727` (Firefox 158).
The Chrome/Gecko engine mismatch is explicitly outside this repair.

## Repaired behavior

- Canvas perturbations address original source pixels. Full reads, crops, negative
  source rectangles and clipped reads agree without changing destination padding.
- Protected 2D image export uses the same straight RGBA representation as
  `getImageData`, avoiding premultiplication-dependent noise amplification.
- Glyph advance and ink bounds share a small positive scale. Empty ink remains
  empty, signs are preserved, and alignment/baseline translations stay coherent.
  Font, em and baseline metrics keep native values.
- Generated WebGL uniform vector/component and varying/fragment-input capacities
  agree. Exact recognized saved generated tables migrate on startup; custom
  tables, seeds and scalar overrides retain their established precedence.
- Extension enumeration and `getExtension` share native support and caller
  permission checks. A configured extension name cannot manufacture support.
- Configured upper-bound capacities are intersected with backend ceilings.
  Saved custom intent stays intact, while reported values cannot grant
  unsupported hardware capacity. Paired vector/component queries are normalized
  together, including one-sided overrides.
- Viewport and point/line queries retain their native typed-array return types.
  Complete arrays are validated before intersecting native dimensions/ranges;
  malformed, reversed or disjoint inputs safely fall back.

## Evidence

The original installed binary reproduced 92 failures in the initial 273-check
canvas probe, with no native-control failure. The expanded dedicated-worker and
transferred-canvas probe reproduced 180 failures against that original app's
backup, again with all native controls passing. The final installed app passes
all 589 canvas checks, all 30 GPU migration/semantics/capacity checks, and the
existing graphics, worker-canvas and WebGL table probes.

The final installed library retest ran the pinned, unmodified upstream CreepJS
and FingerprintJS 48 times (three loads per library across eight cases), passing
449 stability/isolation checks. CreepJS no longer reported `measureText` metric
noise in any sample. Full findings, including remaining warnings, are retained
in `results.json`. `api-consistency-results.json` retains the intermediate run
before the capacity follow-up.

The actual backend supports an 8192-pixel texture/renderbuffer maximum, four
samples and point range `[1,64]`; the repaired getters respect those ceilings,
and an 8192-by-1 texture allocates successfully in both WebGL versions. Previously
the generated profile claimed 16384, eight samples and `[1,1024]` respectively.
Those profile values remain stored; the native intersection is authoritative.

Native build/package and signature verification pass. All 251 JavaScript tests
and 46 Python tests pass. Strict replay applies 136 ordered patches with no
offset, fuzz or drift across 346 hashed native targets. Review is in `review.md`.
Installed XUL SHA-256:
`e7e1cc1415b36f0902c4b97e26f57746c7e51ffb6872c2139fe0b3fea04e5be2`.
The runtime build is `20261015103335`; application.ini records `20261015103359`.

## Interpretation and limits

CreepJS's pixel modification probe compares author-selected fill colors against
readback. Deliberately perturbing those colors remains observable. Its suspicious
GPU/capabilities and low-entropy canvas warnings additionally depend on finite
historical reference tables. Neither those tables nor the library fixtures are
modified here. Passing stability checks does not mean every upstream warning is
absent.

Remaining final CreepJS findings are `pixel data modified`, `suspicious pixel
data`, `suspicious gpu`, and `suspicious capabilities`. Protected geometry also
retains its pre-existing rotate/ghost rectangle warnings. The two Chrome-UA
cases retain the intentionally deferred SpiderMonkey/V8 mismatch. Native control
reports none of these warnings.

Final-result glyph scaling remains calibratable and differs slightly from drawn
raster geometry; it is a semantic repair to the existing extraction design,
not render-time privacy. GPU identity masking likewise does not emulate a
different physical graphics driver. Native-backed capability intersections can
expose backend ceilings/support differences already observable through resource
allocation; this tradeoff prevents advertising unusable functionality.
Alignment, minimum offsets and timeout settings retain their existing configured
override policy; they are excluded from the upper-bound clamp. Reporting a lower
ceiling does not enforce a complete virtual graphics device on every operation.

Known pre-existing `Element.getClientRects` geometry flags remain outside this
canvas/GPU change. No assessment, camera or microphone session is used for these
tests. Browser probes use disposable profiles and the installed Cloakfox binary.
