"""Compile the actual capture copy branch with deterministic Moz2D primitives."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CaptureFallback(unittest.TestCase):
 def test_actual_native_copy_protects_only_fallback(self):
  s=(ROOT/'firefox-src/dom/html/HTMLCanvasElement.cpp').read_text();a=s.index('  static already_AddRefed<DataSourceSurface> CopySurface(');b=s.index('  void SetReturnPlaceholderData(',a);copy=s[a:b]
  # Permit the pre-fix signature so RED demonstrates raw fallback pixels.
  if 'uint32_t aFallbackSeed' not in copy:copy=copy.replace('bool aReturnPlaceholderData)', 'bool aReturnPlaceholderData, uint32_t aFallbackSeed = 0)')
  if 'bool aCanonicalCaptureRequested' not in copy:copy=copy.replace('uint32_t aFallbackSeed = 0)', 'uint32_t aFallbackSeed = 0, bool aCanonicalCaptureRequested = false)')
  harness=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>
#define MOZ_ASSERT assert
template<class T>class RefPtr{T*p=nullptr;public:RefPtr(){}RefPtr(T*a):p(a){}T*operator->()const{return p;}operator T*()const{return p;}T*forget(){auto*r=p;p=nullptr;return r;}};
template<class T>using already_AddRefed=T*;
namespace mozilla::gfx{
enum class SurfaceFormat{B8G8R8A8,B8G8R8X8,R8G8B8A8,R8G8B8X8};
struct Size{int width=2,height=2;bool operator==(const Size&o)const{return width==o.width&&height==o.height;}};
struct CanvasPrivacyMetadata{bool canonical=false;};
class SourceSurface{public:std::vector<uint8_t>bytes=std::vector<uint8_t>(24,87);Size size;int stride=12;SurfaceFormat format=SurfaceFormat::B8G8R8A8;CanvasPrivacyMetadata metadata;enum MapType{READ,WRITE};SourceSurface*GetDataSurface(){return this;}Size GetSize(){return size;}SurfaceFormat GetFormat(){return format;}int GetStride(){return stride;}
 struct ScopedMap{SourceSurface*s;ScopedMap(RefPtr<SourceSurface>a,MapType):s(a){}bool IsMapped(){return true;}int GetStride(){return s->stride;}uint8_t*GetData(){return s->bytes.data();}};};
using DataSourceSurface=SourceSurface;
struct Factory{static SourceSurface*CreateDataSourceSurfaceWithStride(Size s,SurfaceFormat f,int stride){auto*p=new SourceSurface;p->size=s;p->format=f;p->stride=stride;return p;}};
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface*s){return s->metadata;}void SetCanvasPrivacyMetadata(SourceSurface*s,CanvasPrivacyMetadata m){s->metadata=m;}
bool CanExtractCanonicalCanvasPixels(CanvasPrivacyMetadata m){return m.canonical;}
bool IsOpaque(SurfaceFormat f){return f==SurfaceFormat::B8G8R8X8||f==SurfaceFormat::R8G8B8X8;}
int conversions=0;bool conversionOK=true;
bool SwizzleData(const uint8_t*,int,SurfaceFormat,uint8_t*,int,SurfaceFormat,Size){conversions++;return conversionOK;}
bool UnpremultiplyData(const uint8_t*,int,SurfaceFormat,uint8_t*,int,SurfaceFormat,Size){conversions++;return conversionOK;}
bool PremultiplyData(const uint8_t*,int,SurfaceFormat,uint8_t*,int,SurfaceFormat,Size){conversions++;return conversionOK;}
}
using namespace mozilla::gfx;namespace gfx=mozilla::gfx;
int calls=0;uint32_t usedSeed=0;
struct CanvasFingerprintManager{static void ApplyCanvasNoiseRect(uint8_t*p,uint32_t w,uint32_t h,uint32_t stride,uint32_t cw,uint32_t x,uint32_t y,uint32_t seed){calls++;usedSeed=seed;assert(cw==w&&x==0&&y==0);for(unsigned row=0;row<h;row++)for(unsigned col=0;col<w;col++)p[row*stride+col*4]^=1;}};
void GeneratePlaceholderCanvasData(size_t n,uint8_t*p){memset(p,0x5a,n);}
'''+copy+r'''
int main(){
 SourceSurface source;source.bytes[3]=128;RefPtr<SourceSurface> src(&source);
 assert(CopySurface(src,false,0,true)==nullptr); // Requested full mode must not export raw Unknown.
 auto*legacyZero=CopySurface(src,false,0,false);assert(legacyZero&&legacyZero->bytes==source.bytes);delete legacyZero;
 source.metadata.canonical=true;auto*validZero=CopySurface(src,false,0,true);assert(validZero&&validZero->bytes==source.bytes);delete validZero;source.metadata.canonical=false;
 auto*placeholderZero=CopySurface(src,true,0,true);assert(placeholderZero&&placeholderZero->bytes[0]==0x5a);delete placeholderZero;
 auto*protectedCopy=CopySurface(src,false,73);assert(protectedCopy->bytes!=source.bytes);assert(calls==1&&usedSeed==73&&conversions==2);assert(protectedCopy->bytes[3]==128&&protectedCopy->bytes[8]==87);delete protectedCopy;
 auto*repeat=CopySurface(src,false,73);assert(calls==2&&repeat->bytes[0]==(87^1));delete repeat;
 auto*disabled=CopySurface(src,false,0);assert(disabled->bytes==source.bytes&&calls==2);delete disabled;
 source.metadata.canonical=true;auto*canonical=CopySurface(src,false,73);assert(canonical->bytes==source.bytes&&calls==2&&canonical->metadata.canonical);delete canonical;
 source.metadata.canonical=false;auto*placeholder=CopySurface(src,true,73);assert(calls==2&&placeholder->bytes[0]==0x5a);delete placeholder;
 source.format=SurfaceFormat::B8G8R8X8;auto*opaque=CopySurface(src,false,91);assert(calls==3&&usedSeed==91&&opaque->bytes[3]==128);delete opaque;
 conversionOK=false;auto*failed=CopySurface(src,false,91);assert(!failed&&calls==3&&source.bytes[0]==87);
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'capture.cpp';p.write_text(harness);exe=Path(d)/'capture';subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
