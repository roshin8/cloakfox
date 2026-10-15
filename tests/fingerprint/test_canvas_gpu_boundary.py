"""Compile the actual GPU snapshot producer metadata calls."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'firefox-src/dom/canvas'


class GPUProducerBoundary(unittest.TestCase):
    def test_gpu_snapshot_outputs_keep_gpu_provenance(self):
        # Losing one of these calls lets native shader output enter a 2D target
        # without identifying its producer. Compile each exact production call.
        cases = [
            ('WebGLContext.cpp', 'WebGLContext::GetBackBufferSnapshot(', 'dataSurf'),
            ('ClientWebGLContext.cpp', 'ClientWebGLContext::GetFrontBufferSnapshot(', 'surf'),
            ('ClientWebGLContext.cpp', 'ClientWebGLContext::BackBufferSnapshot()', 'surf'),
            ('ClientWebGLContext.cpp', 'ClientWebGLContext::DoReadPixelsAsync()', 'sourceSurface'),
        ]
        calls = []
        for filename, function, variable in cases:
            source = (NATIVE / filename).read_text()
            start = source.index(function)
            # These functions have no unindented nested closing braces.
            body = source[start:source.index('\n}\n', start)]
            call = re.search(rf'gfx::AddCanvasPixelSource\({variable},\s*gfx::CanvasPixelSource::GPU\);', body)
            self.assertIsNotNone(call, f'{function} loses GPU producer provenance')
            calls.append(call.group().replace(variable + ',', '&surface,'))
        program = r'''
#include <cassert>
#include <cstdint>
struct Surface { uint32_t sources = 1; };
namespace gfx {
enum class CanvasPixelSource : uint32_t { GPU = 64 };
void AddCanvasPixelSource(Surface* surface, CanvasPixelSource value) {
  surface->sources |= static_cast<uint32_t>(value);
}
}
int main() {
'''
        for call in calls:
            program += '{ Surface surface; ' + call + ' assert(surface.sources == 65); }\n'
        program += '}\n'
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'gpu.cpp'
            binary = Path(directory) / 'gpu'
            source.write_text(program)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
