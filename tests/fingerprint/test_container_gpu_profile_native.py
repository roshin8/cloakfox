"""Execute the native profile decoder used by context creation/validation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class Profiles(unittest.TestCase):
 def test_all_families_decode_only_whole_catalog_profiles(self):
  source=r'''
#include "CloakfoxGPUProfileCore.hpp"
#include "json.hpp"
#include <cassert>
int main(){
 using namespace CloakfoxGPUProfile;
 assert(!IdentityMessage(0,"(https,example.com)").empty());
 assert(IdentityMessage(0,"(https,example.com)")==IdentityMessage(0,"(https,example.com,f)"));
 assert(IdentityMessage(0,"invalid").empty());
 assert(IdentityMessage(1,"(https,example.com)")!=IdentityMessage(1,"(https,other.com)"));
 assert(IdentityMessage(1,"(https,example.com)")!=CloakfoxSiteSeed::Message("canvas:seed",1,"(https,example.com)"));
 for(unsigned family=1;family<=4;family++){
  for(unsigned id=1;id<=2;id++){
   auto p=Decode((family<<8)|id);assert(p);assert(p->id==id);
   assert(p->texture==4096||p->texture==8192);
   assert((p->texture&(p->texture-1))==0);
   assert(p->vertexUniforms==(id==1?256:1024));
   assert(p->fragmentUniforms==(id==1?224:1024));
   assert(p->bufferBytes==(id==1?256ULL:512ULL)*1024*1024);
   assert(p->storageBytes==128ULL*1024*1024);
   assert(p->vertexTexUnits+p->fragmentTexUnits<=p->combinedTexUnits);
  }
  for(unsigned id=3;id<256;id++)assert(!Decode((family<<8)|id));
  assert(!Decode(family<<8));
 }
 assert(!Decode(0));assert(!Decode(0x500));assert(!Decode(0x10000));
 assert(Family("Apple M1, or similar")==1);assert(Family("Intel UHD")==2);
 assert(Family("AMD Radeon")==3);assert(Family("NVIDIA GTX 980")==4);
 assert(Family("SwiftShader")==0);assert(Family("llvmpipe")==0);
 auto cfg=nlohmann::json::object();assert(EligibleCatalog(cfg,1)==std::vector<uint32_t>({1,2}));
 cfg["webGl:parameters"]={{"3379",4096}};assert(EligibleCatalog(cfg,1)==std::vector<uint32_t>({1}));
 cfg["webGl:parameters"]["3379"]=4095;assert(EligibleCatalog(cfg,1).empty());
 cfg["webGl:parameters"]={{"3386",{4096,4096}}};assert(EligibleCatalog(cfg,4)==std::vector<uint32_t>({1}));
 cfg["webGl:parameters"]["3386"]={4096,100};assert(EligibleCatalog(cfg,4).empty());
 auto legacy=nlohmann::json::parse(R"({"version":1})");assert(DescriptorCatalogMatches(legacy,{1,2}));
 auto modern=nlohmann::json::parse(R"({"version":2,"catalog":[1,2]})");assert(DescriptorCatalogMatches(modern,{1,2}));
 assert(!DescriptorCatalogMatches(modern,{1}));modern["catalog"]={1,1};assert(!DescriptorCatalogMatches(modern,{1,2}));
 assert(!DescriptorCatalogMatches(legacy,{}));legacy["catalog"]={1,2};assert(!DescriptorCatalogMatches(legacy,{1,2}));
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'test.cpp').write_text(source)
   subprocess.run(['clang++','-std=c++17','-I'+str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
   subprocess.run([str(p/'test')],check=True)
