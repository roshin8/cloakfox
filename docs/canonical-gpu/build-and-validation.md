# macOS arm64 canonical GPU backend build

The separately named WebGL SwANGLE and WebGPU Vulkan adapter both use the same
pinned SwiftShader CPU ICD. The ordinary native Metal/CGL paths remain available
when the authoritative default-off `cloakfox.experimental.canvas_pipeline` native pref is false. The authoritative native experiment pref is captured with the owning content global; transferred OffscreenCanvas objects retain their original backing policy. Persona config readiness cannot choose a host fallback. Page API options cannot override it. Unsupported or
failed canonical creation returns context failure/no adapter without hardware
fallback. This does not certify the upstream image/texture sources as canonical.
Existing extraction protection remains enabled.

Build from the reviewed pins, preserving full logs under the work directory:

```sh
python3 scripts/build-canonical-gpu.py --acquire --build --jobs 2
python3 scripts/build-canonical-gpu.py --stage bundle/canonical-gpu
python3 scripts/build-canonical-gpu.py --verify bundle/canonical-gpu
```

The build uses ANGLE's versioned DEPS, `--no-history --nohooks` acquisition, a fixed
depot_tools revision, and the checked-in GN arguments. The only renderer patch
applies to this separate ANGLE checkout: direct absolute adjacent-library loading
of SwiftShader, refusal of any other ICD, and no driver-selection environment or
working-directory mutation. `angle_libs_suffix` keeps its EGL/GLES dispatch names
separate from Gecko's native ANGLE. `command-line-tools.patch` adapts Chromium's
build metadata/path discovery to the installed Apple CLT package when full Xcode
is absent; it does not invent an installed Xcode version.

The final stage contains the three exact dylib names, a transitive checkout
revision inventory, source license/notice files, build arguments, local patch
hashes and SHA256 hashes for the staged files. The CLI verifier rejects missing,
modified or path-escaping artifacts and mismatched renderer identity. Before
`dlopen`/ash entry loading, Gecko independently verifies the fixed three library
files against the bundle manifest, rejects nonregular/symlink files, caps sizes,
and checks the compiled renderer version and ANGLE/SwiftShader revision constants.
No arbitrary manifest filename is loaded. These checks complement the signed app
resource seal; they do not make an unsigned, attacker-replaced application trusted.

Copy the whole stage to `GREDirectory/canonical-gpu` (on macOS the app's
`Contents/Resources/canonical-gpu`). Sign the leaf libraries before regenerating
the manifest hashes, then sign the outer application without rewriting those
libraries. Verify deep signatures and staged hashes after copying. Do not modify
the manifest after sealing the outer application. The existing runtime SHA gate
must pass in both WebGL and WebGPU.

`probe_canonical_gpu_standalone.py` exercises actual CPU Vulkan EGL initialization,
opaque authored colors, shader compilation/JIT and a raster gradient. Its success
establishes the standalone dependency only. Required installed probes must also
exercise sandboxed signed-library JIT, WebGL1/2 and WebGPU WGSL render/compute,
CPU presentation, missing/corrupt resources, policy ownership/restoration, texture
uploads, canvas/media round trips, tainting and existing readback restrictions.
The current user-requested acceptance scope is one Mac; cross-host identity is
not established.

A standalone hardened-runtime shader/JIT smoke also passed using the existing Gecko developer plugin-container entitlements; see `hardened-macos-arm64.txt`. This has not exercised the browser GPU-process seatbelt. Reproduce with `xcrun clang++ -std=c++20 -O1 -I.canonical-gpu-build/angle/include tests/fingerprint/canonical_gpu_smoke.cpp -o .canonical-gpu-build/canonical-gpu-smoke`, sign that test executable with `--options runtime` and the existing developer `plugin-container.xml` entitlements, and run it with the absolute bundle/canonical-gpu path.

Build staging is automated by `scripts/stage-canonical-gpu.py` from `copy-additions.sh`. It verifies every library and notice before replacing the owned source resource directory, verifies copied bytes again, and emits the case-insensitive sorted Gecko install list. `canvas-canonical-gpu-packaging.patch` installs the tree at GREDirectory/canonical-gpu and includes its full notice tree in the macOS package.

GPU snapshots now retain frozen version/context/128-bit owner records when an exact native owner can be derived. `CanonicalGPU` identifies a successfully created forced SwiftShader backend; the original `GPU` source flag remains present. This marker does not qualify upstream uploads or remove extraction protection. WebGPU retains the verified Vulkan CPU adapter on its device, uses readback presentation, and rejects a hardware device when the canvas requires canonical rendering. Browser sandbox, installed rendering, and transfer coverage still require the integrated browser gate.

External GPU inputs retain a conservative context/device-wide source union.
WebGL DOM, ImageBitmap, ImageData, OffscreenCanvas and VideoFrame uploads add
Unknown whenever native source identity is missing or foreign. WebGPU queue
external-image uploads preserve source records on the Device; every subsequent
canvas output compares these with its own frozen owner and adds Unknown for
missing/foreign ownership. External video textures currently contribute Unknown.
These unions survive shader transforms, texture copies and WebGL restoration;
there is no pixel-value or detector-based removal of Unknown.

The native graphics and WebGPU C++ targets plus the real Gecko Rust static
library compiled successfully on the acceptance Mac. The final WebGPU metadata
changes were compiled again. Logs are `docs/canvas-pipeline-completion/gpu-build-real.log`
and `gpu-metadata-build-final.log`. ClientWebGL/base metadata and precise-guard
follow-ups require the coordinated dom/canvas build. The installed corpus is
`tests/fingerprint/probe_canvas_canonical_gpu.py`, selected with `CLOAKFOX_BIN`
and `REPORT_DIR`. Run it once against the intact signed app, then against each
disposable missing/tampered-backend app copy with `--expect-backend-failure`.
No installed-browser GPU acceptance is asserted by the standalone or compile
results above.
