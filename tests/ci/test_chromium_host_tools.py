import importlib.util
import os
import io
import json
import tarfile
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('host_tools', Path(__file__).resolve().parents[2] / 'scripts/ci/chromium_host_tools.py')


class HostToolsTests(unittest.TestCase):
    def setUp(self):
        self.m = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.keg = self.root / 'Cellar/cmake/1.0'
        (self.keg / 'bin').mkdir(parents=True)
        self.tool = self.keg / 'bin/cmake'
        self.tool.write_bytes(b'original')
        (self.root / 'opt').mkdir()
        (self.root / 'opt/cmake').symlink_to('../Cellar/cmake/1.0')
        self.packages = {'cmake': str(self.keg)}
        self.out = self.root / 'snapshot'

    def snapshot(self):
        self.m.snapshot(self.out, self.packages, self.root, 'commit', 'run')

    def restore(self):
        self.m.restore(self.out, self.packages, self.root, 'commit', 'run')

    def test_restores_exact_bytes_and_modes(self):
        identity_spec = importlib.util.spec_from_file_location('identity', Path(__file__).resolve().parents[2] / 'scripts/ci/chromium_host_identity.py')
        identity = importlib.util.module_from_spec(identity_spec)
        identity_spec.loader.exec_module(identity)
        self.tool.chmod(0o755)
        first_host_identity = identity.tree_identity(self.keg, homebrew_package=True)
        self.snapshot()
        self.tool.write_bytes(b'changed!')
        self.tool.chmod(0o644)
        self.restore()
        self.assertEqual(self.tool.read_bytes(), b'original')
        self.assertEqual(self.tool.stat().st_mode & 0o777, 0o755)
        self.assertEqual(identity.tree_identity(self.keg, homebrew_package=True), first_host_identity)

    def test_extra_file_rejects_before_any_write(self):
        self.snapshot()
        self.tool.write_bytes(b'changed!')
        (self.keg / 'extra').write_text('foreign')
        with self.assertRaises(ValueError): self.restore()
        self.assertEqual(self.tool.read_bytes(), b'changed!')

    def test_symlink_substitution_rejects_before_write(self):
        self.snapshot()
        self.tool.unlink()
        self.tool.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): self.restore()
        self.assertTrue(self.tool.is_symlink())

    def test_wrong_run_or_archive_corruption_rejects(self):
        self.snapshot()
        with self.assertRaises(ValueError):
            self.m.restore(self.out, self.packages, self.root, 'commit', 'other-run')
        with (self.out / 'tools.tar.gz').open('ab') as stream: stream.write(b'corrupt')
        with self.assertRaises(ValueError): self.restore()

    def test_foreign_symlink_rejected_at_snapshot(self):
        (self.keg / 'foreign').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): self.snapshot()

    def test_changed_opt_mapping_rejects(self):
        self.snapshot()
        opt = self.root / 'opt/cmake'
        opt.unlink()
        opt.symlink_to(self.keg)
        with self.assertRaises(ValueError): self.restore()

    def test_changed_commit_rejects(self):
        self.snapshot()
        with self.assertRaises(ValueError):
            self.m.restore(self.out, self.packages, self.root, 'other-commit', 'run')

    def test_archive_rejects_traversal_links_duplicates_and_missing_files(self):
        for kind in ('traversal', 'symlink', 'hardlink', 'duplicate', 'missing'):
            with self.subTest(kind=kind):
                self.snapshot()
                archive = self.out / 'tools.tar.gz'
                with tarfile.open(archive, 'w:gz') as tar:
                    if kind != 'missing':
                        member = tarfile.TarInfo('../escape' if kind == 'traversal' else 'cmake/bin/cmake')
                        member.mode = self.tool.stat().st_mode & 0o777
                        if kind in ('symlink', 'hardlink'):
                            member.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
                            member.linkname = '/etc/passwd'
                            tar.addfile(member)
                        else:
                            member.size = len(b'original')
                            tar.addfile(member, io.BytesIO(b'original'))
                            if kind == 'duplicate': tar.addfile(member, io.BytesIO(b'original'))
                manifest_path = self.out / 'manifest.json'
                manifest = json.loads(manifest_path.read_text())
                manifest['archiveSha256'] = self.m.digest(archive)
                manifest_path.write_text(json.dumps(manifest))
                self.tool.write_bytes(b'changed!')
                with self.assertRaises(ValueError): self.restore()
                self.assertEqual(self.tool.read_bytes(), b'changed!')
                self.tool.write_bytes(b'original')

    def test_all_files_validate_before_restore(self):
        second = self.keg / 'bin/second'
        second.write_bytes(b'second')
        self.snapshot()
        archive = self.out / 'tools.tar.gz'
        # A valid archive-level digest must not bypass individual file hashes.
        with tarfile.open(archive, 'w:gz') as tar:
            for name, data in [('cmake/bin/cmake', b'original'), ('cmake/bin/second', b'BROKEN')]:
                member = tarfile.TarInfo(name)
                member.mode = self.tool.stat().st_mode & 0o777
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
        manifest_path = self.out / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['archiveSha256'] = self.m.digest(archive)
        manifest_path.write_text(json.dumps(manifest))
        self.tool.write_bytes(b'changed!')
        with self.assertRaises(ValueError): self.restore()
        self.assertEqual(self.tool.read_bytes(), b'changed!')

    def test_cli_requires_hosted_supported_darwin(self):
        for actions, system, machine in [('false', 'Darwin', 'arm64'), ('true', 'Linux', 'arm64'), ('true', 'Darwin', 'unknown')]:
            with patch.dict(os.environ, {'GITHUB_ACTIONS': actions}), patch.object(self.m.platform, 'system', return_value=system), patch.object(self.m.platform, 'machine', return_value=machine):
                with self.assertRaises(ValueError): self.m.hosted_packages()

    def test_homebrew_root_is_bound_to_the_actual_supported_host_architecture(self):
        with patch.object(self.m.platform, 'machine', return_value='x86_64'):
            self.assertEqual(self.m.homebrew_root(), Path('/usr/local'))
        with patch.object(self.m.platform, 'machine', return_value='arm64'):
            self.assertEqual(self.m.homebrew_root(), Path('/opt/homebrew'))
        with patch.object(self.m.platform, 'machine', return_value='unknown'):
            with self.assertRaises(ValueError): self.m.homebrew_root()

    def test_workflow_restores_before_fingerprinting_or_ninja(self):
        workflow = (Path(__file__).resolve().parents[2] / '.github/workflows/chromium-source-segment.yml').read_text()
        self.assertLess(workflow.index('chromium_host_tools.py restore'), workflow.index('name: Verify real Ninja'))
        self.assertLess(workflow.index('chromium_host_tools.py restore'), workflow.index('name: Build or resume'))
        self.assertLess(workflow.index('name: Publish immutable same-run Homebrew'), workflow.index('name: Build or resume'))
        self.assertIn('chromium-host-tools-${{ github.run_id }}-${{ github.run_attempt }}', workflow)

if __name__ == '__main__': unittest.main()
