"""Imported markers cannot certify a context's earlier native rendering."""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def test_actual_snapshot_certificate_retains_native_backing_failure():
 s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text();a=s.index('CanvasRenderingContext2D::GetOptimizedSnapshot(');a=s.index('  auto policy =',a);b=s.index('  return retSurface.forget();',a);body=s[a:b]
 cp=(ROOT/'firefox-src/gfx/2d/CanvasPrivacy.cpp').read_text();core=cp[cp.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):cp.index('CanvasPrivacyMetadata MergeCanvasPrivacyMetadata(')]
 code=r'''#include <cassert>
#include "CanvasPrivacy.h"
namespace gfx=mozilla::gfx;
using gfx::CanvasPixelSource;
namespace mozilla::gfx {'''+core+r'''
void SetCanvasPrivacyMetadata(CanvasPrivacyMetadata& out,const CanvasPrivacyMetadata& p){out=p;}}
gfx::CanvasPrivacyMetadata snapshot(bool mCanonicalCanvasBacking,uint32_t mCanvasPixelSources){gfx::CanvasPrivacyMetadata mCanvasPrivacyPolicy{1,7,11,13,1},retSurface;
'''+body+r'''
return retSurface;}
int main(){for(auto sources:{2u,2u|4u,2u|64u|512u,2u|16u|1024u}){assert(!gfx::CanExtractCanonicalCanvasPixels(snapshot(false,sources)));assert(gfx::CanExtractCanonicalCanvasPixels(snapshot(true,sources)));}assert(!gfx::CanExtractCanonicalCanvasPixels(snapshot(true,3)));}
'''
 with tempfile.TemporaryDirectory()as d:
  p=Path(d)/'test.cpp';p.write_text('#include <initializer_list>\n'+code);exe=Path(d)/'test';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)

def test_external_print_target_cannot_inherit_canvas_backing_proof():
 s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text();a=s.index('CanvasRenderingContext2D::InitializeWithDrawTarget(');b=s.index('\n}',a);body=s[a:b]
 assert 'mCanvasPixelSources |= uint32_t(CanvasPixelSource::Unknown);' in body
