# Expanded canonical CPU backend

The two `reference-capacity-*.patch` files apply to the existing pinned ANGLE
464fd3e879d6bb72fe8210b3e58b59836f711951 and SwiftShader
a7c547b55474c3d8bde53711eae24ae0e28bbc0a sources. They extend executable CPU
capacity; reference identity, per-container admission and privacy policy remain
Gecko's responsibility. No physical GPU equivalence is claimed.

## Implementation

- Framebuffer outlines are 16384 rows. Their signed 16-bit raster spans remain
  within range. Viewports can be 32767 pixels while raster writes remain clipped
  to the actual framebuffer/scissor. Existing 15 mip levels cover 16384 textures.
- Real per-sample raster/depth/stencil arrays hold eight samples. The setup-state
  bitfield can represent eight. Count-indexed Vulkan standard location tables
  also supply centroid interpolation, explicit sample interpolation and builtins.
  Alpha coverage extends to eight samples. The specialized four-sample resolve
  remains unchanged; two/eight samples use the existing generic resolver that
  averages every sample.
- Interface storage has 132 components, leaving 32 vectors after ANGLE's
  gl_Position reservation. Point polygon setup clamps at 2047 rather than 1023.
- ANGLE's actual uniform binding arrays, combined-block arrays and block dirty
  masks accommodate 96 entries. The existing 192-entry texture arrays allow 96
  units in ES3.1 too. SwiftShader's dynamic descriptor storage supplies 16 stage
  UBOs plus ANGLE's default uniform block.
- ANGLE suppresses relaxed precision decorations in shader translation, and all
  qualifiers report IEEE float32 / signed int32. Dynamic arithmetic tests verify
  both shader stages rather than trusting precision getters.

The existing CPU memory allocation limits still apply. An advertised maximum
image dimension does not guarantee that every combination of dimensions,
formats and sample counts fits available memory.

## Reproduction

Use an owned source tree and output under this159 worktree's `.tools159`.
`build-isolated-reference.py` builds only that tree, with two low-priority jobs,
an own-process-group disk guard and a 2GiB reserve. It preserves partial objects
and logs. On APFS, `cp -cR` can clone an already acquired pinned backend without
modifying the original source or output. The normal `build-canonical-gpu.py`
applies both capacity patches and runs the execution corpus before staging.

```sh
python3 scripts/canonical-gpu/build-isolated-reference.py .tools159/canonical-reference/angle
python3 scripts/build-canonical-gpu.py --work-dir "$PWD/.tools159/canonical-reference" --stage "$PWD/.tools159/canonical-reference/staged-v2"
```

Staging refuses an existing destination. The application bundle must retain its
integrity checks and validate the new patch provenance before deployment.

## Native execution evidence, 2026-10-28

`tests/fingerprint/canonical_gpu_reference.cpp` passed on the expanded CPU backend:

- Horizontal and vertical 16384-pixel render targets, edge readback and rejection
  of a 16385 texture; 32767 viewports clipped to those targets.
- 1024 and 2047-pixel points, all 32 live vec4 varyings, texture unit79 and UBO
  binding79.
- All 12 precision descriptors and dynamic float-mantissa / integer arithmetic
  in lowp and mediump vertex and fragment shaders.
- All 16 S3TC, sRGB S3TC, RGTC and BPTC formats uploaded, decoded and sampled.
- Four independently shaded OVR_multiview2 array layers.
- Every individual sample in 2/4/8-sample color/depth/stencil render targets,
  resolve, alpha coverage, and diagonal-edge coverage against standard positions.

The previous standalone clear and shader corpus also passed with unchanged
SHA256 hashes `e40796989b6e6e6c3b665ad7b86a5218537370b0dd8bd742b74884398a394fe4`
and `d506d4da6f2936bdb873022b106a7cf80d9645794cb331266dd90e091d391ef2`.
Seven packaging/manifest/stage unit tests passed. The linker retained the
pre-existing warning about a missing optional libLTO.dylib argument.

These are backend execution results. Firefox159 admission, per-container policy,
installed sandbox execution and browser probes are separate integration gates.
