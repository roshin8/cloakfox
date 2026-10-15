"""Execute the native profile decoder used by context creation/validation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class Profiles(unittest.TestCase):
 def test_all_families_are_bounded_and_owner_variation_changes_real_limits(self):
  source=r'''
#include "CloakfoxGPUProfileCore.hpp"
#include <cassert>
int main(){
 using namespace CloakfoxGPUProfile;
 assert(!IdentityMessage(0,"(https,example.com)").empty());
 assert(IdentityMessage(0,"(https,example.com)")==IdentityMessage(0,"(https,example.com,f)"));
 assert(IdentityMessage(0,"invalid").empty());
 assert(IdentityMessage(1,"(https,example.com)")!=IdentityMessage(1,"(https,other.com)"));
 assert(IdentityMessage(1,"(https,example.com)")!=CloakfoxSiteSeed::Message("canvas:seed",1,"(https,example.com)"));
 for(unsigned family=1;family<=4;family++)for(unsigned variant=0;variant<256;variant++){
  auto p=Decode((family<<8)|variant);assert(p);
  assert(p->texture>=2048&&p->texture<=8192);
  assert(p->vertexUniforms>=256&&p->vertexUniforms<=511);
  assert(p->fragmentUniforms>=224&&p->fragmentUniforms<=479);
  assert(Decode((family<<8)|(variant^1))->vertexUniforms!=p->vertexUniforms);
 }
 assert(!Decode(0));assert(!Decode(0x500));assert(!Decode(0x10000));
 assert(Family("Apple M1, or similar")==1);assert(Family("Intel UHD")==2);
 assert(Family("AMD Radeon")==3);assert(Family("NVIDIA GTX 980")==4);
 assert(Family("SwiftShader")==0);assert(Family("llvmpipe")==0);
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'test.cpp').write_text(source)
   subprocess.run(['clang++','-std=c++17','-I'+str(ROOT/'additions/cloakcfg'),str(p/'test.cpp'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
   subprocess.run([str(p/'test')],check=True)
