"""Compile the actual gfxFont::Draw collector dispatch, without a browser build."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CanonicalCollectorFallback(unittest.TestCase):
    def test_actual_font_draw_dispatch(self):
        source = Path(os.environ.get('CANONICAL_FONT_SOURCE',
            ROOT / 'firefox-src/gfx/thebes/gfxFont.cpp')).read_text()
        start = source.index('void gfxFont::Draw(const gfxTextRun*')
        start = source.index('  if (aStart >= aEnd)', start)
        end = source.index('  FontDrawParams fontParams;', start)
        dispatch = source[start:end]
        fill_start = source.index('  void FillGlyphBuffer(const gfx::GlyphBuffer&')
        fill_end = source.index('\n  void FlushGlyphs()', fill_start)
        fill = source[fill_start:fill_end]
        code = r'''
#include <cassert>
#include <cstdint>
struct Collector {
 int unsupported=0;
 void FoundUnsupportedFeature(){++unsupported;}
};
struct Target {bool collector;int nativePainted=0;template<class... T>void FillGlyphs(T...){++nativePainted;}};
struct Params {Collector* textDrawer=nullptr;Target*dt=nullptr;};
namespace gfx {struct GlyphBuffer{};}
struct Pattern {};
struct Token {
 bool canonical;int rasterPainted=0;
 bool IsCanonicalFont(){return canonical;}
 void DrawCanonicalGlyphs(Target*target,const gfx::GlyphBuffer&,const Pattern&,void*,int){
  assert(!target->collector);++rasterPainted;
 }
};
struct FontParams {Token*scaledFont;int drawOptions=0;};
struct Renderer {FontParams mFontParams;Params&mRunParams;
''' + fill + r'''
};
struct Font {
 enum {FONT_TYPE_NATIVE,FONT_TYPE_CANONICAL};
 int type;Token token;
 int GetType(){return type;}
 void Draw(uint32_t aStart,uint32_t aEnd,Params& aRunParams){
''' + dispatch + r'''
  Renderer{{&token},aRunParams}.FillGlyphBuffer(gfx::GlyphBuffer{},Pattern{});
 }
};
int main(){
 Collector collector;Target fake{true},real{false}; Params collection{&collector,&fake},raster{nullptr,&real};
 Font canonical{Font::FONT_TYPE_CANONICAL,Token{true}};
 canonical.Draw(0,2,collection);
 assert(collector.unsupported==1 && canonical.token.rasterPainted==0);
 canonical.Draw(0,2,raster);
 assert(canonical.token.rasterPainted==1);
 Font native{Font::FONT_TYPE_NATIVE,Token{false}};
 native.Draw(0,2,collection);
 assert(collector.unsupported==1 && fake.nativePainted==1);
 canonical.Draw(2,2,collection);
 assert(collector.unsupported==1 && canonical.token.rasterPainted==1);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / 'dispatch.cpp'
            executable = Path(directory) / 'dispatch'
            cpp.write_text(code)
            subprocess.run(['c++', '-std=c++17', str(cpp), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()
