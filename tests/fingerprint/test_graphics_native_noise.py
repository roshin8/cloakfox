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
    if (i%4==3 || base[i]==0 || base[(i/4)*4+3]==0) assert(a[i]==base[i]);
    if (base[i]>0 && base[(i/4)*4+3]>0) assert(a[i]>0);
  }
  std::vector<uint8_t> cleared(128,0);
  ApplyCanvasNoise(cleared.data(),cleared.size(),111111);
  for(auto v:cleared) assert(v==0);
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            cpp = Path(temporary) / "noise.cpp"
            exe = Path(temporary) / "noise"
            cpp.write_text("#include <algorithm>\n#include <cstdint>\n#include <vector>\n#include <cassert>\n#include <cstdlib>\n" + function + harness)
            subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", str(cpp), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
