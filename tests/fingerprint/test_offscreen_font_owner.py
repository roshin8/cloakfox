"""Compile actual Offscreen creation capture; identity precedes unused handoff."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
class OffscreenFontOwner(unittest.TestCase):
 def test_actual_capture_has_own_container_and_frozen_font_seed(self):
  source=(ROOT/'firefox-src/dom/canvas/OffscreenCanvas.cpp').read_text()
  header=(ROOT/'firefox-src/dom/canvas/OffscreenCanvas.h').read_text()
  self.assertIn('GetCloakfoxFontIdentity() const override',header)
  a=source.index('void OffscreenCanvas::CaptureCanvasPrivacyPolicy()')
  b=source.index('\nOffscreenCanvas::~OffscreenCanvas()',a)
  capture=source[a:b]
  program=r'''
#include <optional>
#include <array>
#include <cstdint>
#include <cassert>
namespace StaticPrefs {bool enabled=true,full=true;bool cloakfox_enabled(){return enabled;}bool cloakfox_experimental_canvas_pipeline(){return full;}}
struct Principal {bool system=false;struct Attributes {unsigned mUserContextId=7;} attrs;bool IsSystemPrincipal(){return system;}const Attributes& OriginAttributesRef(){return attrs;}};
using nsIPrincipal=Principal;
struct Global {Principal principal;Principal* PrincipalOrNull(){return &principal;}};
namespace gfx {enum class CanvasPixelSource:unsigned{Unknown=1};constexpr unsigned kCanvasPrivacyVersion=1;struct CanvasPrivacyMetadata{unsigned version=0,ucid=0;uint64_t hi=0,lo=0;unsigned source=1;};}
namespace CloakfoxSiteSeed {bool ready=true;uint32_t Derive(unsigned id,const char*,unsigned* jar){return id*100+*jar;}std::optional<std::array<uint64_t,2>>OwnerKey(unsigned,unsigned*){if(!ready)return {};return std::array<uint64_t,2>{1,2};}}
template<typename T>std::optional<T>Some(T value){return value;}
struct OffscreenCanvas {Global global;unsigned jar=42;std::optional<uint64_t>mCloakfoxFontIdentity;bool mCanonicalCanvasBackingPolicy=false;gfx::CanvasPrivacyMetadata mCanvasPrivacyPolicy;Global*GetRelevantGlobal(){return &global;}unsigned*GetCookieJarSettings(){return &jar;}void CaptureCanvasPrivacyPolicy();};
'''+capture+r'''
int main(){
 OffscreenCanvas a;a.CaptureCanvasPrivacyPolicy();
 assert(a.mCloakfoxFontIdentity==((uint64_t(7)<<32)|742));
 const auto transferred=a.mCloakfoxFontIdentity;
 a.global.principal.attrs.mUserContextId=99;a.jar=1;
 assert(a.mCloakfoxFontIdentity==transferred);
 OffscreenCanvas unready;CloakfoxSiteSeed::ready=false;unready.CaptureCanvasPrivacyPolicy();
 assert(unready.mCloakfoxFontIdentity==transferred);
 assert(unready.mCanonicalCanvasBackingPolicy);
 StaticPrefs::enabled=false;OffscreenCanvas off;off.CaptureCanvasPrivacyPolicy();assert(!off.mCloakfoxFontIdentity);
 StaticPrefs::enabled=true;OffscreenCanvas chrome;chrome.global.principal.system=true;chrome.CaptureCanvasPrivacyPolicy();assert(!chrome.mCloakfoxFontIdentity);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'test.cpp';p.write_text(program);exe=Path(d)/'test'
   subprocess.run(['c++','-std=c++17',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
  self.assertIn('cloneData->mCloakfoxFontIdentity = mCloakfoxFontIdentity;',source)
  self.assertIn('wc->mCloakfoxFontIdentity = aData->mCloakfoxFontIdentity;',source)
if __name__=='__main__':unittest.main()
