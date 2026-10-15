"""Execute the drawImage flag expression; canonical SVG needs audited surface."""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def test_actual_svg_surface_flags():
 s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text();a=s.index('uint32_t sfeFlags = nsLayoutUtils::SFE_WANT_FIRST_FRAME_IF_IMAGE',s.index('void CanvasRenderingContext2D::DrawImage'));b=s.index('\n    if (offscreenCanvas)',a);body=s[a:b]
 code='''#include <cstdint>
#include <cassert>
namespace nsLayoutUtils {enum {SFE_WANT_FIRST_FRAME_IF_IMAGE=1,SFE_NO_RASTERIZING_VECTORS=2,SFE_ALLOW_UNCROPPED_UNSCALED=4};}
uint32_t flags(bool mCanonicalCanvasBacking){'''+body+'''return sfeFlags;}
int main(){assert(flags(false)==7);assert(flags(true)==5);}
'''
 with tempfile.TemporaryDirectory()as d:
  p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test';subprocess.run(['c++',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
