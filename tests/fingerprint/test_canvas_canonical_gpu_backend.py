"""Fail-closed native routing contract; renderer pixels need installed probes too."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'firefox-src'


def source(path):
    return (SRC / path).read_text()


def test_canonical_library_has_separate_lifetime_and_absolute_bundle_loading():
    text = source('gfx/gl/GLLibraryEGL.cpp')
    assert 'GLLibraryEGL::GetCanonical' in text
    assert 'sCanonicalInstance' in text
    assert 'libEGL_cloakfox_canonical.dylib' in text
    assert 'libGLESv2_cloakfox_canonical.dylib' in text
    assert 'gfx::gfxVars::GREDirectory()' in text
    assert 'PR_LD_LOCAL' in text


def test_canonical_egl_display_explicitly_requires_swiftshader():
    text = source('gfx/gl/GLLibraryEGL.cpp')
    start = text.index('if (mCanonicalGpu) {', text.index('GLLibraryEGL::CreateDisplayLocked'))
    end = text.index('if (IsExtensionSupported(EGLLibExtension::ANGLE_platform_angle_d3d))', start)
    block = text[start:end]
    assert '0x3450' in block  # EGL_PLATFORM_ANGLE_TYPE_VULKAN_ANGLE
    assert '0x3487' in block  # EGL_PLATFORM_ANGLE_DEVICE_TYPE_SWIFTSHADER_ANGLE
    assert 'return ret;' in block  # No native/WARP/default-display fallback.


def test_requested_canonical_context_does_not_enter_native_driver_dispatch():
    text = source('dom/canvas/WebGLContext.cpp')
    start = text.index('const auto newGL =')
    end = text.index('if (tryNativeGL)', start)
    branch = text[start:end]
    assert 'mOptions.cloakfoxCanonicalGpu' in branch
    assert 'GLContextProviderEGL::CreateHeadless' in branch
    assert 'return' in branch
    provider = source('gfx/gl/GLContextProviderEGL.cpp')
    assert 'GLLibraryEGL::GetCanonical' in provider
    assert 'RendererString().Find("SwiftShader")' in provider
    assert 'RendererString().Find("Vulkan")' in provider


def test_canonical_gpu_flag_is_frozen_and_serialized():
    text = source('dom/canvas/ClientWebGLContext.cpp')
    assert 'mCloakfoxCanonicalGpu.isNothing()' in text
    assert 'cloakfox_experimental_canvas_pipeline()' in text
    assert 'options.cloakfoxCanonicalGpu = *mCloakfoxCanonicalGpu' in text
    assert 'cloakfoxCanonicalGpu,' in source('dom/canvas/WebGLTypes.h')


def test_runtime_integrity_gate_precedes_both_gpu_library_loads():
    text = source('gfx/gl/GLLibraryEGL.cpp')
    assert 'GLLibraryEGL::VerifyCanonicalLibraries' in text
    start = text.index('GLLibraryEGL::GetCanonical')
    end = text.index('/* static */ void GLLibraryEGL::Shutdown', start)
    block = text[start:end]
    assert block.index('VerifyCanonicalLibraries') < block.index('candidate->mGLLibrary = load')
    assert 'CC_SHA256_Update' in text
    assert 'O_NOFOLLOW' in text and 'S_ISREG' in text
    assert '464fd3e879d6bb72fe8210b3e58b59836f711951' in text
    assert 'a7c547b55474c3d8bde53711eae24ae0e28bbc0a' in text
    rust = source('gfx/wgpu_bindings/src/server.rs')
    start = rust.index('fn create_canonical_gpu_instance')
    end = rust.index('\n#[no_mangle]', start)
    assert rust[start:end].index('wgpu_parent_verify_canonical_libraries') < rust[start:end].index('ash::Entry::load_from')


def test_authoritative_pref_and_transferred_offscreen_policy_win_over_stale_config():
    text = source('dom/canvas/ClientWebGLContext.cpp')
    start = text.index('if (mCloakfoxCanonicalGpu.isNothing())')
    end = text.index('options.cloakfoxCanonicalGpu =', start)
    block = text[start:end]
    assert 'cloakfox_experimental_canvas_pipeline()' in block
    assert 'mOffscreenCanvas->CanonicalCanvasBackingPolicy()' in block
    assert 'ExactConfig' not in block
    webgpu = source('dom/webgpu/Instance.cpp')
    assert 'cloakfox_experimental_canvas_pipeline()' in webgpu


def test_canonical_cpu_honors_major_performance_caveat_rejection():
    text = source('dom/canvas/WebGLContext.cpp')
    start = text.index('const auto newGL =')
    end = text.index('if (tryNativeGL)', start)
    branch = text[start:end]
    assert 'mOptions.failIfMajorPerformanceCaveat' in branch
    assert 'FEATURE_FAILURE_CANONICAL_GPU_PERFORMANCE_CAVEAT' in branch


def test_webgl_snapshots_carry_frozen_owner_and_actual_backend_marker():
    source = (ROOT / 'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text()
    assert 'mCloakfoxGpuPrivacyPolicy = mOffscreenCanvas->CanvasPrivacyPolicy()' in source
    assert 'CloakfoxSiteSeed::OwnerKey' in source
    assert 'gfx::SetCanvasPrivacyMetadata(surf, GetCanvasPrivacyMetadata())' in source
    assert 'gfx::CanvasPixelSource::CanonicalGPU' in source
    assert 'gpuPrivacyPolicy' in source


def test_external_snapshot_uses_owner_and_canonical_webgl_forces_cpu_snapshot():
    source = (ROOT / 'firefox-src/dom/canvas/nsICanvasRenderingContextInternal.cpp').read_text()
    assert 'gfx::SetCanvasPrivacyMetadata(surf, GetCanvasPrivacyMetadata())' in source
    source = (ROOT / 'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text()
    start = source.index('mozilla::ipc::IProtocol* ClientWebGLContext::SupportsSnapshotExternalCanvas()')
    block = source[start:source.index('RefPtr<gfx::SourceSurface>', start)]
    assert 'cloakfoxCanonicalGpu' in block and 'return nullptr' in block


def test_frozen_canonical_context_cannot_opt_out_of_precise_guard():
    source = (ROOT / 'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text()
    start = source.index('static bool CloakfoxBlockPixelReadback')
    block = source[start:source.index('\nvoid ClientWebGLContext::ReadPixels', start)]
    assert 'bool canonicalGpu' in block
    assert 'if (!canonicalGpu &&' in block
    assert source.count('mCloakfoxCanonicalGpu.valueOr(false)') >= 2


def test_external_webgl_uploads_monotonically_poison_unknown_or_foreign_sources():
    source=(ROOT / 'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text()
    assert 'mCloakfoxGpuImportedSources |=' in source
    assert 'imported.ownerHi != mCloakfoxGpuPrivacyPolicy.ownerHi' in source
    assert 'metadata.sources |= mCloakfoxGpuImportedSources' in source


def test_same_owner_incomplete_producer_cannot_borrow_gpu_marker():
    source=(ROOT/'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text()
    start=source.index('if (src.mImageBitmap ||')
    block=source[start:source.index('const auto& rawUnpacking',start)]
    assert 'gfx::CanImportCanonicalCanvasPixels(imported)' in block
    assert '!verifiedOwnerless' in block
