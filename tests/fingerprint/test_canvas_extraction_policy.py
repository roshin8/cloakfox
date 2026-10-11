"""Verify deterministic canvas policy selection without weakening native gates."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def fragments(patch="canvas-spoofing.patch"):
    return "\n".join(line[1:] for line in
                     (ROOT / "patches" / patch).read_text().splitlines()
                     if line.startswith(("+", " ")) and not line.startswith("+++"))


class CanvasExtractionPolicy(unittest.TestCase):
    def test_both_canvas_routes_check_permission_before_seed_policy(self):
        source = fragments()
        gates = re.findall(
            r'if \(!IsImageExtractionAllowed\([^;]+?\)\) \{\s*'
            r'return ImageExtraction::Placeholder;\s*\}\s*'
            r'if \(UseCloakfoxCanvasNoise\(aPrincipal\)\) \{\s*'
            r'return ImageExtraction::Unrestricted;\s*\}', source)
        self.assertEqual(len(gates), 2, "HTML and OffscreenCanvas must retain permission denial")

    def test_actual_policy_respects_disabled_missing_zero_and_container_seeds(self):
        source = fragments("site-fingerprint-isolation.patch")
        start = source.index("static bool UseCloakfoxCanvasNoise(")
        end = source.index("\n}", start) + 2
        helper = source[start:end]
        compiler = shutil.which("clang++") or shutil.which("g++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        code = r'''
#include <cassert>
#include <cstdint>
#include <optional>
#include <string>
struct nsIPrincipal {
  struct Attributes { uint32_t mUserContextId; } attrs;
  const Attributes& OriginAttributesRef() const { return attrs; }
};
namespace StaticPrefs {
  bool enabled = false;
  bool cloakfox_enabled() { return enabled; }
}
struct nsICookieJarSettings { bool valid = true; };
namespace CloakfoxSiteSeed {
  std::optional<uint32_t> seeds[3];
  int calls = 0;
  std::optional<uint32_t> BaseSeed(uint32_t context, const std::string& key) {
    assert(key == "canvas:seed" && context < 3);
    ++calls;
    return seeds[context];
  }
  uint32_t Derive(uint32_t context, const std::string& key, nsICookieJarSettings* settings) {
    assert(key == "canvas:seed");
    return settings && settings->valid ? seeds[context].value_or(0) : 0;
  }
}
''' + helper + r'''
int main() {
  nsICookieJarSettings valid, unavailable{false};
  nsIPrincipal defaultContext{{0}}, containerA{{1}}, containerB{{2}};
  CloakfoxSiteSeed::seeds[1] = 111111;
  CloakfoxSiteSeed::seeds[2] = 0;
  assert(!UseCloakfoxCanvasNoise(&containerA, &valid));
  assert(CloakfoxSiteSeed::calls == 0);  // disabled Cloakfox keeps Firefox policy
  StaticPrefs::enabled = true;
  assert(!UseCloakfoxCanvasNoise(nullptr, &valid));
  assert(!UseCloakfoxCanvasNoise(&defaultContext, &valid));  // no configured seed
  assert(UseCloakfoxCanvasNoise(&containerA, &valid));
  assert(!UseCloakfoxCanvasNoise(&containerA, &unavailable));
  assert(!UseCloakfoxCanvasNoise(&containerA, nullptr));
  assert(UseCloakfoxCanvasNoise(&containerB, &valid));  // explicit zero means no noise
  CloakfoxSiteSeed::seeds[1].reset();
  assert(!UseCloakfoxCanvasNoise(&containerA, &valid));  // no stale global decision
  assert(UseCloakfoxCanvasNoise(&containerB, &valid));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "policy.cpp"
            binary = Path(directory) / "policy"
            cpp.write_text(code)
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
