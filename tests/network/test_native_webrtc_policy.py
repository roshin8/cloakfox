"""Compile and exercise the actual production mode resolver, without Gecko build."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeRTCPolicy(unittest.TestCase):
    def test_production_resolver_preserves_normal_and_fails_closed(self):
        patch = (ROOT / 'patches/cloakfox-webrtc-network-policy.patch').read_text()
        source = '\n'.join(line[1:] for line in patch.splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
        match = re.search(r'static int32_t ResolveCloakfoxWebRTCMode\(.*?\n}', source, re.S)
        self.assertIsNotNone(match, 'Native policy resolver is not implemented')
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required for native policy test')
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / 'policy.cpp'
            program.write_text('#include <cstdint>\n#include <cassert>\n' + match.group(0) + '''
int main() {
  assert(ResolveCloakfoxWebRTCMode(0, 0) == 0);
  assert(ResolveCloakfoxWebRTCMode(0, 1) == 1);
  assert(ResolveCloakfoxWebRTCMode(0, 0, 1) == 1);
  assert(ResolveCloakfoxWebRTCMode(0, 1, 0) == 1);
  assert(ResolveCloakfoxWebRTCMode(0, 0, 2) == 2);
  assert(ResolveCloakfoxWebRTCMode(0, 0, -1) == 2);
  assert(ResolveCloakfoxWebRTCMode(0, 0, 99) == 2);
  assert(ResolveCloakfoxWebRTCMode(1, 0, 0) == 2);
  for (int rtc : {-2147483647, -1, 2, 3, 2147483647}) {
    assert(ResolveCloakfoxWebRTCMode(0, rtc) == 2);
  }
  for (int network : {-2147483647, -1, 1, 2, 3, 2147483647}) {
    for (int rtc : {0, 1, 2, -1, 2147483647}) {
      assert(ResolveCloakfoxWebRTCMode(network, rtc) == 2);
    }
  }
}
'''.replace('int main()', '#include <initializer_list>\nint main()'))
            executable = Path(directory) / 'policy'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', str(program), '-o', str(executable)], check=True, capture_output=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()
