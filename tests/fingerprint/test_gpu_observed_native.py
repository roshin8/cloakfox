"""Compile production observed admission and descriptor policy."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class ObservedNative(unittest.TestCase):
 def test_observed_complete_pairs_and_strict_descriptor(self):
  source=r'''
#include "CloakfoxGPUProfileCore.hpp"
#include "json.hpp"
#include <cassert>
int main(){
 using namespace CloakfoxGPUProfile;using namespace CloakfoxGPUReference;
 for(const auto& p:kProfiles){
  nlohmann::json cfg={{"webGl:renderer",p.renderer},{"webGl:vendor",p.vendor},{"navigator.platform",std::string_view(p.os)=="mac"?"MacIntel":"Win32"},{"navigator.oscpu",std::string_view(p.os)=="mac"?"Intel Mac OS X 10.15":"Windows NT 10.0; Win64; x64"}};
  const auto selected=EligibleReferences(cfg,p.family,true);
  if(p.family==1){assert(selected.empty());continue;}
  if(!Observed(p.code)){assert(selected==std::vector<uint32_t>{p.code+4096});continue;}
  assert(selected==std::vector<uint32_t>{p.code});assert(Decode(p.code));
  assert(Cap(p.code,true,34045)==2&&Cap(p.code,true,36203)==0xfffffffe);
  assert(ObservedLodBias(p.code)==2);for(bool gl2:{false,true})assert(ObservedStencilMask(p.code,gl2)==0x7fffffff);
  nlohmann::json d={{"version",4u},{"mode","observed-reference"},{"source",kSource},{"privacyPolicy","observed-reference-v1"},{"adaptation","observed:full32;native-stencil;typed-lod-bias;fixed-restart-index;deny-debug-shaders-and-timers;omit-version-specific-provoking-vertex;WebGPU-canonical-device"},{"catalog",selected}};
  assert(ObservedDescriptorMatches(d,selected));assert(!ReferenceDescriptorMatches(d,selected));
  d["catalog"][0]=p.code-4096;assert(!ObservedDescriptorMatches(d,selected));d["catalog"]=selected;
  d["source"]="wrong";assert(!ObservedDescriptorMatches(d,selected));d["source"]=kSource;
  d["version"]=3u;assert(!ObservedDescriptorMatches(d,selected));d["version"]=4u;
  d["privacyPolicy"]="reference-protected-v1";assert(!ObservedDescriptorMatches(d,selected));
  cfg["rendering:gpu_reference:ceilings"]={{"webgl2",{{"34045",1}}}};assert(EligibleReferences(cfg,p.family,true).empty());
 }
 assert(!Observed(32770)&&ObservedStencilMask(32770,true)==0&&ObservedLodBias(32770)==0);
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cpp').write_text(source)
   result=subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   subprocess.run([str(p/'test')],check=True)
