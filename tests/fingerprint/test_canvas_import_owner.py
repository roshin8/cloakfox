"""Imported canvas records may never silently acquire destination ownership."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class ImportOwner(unittest.TestCase):
 def test_actual_accumulation_policy(self):
  s=(ROOT/'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text();a=s.index('void CanvasRenderingContext2D::AccumulateCanvasSource(');b=s.index('\n}',a)+2
  body=s[a:b].replace('CanvasRenderingContext2D::','Context::')
  cp=(ROOT/'firefox-src/gfx/2d/CanvasPrivacy.cpp').read_text()
  core=cp[cp.index('CanvasPrivacyMetadata NormalizeCanvasPrivacyMetadata('):cp.index('CanvasPrivacyMetadata MergeCanvasPrivacyMetadata(')]
  body='namespace mozilla::gfx{'+core+'}\n'+body
  a=s.index('void CanvasRenderingContext2D::AccumulateCanvasFilterSources(');b=s.index('\n}',a)+2
  body+='\n'+s[a:b].replace('CanvasRenderingContext2D::','Context::')
  use=s[s.index('~AdjustedTargetForFilter()'):s.index('DrawTarget* DT()')]
  self.assertLess(use.index('AccumulateCanvasFilterSources()'),use.index('RenderFilterDescription('))
  fixture=r'''#include <cassert>
#include <vector>
#include "CanvasPrivacy.h"
namespace gfx=mozilla::gfx;
using gfx::CanvasPixelSource;
namespace mozilla::gfx{class SourceSurface{public:CanvasPrivacyMetadata metadata;};CanvasPrivacyMetadata GetCanvasPrivacyMetadata(SourceSurface*s){return s?s->metadata:CanvasPrivacyMetadata{};}}
struct Context{gfx::CanvasPrivacyMetadata mCanvasPrivacyPolicy{1,7,11,13,2};uint32_t mCanvasPixelSources=2;void AccumulateCanvasSource(gfx::SourceSurface*);void AccumulateCanvasFilterSources();struct State{std::vector<gfx::SourceSurface*>filterAdditionalImages;}state;State&CurrentState(){return state;}};
'''+body+r'''
int main(){gfx::SourceSurface same;same.metadata={1,7,11,13,2};Context a;a.AccumulateCanvasSource(&same);assert(a.mCanvasPixelSources==2);assert(a.mCanvasPrivacyPolicy.ownerHi==11);
gfx::SourceSurface foreign;foreign.metadata={1,8,17,19,2};Context b;b.AccumulateCanvasSource(&foreign);assert(b.mCanvasPixelSources&1);assert(b.mCanvasPrivacyPolicy.ownerHi==11);
gfx::SourceSurface unowned;Context c;c.AccumulateCanvasSource(&unowned);assert(c.mCanvasPixelSources&1);
Context d;d.AccumulateCanvasSource(nullptr);assert(d.mCanvasPixelSources&1);
Context filtered;filtered.state.filterAdditionalImages={&same,&foreign};filtered.AccumulateCanvasFilterSources();assert(filtered.mCanvasPixelSources&1);
gfx::SourceSurface cpu,gpu;cpu.metadata={1,7,11,13,64|512};gpu.metadata={1,7,11,13,64};Context laundering;laundering.AccumulateCanvasSource(&cpu);assert(!(laundering.mCanvasPixelSources&1));laundering.AccumulateCanvasSource(&gpu);assert(laundering.mCanvasPixelSources&1);
gfx::SourceSurface decode,color;decode.metadata={1,7,11,13,2|32|128};color.metadata={1,7,11,13,2|32|256};Context media;media.AccumulateCanvasSource(&decode);media.AccumulateCanvasSource(&color);assert(media.mCanvasPixelSources&1);
}
'''
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'import.cpp';p.write_text(fixture);exe=Path(d)/'import';subprocess.run(['c++','-std=c++17','-I',str(ROOT/'firefox-src/gfx/2d'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
