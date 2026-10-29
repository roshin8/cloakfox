"""Execute the native manifest gate and packaging verifier for reference backend."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
class Manifest(unittest.TestCase):
 def test_native_gate_accepts_only_pinned_reference_patch_provenance(self):
  header=ROOT/'additions/cloakcfg/CloakfoxCanonicalBackend.hpp'
  self.assertTrue(header.exists(),'native reference-backend manifest gate missing')
  program=r'''
#include "CloakfoxCanonicalBackend.hpp"
#include <cassert>
int main(){using nlohmann::json;
 json legacy={{"rendererVersion",1}};assert(CloakfoxCanonicalBackend::ManifestVersionAllowed(legacy));
 json reference={{"rendererVersion",2},{"capacityProfile","reference-v1"},{"localPatches",json::object()}};
 for(const auto& p:CloakfoxCanonicalBackend::kPatches)reference["localPatches"][p.name]=p.sha256;
 assert(CloakfoxCanonicalBackend::ManifestVersionAllowed(reference));
 auto bad=reference;bad["localPatches"].erase("reference-capacity-angle.patch");assert(!CloakfoxCanonicalBackend::ManifestVersionAllowed(bad));
 bad=reference;bad["localPatches"]["reference-capacity-swiftshader.patch"]="changed";assert(!CloakfoxCanonicalBackend::ManifestVersionAllowed(bad));
 bad=reference;bad["localPatches"]["extra.patch"]="unreviewed";assert(!CloakfoxCanonicalBackend::ManifestVersionAllowed(bad));
 bad=reference;bad["capacityProfile"]="host-driver";assert(!CloakfoxCanonicalBackend::ManifestVersionAllowed(bad));
 for(const char* v:{"null","true","\"2\"","2.0","3","-1"}){bad=reference;bad["rendererVersion"]=json::parse(v);assert(!CloakfoxCanonicalBackend::ManifestVersionAllowed(bad));}
}
'''
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'case.cpp').write_text(program)
   subprocess.run(['clang++','-std=c++17','-I'+str(ROOT/'additions/cloakcfg'),str(p/'case.cpp'),'-o',str(p/'case')],check=True,capture_output=True,text=True)
   subprocess.run([str(p/'case')],check=True)
