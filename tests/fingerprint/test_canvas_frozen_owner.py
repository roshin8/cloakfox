"""Execute the production creation capture branch with explicit transfer owners."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class FrozenOwner(unittest.TestCase):
 def test_context_retains_original_offscreen_owner_and_configuration(self):
  s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text();a=s.index('void CanvasRenderingContext2D::CaptureCanonicalCanvasPolicy()');body=s[s.index('{',a)+1:s.index('\n}\n',a)];a=s.index('// Cloakfox canonical policy.');policy=s[a:s.index('// End Cloakfox canonical policy.',a)]
  program=r'''#include "json.hpp"
#include "CanvasPrivacy.h"
#include <cassert>
#include <array>
#include <optional>
namespace gfx=mozilla::gfx;
using gfx::CanvasPixelSource;
struct Settings {};
struct nsIPrincipal {bool system=false;struct Attributes{unsigned mUserContextId=7;}attrs;bool IsSystemPrincipal(){return system;}Attributes&OriginAttributesRef(){return attrs;}};
namespace StaticPrefs{bool enabled=true,requested=true;bool cloakfox_enabled(){return enabled;}bool cloakfox_experimental_canvas_pipeline(){return requested;}}
namespace CloakfoxSiteSeed{
 nlohmann::json cfg={{"canvas:canonical_2d",true}};
 nlohmann::json ExactConfig(unsigned){return cfg;}
 std::optional<std::array<uint64_t,2>> OwnerKey(unsigned id,Settings*){return std::array<uint64_t,2>{id+11,29};}
}
struct Offscreen{
 gfx::CanvasPrivacyMetadata policy{1,51,71,83,1};
 const gfx::CanvasPrivacyMetadata&CanvasPrivacyPolicy(){return policy;}
 bool CanonicalCanvasBackingPolicy(){return true;}
};
'''+policy+r'''
struct Context{
 gfx::CanvasPrivacyMetadata mCanvasPrivacyPolicy;
 uint32_t mCanvasPixelSources=0;
 bool mCanonicalCanvasPolicyCaptured=false,mCanonicalCanvasBacking=false;
 nsIPrincipal principal;Settings settings;Offscreen*mOffscreenCanvas=nullptr;
 nsIPrincipal*PrincipalOrNull(){return &principal;}
 Settings*GetCookieJarSettings(){return &settings;}
 void capture(){
'''+body+r'''
 }
};
int main(){
 Context c;c.capture();assert(c.mCanonicalCanvasBacking);assert(c.mCanvasPrivacyPolicy.userContextId==7 && c.mCanvasPrivacyPolicy.ownerHi==18 && c.mCanvasPrivacyPolicy.ownerLo==29);
 CloakfoxSiteSeed::cfg["canvas:canonical_2d"]=false;c.principal.attrs.mUserContextId=99;c.capture();assert(c.mCanonicalCanvasBacking&&c.mCanvasPrivacyPolicy.userContextId==7);
 Context stale;stale.capture();assert(stale.mCanonicalCanvasBacking);
 Offscreen sender;Context receiver;receiver.mOffscreenCanvas=&sender;receiver.principal.attrs.mUserContextId=99;receiver.capture();assert(receiver.mCanonicalCanvasBacking);assert(receiver.mCanvasPrivacyPolicy.userContextId==51&&receiver.mCanvasPrivacyPolicy.ownerHi==71&&receiver.mCanvasPrivacyPolicy.ownerLo==83);
 StaticPrefs::enabled=false;Context native;native.capture();assert(!native.mCanonicalCanvasBacking&&native.mCanvasPrivacyPolicy.version==0);
}
'''
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'owner.cpp';f.write_text(program);exe=Path(d)/'owner';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),'-I',str(ROOT/'firefox-src/gfx/2d'),str(f),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
