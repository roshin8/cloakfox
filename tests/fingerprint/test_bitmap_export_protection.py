"""Compile the real bitmap serializer's extraction decision with real provenance."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class BitmapExport(unittest.TestCase):
 def test_native_export_decision_rejects_unknown_zero_and_foreign_proof(self):
  s=(ROOT/'firefox-src/dom/canvas/ImageBitmapRenderingContext.cpp').read_text()
  self.assertIn('// Cloakfox bitmap export policy.',s,'bitmap serializer has no extraction protection')
  policy=s[s.index('// Cloakfox bitmap export policy.'):s.index('// End Cloakfox bitmap export policy.')]
  core=(ROOT/'additions/gfx/2d/CanvasPrivacy.cpp').read_text();core=core[core.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):core.index('void AddCanvasPixelSource(')]
  source='#include <cassert>\n#include "CanvasPrivacy.h"\nnamespace gfx=mozilla::gfx;\nnamespace mozilla::gfx{'+core+'}\n'+policy+r'''
int main(){using namespace gfx;using E=CloakfoxBitmapExtraction;
 CanvasPrivacyMetadata own{1,7,11,13,2},other{1,8,17,19,2},unknown{},host=own;host.sources|=8;
 assert(CloakfoxBitmapExportPolicy(true,true,true,unknown,own,0)==E::Refuse);
 assert(CloakfoxBitmapExportPolicy(true,true,true,unknown,own,42)==E::Noise);
 assert(CloakfoxBitmapExportPolicy(true,true,true,host,own,42)==E::Noise);
 assert(CloakfoxBitmapExportPolicy(true,true,true,other,own,42)==E::Noise);
 assert(CloakfoxBitmapExportPolicy(true,true,true,other,own,0)==E::Refuse);
 assert(CloakfoxBitmapExportPolicy(true,true,true,own,own,0)==E::Canonical);
 CanvasPrivacyMetadata raster{0,0,0,0,16|1024};
 assert(CloakfoxBitmapExportPolicy(true,true,true,raster,own,0)==E::Canonical);
 assert(CloakfoxBitmapExportPolicy(true,true,false,unknown,own,42)==E::Noise);
 assert(CloakfoxBitmapExportPolicy(true,true,false,unknown,own,0)==E::Native);
 assert(CloakfoxBitmapExportPolicy(false,true,true,unknown,own,42)==E::Native);
 assert(CloakfoxBitmapExportPolicy(true,false,true,unknown,own,42)==E::Native);
 auto site=own;site.ownerLo++;assert(CloakfoxBitmapExportPolicy(true,true,true,own,site,42)==E::Noise);
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'test.cpp').write_text(source);subprocess.run(['clang++','-std=c++17','-I'+str(ROOT/'additions/gfx/2d'),str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
