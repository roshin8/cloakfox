"""Execute the production fallback decision with initially unloaded charmaps.

The first canvas draw cannot be repaired by a later layout reflow: skipping an
allowed family permanently paints missing-glyph boxes into that bitmap.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CanvasFirstGlyphFallback(unittest.TestCase):
    def test_masked_content_searches_cold_allowed_families_synchronously(self):
        source = (ROOT / 'firefox-src/gfx/thebes/gfxPlatformFontList.cpp').read_text()
        start = source.index('        if (!family.IsFullyInitialized() &&')
        end = source.index('\n      }\n      if (data.mBestMatch)', start)
        decision = source[start:end]
        harness = r'''
#include <cassert>
struct Provider { bool masked; };
bool MaskedFontListAppliesTo(Provider* p) { return p && p->masked; }
namespace StaticPrefs { bool gfx_font_rendering_fallback_async() { return true; } }
bool XRE_IsParentProcess() { return false; }
struct Match { double mMatchDistance = 1.; };
struct Family {
  bool ready = false;
  bool IsFullyInitialized() { return ready; }
  void SearchAllFontsForChar(int, Match* match) {
    ready = true; // actual SearchAllFontsForChar initializes missing cmaps
    match->mMatchDistance = 0.;
  }
};
int SharedFontList() { return 0; }
int loads;
void StartCmapLoadingFromFamily(int) { ++loads; }
bool draw(Provider* aFontVisibilityProvider, Family& family) {
 Match data; int i=0;
 for (int once=0; once<1; ++once) {
 DECISION
 }
 return data.mMatchDistance == 0.;
}
int main() {
 Provider masked{true}, native{false};
 Family cold;
 assert(draw(&masked,cold));
 assert(cold.ready && loads == 0);
 assert(draw(&masked,cold));
 Family normal;
 assert(!draw(&native,normal));
 assert(!normal.ready && loads == 1);
 Family chrome;
 assert(!draw(nullptr,chrome));
 assert(!chrome.ready && loads == 2);
}
'''.replace('DECISION', decision)
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory, 'fallback.cpp')
            exe = Path(directory, 'fallback')
            cpp.write_text(harness)
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
