"""Compile the actual WebGPU canvas ownership gates, including no-import output."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2] / 'firefox-src'


def test_native_webgpu_canvas_device_owner_boundary():
    device = (ROOT / 'dom/webgpu/Device.cpp').read_text()
    signature = 'bool Device::HasCanvasPrivacyOwner('
    assert signature in device, 'Device needs an exact canvas/device privacy-owner predicate'
    start = device.index(signature)
    predicate = device[start:device.index('\n}\n', start) + 3]
    canvas = (ROOT / 'dom/webgpu/CanvasContext.cpp').read_text()
    start = canvas.index('  if (mCanonicalGpuRequired && !aConfig.mDevice->mCanonicalGpu)')
    gates = canvas[start:canvas.index('  mConfiguration.reset(', start)]
    start = canvas.index('gfx::CanvasPrivacyMetadata CanvasContext::GetCanvasPrivacyMetadata() const')
    metadata = canvas[start:canvas.index('already_AddRefed<gfx::SourceSurface> CanvasContext::GetSurfaceSnapshot', start)]
    privacy = (ROOT / 'gfx/2d/CanvasPrivacy.cpp').read_text()
    privacy = privacy[privacy.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):privacy.index('void AddCanvasPixelSource(')]
    harness = r'''
#include <cassert>
#include <initializer_list>
#include "CanvasPrivacy.h"
namespace mozilla::gfx {
''' + privacy + r'''
}
namespace mozilla::webgpu {
struct Device {
 bool mCanonicalGpu=true;
 gfx::CanvasPrivacyMetadata mGpuPrivacyPolicy{1,7,123,456,64};
 bool HasCanvasPrivacyOwner(const gfx::CanvasPrivacyMetadata&)const;
 uint32_t ExternalGpuSourcesFor(const gfx::CanvasPrivacyMetadata&)const{return 0;}
};
''' + predicate + r'''
struct Configuration {Device*mDevice;};
struct ErrorResult {bool failed=false;void ThrowInvalidStateError(const char*){failed=true;}};
struct CanvasContext {
 bool mCanonicalGpuRequired=true;
 gfx::CanvasPrivacyMetadata mGpuPrivacyPolicy{1,7,123,456,64};
 Configuration*mConfiguration=nullptr;
 void Configure(const Configuration&aConfig,ErrorResult&aRv){
''' + gates + r'''
 mConfiguration=const_cast<Configuration*>(&aConfig);
 }
 gfx::CanvasPrivacyMetadata GetCanvasPrivacyMetadata()const;
};
''' + metadata + r'''
}
using namespace mozilla;
using namespace mozilla::webgpu;
int main(){
 const gfx::CanvasPrivacyMetadata owner{1,7,123,456,64};
 const gfx::CanvasPrivacyMetadata cases[]={owner,{1,8,123,456,64},{1,7,999,456,64},
  {1,7,123,999,64},{0,0,0,0,64},{2,7,123,456,64},{1,7,0,0,64}};
 for(auto policy:cases)for(bool canonical:{false,true})for(bool required:{false,true}){
  Device device;device.mCanonicalGpu=canonical;Configuration config{&device};
  CanvasContext canvas;canvas.mCanonicalGpuRequired=required;canvas.mGpuPrivacyPolicy=policy;
  bool same=policy.version==1&&policy.userContextId==7&&policy.ownerHi==123&&policy.ownerLo==456;
  assert(device.HasCanvasPrivacyOwner(policy)==same);
  ErrorResult rv;canvas.Configure(config,rv);
  assert(rv.failed==(required&&(!canonical||!same)));
  assert((canvas.mConfiguration==nullptr)==rv.failed);
  // Defense in depth: even a stale or bypassed configuration cannot certify
  // recipient-device pixels with the transferred canvas's sender identity.
  canvas.mConfiguration=&config;
  auto result=canvas.GetCanvasPrivacyMetadata();
  assert(gfx::CanExtractCanonicalCanvasPixels(result)==(canonical&&same));
 }
 Device missing;missing.mGpuPrivacyPolicy={};assert(!missing.HasCanvasPrivacyOwner(owner));
 missing.mGpuPrivacyPolicy={1,7,0,0,64};assert(!missing.HasCanvasPrivacyOwner({1,7,0,0,64}));
}
'''
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'owner.cpp'
        source.write_text(harness)
        binary = Path(directory) / 'owner'
        subprocess.run(['c++', '-std=c++17', '-I', str(ROOT / 'gfx/2d'), str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
