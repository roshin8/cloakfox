"""Exercise the native label-masking branch with each actual media source kind.

The small harness compiles the production branch, without opening any devices.
A live capture retry remains necessary to verify the installed browser/site.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CaptureLabelScope(unittest.TestCase):
    def test_only_physical_devices_receive_generic_labels(self):
        patch = (ROOT / 'patches/cloakfox-capture-label-scope.patch').read_text()
        source = '\n'.join(line[1:] for line in patch.splitlines()
                           if line.startswith(('+', ' ')) and not line.startswith('+++'))
        branch = re.search(
            r'if \(maskLabels(?:[^{}]*)\) \{\s*'
            r'nsRFPService::GetMediaDeviceName\(name, device->mKind\);\s*\}',
            source,
        )
        self.assertIsNotNone(branch, 'Native masking branch not found')
        prepared = ROOT / 'firefox-src/dom/media/MediaManager.cpp'
        if prepared.exists():
            self.assertIn(branch.group(), prepared.read_text())
        compiler = shutil.which('clang++') or shutil.which('c++')
        self.assertIsNotNone(compiler)
        program = r'''
#include <iostream>
#include <string>
enum class MediaSourceEnum { Camera, Microphone, Screen, Window, Browser, AudioCapture };
enum class MediaDeviceKind { Videoinput, Audioinput, Audiooutput };
struct Device { MediaSourceEnum mMediaSource; MediaDeviceKind mKind; };
namespace nsRFPService {
void GetMediaDeviceName(std::string& name, MediaDeviceKind kind) {
  name = kind == MediaDeviceKind::Videoinput ? "Internal Camera" :
         kind == MediaDeviceKind::Audioinput ? "Internal Microphone" : "Internal Speaker";
}
}
int main() {
  for (bool maskLabels : {true, false}) {
    for (auto source : {MediaSourceEnum::Camera, MediaSourceEnum::Microphone,
        MediaSourceEnum::Screen, MediaSourceEnum::Window,
        MediaSourceEnum::Browser, MediaSourceEnum::AudioCapture}) {
      Device storage{source, source == MediaSourceEnum::Microphone ? MediaDeviceKind::Audioinput : MediaDeviceKind::Videoinput};
      Device* device = &storage;
      std::string name = "original source";
      BRANCH
      std::cout << name << '\n';
    }
    Device output{MediaSourceEnum::AudioCapture, MediaDeviceKind::Audiooutput};
    Device* device = &output;
    std::string name = "original source";
    BRANCH
    std::cout << name << '\n';
  }
}
'''.replace('BRANCH', branch.group())
        with tempfile.TemporaryDirectory() as tmp:
            cpp, binary = Path(tmp, 'labels.cpp'), Path(tmp, 'labels')
            cpp.write_text(program)
            subprocess.run([compiler, '-std=c++17', str(cpp), '-o', str(binary)], check=True)
            labels = subprocess.check_output([str(binary)], text=True).splitlines()
        self.assertEqual(labels[:2], ['Internal Camera', 'Internal Microphone'])
        self.assertEqual(labels[6], 'Internal Speaker')
        self.assertEqual(labels[2:6] + labels[7:], ['original source'] * 11,
                         'Screen/window/tab capture must never be renamed as a camera')


if __name__ == '__main__':
    unittest.main()
