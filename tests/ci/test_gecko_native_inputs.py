import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def api():
    spec = importlib.util.spec_from_file_location('gecko_native_inputs', ROOT / 'scripts/ci/gecko_native_inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeInputs(unittest.TestCase):
    def test_forged_archive_cannot_escape_or_install_links(self):
        module = api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, name in enumerate(('../escape', '/absolute', 'bin/link')):
                inputs = root / str(index)
                inputs.mkdir()
                archive = inputs / 'native-inputs.tar.gz'
                with tarfile.open(archive, 'w:gz') as bundle:
                    member = tarfile.TarInfo(name)
                    if name == 'bin/link':
                        member.type = tarfile.SYMTYPE
                        member.linkname = '/tmp'
                        bundle.addfile(member)
                    else:
                        member.size = 1
                        bundle.addfile(member, io.BytesIO(b'x'))
                (inputs / 'native-inputs.json').write_text(json.dumps({
                    'gitSha': 'commit', 'archiveSha256': module.digest(archive)}))
                with self.assertRaises(ValueError):
                    module.restore(inputs, root / f'restored{index}', 'commit')
                self.assertFalse((root / f'restored{index}').exists())
            self.assertFalse((root / 'escape').exists())

    def test_missing_native_inputs_fail_before_publication(self):
        module = api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'src').mkdir()
            (root / 'bin').mkdir()
            with self.assertRaises(FileNotFoundError):
                module.pack(root / 'src', root / 'bin', root / 'output', 'commit')
            self.assertFalse((root / 'output/native-inputs.tar.gz').exists())

    def test_roundtrip_materializes_files_and_binds_commit_and_archive(self):
        module = api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, binary = root / 'src', root / 'bin'
            binary.mkdir()
            for name in module.REQUIRED_BINARIES:
                (binary / name).write_bytes(name.encode())
            (binary / 'xpcshell').chmod(0o755)
            for name in module.FIXTURES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'video')
            extra = source / 'dom/media/test/reftest/color_quads/a.mp4'
            extra.parent.mkdir(parents=True)
            extra.write_bytes(b'quad')
            header = source / 'media/ffvpx/libavcodec/avcodec.h'
            header.parent.mkdir(parents=True)
            header.write_bytes(b'header')
            # dist/bin has source links; materialize only selected files, never
            # recurse into moz-src (which points to the entire source tree).
            (binary / 'application.ini').symlink_to(header)
            (binary / 'moz-src').symlink_to(source, target_is_directory=True)
            module.pack(source, binary, root / 'output', 'commit')
            archive = root / 'output/native-inputs.tar.gz'
            with tarfile.open(archive) as bundle:
                self.assertTrue(all(row.isfile() for row in bundle))
                self.assertFalse(any('moz-src' in row.name for row in bundle))
            with self.assertRaises(ValueError):
                module.restore(root / 'output', root / 'wrong', 'other')
            self.assertFalse((root / 'wrong').exists())
            module.restore(root / 'output', root / 'restored', 'commit')
            self.assertEqual((root / 'restored/bin/application.ini').read_bytes(), b'header')
            self.assertTrue((root / 'restored/bin/xpcshell').stat().st_mode & 0o111)
            self.assertEqual((root / 'restored/firefox-src' / extra.relative_to(source)).read_bytes(), b'quad')
            archive.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                module.restore(root / 'output', root / 'corrupt', 'commit')
            self.assertFalse((root / 'corrupt').exists())

