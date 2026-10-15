# Canvas and GPU consistency repairs

The installed 158 build passes the previous library stability checks, but upstream
CreepJS identifies deliberate pixel perturbation, invalid empty text metrics, and
GPU parameter combinations absent from its historical reference set. Chromium
versus Gecko identification is deferred by the user.

## Scope

1. Make canvas noise address pixels by their original coordinates, so cropping
   does not change the value returned for the same pixel.
2. Apply canvas extraction noise in straight RGBA for both pixel reads and image
   serialization. Preserve alpha, exact clears, and coverage of nonzero RGB under
   zero alpha. Keep owning site/container seeds.
3. Preserve zero and sign invariants of text geometry instead of adding offsets
   to empty ink bounds. Retain deterministic nonzero geometry protection.
4. Repair proven WebGL vector/component contradictions and extension advertising
   that claims unsupported implementations. Preserve native validation and mutable
   state. Document any larger capability emulation work that remains.
5. Follow up the reproduced maximum-texture allocation failure by intersecting
   advertised fixed upper-bound capacities with real backend ceilings. Preserve
   native enum validation and treat alignment/lower bounds separately. This can
   expose backend ceilings already observable through allocations; it does not
   emulate a different physical GPU.

## Verification

- Reproduce defects against the installed binary before changing that binary.
- Run regression probes against the repaired development build, including native
  mode and reload/site/container isolation.
- Run JavaScript/Python regression suites, native build, and strict patch replay.
- Review implementation before packaging and installing the repaired app.
- Rerun regression probes and pinned, unmodified CreepJS and FingerprintJS against
  `/Applications/Cloakfox.app`, recording remaining upstream flags verbatim.

## Limits

CreepJS directly compares authored pixel colors with extracted colors, so deliberate
pixel noise remains detectable. Its GPU/canvas reference tables are finite historical
datasets, not standards conformance tests. This work will not copy those tables,
alter library fixtures, special-case their inputs, or remove site/container privacy
to obtain a clean detector score. Complete GPU capacity emulation and render-time
privacy are separate architecture changes if extraction repairs prove insufficient.
