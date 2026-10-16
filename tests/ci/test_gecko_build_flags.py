"""Compile the transitive GTK include using the owning patch's build flags."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WebGpuBuildFlags(unittest.TestCase):
    def test_egl_header_dependency_has_gtk_flags_only_on_gtk(self):
        patch = (ROOT / 'patches/canvas-complete-renderer.patch').read_text()
        section = patch.split('+++ b/dom/webgpu/moz.build\n', 1)[1].split('\n--- a/', 1)[0]
        build = '\n'.join(line[1:] for line in section.splitlines() if line.startswith((' ', '+')))
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'Native build-flag smoke test requires a C++ compiler')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'gtk/gdk').mkdir(parents=True)
            (root / 'gtk/gdk/gdk.h').write_text('#define GTK_HEADER_FOUND 1\n')
            source = root / 'include.cpp'
            source.write_text('#include <gdk/gdk.h>\nstatic_assert(GTK_HEADER_FOUND == 1);\n')
            for toolkit in ('gtk', 'cocoa', 'android'):
                namespace = {'CONFIG': {'MOZ_WIDGET_TOOLKIT': toolkit, 'MOZ_GTK3_CFLAGS': ['-I' + str(root / 'gtk')]},
                             'CXXFLAGS': [], 'LOCAL_INCLUDES': [], 'include': lambda _: None}
                exec(compile(build, 'dom/webgpu/moz.build patch', 'exec'), namespace)
                if toolkit == 'gtk':
                    subprocess.run([compiler, '-std=c++17', '-fsyntax-only', *namespace['CXXFLAGS'], str(source)], check=True)
                else:
                    self.assertEqual(namespace['CXXFLAGS'], [], toolkit)
