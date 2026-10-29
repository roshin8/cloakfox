"""Compile the exact production reference registry, admission and descriptor checks."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class ReferenceNative(unittest.TestCase):
 def test_owner_independent_registry_and_native_admission(self):
  source=r'''
#include "CloakfoxGPUProfileCore.hpp"
#include "json.hpp"
#include <cassert>
int main(){
 using namespace CloakfoxGPUProfile;
 using namespace CloakfoxGPUReference;
 assert(!Lookup(0x8000)&&!Lookup(0x8005)&&!Lookup(0xffff));
 for(const auto& reference:kProfiles){
  if(Observed(reference.code))continue;
  auto config=nlohmann::json::parse("{}");config["webGl:renderer"]=reference.renderer;config["webGl:vendor"]=reference.vendor;config["navigator.platform"]=reference.family==1?"MacIntel":"Win32";config["navigator.oscpu"]=reference.family==1?"Intel Mac OS X 10.15":"Windows NT 10.0; Win64; x64";
  auto eligible=EligibleReferences(config,reference.family);assert(eligible==std::vector<uint32_t>{reference.code});
  config["webGl:parameters"]={{"3379",1}};config["webGl2:parameters"]={{"35375",1}};
  assert(EligibleReferences(config,reference.family)==eligible); // BF tables are not manual ceilings.
  config["rendering:gpu_reference:ceilings"]={{"webgl",{{"3379",1}}}};assert(EligibleReferences(config,reference.family).empty());config.erase("rendering:gpu_reference:ceilings");
  auto descriptor=nlohmann::json::parse(R"({"version":3,"mode":"reference","source":"6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936","privacyPolicy":"reference-protected-v1","adaptation":"Firefox146-to159:canonical-renderer;deny-debug-shaders-and-timers;omit-version-specific-provoking-vertex;WebGPU-canonical-device","catalog":[]})");
  descriptor["catalog"].push_back(reference.code);assert(ReferenceDescriptorMatches(descriptor,eligible));
  descriptor["catalog"].push_back(reference.code);assert(!ReferenceDescriptorMatches(descriptor,eligible));descriptor["catalog"].erase(1);
  descriptor["source"]="forged";assert(!ReferenceDescriptorMatches(descriptor,eligible));
  for(bool gl2:{false,true}){
   auto p=Decode(reference.code,gl2);assert(p);assert(p->bufferBytes==268435456&&p->storageBytes==134217728); // WebGPU is canonical, not historical source data.
   auto c=ForContext(reference.code,gl2);assert(c&&c->precisionCount==12);
   assert(Cap(reference.code,gl2,3408)==4);assert(ReferenceScalarSupported(*Find(reference.code,gl2,3408),4));
   assert(!HasExtension(*c,"WEBGL_debug_shaders")&&!HasExtension(*c,"EXT_disjoint_timer_query")&&!HasExtension(*c,"WEBGL_provoking_vertex"));
   for(size_t i=0;i<c->parameterCount;i++){
    const auto& requirement=c->parameters[i];if(requirement.components!=1)continue;
    assert(ReferenceScalarSupported(requirement,requirement.lo));
    if(requirement.pname==35076)assert(!ReferenceScalarSupported(requirement,requirement.lo+1));
    else assert(!ReferenceScalarSupported(requirement,requirement.lo-1));
   }
   for(size_t i=0;i<c->precisionCount;i++){
    const auto& required=c->precision[i];assert(ReferencePrecisionSupported(required,required.rangeMin,required.rangeMax,required.precision));
    assert(!ReferencePrecisionSupported(required,required.rangeMin-1,required.rangeMax,required.precision));
   }
   if(gl2){assert(Cap(reference.code,true,36348)*4==Cap(reference.code,true,35659));assert(Cap(reference.code,true,35659)==Cap(reference.code,true,37154));assert(Cap(reference.code,true,35659)==Cap(reference.code,true,37157));}
  }
  config["navigator.platform"]="Linux x86_64";assert(EligibleReferences(config,reference.family).empty());
  config["webGl:vendor"]="borrowed";assert(EligibleReferences(config,reference.family).empty());
 }
 assert(Decode(0x101)&&Decode(0x402)&&!Decode(0x8005));
 assert(Decode(32769,false)->fragmentInputs!=Decode(32769,true)->fragmentInputs);
}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.cpp').write_text(source)
   result=subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
