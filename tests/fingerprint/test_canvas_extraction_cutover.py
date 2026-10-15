"""Each legacy noise entry point must gate on the actual retained producer graph."""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def test_production_eligibility_and_all_readback_gates():
 s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text();a=s.index('bool CanvasRenderingContext2D::CanExtractCanonicalPixels() const');b=s.index('\n}',a)+2;method=s[a:b].replace('CanvasRenderingContext2D::','Context::')
 assert 'if (ret && !CanExtractCanonicalPixels())'in s
 assert 'if (!CanExtractCanonicalPixels())'in s
 g=(ROOT/'firefox-src/dom/canvas/ClientWebGLContext.cpp').read_text();assert 'if (buffer && !gfx::CanExtractCanonicalCanvasPixels(gpuPrivacyPolicy))'in g
 assert 'if (!gfx::CanExtractCanonicalCanvasPixels(gpuPrivacyPolicy))'in g
 assert g.index('const auto gpuPrivacyPolicy = GetCanvasPrivacyMetadata();',g.index('ClientWebGLContext::DoReadPixelsAsync()'))<g.index('gfx::CanExtractCanonicalCanvasPixels(gpuPrivacyPolicy) ? 0 :',g.index('ClientWebGLContext::DoReadPixelsAsync()'))
 cp=(ROOT/'firefox-src/gfx/2d/CanvasPrivacy.cpp').read_text();core=cp[cp.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):cp.index('CanvasPrivacyMetadata MergeCanvasPrivacyMetadata(')]
 code='''#include <cassert>
#include "CanvasPrivacy.h"
namespace gfx=mozilla::gfx;
namespace mozilla::gfx {'''+core+'''}
struct Context{bool mCanonicalCanvasBacking=true;gfx::CanvasPrivacyMetadata mCanvasPrivacyPolicy{1,7,11,13,1};uint32_t mCanvasPixelSources=2;bool CanExtractCanonicalPixels()const;};
'''+method+'''
int main(){Context c;assert(c.CanExtractCanonicalPixels());c.mCanvasPixelSources|=1;assert(!c.CanExtractCanonicalPixels());c.mCanvasPixelSources=2|64;assert(!c.CanExtractCanonicalPixels());c.mCanvasPixelSources|=512;assert(c.CanExtractCanonicalPixels());c.mCanonicalCanvasBacking=false;assert(!c.CanExtractCanonicalPixels());c.mCanonicalCanvasBacking=true;c.mCanvasPrivacyPolicy.ownerHi=c.mCanvasPrivacyPolicy.ownerLo=0;assert(!c.CanExtractCanonicalPixels());}
'''
 with tempfile.TemporaryDirectory()as d:
  p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)

def test_fullmode_unverified_unseeded_2d_readbacks_refuse_output():
 s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text()
 a=s.index('CanvasRenderingContext2D::GetImageBuffer(');b=s.index('CanvasRenderingContext2D::GetInputStream(',a)
 assert 'if (mCanonicalCanvasBacking && canvasSeed == 0) return nullptr;' in s[a:b]
 a=s.index('CanvasRenderingContext2D::GetImageDataArray(');body=s[a:]
 assert 'if (mCanonicalCanvasBacking && canvasSeed == 0) {\n      readback->Unmap();\n      return NS_ERROR_NOT_AVAILABLE;' in body
