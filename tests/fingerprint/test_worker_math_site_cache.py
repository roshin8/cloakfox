"""Run the production worker Math cache with controlled snapshot/site changes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class WorkerMathSiteCache(unittest.TestCase):
    def test_live_site_seed_recomputes_only_for_changed_context(self):
        compiler = shutil.which('clang++')
        if not compiler:
            self.skipTest('C++ compiler unavailable')
        source = (ROOT / 'firefox-src/dom/workers/WorkerPrivate.cpp').read_text()
        start = source.index('static uint32_t CloakfoxWorkerSiteMathSeed(')
        end = source.index('\nstatic bool CloakfoxWorkerMath(', start)
        helper = source[start:end]
        code = r'''
#include <cassert>
#include <cstdint>
#include <string>
using nsAutoString = std::string;
using nsString = std::string;
bool NS_FAILED(int result) { return result != 0; }
std::string overlay = "one";
std::string CloakConfigOverlay_Get(uint32_t) { return overlay; }
struct Settings {
  std::string partition;
  int GetPartitionKey(std::string& out) { out = partition; return 0; }
};
struct Attributes { uint32_t mUserContextId; };
struct WorkerPrivate {
  Attributes attributes;
  Settings settings;
  Attributes& GetOriginAttributes() { return attributes; }
  Settings* CookieJarSettings() { return &settings; }
};
int derivations = 0;
namespace CloakfoxSiteSeed {
uint32_t Derive(uint32_t ucid, const char*, Settings* settings) {
  ++derivations;
  if (overlay.empty()) return 0;
  return ucid * 100 + overlay.size() + settings->partition.size();
}
}
''' + helper + r'''
int main() {
  WorkerPrivate worker{{7},{"(https,one.test)"}};
  const auto first = CloakfoxWorkerSiteMathSeed(&worker);
  assert(derivations == 1);
  for (int i=0; i<10000; ++i) assert(CloakfoxWorkerSiteMathSeed(&worker) == first);
  assert(derivations == 1);
  overlay = "regenerated";
  assert(CloakfoxWorkerSiteMathSeed(&worker) != first);
  assert(derivations == 2);
  worker.settings.partition = "(https,other-domain.test)";
  CloakfoxWorkerSiteMathSeed(&worker);
  assert(derivations == 3);
  worker.attributes.mUserContextId = 0;
  CloakfoxWorkerSiteMathSeed(&worker);
  assert(derivations == 4);
  overlay.clear();
  assert(CloakfoxWorkerSiteMathSeed(&worker) == 0);
  assert(derivations == 5);
  overlay = "one";
  assert(CloakfoxWorkerSiteMathSeed(&worker) != 0);
  assert(derivations == 6);
  assert(CloakfoxWorkerSiteMathSeed(nullptr) == 0);
}
'''
        with tempfile.TemporaryDirectory(prefix='cloakfox157-math-cache-') as temp:
            path = Path(temp)
            (path / 'test.cpp').write_text(code)
            build = subprocess.run([compiler, '-std=c++17', str(path/'test.cpp'), '-o', str(path/'test')], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(path/'test')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
