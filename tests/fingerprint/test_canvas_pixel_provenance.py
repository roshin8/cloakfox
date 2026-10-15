"""Execute production metadata code with minimal surface/mutex primitives."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CanvasProvenance(unittest.TestCase):
 def test_conservative_copy_and_concurrent_contributors(self):
  h=ROOT/'firefox-src/gfx/2d/CanvasPrivacy.h';p=ROOT/'firefox-src/gfx/2d/CanvasPrivacy.cpp'
  self.assertTrue(h.exists() and p.exists(),'producer metadata not implemented')
  codec=(ROOT/'firefox-src/gfx/ipc/GfxMessageUtils.h').read_text()
  start=codec.index('struct ParamTraits<mozilla::gfx::CanvasPrivacyMetadata>')
  ipc='template <>\n'+codec[start:codec.index('\n};',start)+3]
  implementation='\n'.join(line for line in p.read_text().splitlines() if not line.startswith('#include'))
  harness=r'''
#include <map>
#include <mutex>
#include <thread>
#include <vector>
#include <cassert>
#include "CanvasPrivacy.h"
namespace mozilla {using StaticMutex=std::mutex;using StaticMutexAutoLock=std::lock_guard<std::mutex>;}
namespace mozilla::gfx {
struct UserDataKey {};
class SourceSurface {std::map<UserDataKey*,std::pair<void*,void(*)(void*)>> data;
public:
 ~SourceSurface(){for(auto&v:data)v.second.second(v.second.first);}
 void*GetUserData(UserDataKey*k)const{auto v=data.find(k);return v==data.end()?nullptr:v->second.first;}
 void AddUserData(UserDataKey*k,void*v,void(*destroy)(void*)){assert(!data.count(k));data[k]={v,destroy};}
};
}
'''+implementation+r'''
namespace IPC {
struct MessageWriter {std::vector<uint64_t> data;};
struct MessageReader {std::vector<uint64_t> data;size_t index=0;};
template<class T>struct ParamTraits;
template<class...T>void WriteParams(MessageWriter*w,T...v){(w->data.push_back(v),...);}
template<class T>bool ReadOne(MessageReader*r,T*out){if(r->index==r->data.size())return false;*out=static_cast<T>(r->data[r->index++]);return true;}
template<class...T>bool ReadParams(MessageReader*r,T&...v){return (ReadOne(r,&v)&&...);}
'''+ipc+r'''
}
'''+r'''
using namespace mozilla::gfx;
int main(){
 SourceSurface empty,software,gpu,destination;
 assert(GetCanvasPixelSources(nullptr)==1 && GetCanvasPixelSources(&empty)==1);
 AddCanvasPixelSource(&software,CanvasPixelSource::Software2D);assert(GetCanvasPixelSources(&software)==2);
 AddCanvasPixelSource(&software,CanvasPixelSource::FixedFontOutline);assert(GetCanvasPixelSources(&software)==6);
 AddCanvasPixelSource(&gpu,CanvasPixelSource::GPU);MergeCanvasPixelSources(&destination,&software);MergeCanvasPixelSources(&destination,&gpu);assert(GetCanvasPixelSources(&destination)==70);
 MergeCanvasPixelSources(&destination,&empty);assert(GetCanvasPixelSources(&destination)==71);
 MergeCanvasPixelSources(&destination,nullptr);assert(GetCanvasPixelSources(&destination)==71);
 AddCanvasPixelSource(&destination,static_cast<CanvasPixelSource>(0x80000000u));assert(GetCanvasPixelSources(&destination)==71);
 CanvasPrivacyMetadata owner{1, 7, 123, 456, 2};
 assert(CanExtractCanonicalCanvasPixels(owner));
 assert(CanImportCanonicalCanvasPixels(owner));
 assert(CanImportCanonicalCanvasPixels({0,0,0,0,16|1024}));
 assert(CanImportCanonicalCanvasPixels({0,0,0,0,16|1024|256}));
 assert(CanImportCanonicalCanvasPixels({0,0,0,0,32|128|256}));
 assert(!CanImportCanonicalCanvasPixels({0,0,0,0,1024}));
 assert(!CanImportCanonicalCanvasPixels({0,0,0,0,16|1024|1}));
 assert(!CanImportCanonicalCanvasPixels({0,0,0,0,16|1024|8}));
 assert(!CanImportCanonicalCanvasPixels({0,0,0,0,16|1024|64|512}));
 assert(!CanImportCanonicalCanvasPixels({0,0,0,0,16|1024|32}));
 assert(!CanImportCanonicalCanvasPixels({0,0,0,0,32|128}));
 assert(!CanImportCanonicalCanvasPixels({0,7,0,0,16|1024}));
 assert(!CanImportCanonicalCanvasPixels({1,7,0,0,16|1024}));

 assert(!CanExtractCanonicalCanvasPixels({0,0,0,0,2}));
 assert(!CanExtractCanonicalCanvasPixels({1,7,123,456,3}));
 assert(!CanExtractCanonicalCanvasPixels({1,7,123,456,10}));
 assert(!CanExtractCanonicalCanvasPixels({1,7,123,456,66}));
 assert(CanExtractCanonicalCanvasPixels({1,7,123,456,64|512}));
 assert(!CanExtractCanonicalCanvasPixels({1,7,123,456,2|32|256}));
 assert(CanExtractCanonicalCanvasPixels({1,7,123,456,2|32|128|256}));
 assert(CanExtractCanonicalCanvasPixels({1,7,123,456,32|128|256}));
 assert(!CanExtractCanonicalCanvasPixels({1,7,123,456,2|32|128|256|1}));
 assert(!CanExtractCanonicalCanvasPixels({999,7,123,456,2}));

 IPC::MessageWriter writer;
 IPC::ParamTraits<CanvasPrivacyMetadata>::Write(&writer,owner);
 IPC::MessageReader reader{writer.data};CanvasPrivacyMetadata decoded;
 assert(IPC::ParamTraits<CanvasPrivacyMetadata>::Read(&reader,&decoded) && decoded==owner);
 reader={writer.data};reader.data[0]=999;
 assert(IPC::ParamTraits<CanvasPrivacyMetadata>::Read(&reader,&decoded) && decoded.version==0 && (decoded.sources&1));
 reader={writer.data};reader.data.pop_back();decoded=owner;
 assert(!IPC::ParamTraits<CanvasPrivacyMetadata>::Read(&reader,&decoded) && decoded==owner);
 SourceSurface owned, copied;
 SetCanvasPrivacyMetadata(&owned,owner);
 auto original=GetCanvasPrivacyMetadata(&owned);
 assert(original.version==1 && original.userContextId==7 && original.ownerHi==123 && original.ownerLo==456 && original.sources==2);
 AddCanvasPixelSource(&owned,CanvasPixelSource::Media);
 MergeCanvasPixelSources(&copied,&owned);
 auto retained=GetCanvasPrivacyMetadata(&copied);
 assert(retained.ownerHi==123 && retained.ownerLo==456 && retained.sources==34);
 auto foreign=owner; foreign.ownerHi=124;
 SetCanvasPrivacyMetadata(&copied,foreign);
 auto mixed=GetCanvasPrivacyMetadata(&copied);
 assert(mixed.version==0 && mixed.ownerHi==0 && (mixed.sources & 1));
 SetCanvasPrivacyMetadata(&copied,owner);
 assert(GetCanvasPrivacyMetadata(&copied).version==0);
 auto malformed=owner; malformed.version=999;
 auto unknown=NormalizeCanvasPrivacyMetadata(malformed);
 assert(unknown.version==0 && unknown.ownerHi==0 && (unknown.sources & 1));
 malformed=owner;malformed.sources=0x80000000u;
 assert(NormalizeCanvasPrivacyMetadata(malformed).version==0);
 SourceSurface shared;std::vector<std::thread>threads;
 for(unsigned bit=0;bit<7;bit++)threads.emplace_back([&shared,bit](){for(unsigned i=0;i<1000;i++)AddCanvasPixelSource(&shared,static_cast<CanvasPixelSource>(1u<<bit));});
 for(auto&t:threads)t.join();assert(GetCanvasPixelSources(&shared)==127);
 assert(NormalizeCanvasPixelSources(0)==1 && NormalizeCanvasPixelSources(0x80000000u)==1);
}
'''
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'provenance.cpp';f.write_text(harness);exe=Path(d)/'provenance'
   subprocess.run(['c++','-std=c++17','-pthread','-I',str(h.parent),str(f),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)

class DescriptorOwnership(unittest.TestCase):
 def test_rgb_allocation_drops_previous_pixel_owner(self):
  source=(ROOT/'firefox-src/gfx/layers/ImageContainer.cpp').read_text()
  begin=source.index('/* static */ nsresult Image::AllocateSurfaceDescriptorBufferRgb(')
  end=source.index('\nnsresult Image::BuildSurfaceDescriptorBuffer(',begin)
  allocation=source[begin:end]
  harness=r'''
#include <cstdint>
#include <functional>
#include <cassert>
#include <optional>
#include "CanvasPrivacy.h"
using nsresult=int;
constexpr int NS_OK=0,NS_ERROR_INVALID_ARG=1,NS_ERROR_OUT_OF_MEMORY=2;
#define MOZ_ASSERT(x) assert(x)
namespace gfx {
struct IntSize {int width,height;};
enum class SurfaceFormat { BGRA };
enum class ColorSpace2 {SRGB};enum class TransferFunction {SRGB};
using CanvasPrivacyMetadata=mozilla::gfx::CanvasPrivacyMetadata;
}
namespace layers {
struct MemoryOrShmem {
 enum Type{Tuintptr_t,TShmem};uintptr_t pointer=0;
 Type type()const{return Tuintptr_t;}
 uintptr_t get_uintptr_t()const{return pointer;}
 struct FakeShmem {template<class T>T*get()const{return nullptr;}};
 FakeShmem get_Shmem()const{return {};}
};
}
using namespace layers;
struct RGBDescriptor {RGBDescriptor()=default;RGBDescriptor(gfx::IntSize,gfx::SurfaceFormat,gfx::ColorSpace2,gfx::TransferFunction){}};
struct SurfaceDescriptorBuffer {
 RGBDescriptor description;MemoryOrShmem memory;gfx::CanvasPrivacyMetadata privacy;
 auto&desc(){return description;}auto&data(){return memory;}auto&canvasPrivacy(){return privacy;}
};
struct ImageDataSerializer {
 static std::optional<uint32_t> ComputeRGBStride(gfx::SurfaceFormat,int width){return width*4;}
 static std::optional<uint32_t> ComputeRGBBufferSize(gfx::IntSize s,gfx::SurfaceFormat){return s.width*s.height*4;}
};
template<class T>struct Maybe:std::optional<T>{
 using std::optional<T>::optional;
 Maybe(std::optional<T>x):std::optional<T>(x){}
 bool isNothing()const{return !this->has_value();}
};
// The stride local uses upstream Maybe's isNothing API as well.
struct Stride {
 uint32_t value_;bool isNothing()const{return false;}uint32_t value()const{return value_;}
};
struct NativeSerializer:ImageDataSerializer {
 static Stride ComputeRGBStride(gfx::SurfaceFormat,int width){return {uint32_t(width*4)};}
};
#define ImageDataSerializer NativeSerializer
struct Image {static nsresult AllocateSurfaceDescriptorBufferRgb(const gfx::IntSize&,gfx::SurfaceFormat,uint8_t*&,SurfaceDescriptorBuffer&,int32_t&,const std::function<layers::MemoryOrShmem(uint32_t)>&);};
'''+allocation+r'''
int main(){
 uint8_t pixels[16];uint8_t*output=nullptr;int32_t stride=0;
 SurfaceDescriptorBuffer reused;
 reused.canvasPrivacy()={1,7,123,456,2};
 auto result=Image::AllocateSurfaceDescriptorBufferRgb({2,2},gfx::SurfaceFormat::BGRA,output,reused,stride,[&](uint32_t length){assert(length==16);return MemoryOrShmem{uintptr_t(pixels)};});
 assert(result==NS_OK && output==pixels && stride==8);
 assert(reused.canvasPrivacy().version==0 && reused.canvasPrivacy().ownerHi==0 && reused.canvasPrivacy().sources==1);
}
'''
  with tempfile.TemporaryDirectory() as d:
   cpp=Path(d)/'descriptor.cpp';exe=Path(d)/'descriptor'
   cpp.write_text(harness)
   subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(cpp),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
   # Negative control: remove the reset from the actual function, not live source.
   cpp.write_text(harness.replace('aSdBuffer.canvasPrivacy() = gfx::CanvasPrivacyMetadata{};', ''))
   subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(cpp),'-o',str(exe)],check=True)
   negative=subprocess.run([str(exe)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   self.assertNotEqual(negative.returncode,0,'stale-owner allocation mutation must fail')

if __name__=='__main__':unittest.main()
