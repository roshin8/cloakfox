"""Check async WebGL snapshot integration and compile the actual noise helpers.

Runs without a Firefox build: python3 tests/fingerprint/test_webgl_async_readback.py
The C++ test uses code extracted from the shipped patches, with only Gecko data
containers stubbed. Browser captureStream behavior still requires a runtime probe.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def patched_fragments(name):
    return "\n".join(
        line[1:] for line in (ROOT / "patches" / name).read_text().splitlines()
        if line.startswith(("+", " ")) and not line.startswith("+++")
    )


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class AsyncWebGLReadback(unittest.TestCase):
    def test_seed_is_captured_before_callback_and_noise_precedes_swizzle(self):
        source = patched_fragments("webgl-readback-noise.patch")
        seed = re.search(
            r'const uint32_t noiseSeed\s*=\s*MaskConfig::GetUint32\('
            r'"canvas:seed", GetUserContextId\(\)\)\.value_or\(0\);', source
        )
        self.assertIsNotNone(seed, "resolve the requesting canvas seed before dispatch")
        callback = source.index("ipcPromise->Then(")
        self.assertLess(seed.end(), callback)
        self.assertRegex(source[callback:], r'expectedSize, noiseSeed\]\(webgl::ReadPixelsResultIpc')
        # Late configuration lookup would resolve a different or absent JS realm.
        self.assertNotIn("MaskConfig::", source[callback:])
        call = "CloakfoxNoiseReadPixels(desc, pixels, noiseSeed);"
        self.assertEqual(source.count(call), 1)
        copy = source.index("Memcpy(&destRow, srcRow);", callback)
        self.assertLess(copy, source.index(call))
        self.assertLess(source.index(call), source.index("gfx::SwizzleYFlipData(", callback))

    def test_real_noise_helpers_preserve_snapshot_semantics(self):
        compiler = shutil.which("clang++") or shutil.which("g++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        helper = function(patched_fragments("webgl-readback-noise.patch"),
                          "static void CloakfoxNoiseReadPixels(")
        noise = function(patched_fragments("canvas-spoofing.patch"),
                         "void CanvasFingerprintManager::ApplyCanvasNoise(")
        code = r'''
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <vector>
constexpr int LOCAL_GL_UNSIGNED_BYTE = 1, LOCAL_GL_RGBA = 2;
namespace webgl { struct ReadPixelsDesc { struct { int type, format; } pi; }; }
template<class T> struct Span {
  std::vector<T>& values;
  size_t size() const { return values.size(); }
  T* data() const { return values.data(); }
};
namespace mozilla::dom {
class CanvasFingerprintManager {
 public: static void ApplyCanvasNoise(uint8_t*, uint32_t, uint32_t);
};
''' + noise + '\n}\n' + helper + r'''
int main() {
  const webgl::ReadPixelsDesc rgba{{LOCAL_GL_UNSIGNED_BYTE, LOCAL_GL_RGBA}};
  std::vector<uint8_t> ipcBuffer;
  for (int i = 0; i < 64; ++i) {
    ipcBuffer.insert(ipcBuffer.end(), {80, 120, 160, uint8_t(i * 4)});
  }
  const auto original = ipcBuffer;
  uint32_t requestingSeed = 111111;
  const uint32_t noiseSeed = requestingSeed;
  // Model IPC completion using the product's checked by-value seed capture.
  auto complete = [noiseSeed, &rgba](std::vector<uint8_t>& copiedPixels) {
    CloakfoxNoiseReadPixels(rgba, Span<uint8_t>{copiedPixels}, noiseSeed);
  };
  requestingSeed = 999999;  // navigation/domain overlay changes before reply
  auto captured = ipcBuffer;
  complete(captured);
  auto repeated = ipcBuffer;
  complete(repeated);
  auto otherIdentity = ipcBuffer;
  CloakfoxNoiseReadPixels(rgba, Span<uint8_t>{otherIdentity}, requestingSeed);
  assert(captured != original && captured != otherIdentity && captured == repeated);
  assert(ipcBuffer == original);  // noise only the snapshot's copied storage
  for (size_t i = 3; i < captured.size(); i += 4) assert(captured[i] == original[i]);
  auto disabled = original;
  CloakfoxNoiseReadPixels(rgba, Span<uint8_t>{disabled}, 0);
  assert(disabled == original);
  for (const auto desc : {webgl::ReadPixelsDesc{{3, LOCAL_GL_RGBA}},
                          webgl::ReadPixelsDesc{{LOCAL_GL_UNSIGNED_BYTE, 4}}}) {
    auto unsupported = original;
    CloakfoxNoiseReadPixels(desc, Span<uint8_t>{unsupported}, noiseSeed);
    assert(unsupported == original);
  }
  std::vector<uint8_t> shortBuffer{1, 2, 3};
  CloakfoxNoiseReadPixels(rgba, Span<uint8_t>{shortBuffer}, noiseSeed);
  assert((shortBuffer == std::vector<uint8_t>{1, 2, 3}));
  std::vector<uint8_t> transparent(256, 0);
  CloakfoxNoiseReadPixels(rgba, Span<uint8_t>{transparent}, noiseSeed);
  assert(std::all_of(transparent.begin(), transparent.end(), [](auto b) { return b == 0; }));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "readback.cpp"
            binary = Path(directory) / "readback"
            source.write_text(code)
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
