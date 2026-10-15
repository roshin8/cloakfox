"""Execute the production scaling branch with observable backend and owner values."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class ScaleMetadata(unittest.TestCase):
 def test_canonical_scaling_uses_software_and_retains_owner(self):
  s=(ROOT/'firefox-src/gfx/thebes/gfxUtils.cpp').read_text();a=s.index('already_AddRefed<SourceSurface> gfxUtils::ScaleSourceSurface(');b=s.index('\nconst uint32_t gfxUtils::sNumFrameColors',a);body=s[a:b].replace('gfxUtils::ScaleSourceSurface','ScaleSourceSurface')
  fixture=r'''
#include <cassert>
#include "CanvasPrivacy.h"
#define MOZ_ASSERT assert
template<class T>class RefPtr{T*p=nullptr;public:RefPtr(){}RefPtr(T*a):p(a){}T*operator->()const{return p;}operator T*()const{return p;}T*forget(){return p;}};
template<class T>using already_AddRefed=T*;
namespace mozilla::gfx{
enum class BackendType{SKIA,OTHER};
struct IntSize{int width=2,height=2;bool IsEmpty()const{return false;}bool operator!=(const IntSize&o)const{return width!=o.width||height!=o.height;}};
struct Point{};struct Size{Size(IntSize){}};struct Rect{Rect(Point,Size){}};
class SourceSurface{public:CanvasPrivacyMetadata metadata;IntSize GetSize(){return{};}int GetFormat(){return 4;}};
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface*s){return s->metadata;}
void SetCanvasPrivacyMetadata(SourceSurface*s,const CanvasPrivacyMetadata&m){if(s)s->metadata=m;}
struct DrawTarget{SourceSurface surface;bool IsValid(){return true;}void DrawSurface(SourceSurface*,Rect,Rect){}SourceSurface*GetBackingSurface(){return &surface;}};
struct Factory{static BackendType backend;static DrawTarget*CreateDrawTarget(BackendType b,IntSize,int){backend=b;return new DrawTarget;}};BackendType Factory::backend=BackendType::OTHER;
}
namespace gfx=mozilla::gfx;using namespace mozilla::gfx;
namespace gfxVars{BackendType ContentBackend(){return BackendType::OTHER;}}
'''+body+r'''
int main(){
 SourceSurface canonical;canonical.metadata={1,7,13,17,2};auto*out=ScaleSourceSurface(canonical,{3,3});assert(Factory::backend==BackendType::SKIA);assert(out->metadata==canonical.metadata);
 SourceSurface native;auto*other=ScaleSourceSurface(native,{3,3});assert(Factory::backend==BackendType::OTHER);assert(other->metadata==native.metadata);
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'scale.cpp';p.write_text(fixture);exe=Path(d)/'scale';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
