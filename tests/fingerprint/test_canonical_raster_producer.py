"""Exercise actual fixed-decode cache policy and immutable raster proof."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class RasterProducer(unittest.TestCase):
 def test_actual_native_policy(self):
  s=(ROOT/'firefox-src/image/RasterImage.cpp').read_text()
  self.assertTrue('static uint32_t CloakfoxRasterDecodeFlags(' in s,'common raster cache policy absent')
  a=s.index('static uint32_t CloakfoxRasterDecodeFlags(');b=s.index('// End Cloakfox raster producer policy.',a)
  body=s[a:b]
  fixture=r'''#include <cstdint>
#include <cassert>
struct imgIContainer{enum:uint32_t{FLAG_DECODE_TO_SRGB_COLORSPACE=4,FLAG_DECODE_NO_COLORSPACE_CONVERSION=2,FLAG_DECODE_NO_PREMULTIPLY_ALPHA=1};};
'''+body+r'''
int main(){assert(CloakfoxRasterDecodeFlags(0,false)==0);assert(CloakfoxRasterDecodeFlags(0,true)==4);assert(CloakfoxRasterDecodeFlags(2,true)==2);assert(CloakfoxRasterDecodeFlags(6,true)==2);assert(CloakfoxRasterDecodeFlags(1,true)==5);assert(CloakfoxRasterDecodeFlags(0,true)==4);assert(CloakfoxRasterDecodeFlags(4,false)==4);}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'policy.cpp';p.write_text(fixture);exe=Path(d)/'policy';subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
 def test_actual_decoder_intent(self):
  s=(ROOT/'firefox-src/image/Decoder.cpp').read_text();a=s.index('int Decoder::GetCMSRenderingIntent() const {');b=s.index('qcms_profile* Decoder::GetCMSOutputProfile()',a);body=s[a:b]
  code=r'''#include <cassert>
namespace SurfaceFlags{constexpr int TO_SRGB_COLORSPACE=4;}
struct gfxPlatform{inline static int native=2;static int GetRenderingIntent(){return native;}};
struct Decoder{int mSurfaceFlags=0;int GetCMSRenderingIntent()const;};
'''+body+r'''
int main(){Decoder d;assert(d.GetCMSRenderingIntent()==2);d.mSurfaceFlags=4;assert(d.GetCMSRenderingIntent()==-1);gfxPlatform::native=3;assert(d.GetCMSRenderingIntent()==-1);d.mSurfaceFlags=0;assert(d.GetCMSRenderingIntent()==3);}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'intent.cpp';p.write_text(code);exe=Path(d)/'intent';subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
 def test_actual_finished_frame_certificate(self):
  s=(ROOT/'firefox-src/image/RasterImage.cpp').read_text();a=s.index('  RefPtr<SourceSurface> surface = result.Surface()->GetSourceSurface();',s.index('RasterImage::GetFrameAtSize('));b=s.index('  return surface.forget();',a)+len('  return surface.forget();');body=s[a:b]
  code=r'''#include <cassert>
#include <cstdint>
#include "CanvasProducerAudit.hpp"
namespace SurfaceFlags{constexpr int TO_SRGB_COLORSPACE=4,NO_COLORSPACE_CONVERSION=2;}
namespace gfx {
enum class CanvasPixelSource:uint32_t{ExternalPixels=16,CanonicalRaster=1024};
struct Policy{uint32_t version=0,userContextId=0;uint64_t ownerHi=0,ownerLo=0;uint32_t sources=1;};
struct SourceSurface{Policy policy;};
void SetCanvasPrivacyMetadata(SourceSurface*s,Policy p){s->policy=p;}
Policy GetCanvasPrivacyMetadata(SourceSurface*s){return s?s->policy:Policy{};}
bool CanImportCanonicalCanvasPixels(Policy p){return p.sources==1040;}
}
using gfx::SourceSurface;
template<class T>struct RefPtr{T*p;RefPtr(T*v):p(v){}operator T*()const{return p;}T*forget(){return p;}};
struct Frame{SourceSurface source;bool finished=false;bool IsFinished(){return finished;}SourceSurface*GetSourceSurface(){return &source;}};
struct Drawable{Frame frame;int flags=0;Frame*operator->(){return &frame;}int GetSurfaceFlags(){return flags;}};
struct Result{Drawable drawable;Drawable&Surface(){return drawable;}};
SourceSurface*Export(Result&result){
'''+body+r'''
}
int main(){Result native;native.drawable.frame.finished=true;assert(Export(native)->policy.sources==1);Result partial;partial.drawable.flags=4;assert(Export(partial)->policy.sources==1);Result fixed;fixed.drawable.flags=4;fixed.drawable.frame.finished=true;auto p=Export(fixed)->policy;assert(p.sources==1040&&!p.version&&!p.ownerHi&&!p.ownerLo);Result none;none.drawable.flags=2;none.drawable.frame.finished=true;assert(Export(none)->policy.sources==1040);}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'proof.cpp';p.write_text(code);exe=Path(d)/'proof';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
