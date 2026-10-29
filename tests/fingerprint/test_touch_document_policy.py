"""Compile the actual TouchEvent docshell policy and prove privileged callers never read persona IPC."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class TouchDocumentPolicy(unittest.TestCase):
 def test_exact_native_helper_and_preference_branch(self):
  source=(ROOT/'firefox-src/dom/events/TouchEvent.cpp').read_text()
  helper=re.search(r'static std::optional<uint32_t> CloakfoxContentTouchPoints\(nsIDocShell\* aDocShell\) \{.*?\n\}',source,re.S)
  self.assertIsNotNone(helper,'Privileged touch eligibility must be gated by the actual document principal before persona reads')
  start=source.index('bool TouchEvent::PrefEnabled(nsIDocShell* aDocShell)');end=source.index('\n}',start)+2
  body=source[start:end]
  program=r'''
#include "json.hpp"
#include <cassert>
#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#define MOZ_DIAGNOSTIC_ASSERT(x) assert(x)
#define MOZ_WIDGET_COCOA 1
bool NS_IsMainThread(){return true;}bool XRE_IsParentProcess(){return true;}
static unsigned reads=0,lastOwner=999;static bool master=true,rfp=false,platformTouch=true;static int nativePref=1;
std::unordered_map<uint32_t,std::string> configs;
std::string CloakConfigOverlay_Get(uint32_t owner){reads++;lastOwner=owner;return configs[owner];}
namespace mozilla {
struct StaticPrefs {static bool cloakfox_enabled(){return master;}static int dom_w3c_touch_events_enabled(){return nativePref;}};
namespace dom {
enum class TouchEventsOverride {None,Enabled,Disabled};
struct Principal {bool system;bool IsSystemPrincipal()const{return system;}};
struct Document {Principal* principal;Principal* NodePrincipal()const{return principal;}};
struct Attributes {uint32_t mUserContextId;};
struct BrowsingContext {bool chrome;Attributes attrs;TouchEventsOverride override=TouchEventsOverride::None;bool IsChrome()const{return chrome;}Attributes& OriginAttributesRef(){return attrs;}TouchEventsOverride TouchEventsOverride()const{return override;}};
struct nsIDocShell {Document* doc;BrowsingContext* context;Document* GetExtantDocument(){return doc;}BrowsingContext* GetBrowsingContext(){return context;}};
struct TouchEvent {static bool PrefEnabled(nsIDocShell*);};
struct RFPTarget {static constexpr int PointerEvents=1;};
struct nsContentUtils {static bool ShouldResistFingerprinting(nsIDocShell*,int){return rfp;}static void InitializeTouchEventTable(){}};
struct CrashReporter {struct Annotation {static constexpr int HasDeviceTouchScreen=1;};static void RecordAnnotationBool(int,bool){}};
static bool PlatformSupportsTouch(){return platformTouch;}
'''+helper.group()+'\n'+body+r'''
}}
int main(){
 using namespace mozilla::dom;
 Principal system{true},content{false};Document systemDoc{&system},contentDoc{&content};
 BrowsingContext chrome{true,{0}},owner7{false,{7}},owner0{false,{0}};
 nsIDocShell settings{&systemDoc,&owner7},browser{&systemDoc,&chrome},chromeTree{&contentDoc,&chrome},web{&contentDoc,&owner7},defaultWeb{&contentDoc,&owner0},uncreated{nullptr,&owner7},noOwner{&contentDoc,nullptr};
 configs[0]=R"({"navigator:maxTouchPoints":9})";configs[7]=R"({"navigator:maxTouchPoints":0})";
 for(auto* shell:{&settings,&browser,&chromeTree,&uncreated}){
  reads=0;nativePref=1;assert(TouchEvent::PrefEnabled(shell));assert(reads==0);
  nativePref=0;assert(!TouchEvent::PrefEnabled(shell));assert(reads==0);
 }
 reads=0;nativePref=1;assert(TouchEvent::PrefEnabled(nullptr));assert(reads==0);
 assert(!TouchEvent::PrefEnabled(&web)&&reads==1&&lastOwner==7); // own denial, no owner0/native fallback
 configs[7]=R"({"navigator:maxTouchPoints":3})";nativePref=0;assert(TouchEvent::PrefEnabled(&web)&&lastOwner==7);
 assert(TouchEvent::PrefEnabled(&defaultWeb)&&lastOwner==0); // exact default owner is not ambient context999
 for(const auto* malformed:{"{}","null",R"({"navigator:maxTouchPoints":-1})",R"({"navigator:maxTouchPoints":"3"})",R"({"navigator:maxTouchPoints":4294967296})","corrupt"}){
  configs[7]=malformed;nativePref=1;assert(!TouchEvent::PrefEnabled(&web));
 }
 reads=0;nativePref=1;assert(!TouchEvent::PrefEnabled(&noOwner));assert(reads==0);
 owner7.override=TouchEventsOverride::Enabled;reads=0;assert(TouchEvent::PrefEnabled(&web)&&reads==0);
 owner7.override=TouchEventsOverride::Disabled;assert(!TouchEvent::PrefEnabled(&web)&&reads==0);owner7.override=TouchEventsOverride::None;
 master=false;reads=0;assert(TouchEvent::PrefEnabled(&web)&&reads==0);master=true;
}
'''
  # Match the Gecko method name without colliding with the test enum's name.
  program=program.replace('TouchEventsOverride TouchEventsOverride()const','mozilla::dom::TouchEventsOverride TouchEventsOverride()const')
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cpp').write_text(program)
   result=subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
