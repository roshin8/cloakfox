"""The imported AV1 paths need shared Dolby Vision providers on every OS."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Sources(list):
    def __getitem__(self, name):
        if isinstance(name, str):
            return type('Flags', (), {'flags': []})()
        return super().__getitem__(name)


def appended_build(path):
    patch = (ROOT / 'patches/canvas-complete-renderer.patch').read_text()
    section = patch.split('+++ b/' + path + '\n', 1)[1].split('\n--- a/', 1)[0]
    rendered = '\n'.join(line[1:] for line in section.splitlines() if line.startswith((' ', '+')))
    return rendered.split('include("../ffvpxcommon.mozbuild")', 1)[1]


class VideoDependencies(unittest.TestCase):
    def test_shared_metadata_exports_follow_video_not_macos(self):
        patch = (ROOT / 'patches/canvas-complete-renderer.patch').read_text()
        section = patch.split('+++ b/media/ffvpx/libavutil/avutil.symbols\n', 1)[1].split('\n--- a/', 1)[0]
        exports = '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+'))
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        for darwin in (False, True):
            for audio_only in (False, True):
                defines = (['-DXP_DARWIN'] if darwin else []) + (['-DMOZ_FFVPX_AUDIOONLY'] if audio_only else [])
                result = subprocess.run([compiler, '-E', '-P', '-x', 'c', *defines, '-'],
                                        input=exports, text=True, capture_output=True, check=True)
                symbols = result.stdout.split()
                for symbol in ('av_dovi_alloc', 'av_dovi_metadata_alloc', 'av_dovi_find_level'):
                    self.assertEqual(symbols.count(symbol), 0 if audio_only else 1)

    def test_all_video_targets_supply_dovi_without_enabling_extra_decoders(self):
        codec = appended_build('media/ffvpx/libavcodec/moz.build')
        utility = appended_build('media/ffvpx/libavutil/moz.build')
        for platform in ('Linux', 'Darwin', 'WINNT', 'Android'):
            for audio_only in (False, True):
                with self.subTest(platform=platform, audio_only=audio_only):
                    config = {'OS_ARCH': platform, 'MOZ_FFVPX_AUDIOONLY': audio_only}
                    namespaces = []
                    for build in (codec, utility):
                        env = {'CONFIG': config, 'SOURCES': Sources(), 'DIRS': [], 'TOPSRCDIR': '/source'}
                        exec(compile(build, 'ffvpx owning build section', 'exec'), env)
                        namespaces.append(env)
                    sources, util = (env['SOURCES'] for env in namespaces)
                    for name in ('dovi_rpu.c', 'dovi_rpudec.c'):
                        self.assertEqual(sources.count(name), 0 if audio_only else 1, name)
                    self.assertEqual(util.count('dovi_meta.c'), 0 if audio_only else 1)
                    self.assertEqual('h264dec.c' in sources, platform == 'Darwin' and not audio_only)
                    self.assertEqual(namespaces[0]['DIRS'], ['hevc'] if platform == 'Darwin' and not audio_only else [])
