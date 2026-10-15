# Canonical GPU dependency review — 2026-10-15

Status: pinned SwANGLE built, staged, and standalone shader/JIT tested. Native WebGL integration compiles; WebGPU source integration awaits the main Rust/browser build and installed acceptance. **This is not a complete-pipeline certification**.
Acceptance scope requested by user: macOS arm64 on the current Mac. No cross-host
pixel identity claim follows from this scope.

The candidate is SwANGLE: ANGLE OpenGL ES/EGL over SwiftShader CPU Vulkan. Apple's
Metal renderer, CGL software rendering, a generic GPU name and capability limiting
are not canonical producers. Existing extraction protections remain required.

## Pin and upstream evidence

* Gecko's `gfx/angle/moz.yaml` pins ANGLE
  `464fd3e879d6bb72fe8210b3e58b59836f711951` (BSD-3-Clause).
* That exact [ANGLE DEPS](https://chromium.googlesource.com/angle/angle/+/464fd3e879d6bb72fe8210b3e58b59836f711951/DEPS)
  pins SwiftShader `a7c547b55474c3d8bde53711eae24ae0e28bbc0a`
  (Apache-2.0), Vulkan headers `d314eae73fdc90847bb8304a86ee7c6a8ee023b6`,
  Vulkan loader `59a70594de4559fd3aed73fe8ac2d6c48ca002d4`, and
  VulkanMemoryAllocator `7e55b011e16182fc349149abbd3aaf3b1db46421`.
* [ANGLE's pinned GN configuration](https://chromium.googlesource.com/angle/angle/+/464fd3e879d6bb72fe8210b3e58b59836f711951/gni/angle.gni)
  enables Vulkan on macOS and supports `angle_enable_swiftshader`.
* [SwiftShader's pinned CMake configuration](https://swiftshader.googlesource.com/SwiftShader/+/a7c547b55474c3d8bde53711eae24ae0e28bbc0a/CMakeLists.txt)
  recognizes `CMAKE_OSX_ARCHITECTURES=arm64` as aarch64; default Reactor backend
  is LLVM. This establishes a supported source configuration, not tested browser
  integration or deterministic output across CPU architectures.
* [SwiftShader license](https://swiftshader.googlesource.com/SwiftShader/+/a7c547b55474c3d8bde53711eae24ae0e28bbc0a/LICENSE.txt)
  is Apache-2.0. Release packaging must include transitive notices, including
  SwiftShader's embedded LLVM, SPIR-V and Vulkan dependencies, not just this file.

## Gecko integration constraints

Mozilla's ANGLE vendoring prunes unused files and generates
`libANGLE_no_vulkan_gn`; its `gfx/angle/gn-configs/angle.json` explicitly disables
Vulkan. Merely installing SwiftShader cannot add a missing ANGLE backend.

Use separately built, separately packaged SwANGLE dylibs and an isolated
`GLLibraryEGL` instance for immutable canonical contexts. Load them from the app
bundle by absolute path, with explicit Vulkan/SwiftShader display attributes.
The default native Metal/EGL singleton must retain its current libraries.
A canonical library/display/context creation failure must not try native GL.
Never set a process-global Vulkan driver environment variable to select policy.

Gecko's GPU sandbox permits executable mappings under its app path.
`security/mac/hardenedruntime/{developer,production}/plugin-container.xml` already
contains Apple's `com.apple.security.cs.allow-jit` entitlement for MAP_JIT.
SwiftShader's actual Reactor memory-protection/thread behavior still requires a
signed, sandboxed installed-browser test; the entitlement alone proves nothing.
No sandbox weakening is authorized or necessary to assume in advance.

WebGL presentation must also avoid automatically choosing `SurfaceFactory_IOSurface`
for a CPU Vulkan context. Its backing, snapshot and upload routes require CPU
surfaces or explicitly supported interop. WebGPU now has independent, explicit-entry SwiftShader Vulkan adapter routing in the native/Rust patch. Its actual adapter/compute/presentation path still requires compiled installed-browser verification. SwANGLE success alone cannot certify wgpu output.

## Current acquisition

`.canonical-gpu-build/angle` is a disposable, untracked exact-pin checkout.
Dependencies are acquired with gclient `--nohooks --no-history --jobs=4`; only renderer
and necessary build dependencies are retained. Standalone build parallelism is two.
Do not package or qualify its pixels until standalone tests, Gecko integration,
resource notices and signed sandbox tests pass.

Actual GN build uses SwiftShader's LLVM 10 Reactor (shown in raw renderer output), not the CMake default. The installed CLT27 SDK is newer than the pinned lld TAPI reader, so the checked-in GN arguments use Apple's linker (`use_lld=false`). ANGLE's VulkanMac WSI translation units require IOSurface/QuartzCore framework linkage even with its separate Metal renderer disabled; these frameworks do not select a hardware Vulkan device.

WebGPU Vulkan portability also requires vendored `renderdoc-sys` 1.1.0 (MIT OR Apache-2.0), without transitive dependencies. The official crates.io archive SHA-256 is `19b30a45b0cd0bcca8037f3d0dc3421eaf95327a17cad11964fb8179b4fc4832`; both licenses and Cargo file checksums are retained. This provides API bindings, not an additional bundled renderer or runtime downloader.
