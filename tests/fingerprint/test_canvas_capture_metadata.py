"""Run production capture CopySurface and metadata code with small Moz2D primitives."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CaptureMetadata(unittest.TestCase):
 def test_native_capture_copy_retains_owner_before_image_wrapper(self):
  s=(ROOT/'firefox-src/dom/html/HTMLCanvasElement.cpp').read_text();a=s.index('  static already_AddRefed<DataSourceSurface> CopySurface(');b=s.index('  void SetReturnPlaceholderData(',a);copy=s[a:b]
  implementation='\n'.join(x for x in (ROOT/'firefox-src/gfx/2d/CanvasPrivacy.cpp').read_text().splitlines() if not x.startswith('#include'))
  harness=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <mutex>
#include <vector>
#include "CanvasPrivacy.h"
#define MOZ_ASSERT assert
namespace mozilla{using StaticMutex=std::mutex;using StaticMutexAutoLock=std::lock_guard<std::mutex>;}
template<class T>class RefPtr{T*p=nullptr;public:RefPtr(){}RefPtr(T*a):p(a){}T*operator->()const{return p;}operator T*()const{return p;}T*forget(){auto*r=p;p=nullptr;return r;}};
template<class T>using already_AddRefed=T*;
namespace mozilla::gfx{
enum class SurfaceFormat {R8G8B8A8};
struct UserDataKey{};struct Size{int width=2,height=2;bool operator==(const Size&o)const{return width==o.width&&height==o.height;}};
class SourceSurface{std::map<UserDataKey*,std::pair<void*,void(*)(void*)>>data;
public:std::vector<uint8_t>bytes=std::vector<uint8_t>(16,87);Size size;int stride=8;SurfaceFormat format=SurfaceFormat::R8G8B8A8;enum MapType{READ,WRITE};
 ~SourceSurface(){for(auto&v:data)v.second.second(v.second.first);}
 void*GetUserData(UserDataKey*k)const{auto i=data.find(k);return i==data.end()?nullptr:i->second.first;}
 void AddUserData(UserDataKey*k,void*v,void(*d)(void*)){assert(!data.count(k));data[k]={v,d};}
 SourceSurface*GetDataSurface(){return this;}Size GetSize(){return size;}SurfaceFormat GetFormat(){return format;}int GetStride(){return stride;}
 struct ScopedMap{SourceSurface*s;ScopedMap(RefPtr<SourceSurface>a,MapType):s(a){}bool IsMapped(){return true;}int GetStride(){return s->stride;}uint8_t*GetData(){return s->bytes.data();}};
};
using DataSourceSurface=SourceSurface;
struct Factory{static SourceSurface*CreateDataSourceSurfaceWithStride(Size s,SurfaceFormat f,int stride){auto*p=new SourceSurface;p->size=s;p->format=f;p->stride=stride;return p;}};
}
'''+implementation+r'''
using namespace mozilla::gfx;
namespace gfx=mozilla::gfx;
namespace mozilla::gfx {
bool IsOpaque(SurfaceFormat){return false;}
bool SwizzleData(const uint8_t*,int,SurfaceFormat,uint8_t*,int,SurfaceFormat,Size){return true;}
bool UnpremultiplyData(const uint8_t*,int,SurfaceFormat,uint8_t*,int,SurfaceFormat,Size){return true;}
bool PremultiplyData(const uint8_t*,int,SurfaceFormat,uint8_t*,int,SurfaceFormat,Size){return true;}
}
struct CanvasFingerprintManager{static void ApplyCanvasNoiseRect(uint8_t*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t){assert(false);}};
void GeneratePlaceholderCanvasData(size_t n,uint8_t*p){memset(p,0x5a,n);}
'''+copy+r'''
int main(){
 SourceSurface source;CanvasPrivacyMetadata owner{1,7,19,23,2};SetCanvasPrivacyMetadata(&source,owner);
 RefPtr<SourceSurface> src(&source);auto*copied=CopySurface(src,false);assert(copied&&copied->bytes==source.bytes);assert(GetCanvasPrivacyMetadata(copied)==owner);
 auto*placeholder=CopySurface(src,true);assert(GetCanvasPrivacyMetadata(placeholder).version==0);assert(placeholder->bytes[0]==0x5a);
 SourceSurface native;RefPtr<SourceSurface> n(&native);auto*unknown=CopySurface(n,false);assert(GetCanvasPrivacyMetadata(unknown).version==0);
 delete copied;delete placeholder;delete unknown;
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'capture.cpp';p.write_text(harness);exe=Path(d)/'capture';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
