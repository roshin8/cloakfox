# Rendering privacy modes review

Independent review covered new canvas native code/settings policy and GPU
context/host/serialization code. Base is `a35115c727`; the earlier uncommitted
canvas/GPU consistency repair is retained underneath these two new ordered patches.

Findings resolved before installation:

- Capture canvas policy on context creation, including unused contexts that draw
  only after a toggle and bitmap reset; lazy target allocation was insufficient.
- Enforce advertised point and line raster ranges in shader/driver paths, while
  preserving the application's requested GL line-width state.
- Initialize explicit IPC layout padding and include the internal profile option
  in serialized tied fields; preserve host/client structure size assertions.
- Preserve valid legacy precision masks when the mode is off; clipping to native
  precision would add a backend-dependent ceiling signal. Invalid precision tuples
  fall through existing block policy, and native enum validation runs first.
- Read fixed GPU configuration from the exact owning container on workers as well
  as windows. Guard both overlay and base fallback behind the master switch.
- Use one shared-capacity baseline for WebGL1/2 instead of different minima for
  what represents the same device. Native whole-profile support remains required.

Fixture corrections are recorded in run logs: JavaScript worker syntax, Gecko's
INVALID_VALUE for an excessive active texture unit, bounded navigation readiness,
and six-element canvas transform comparisons. No upstream detector was edited.

Final source reviews found no further actionable issues. Review is evidence of
inspection, not a guarantee against all information leaks or compatibility bugs.
Runtime acceptance additionally checks strict integer/PBO readback, explicit
compatibility opt-out, real resource allocation/compiler limits, container/site
ownership, workers, context restoration, settings persistence and native controls.
