"""Compile actual SVG cache policy; renderer toggles invalidate even unchanged seed."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class SVGPolicy(unittest.TestCase):
 def test_actual_cache_transition(self):
  s=(ROOT/'firefox-src/image/VectorImage.cpp').read_text();self.assertTrue('void VectorImage::RefreshCloakfoxRenderPolicy()' in s,'SVG renderer cache policy absent')
  a=s.index('void VectorImage::RefreshCloakfoxRenderPolicy()');b=s.index('static gfx::CanvasPrivacyMetadata CloakfoxSVGOwner(',a);body=s[a:b]
  code=r'''#include <cassert>
#include <cstdint>
#include <optional>
#define MOZ_ASSERT assert
bool NS_IsMainThread(){return true;}auto Nothing(){return std::optional<uint64_t>{};}
template<class T>auto Some(T value){return std::optional<T>(value);}
struct StaticPrefs{inline static bool master=true,full=false;static bool cloakfox_enabled(){return master;}static bool cloakfox_experimental_canvas_pipeline(){return full;}};
struct Context{uint64_t identity=17;std::optional<uint64_t> GetCloakfoxFontIdentity(){return identity;}};
struct Doc{Context context;Context*GetPresContext(){return &context;}};
struct Wrapper{Doc doc;int flushes=0;Doc*GetDocument(){return &doc;}void FlushLayout(){flushes++;}};
struct VectorImage;void*ImageKey(VectorImage*p){return p;}
struct SurfaceCache{inline static int removed=0;static void RemoveImage(void*){removed++;}};
struct OptionalIdentity:std::optional<uint64_t>{using std::optional<uint64_t>::optional;};
struct VectorImage{Wrapper*mSVGDocumentWrapper;std::optional<bool>mCloakfoxRenderPolicy;uint64_t mCloakfoxFontIdentity=0;void RefreshCloakfoxRenderPolicy();};
'''+body.replace('identity.valueOr(0)','identity.value_or(0)')+r'''
int main(){Wrapper wrapper;VectorImage image{&wrapper};image.RefreshCloakfoxRenderPolicy();assert(!SurfaceCache::removed);StaticPrefs::full=true;image.RefreshCloakfoxRenderPolicy();assert(SurfaceCache::removed==1);image.RefreshCloakfoxRenderPolicy();assert(SurfaceCache::removed==1);wrapper.doc.context.identity=21;image.RefreshCloakfoxRenderPolicy();assert(SurfaceCache::removed==2);StaticPrefs::master=false;image.RefreshCloakfoxRenderPolicy();assert(SurfaceCache::removed==3);assert(wrapper.flushes==5);}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'policy.cpp';p.write_text(code);exe=Path(d)/'policy';subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
