"""Native WebGPU selection contracts; actual WGSL pixels need installed probes."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2] / 'firefox-src'

def test_macos_compiles_cpu_vulkan_support():
    text=(ROOT/'gfx/wgpu_bindings/Cargo.toml').read_text()
    assert 'features = ["metal", "vulkan-portability"]' in text

def test_canonical_webgpu_loads_explicit_entry_without_environment():
    text=(ROOT/'gfx/wgpu_bindings/src/server.rs').read_text()
    assert 'create_canonical_gpu_instance' in text
    start=text.index('fn create_canonical_gpu_instance')
    end=text.index('\n#[no_mangle]',start)
    block=text[start:end]
    assert 'ash::Entry::load_from' in block
    assert 'init_with_entry' in block
    assert 'std::env::set_var' not in block
    assert 'DeviceType::Cpu' in text and '0x1AE0' in text and '0xC0DE' in text

def test_canonical_request_has_exclusive_instance_and_polls_devices():
    text=(ROOT/'gfx/wgpu_bindings/src/server.rs').read_text()
    start=text.index('Message::RequestAdapter {')
    end=text.index('// Prefer to use the dx12 backend',start)
    block=text[start:end]
    assert 'cloakfox_canonical_gpu' in block
    assert 'result = Some(false)' in block
    assert 'canonical_gpu_instance' in text[text.index('fn wgpu_server_poll_all_devices'):text.index('fn wgpu_server_poll_all_devices')+750]

def test_frozen_owning_policy_never_comes_from_webidl_options():
    text=(ROOT/'dom/webgpu/Instance.cpp').read_text()
    assert 'cloakfox_experimental_canvas_pipeline()' in text
    assert 'mCanonicalGpu' in text
    assert 'mForceFallbackAdapter, mCanonicalGpu' in text
    assert 'cloakfox_canonical_gpu: bool' in (ROOT/'gfx/wgpu_bindings/src/client.rs').read_text()


def test_webgpu_output_requires_verified_adapter_and_owner_record():
    source = (ROOT / 'dom/webgpu/CanvasContext.cpp').read_text()
    assert 'mCanonicalGpuRequired && !aConfig.mDevice->mCanonicalGpu' in source
    assert 'gfx::SetCanvasPrivacyMetadata(snapshot, GetCanvasPrivacyMetadata())' in source
    assert 'gfx::CanvasPixelSource::CanonicalGPU' in source
    assert 'CloakfoxSiteSeed::OwnerKey' in source
    adapter = (ROOT / 'dom/webgpu/Adapter.cpp').read_text()
    assert 'mParent->IsCanonicalGpu()' in adapter
    assert 'WGPUDeviceType_Cpu' in adapter


def test_external_webgpu_uploads_track_device_wide_sources():
    queue=(ROOT/'dom/webgpu/Queue.cpp').read_text()
    device=(ROOT/'dom/webgpu/Device.cpp').read_text()
    canvas=(ROOT/'dom/webgpu/CanvasContext.cpp').read_text()
    assert 'mParent->AcceptExternalGpuInput' in queue
    assert 'gfx::MergeCanvasPrivacyMetadata(mExternalGpuSources' in device
    assert 'mExternalGpuSources.ownerHi != aOwner.ownerHi' in device
    assert 'ExternalGpuSourcesFor(mGpuPrivacyPolicy)' in canvas


def test_webgpu_device_rejects_incomplete_source_before_union():
    source=(ROOT/'dom/webgpu/Device.cpp').read_text()
    start=source.index('void Device::RecordExternalGpuSource')
    block=source[start:source.index('uint32_t Device::ExternalGpuSourcesFor',start)]
    assert 'gfx::CanImportCanonicalCanvasPixels(aSource)' in block
    assert block.index('gfx::CanImportCanonicalCanvasPixels') < block.index('gfx::MergeCanvasPrivacyMetadata')


def test_map_read_guard_rejects_asynchronously_before_driver_request():
    source=(ROOT/'dom/webgpu/Buffer.cpp').read_text()
    start=source.index('already_AddRefed<dom::Promise> Buffer::MapAsync(')
    block=source[start:source.index('static void ExternalBufferFreeCallback',start)]
    guard=block.index('mParent->ShouldBlockMapRead(aMode)')
    assert guard < block.index('ffi::wgpu_client_buffer_map(')
    assert 'MaybeRejectWithOperationError' in block[guard:]
    device=(ROOT/'dom/webgpu/Device.h').read_text()
    assert 'const gfx::CanvasPrivacyMetadata mGpuPrivacyPolicy' in device


def test_canonical_ingress_is_checked_before_external_upload_or_cache_reuse():
    queue=(ROOT/'dom/webgpu/Queue.cpp').read_text()
    start=queue.index('void Queue::CopyExternalImageToTexture(')
    block=queue[start:]
    assert block.index('AcceptExternalGpuInput')<block.index('dataSurface->GetSize()')
    external=(ROOT/'dom/webgpu/ExternalTexture.cpp').read_text()
    assert 'PrepareCanonicalExternalTextureInput(aDevice, image' in external
    start=external.index('ExternalTextureCache::GetOrCreateSource(')
    block=external[start:external.index('void ExternalTextureCache::RemoveSource',start)]
    assert block.index('PrepareCanonicalExternalTextureInput')<block.index('return source;')
    start=external.index('\nExternalTextureSourceClient::Create(')
    block=external[start:external.index('ExternalTextureSourceClient::GetOrCreateExternalTexture(',start)]
    assert block.index('PrepareCanonicalExternalTextureInput')<block.index('BuildSurfaceDescriptorGPUVideoOrBuffer')<block.index('SendCreateExternalTextureSource')
    assert 'uploadImage->BuildSurfaceDescriptorGPUVideoOrBuffer' in block
