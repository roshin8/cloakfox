"""Compile production optional glyph policy/math; runtime coverage is separate."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CanvasRenderPrivacy(unittest.TestCase):
    def test_strict_opt_in_and_bounded_deterministic_offsets(self):
        source = (ROOT / 'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text()
        self.assertTrue('static uint32_t CloakfoxGlyphPolicySeed(' in source,
                      'optional rendering policy has not been implemented')
        begin = source.index('static uint32_t CloakfoxGlyphPolicySeed(')
        end = source.index('void CanvasRenderingContext2D::CaptureGlyphPrivacyPolicy()', begin)
        helpers = source[begin:end]
        harness = r'''
int main() {
  auto cfg=nlohmann::json::object();
  assert(CloakfoxGlyphPolicySeed(cfg,111111)==0);
  for(auto bad : {R"(false)",R"(1)",R"("true")",R"(null)",R"({})"}) {
    cfg["canvas:render_privacy"]=nlohmann::json::parse(bad);
    assert(CloakfoxGlyphPolicySeed(cfg,111111)==0);
  }
  cfg["canvas:render_privacy"]=true;
  assert(CloakfoxGlyphPolicySeed(cfg,0)==0);
  assert(CloakfoxGlyphPolicySeed(cfg,111111)==111111);
  assert(CloakfoxGlyphOffset(0,0)==0 && CloakfoxGlyphOffset(0,1)==0);
  bool axisDiffers=false,seedDiffers=false;
  for(uint32_t seed=1;seed<100000;++seed) {
    auto x=CloakfoxGlyphOffset(seed,0), y=CloakfoxGlyphOffset(seed,1);
    assert(x==CloakfoxGlyphOffset(seed,0));
    assert(std::abs(x)>=0.0625 && std::abs(x)<0.125);
    assert(std::abs(y)>=0.0625 && std::abs(y)<0.125);
    axisDiffers |= x!=y;
    seedDiffers |= x!=CloakfoxGlyphOffset(seed+1024,0);
  }
  assert(axisDiffers && seedDiffers);
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            cpp = Path(temporary) / 'glyph.cpp'
            exe = Path(temporary) / 'glyph'
            cpp.write_text('#include "json.hpp"\n#include <cassert>\n#include <cstdint>\n#include <cmath>\n' + helpers + harness)
            subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-I',str(ROOT/'additions/cloakcfg'),str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_policy_captured_before_context_options_can_return(self):
        source = (ROOT / 'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text()
        begin = source.index('CanvasRenderingContext2D::SetContextOptions(')
        end = source.index('UniquePtr<uint8_t[]> CanvasRenderingContext2D::GetImageBuffer(', begin)
        body = source[begin:end]
        self.assertTrue('CaptureGlyphPrivacyPolicy();' in body,
                        'unused contexts must capture policy during initialization')
        self.assertLess(body.index('CaptureGlyphPrivacyPolicy();'),
                        body.index('if (aOptions.isNullOrUndefined())'))

    def test_rendering_addition_does_not_replace_extraction_or_metrics(self):
        source = (ROOT / 'firefox-src/dom/canvas/CanvasRenderingContext2D.cpp').read_text()
        for start,end in [('UniquePtr<uint8_t[]> CanvasRenderingContext2D::GetImageBuffer(', 'NS_IMETHODIMP\nCanvasRenderingContext2D::GetInputStream('),('nsresult CanvasRenderingContext2D::GetImageDataArray(', 'void CanvasRenderingContext2D::EnsureErrorTarget()')]:
            body=source[source.index(start):source.index(end)]
            self.assertIn('ApplyCanvasNoiseRect(',body)
            self.assertNotIn('GlyphPrivacy',body)
        self.assertIn('totalWidth * metricScale', source)


if __name__ == '__main__':
    unittest.main()
