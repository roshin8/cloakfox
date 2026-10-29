"""Compile the actual native decoration conversion and its paint fallback."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CanonicalFontDecoration(unittest.TestCase):
    def test_actual_conversion_and_fallback(self):
        source = Path(os.environ.get('CANONICAL_DECORATION_SOURCE',
            ROOT / 'firefox-src/layout/painting/nsCSSRendering.cpp')).read_text()
        start = source.index('static bool GetSkFontFromGfxFont(')
        end = source.index('\n}\n', start) + 3
        conversion = source[start:end]
        start = source.index('    SkFont skiafont;', end)
        end = source.index('\n    // Create a text blob', start)
        fallback = source[start:end]
        code = r'''
#include <cassert>
#include <cstdint>
static int baseAccess=0,linePaint=0,skiaInk=0;
struct DrawTarget{};
struct SkTypeface{};
using Float=float;
struct ScaledFont {
 virtual ~ScaledFont()=default;
 virtual bool IsCanonicalFont() const {return false;}
 virtual Float GetSize() const {return 16;}
};
// Same inheritance boundary as the real canonical font. It has no
// ScaledFontBase storage, SkTypeface member or GetSkTypeface operation.
struct CanonicalScaledFont final:ScaledFont {
 bool IsCanonicalFont() const override {return true;}
};
struct ScaledFontBase:ScaledFont {
 SkTypeface* face=nullptr;
 SkTypeface* GetSkTypeface(){++baseAccess;assert(!IsCanonicalFont());return face;}
};
template<class T>struct RefPtr {
 T* value;RefPtr(T* v):value(v){};T* get(){return value;}T* operator->(){return value;}
 explicit operator bool() const{return value;}
};
struct gfxFont {
 ScaledFont* value;int requests=0;
 ScaledFont* GetScaledFont(DrawTarget*){++requests;return value;}
};
struct SkFont {
 SkTypeface* face=nullptr;float size=0;
 SkFont()=default;SkFont(SkTypeface* f,float s):face(f),size(s){}
};
SkTypeface* sk_ref_sp(SkTypeface* p){return p;}
float SkFloatToScalar(float v){return v;}
''' + conversion + r'''
void PaintDecorationLineInternal(void*,DrawTarget&,int,int){++linePaint;}
void PaintSingleRun(gfxFont* font){
 DrawTarget aDrawTarget;void* aFrame=nullptr;int aParams=0,rect=0;
''' + fallback + r'''
 ++skiaInk;
}
int main(){
 CanonicalScaledFont canonical;gfxFont owned{&canonical};
 PaintSingleRun(&owned);
 assert(baseAccess==0 && linePaint==1 && skiaInk==0 && owned.requests==1);
 SkTypeface typeface;ScaledFontBase native;native.face=&typeface;gfxFont host{&native};
 PaintSingleRun(&host);
 assert(baseAccess==1 && linePaint==1 && skiaInk==1 && host.requests==1);
 DrawTarget target;SkFont converted;
 assert(GetSkFontFromGfxFont(target,&host,converted));
 assert(converted.face==&typeface && converted.size==16 && baseAccess==2);
 native.face=nullptr;PaintSingleRun(&host);
 assert(baseAccess==3 && linePaint==2 && skiaInk==1 && host.requests==3);
 gfxFont absent{nullptr};PaintSingleRun(&absent);
 assert(baseAccess==3 && linePaint==3 && skiaInk==1 && absent.requests==1);
}
'''
        with tempfile.TemporaryDirectory(prefix='canonical-decoration-') as temp:
            cpp = Path(temp) / 'conversion.cpp'
            binary = Path(temp) / 'conversion'
            cpp.write_text(code)
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',
                '-fsanitize=undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)


if __name__ == '__main__':
    unittest.main()
