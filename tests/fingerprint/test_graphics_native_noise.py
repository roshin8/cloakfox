"""Compile the actual canvas byte-noise routine without building Gecko."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CanvasNoise(unittest.TestCase):
    def test_each_channel_and_exact_empty_pixels(self):
        source = (ROOT / "firefox-src/dom/base/CanvasFingerprintManager.cpp").read_text()
        start = source.index("void CanvasFingerprintManager::ApplyCanvasNoise")
        end = source.index("void CanvasFingerprintManager::DisableFunction", start)
        function = source[start:end].replace("CanvasFingerprintManager::", "")
        harness = r'''
int main() {
  std::vector<uint8_t> base(4096 * 4, 255);
  // Opaque white, text antialiasing, pure green, transparent coloured pixels.
  for (size_t i=0; i<base.size(); i+=16) {
    base[i+4]=31; base[i+5]=31; base[i+6]=31;
    base[i+8]=0; base[i+9]=200; base[i+10]=0;
    base[i+12]=70; base[i+13]=80; base[i+14]=90; base[i+15]=0;
  }
  auto a=base, b=base, repeat=base, disabled=base;
  ApplyCanvasNoise(a.data(), a.size(), 111111);
  ApplyCanvasNoise(b.data(), b.size(), 999999);
  ApplyCanvasNoise(repeat.data(), repeat.size(), 111111);
  ApplyCanvasNoise(disabled.data(), disabled.size(), 0);
  assert(a == repeat && disabled == base);
  auto nearby=base;
  ApplyCanvasNoise(nearby.data(), nearby.size(), 111111 + 1024);
  assert(a != nearby && "seeds differing above the low ten bits stay isolated");
  for (size_t channel=0; channel<3; ++channel) {
    bool changed=false;
    for(size_t i=channel; i<a.size(); i+=4) changed |= a[i]!=b[i];
    assert(changed && "each usable RGB channel must vary across seeds");
  }
  for(size_t i=0; i<a.size(); ++i) {
    assert(std::abs(int(a[i])-int(base[i]))<=1);
    if (i%4==3 || base[i]==0) assert(a[i]==base[i]);
    if (i%4!=3 && base[i]>0) assert(a[i]>0);
  }
  std::vector<uint8_t> cleared(128,0);
  ApplyCanvasNoise(cleared.data(),cleared.size(),111111);
  for(auto v:cleared) assert(v==0);
  // WebGL shaders retain RGB even when alpha is zero. Every such RGB
  // channel must remain protected; alpha itself stays exact.
  for(size_t c=0;c<3;++c) {
    bool changed=false;
    for(size_t i=12+c;i<a.size();i+=16) changed |= a[i]!=b[i];
    assert(changed && "zero-alpha shader RGB must vary across seeds");
  }
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            cpp = Path(temporary) / "noise.cpp"
            exe = Path(temporary) / "noise"
            cpp.write_text("#include <algorithm>\n#include <cstdint>\n#include <vector>\n#include <cassert>\n#include <cstdlib>\n" + function + harness)
            subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", str(cpp), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_readback_only_touches_written_pixel_rows(self):
        canvas = (ROOT / "firefox-src/dom/base/CanvasFingerprintManager.cpp").read_text()
        begin = canvas.index("void CanvasFingerprintManager::ApplyCanvasNoise")
        end = canvas.index("void CanvasFingerprintManager::DisableFunction", begin)
        apply = canvas[begin:end].replace("CanvasFingerprintManager::", "")
        webgl = (ROOT / "firefox-src/dom/canvas/ClientWebGLContext.cpp").read_text()
        begin = webgl.index("static uint32_t CloakfoxAdvanceCanvasSeed")
        end = webgl.index("bool ClientWebGLContext::DoReadPixels", begin)
        function = webgl[begin:end].replace("mozilla::dom::CanvasFingerprintManager::", "")
        stubs = r'''
constexpr uint32_t LOCAL_GL_UNSIGNED_BYTE = 5121, LOCAL_GL_RGBA = 6408;
struct Rect { int32_t x=0,y=0,width=0,height=0; bool IsEmpty() const {return width<=0 || height<=0;} };
namespace webgl {
struct ReadPixelsDesc {
  struct {uint32_t format=LOCAL_GL_RGBA,type=LOCAL_GL_UNSIGNED_BYTE;} pi;
  struct {uint32_t skipRows=0,skipPixels=0;} packState;
  struct {uint32_t x=0,y=0;} size;
};
struct ReadPixelsResult { Rect subrect; size_t byteStride=0; };
}
template<class T> struct Span {
  T* pointer; size_t length;
  T* data() const {return pointer;} size_t size() const {return length;}
};
'''
        harness = r'''
int main() {
  const uint32_t seed=111111;
  webgl::ReadPixelsDesc desc; desc.size={3,3}; desc.packState={1,1};
  webgl::ReadPixelsResult result{{1,1,2,2},24};
  std::vector<uint8_t> bytes(160,88), expected=bytes;
  std::vector<uint8_t> tight(3*3*4,88);
  ApplyCanvasNoise(tight.data(),tight.size(),seed);
  // Only rect (1,1)-(3,3) was actually written, packed after one row/pixel.
  for (size_t y=1;y<3;++y) for(size_t x=1;x<3;++x) for(size_t c=0;c<4;++c)
    expected[(y+1)*24+(x+1)*4+c]=tight[(y*3+x)*4+c];
  CloakfoxNoiseReadPixels(desc,result,Span<uint8_t>{bytes.data(),bytes.size()},seed);
  assert(bytes==expected && "padding, prefix, tail and clipped pixels stay exact");
  auto failed=expected;result.byteStride=0;
  CloakfoxNoiseReadPixels(desc,result,Span<uint8_t>{bytes.data(),bytes.size()},seed);
  assert(bytes==failed);
  result.byteStride=24;result.subrect={};
  CloakfoxNoiseReadPixels(desc,result,Span<uint8_t>{bytes.data(),bytes.size()},seed);
  assert(bytes==failed);
  result.subrect={1,1,2,2};desc.pi.type=5126;
  CloakfoxNoiseReadPixels(desc,result,Span<uint8_t>{bytes.data(),bytes.size()},seed);
  assert(bytes==failed && "precise compute data stays exact");
  for(uint32_t n : {0u,1u,2u,3u,255u,4096u}) {
    uint32_t loop=seed;
    for(uint32_t i=0;i<n;++i) loop=loop*1664525u+1013904223u;
    assert(CloakfoxAdvanceCanvasSeed(seed,n)==loop);
  }
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            cpp=Path(temporary)/"readback.cpp"; exe=Path(temporary)/"readback"
            cpp.write_text("#include <algorithm>\n#include <cstdint>\n#include <vector>\n#include <cassert>\n#include <cstdlib>\n"+stubs+apply+function+harness)
            subprocess.run([os.environ.get("CXX","c++"),"-std=c++17",str(cpp),"-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True)


if __name__ == "__main__":
    unittest.main()
