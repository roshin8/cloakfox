"""Execute production GPU import boundaries against real metadata predicates."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2] / 'firefox-src'


def test_actual_gpu_import_boundaries_accept_only_verified_inputs():
    metadata=(ROOT/'gfx/2d/CanvasPrivacy.cpp').read_text()
    metadata=metadata[metadata.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):metadata.index('void AddCanvasPixelSource(')]
    webgl=(ROOT/'dom/canvas/ClientWebGLContext.cpp').read_text()
    start=webgl.index('if (src.mImageBitmap ||')
    webgl=webgl[start:webgl.index('const auto& rawUnpacking',start)]
    device=(ROOT/'dom/webgpu/Device.cpp').read_text()
    device=device[device.index('bool Device::AcceptExternalGpuInput'):device.index('Device::~Device()')]
    harness=r'''
#include <cassert>
#include <initializer_list>
#include "CanvasPrivacy.h"
namespace mozilla::gfx {
'''+metadata+r'''
class SourceSurface {public:CanvasPrivacyMetadata metadata;};
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface*s){return s?s->metadata:CanvasPrivacyMetadata{};}
}
using namespace mozilla;
bool dispatched;
uint32_t ImportWebGL(gfx::CanvasPrivacyMetadata owner,gfx::CanvasPrivacyMetadata input,bool canonical=true){
 auto mCloakfoxGpuPrivacyPolicy=owner;uint32_t mCloakfoxGpuImportedSources=0;
 struct {bool mImageBitmap=true,mImageData=false,mOffscreenCanvas=false,mVideoFrame=false,mDomElem=false;}src;
 gfx::SourceSurface surface{input};struct Desc {gfx::SourceSurface*sourceSurf;};Desc descriptor{&surface};auto*desc=&descriptor;
 struct {struct {struct {bool cloakfoxCanonicalGpu;} options;} info;} state;state.info.options.cloakfoxCanonicalGpu=canonical;auto*notLost=&state;
 constexpr int LOCAL_GL_INVALID_OPERATION=1282;auto EnqueueError=[](int,const char*){};
 dispatched=false;[&](){
'''+webgl+r'''
 dispatched=true;}();
 return mCloakfoxGpuImportedSources;
}
namespace mozilla::dom {struct GPUMapMode_Binding {static constexpr uint32_t READ=1;};}
namespace mozilla::webgpu {
class Device {public:
 bool mCanonicalGpu=true;
 gfx::CanvasPrivacyMetadata mGpuPrivacyPolicy{1,7,123,456,64|512};
 bool AcceptExternalGpuInput(gfx::CanvasPrivacyMetadata);
 bool ShouldBlockMapRead(uint32_t)const;
 bool mHasExternalGpuSources=false;
 uint32_t mOwnerlessGpuSources=0;
 gfx::CanvasPrivacyMetadata mExternalGpuSources;
 void RecordExternalGpuSource(gfx::CanvasPrivacyMetadata);
 uint32_t ExternalGpuSourcesFor(const gfx::CanvasPrivacyMetadata&)const;
};
'''+device+r'''
}
using namespace mozilla::gfx;
using mozilla::webgpu::Device;
int main(){
 const CanvasPrivacyMetadata owner{1,7,123,456,64|512};
 const CanvasPrivacyMetadata raster{0,0,0,0,16|1024};
 const CanvasPrivacyMetadata media{0,0,0,0,32|128|256};
 const CanvasPrivacyMetadata valid[]={raster,{0,0,0,0,16|1024|256},media,owner};
 for(auto input:valid){
   assert(!(ImportWebGL(owner,input)&1));assert(dispatched);
   Device device;assert(device.AcceptExternalGpuInput(input));
   assert(!(device.ExternalGpuSourcesFor(owner)&1));
   assert(!device.ShouldBlockMapRead(1));
 }
 const CanvasPrivacyMetadata invalid[]={
  {0,0,0,0,16},{0,0,0,0,1024},{0,0,0,0,32|128},{0,0,0,0,32|256},
  {0,0,0,0,32|128|256|1},{0,0,1,0,16|1024},{2,0,0,0,16|1024},
  {0,1,0,0,16|1024},{0,0,0,0,16|1024|8},{1,7,123,999,64|512},
  {1,7,123,456,64}};
 for(auto input:invalid){
   assert(ImportWebGL(owner,input)&1);assert(!dispatched);
   ImportWebGL(owner,input,false);assert(dispatched);
   Device device;assert(!device.AcceptExternalGpuInput(input));device.RecordExternalGpuSource(raster);device.RecordExternalGpuSource(media);device.RecordExternalGpuSource(owner);
   assert(device.ExternalGpuSourcesFor(owner)&1);
   assert(device.ShouldBlockMapRead(1));
   assert(!device.ShouldBlockMapRead(2));
   device.mCanonicalGpu=false;assert(device.AcceptExternalGpuInput(input));assert(!device.ShouldBlockMapRead(1));
 }
 Device mixed;for(auto input:{raster,media,owner,raster})mixed.RecordExternalGpuSource(input);
 assert(!(mixed.ExternalGpuSourcesFor(owner)&1));
 assert((mixed.ExternalGpuSourcesFor(owner)&(16|1024|32|128|256|64|512))==(16|1024|32|128|256|64|512));
 assert(mixed.ExternalGpuSourcesFor({1,7,123,999,64|512})&1);
 Device empty;assert(!empty.ShouldBlockMapRead(1));
 Device free;free.RecordExternalGpuSource(raster);free.RecordExternalGpuSource(media);
 assert(!(free.ExternalGpuSourcesFor(owner)&1));
}
'''
    with tempfile.TemporaryDirectory() as directory:
        source=Path(directory)/'gpu-import.cpp';source.write_text(harness)
        executable=Path(directory)/'gpu-import'
        subprocess.run(['c++','-std=c++17','-I',str(ROOT/'gfx/2d'),str(source),'-o',str(executable)],check=True)
        subprocess.run([str(executable)],check=True)


def test_native_gpu_context_cannot_inherit_canonical_backend_proof():
    metadata=(ROOT/'gfx/2d/CanvasPrivacy.cpp').read_text()
    metadata=metadata[metadata.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):metadata.index('void AddCanvasPixelSource(')]
    webgl=(ROOT/'dom/canvas/ClientWebGLContext.cpp').read_text()
    start=webgl.index('gfx::CanvasPrivacyMetadata ClientWebGLContext::GetCanvasPrivacyMetadata() const')
    webgl=webgl[start:webgl.index('RefPtr<gfx::SourceSurface> ClientWebGLContext::GetFrontBufferSnapshot',start)]
    webgpu=(ROOT/'dom/webgpu/CanvasContext.cpp').read_text()
    start=webgpu.index('gfx::CanvasPrivacyMetadata CanvasContext::GetCanvasPrivacyMetadata() const')
    webgpu=webgpu[start:webgpu.index('already_AddRefed<gfx::SourceSurface> CanvasContext::GetSurfaceSnapshot',start)]
    harness=r'''
#include <cassert>
#include "CanvasPrivacy.h"
namespace mozilla::gfx {
'''+metadata+r'''
}
namespace mozilla {
struct Options{bool cloakfoxCanonicalGpu=false;};
struct Info{Options options;};struct NotLost{Info info;};
class ClientWebGLContext {public:
 gfx::CanvasPrivacyMetadata mCloakfoxGpuPrivacyPolicy{1,7,123,456,64};
 uint32_t mCloakfoxGpuImportedSources=0;
 NotLost*mNotLost=nullptr;
 gfx::CanvasPrivacyMetadata GetCanvasPrivacyMetadata()const;
};
'''+webgl+r'''
namespace webgpu {
struct Device {bool mCanonicalGpu=false;uint32_t sources=0;
 uint32_t ExternalGpuSourcesFor(const gfx::CanvasPrivacyMetadata&)const{return sources;}
};struct Configuration{Device*mDevice;};
class CanvasContext {public:
 gfx::CanvasPrivacyMetadata mGpuPrivacyPolicy{1,7,123,456,64};
 Configuration*mConfiguration=nullptr;
 gfx::CanvasPrivacyMetadata GetCanvasPrivacyMetadata()const;
};
'''+webgpu+r'''
}
}
using namespace mozilla;
int main(){
 for(uint32_t imported:{uint32_t(0),uint32_t(64|512),uint32_t(2|64|512)}){
  NotLost native,canonical;canonical.info.options.cloakfoxCanonicalGpu=true;
  ClientWebGLContext context;context.mNotLost=&native;context.mCloakfoxGpuImportedSources=imported;
  auto record=context.GetCanvasPrivacyMetadata();
  assert((record.sources&1) && !gfx::CanExtractCanonicalCanvasPixels(record));
  context.mNotLost=&canonical;record=context.GetCanvasPrivacyMetadata();
  assert(!(record.sources&1) && gfx::CanExtractCanonicalCanvasPixels(record));
  context.mCloakfoxGpuImportedSources|=1;
  assert(!gfx::CanExtractCanonicalCanvasPixels(context.GetCanvasPrivacyMetadata()));
  context.mNotLost=nullptr;assert(context.GetCanvasPrivacyMetadata().sources&1);
  webgpu::Device device;device.sources=imported;webgpu::Configuration configuration{&device};
  webgpu::CanvasContext canvas;canvas.mConfiguration=&configuration;
  record=canvas.GetCanvasPrivacyMetadata();assert((record.sources&1) && !gfx::CanExtractCanonicalCanvasPixels(record));
  device.mCanonicalGpu=true;record=canvas.GetCanvasPrivacyMetadata();assert(!(record.sources&1) && gfx::CanExtractCanonicalCanvasPixels(record));
  device.sources|=1;assert(!gfx::CanExtractCanonicalCanvasPixels(canvas.GetCanvasPrivacyMetadata()));
  canvas.mConfiguration=nullptr;assert(canvas.GetCanvasPrivacyMetadata().sources&1);
 }
}
'''
    harness=harness.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
    with tempfile.TemporaryDirectory() as directory:
        source=Path(directory)/'gpu-proof.cpp';source.write_text(harness)
        executable=Path(directory)/'gpu-proof'
        subprocess.run(['c++','-std=c++17','-I',str(ROOT/'gfx/2d'),str(source),'-o',str(executable)],check=True)
        subprocess.run([str(executable)],check=True)


def test_poisoned_canonical_webgpu_direct_encoders_refuse_raw_pixels():
    metadata=(ROOT/'gfx/2d/CanvasPrivacy.cpp').read_text()
    metadata=metadata[metadata.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):metadata.index('void AddCanvasPixelSource(')]
    source=(ROOT/'dom/webgpu/CanvasContext.cpp').read_text()
    sections=[]
    for signature in ['mozilla::UniquePtr<uint8_t[]> CanvasContext::GetImageBuffer(', 'NS_IMETHODIMP CanvasContext::GetInputStream(']:
        start=source.index(signature)
        body=source[source.index('{',start)+1:source.index('  gfxAlphaType any;',start)]
        guard=body[body.find('  if ('):]
        assert 'CanExtractCanonicalCanvasPixels(GetCanvasPrivacyMetadata())' in guard
        sections.append(guard)
    harness=r'''
#include <cassert>
#include <cstddef>
#include "CanvasPrivacy.h"
namespace mozilla::gfx {
'''+metadata+r'''
}
using namespace mozilla;
constexpr int NS_ERROR_NOT_AVAILABLE=1;
struct Device{bool mCanonicalGpu=false;};struct Configuration{Device*mDevice;};
struct CanvasContext{
 bool mCanonicalGpuRequired=false;Configuration*mConfiguration=nullptr;
 gfx::CanvasPrivacyMetadata metadata{1,7,123,456,64|512};
 gfx::CanvasPrivacyMetadata GetCanvasPrivacyMetadata()const{return metadata;}
 void*ImageBuffer(){
'''+sections[0]+r'''
 return this;
 }
 int InputStream(){
'''+sections[1]+r'''
 return 0;
 }
};
int main(){
 Device device;Configuration configuration{&device};CanvasContext c;c.mConfiguration=&configuration;
 for(unsigned sources:{unsigned(64|512),unsigned(64|512|1),unsigned(64)}){
  c.metadata.sources=sources;
  for(bool required:{false,true})for(bool actual:{false,true}){
   c.mCanonicalGpuRequired=required;device.mCanonicalGpu=actual;
   const bool blocked=(required||actual)&&!gfx::CanExtractCanonicalCanvasPixels(c.metadata);
   assert((c.ImageBuffer()==nullptr)==blocked);
   assert((c.InputStream()==NS_ERROR_NOT_AVAILABLE)==blocked);
  }
 }
}
'''
    harness=harness.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'gpu-encode.cpp';path.write_text(harness)
        binary=Path(directory)/'gpu-encode'
        subprocess.run(['c++','-std=c++17','-I',str(ROOT/'gfx/2d'),str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)


def test_poisoned_canonical_gl_buffer_read_refuses_before_destination_access():
    source=(ROOT/'dom/canvas/ClientWebGLContext.cpp').read_text()
    start=source.index('void ClientWebGLContext::GetBufferSubData(')
    block=source[start:source.index('\n////',start)]
    begin=block.index('  if (notLost->info.options.cloakfoxCanonicalGpu')
    guard=block[begin:block.index('\n  size_t elemSize',begin)]
    assert 'CanExtractCanonicalCanvasPixels(GetCanvasPrivacyMetadata())' in guard
    assert begin<block.index('dstData.ProcessFixedData')<block.index('child->SendGetBufferSubData')
    metadata=(ROOT/'gfx/2d/CanvasPrivacy.cpp').read_text()
    metadata=metadata[metadata.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):metadata.index('void AddCanvasPixelSource(')]
    harness='''#include <cassert>\n#include <initializer_list>\n#include "CanvasPrivacy.h"\nnamespace mozilla::gfx {\n'''+metadata+r'''
}
using namespace mozilla;
constexpr int LOCAL_GL_INVALID_OPERATION=1282;
struct Options{bool cloakfoxCanonicalGpu=false;};struct Info{Options options;};struct NotLost{Info info;};
struct Context{
 NotLost data;NotLost*notLost=&data;
 gfx::CanvasPrivacyMetadata policy{1,7,123,456,64|512};
 bool dispatched=false;unsigned dest=77;int error=0;
 gfx::CanvasPrivacyMetadata GetCanvasPrivacyMetadata()const{return policy;}
 void EnqueueError(int code,const char*){error=code;}
 void Read(){
'''+guard+r'''
  dispatched=true;dest=123;
 }
};
int main(){
 for(bool canonical:{false,true})for(unsigned sources:{unsigned(64|512),unsigned(64|512|1),unsigned(64)}){
  Context c;c.data.info.options.cloakfoxCanonicalGpu=canonical;c.policy.sources=sources;c.Read();
  const bool blocked=canonical&&!gfx::CanExtractCanonicalCanvasPixels(c.policy);
  assert(c.dispatched!=blocked);assert(c.dest==(blocked?77u:123u));assert(c.error==(blocked?1282:0));
 }
}
'''
    with tempfile.TemporaryDirectory()as directory:
        path=Path(directory)/'gl-buffer.cpp';path.write_text(harness)
        binary=Path(directory)/'gl-buffer'
        subprocess.run(['c++','-std=c++17','-I',str(ROOT/'gfx/2d'),str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)


def test_authored_imagedata_gets_proof_on_fresh_validated_wrapper():
    source=(ROOT/'dom/canvas/ClientWebGLContext.cpp').read_text()
    start=source.index('if (src.mImageData) {')
    block=source[start:source.index('if (src.mOffscreenCanvas)',start)]
    assert 'gfx::SetCanvasPrivacyMetadata(surf' in block
    assert 'gfx::CanvasPixelSource::CanonicalRaster' in block
    assert block.index('CreateWrappingDataSourceSurface')<block.index('gfx::SetCanvasPrivacyMetadata(surf')<block.rindex('nogc.reset()')
