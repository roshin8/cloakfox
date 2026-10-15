"""Compile actual canonical policy/routing branches, not a parallel model."""
from pathlib import Path
import os,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
NATIVE=Path(os.environ.get('CLOAKFOX_CANVAS_SOURCE',ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp'))
class CanonicalBacking(unittest.TestCase):
 def test_creation_gates_and_allocation_cannot_fall_back(self):
  s=NATIVE.read_text()
  self.assertTrue('// Cloakfox canonical policy.' in s,'canonical policy not implemented')
  policy=s[s.index('// Cloakfox canonical policy.'):s.index('// End Cloakfox canonical policy.')]
  self.assertTrue('// Cloakfox canonical allocation.' in s,'canonical allocation not implemented')
  route=s[s.index('// Cloakfox canonical allocation.'):s.index('// End Cloakfox canonical allocation.')]
  program='''#include "json.hpp"
#include <cassert>
'''+policy+'''
struct Fixture {
 bool mCanonicalCanvasBacking=false,basic=false,accelerated=true,shared=true;
 int basicCalls=0,acceleratedCalls=0,sharedCalls=0;
 int newTarget=0,newProvider=0,aError=0;
 bool TryBasicTarget(int&,int&,int&) {++basicCalls;return basic;}
 bool TryAcceleratedTarget(int&,int&) {++acceleratedCalls;return accelerated;}
 bool TrySharedTarget(int&,int&) {++sharedCalls;return shared;}
 bool run() {
'''+route+'''
 return created;
 }
};
int main(){
 assert(CloakfoxCanonicalCanvasPolicy(true,true,true));
 assert(!CloakfoxCanonicalCanvasPolicy(false,true,true));
 assert(!CloakfoxCanonicalCanvasPolicy(true,false,true));
 assert(!CloakfoxCanonicalCanvasPolicy(true,true,false));
 Fixture protectedFailure;protectedFailure.mCanonicalCanvasBacking=true;
 assert(!protectedFailure.run());assert(protectedFailure.basicCalls==1&&protectedFailure.acceleratedCalls==0&&protectedFailure.sharedCalls==0);
 Fixture protectedSuccess;protectedSuccess.mCanonicalCanvasBacking=true;protectedSuccess.basic=true;
 assert(protectedSuccess.run());assert(protectedSuccess.basicCalls==1&&protectedSuccess.acceleratedCalls==0&&protectedSuccess.sharedCalls==0);
 Fixture native;assert(native.run());assert(native.acceleratedCalls==1&&native.basicCalls==0);
 Fixture nativeFallback;nativeFallback.accelerated=false;nativeFallback.shared=false;nativeFallback.basic=true;
 assert(nativeFallback.run());assert(nativeFallback.acceleratedCalls==1&&nativeFallback.sharedCalls==1&&nativeFallback.basicCalls==1);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'policy.cpp';p.write_text(program);exe=Path(d)/'policy'
   subprocess.run(['c++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),'-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
 def test_borrowed_targets_must_stay_basic_and_skia(self):
  s=NATIVE.read_text()
  start=s.index('bool CanvasRenderingContext2D::BorrowTarget(')
  body=s[s.index('{',start)+1:s.index('  if (!mBufferProvider->PreservesDrawingState()',start)]
  harness=r'''#include <cassert>
struct IntRect {};
enum class BackendType { SKIA, OTHER };
struct Target { bool valid=true;BackendType backend=BackendType::SKIA;bool IsValid(){return valid;}BackendType GetBackendType(){return backend;} };
struct Ref {Target* p=nullptr;Ref&operator=(Target*t){p=t;return *this;}explicit operator bool()const{return p;}Target*operator->(){return p;}Target*forget(){auto*t=p;p=nullptr;return t;}};
struct Provider {bool refresh=false,accelerated=false,shared=false;int borrowed=0,returned=0;Target target;
 bool RequiresRefresh(){return refresh;}bool IsAccelerated(){return accelerated;}bool IsShared(){return shared;}
 Target*BorrowDrawTarget(const IntRect&){++borrowed;return &target;}void ReturnDrawTarget(Target*){++returned;}
};
struct Context {bool mCanonicalCanvasBacking=true;Provider provider;Provider*mBufferProvider=&provider;Ref mTarget;
 bool UseSoftwareRendering(){return false;}
 bool run(const IntRect&aPersistedRect={}) {
'''+body+r'''
 return true;
 }
};
int main(){
 Context good;assert(good.run());assert(good.provider.borrowed==1);
 Context shared;shared.provider.shared=true;assert(!shared.run());assert(shared.provider.borrowed==0);
 Context accelerated;accelerated.provider.accelerated=true;assert(!accelerated.run());assert(accelerated.provider.borrowed==0);
 Context other;other.provider.target.backend=BackendType::OTHER;assert(!other.run());assert(other.provider.returned==1&&!other.mTarget);
 Context invalid;invalid.provider.target.valid=false;assert(!invalid.run());assert(invalid.provider.returned==1);
 Context native;native.mCanonicalCanvasBacking=false;native.provider.target.backend=BackendType::OTHER;assert(native.run());
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'borrow.cpp';p.write_text(harness);exe=Path(d)/'borrow'
   subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
 def test_unused_context_captures_exact_owner_and_freezes_policy(self):
  s=NATIVE.read_text();name='void CanvasRenderingContext2D::CaptureCanonicalCanvasPolicy()'
  self.assertTrue(name in s,'creation capture not implemented')
  a=s.index('// Cloakfox canonical policy.');b=s.index('// End Cloakfox canonical policy.',a);policy=s[a:b]
  a=s.index(name);body=s[s.index('{',a)+1:s.index('\n}\n',a)]
  a=s.index('CanvasRenderingContext2D::SetContextOptions(');b=s.index('if (aOptions.isNullOrUndefined())',a)
  self.assertTrue('CaptureCanonicalCanvasPolicy();' in s[a:b],'unused context must capture before options early return')
  harness=r'''#include "json.hpp"
#include <cassert>
struct nsIPrincipal {bool system=false;struct Attributes {unsigned mUserContextId=7;}attrs;bool IsSystemPrincipal(){return system;}Attributes&OriginAttributesRef(){return attrs;}};
namespace StaticPrefs {bool enabled=true,requested=true;bool cloakfox_enabled(){return enabled;}bool cloakfox_experimental_canvas_pipeline(){return requested;}}
namespace CloakfoxSiteSeed {nlohmann::json cfg0={{"canvas:canonical_2d",false}},cfg7={{"canvas:canonical_2d",true}};nlohmann::json ExactConfig(unsigned id){return id==7?cfg7:cfg0;}}
'''+policy+r'''
#include "CanvasPrivacy.h"
#include <array>
#include <optional>
namespace gfx=mozilla::gfx;
using gfx::CanvasPixelSource;
namespace CloakfoxSiteSeed {std::optional<std::array<uint64_t,2>> OwnerKey(unsigned id,void*){return std::array<uint64_t,2>{id+11,29};}}
struct Offscreen {bool CanonicalCanvasBackingPolicy(){return false;}gfx::CanvasPrivacyMetadata CanvasPrivacyPolicy(){return {};}};
struct Context {gfx::CanvasPrivacyMetadata mCanvasPrivacyPolicy;Offscreen*mOffscreenCanvas=nullptr;void*GetCookieJarSettings(){return nullptr;}uint32_t mCanvasPixelSources=0;bool mCanonicalCanvasPolicyCaptured=false,mCanonicalCanvasBacking=false;nsIPrincipal principal;bool absent=false;nsIPrincipal*PrincipalOrNull(){return absent?nullptr:&principal;}
 void capture(){
'''+body+r'''
 }
};
int main(){
 Context owned;owned.capture();assert(owned.mCanonicalCanvasBacking);assert(owned.mCanvasPixelSources==2);
 CloakfoxSiteSeed::cfg7["canvas:canonical_2d"]=false;owned.capture();assert(owned.mCanonicalCanvasBacking);
 StaticPrefs::requested=false;Context updated;updated.capture();assert(!updated.mCanonicalCanvasBacking);assert(updated.mCanvasPixelSources==0);StaticPrefs::requested=true;
 CloakfoxSiteSeed::cfg7["canvas:canonical_2d"]=true;
 Context defaultOwner;defaultOwner.principal.attrs.mUserContextId=0;defaultOwner.capture();assert(defaultOwner.mCanonicalCanvasBacking);
 Context chrome;chrome.principal.system=true;chrome.capture();assert(!chrome.mCanonicalCanvasBacking);
 Context missing;missing.absent=true;missing.capture();assert(!missing.mCanonicalCanvasBacking);
 StaticPrefs::enabled=false;Context masterOff;masterOff.capture();assert(!masterOff.mCanonicalCanvasBacking);
 StaticPrefs::enabled=true;masterOff.capture();assert(!masterOff.mCanonicalCanvasBacking);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'capture.cpp';p.write_text(harness);exe=Path(d)/'capture'
   subprocess.run(['c++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),'-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
