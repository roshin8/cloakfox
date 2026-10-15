"""Exercise real bitmap data-wrapper acquisition with conservative owner merging."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class BitmapDataPolicy(unittest.TestCase):
 def test_actual_wrapper_preserves_pixel_policy(self):
  s=(ROOT/'firefox-src/dom/canvas/ImageBitmap.cpp').read_text();a=s.index('static already_AddRefed<DataSourceSurface> CanvasDataSurface(');b=s.index('\n}',a)+2
  core=(ROOT/'firefox-src/gfx/2d/CanvasPrivacy.cpp').read_text();core=core[core.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):core.index('void AddCanvasPixelSource(')]
  cpp=r'''#include <cassert>
#include <optional>
#include "CanvasPrivacy.h"
namespace gfx=mozilla::gfx;using namespace gfx;
template<class T>using already_AddRefed=T*;
template<class T>struct RefPtr{T*p;RefPtr(T*a):p(a){}operator T*()const{return p;}T*operator->(){return p;}T*forget(){return p;}};
namespace mozilla::gfx{struct SourceSurface{std::optional<CanvasPrivacyMetadata>meta;SourceSurface*data=nullptr;SourceSurface*GetDataSurface(){return data;}};using DataSourceSurface=SourceSurface;
'''+core+r'''
CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface*s){return s&&s->meta?*s->meta:CanvasPrivacyMetadata{};}
void SetCanvasPrivacyMetadata(SourceSurface*s,const CanvasPrivacyMetadata&m){if(s)s->meta=s->meta?MergeCanvasPrivacyMetadata(*s->meta,m):NormalizeCanvasPrivacyMetadata(m);}
}
'''+s[a:b]+r'''
int main(){SourceSurface src,dst;src.data=&dst;src.meta=CanvasPrivacyMetadata{1,7,11,13,2};assert(CanvasDataSurface(&src)==&dst);assert(dst.meta==src.meta);
SourceSurface raster,out;raster.data=&out;raster.meta=CanvasPrivacyMetadata{0,0,0,0,16|1024};assert(CanImportCanonicalCanvasPixels(*CanvasDataSurface(&raster)->meta));
SourceSurface poisoned;poisoned.meta=CanvasPrivacyMetadata{};src.data=&poisoned;CanvasDataSurface(&src);assert(GetCanvasPrivacyMetadata(&poisoned).sources&1);
SourceSurface noData;assert(CanvasDataSurface(&noData)==nullptr);assert(CanvasDataSurface(nullptr)==nullptr);
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'bitmap.cpp';p.write_text(cpp);exe=Path(d)/'bitmap';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
