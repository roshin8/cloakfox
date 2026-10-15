"""Nested native image render scopes reject observed fallback producers."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class ProducerAudit(unittest.TestCase):
 def test_real_scope(self):
  self.assertTrue((ROOT/'additions/cloakcfg/CanvasProducerAudit.hpp').exists(),'actual producer audit scope absent')
  code=r'''#include <cassert>
#include <thread>
#include "CanvasProducerAudit.hpp"
using Cloakfox::CanvasProducerAudit;
int main(){
 CanvasProducerAudit::Observe(false,8);
 {CanvasProducerAudit outer;CanvasProducerAudit::Observe(true,4);{CanvasProducerAudit inner;CanvasProducerAudit::Observe(true,16);assert(inner.Succeeded());}assert(outer.Succeeded()&&outer.Sources()==20);}
 {CanvasProducerAudit outer;{CanvasProducerAudit inner;CanvasProducerAudit::Observe(false,8);assert(!inner.Succeeded());}assert(!outer.Succeeded());}
 {CanvasProducerAudit clean;std::thread other([]{CanvasProducerAudit bad;CanvasProducerAudit::Observe(false,8);assert(!bad.Succeeded());});other.join();assert(clean.Succeeded()&&clean.Sources()==0);}
 {CanvasProducerAudit owner(7,11,13);{CanvasProducerAudit foreign(7,17,19);}assert(!owner.Succeeded());}
 {CanvasProducerAudit owner(7,11,13);CanvasProducerAudit::Observe(true,2,7,11,13);assert(owner.Succeeded());CanvasProducerAudit::Observe(true,2,7,17,19);assert(!owner.Succeeded());}
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'audit.cpp';p.write_text(code);exe=Path(d)/'audit';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'additions/cloakcfg'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
