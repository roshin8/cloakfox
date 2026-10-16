"""Checkpoint boundaries use actual files, timestamps, links and hostile archives."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import os
import subprocess
import textwrap

PATH = Path(__file__).resolve().parents[2] / 'scripts/ci/chromium_checkpoint.py'


def load():
    spec = importlib.util.spec_from_file_location('checkpoint', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Checkpoints(unittest.TestCase):
    def test_different_runner_provenance_can_resume_only_identical_host_bytes(self):
        module = load()
        host_spec = importlib.util.spec_from_file_location('host_identity', PATH.with_name('chromium_host_identity.py'))
        host = importlib.util.module_from_spec(host_spec)
        host_spec.loader.exec_module(host)
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sdk = base / 'sdk'
            sdk.mkdir()
            (sdk / 'header.h').write_text('original ABI')
            root = base / 'build'
            root.mkdir()
            obj = root / 'compiled.o'
            obj.write_bytes(b'preserved compiled object')
            original = obj.read_bytes()
            original_stamp = obj.stat().st_mtime_ns
            identity = {'identityVersion': 2, 'gitSha': 'same-commit',
                        'hostBuildInputs': host.tree_identity(sdk)}
            archive = base / 'handoff/workspace.tar.gz'
            module.save(root, archive, identity, provenance={'runnerImage': 'image-A'})
            receipt = json.loads(archive.with_suffix('.json').read_text())
            self.assertEqual(receipt['provenance']['runnerImage'], 'image-A')
            shutil.rmtree(root)
            module.restore(root, archive, identity)
            self.assertEqual(obj.read_bytes(), original)
            self.assertEqual(obj.stat().st_mtime_ns, original_stamp)
            shutil.rmtree(root)
            (sdk / 'header.h').write_text('changed ABI')
            with self.assertRaisesRegex(ValueError, 'hostBuildInputs'):
                module.restore(root, archive, {**identity, 'hostBuildInputs': host.tree_identity(sdk)})
            self.assertFalse(root.exists())
            # A v1 checkpoint cannot be silently upgraded across images.
            module.save(sdk, archive, {'gitSha': 'same-commit', 'runnerImage': 'image-A'})
            with self.assertRaisesRegex(ValueError, 'identity'):
                module.restore(root, archive, {'gitSha': 'same-commit', 'runnerImage': 'image-B'})
            self.assertFalse(root.exists())

    def test_roundtrip_preserves_objects_timestamps_and_links(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'build'
            (root / 'out').mkdir(parents=True)
            obj = root / 'out/compiled.o'
            obj.write_bytes(b'compiled object')
            (root / 'out/link').symlink_to('compiled.o')
            (root / 'out/absolute-internal').symlink_to(obj)
            stamp = obj.stat().st_mtime_ns
            identity = {'gitSha': 'abc', 'root': str(root), 'toolchain': 'sdk-test'}
            archive = base / 'handoff/workspace.tar.gz'
            module.validate_links(root)
            module.save(root, archive, identity)
            shutil.rmtree(root)
            module.restore(root, archive, identity)
            self.assertEqual(obj.read_bytes(), b'compiled object')
            self.assertEqual(obj.stat().st_mtime_ns, stamp)
            self.assertEqual((root / 'out/absolute-internal').read_bytes(), b'compiled object')
            self.assertFalse(Path(os.readlink(root / 'out/absolute-internal')).is_absolute())
            self.assertTrue((root / 'out/link').is_symlink())
            self.assertEqual((root / 'out/link').read_bytes(), b'compiled object')

    def test_rejects_changed_archive_or_wrong_identity_without_extracting(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'build'
            root.mkdir()
            (root / 'source').write_text('pinned')
            archive = base / 'handoff/workspace.tar.gz'
            identity = {'gitSha': 'abc'}
            module.save(root, archive, identity)
            shutil.rmtree(root)
            with self.assertRaisesRegex(ValueError, 'identity'):
                module.restore(root, archive, {'gitSha': 'changed'})
            self.assertFalse(root.exists())
            with archive.open('ab') as file:
                file.write(b'tamper')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                module.restore(root, archive, identity)
            self.assertFalse(root.exists())

    def test_rejects_archive_member_escape(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = base / 'workspace.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                entry = tarfile.TarInfo('workspace/../../escape')
                entry.size = 1
                bundle.addfile(entry, io.BytesIO(b'x'))
            archive.with_suffix('.json').write_text(json.dumps({'schemaVersion': 1, 'identity': {}, 'sha256': module.digest(archive)}))
            with self.assertRaises((ValueError, tarfile.FilterError)):
                module.restore(base / 'build', archive, {})
            self.assertFalse((base / 'escape').exists())

    def test_external_symlink_is_rejected(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'build'
            root.mkdir()
            (root / 'external').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'external symlink'):
                module.validate_links(root)
            with self.assertRaisesRegex(ValueError, 'external symlink'):
                module.save(root, base / 'checkpoint/workspace.tar.gz', {})

    def test_reserve_rejects_checkpoint_creation_and_extraction(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'build'
            root.mkdir()
            (root / 'input').write_text('pinned')
            archive = base / 'checkpoint/workspace.tar.gz'
            with patch.object(module.shutil, 'disk_usage', return_value=SimpleNamespace(free=9*module.GIB)):
                with self.assertRaisesRegex(RuntimeError, 'storage reserve'):
                    module.save(root, archive, {})
            module.save(root, archive, {})
            shutil.rmtree(root)
            with patch.object(module.shutil, 'disk_usage', return_value=SimpleNamespace(free=9*module.GIB)):
                with self.assertRaisesRegex(RuntimeError, 'storage reserve'):
                    module.restore(root, archive, {})
            self.assertFalse((root / 'input').exists())

    def test_workflow_gate_rejects_unfinished_or_failed_segments(self):
        workflow = PATH.parents[2] / '.github/workflows/chromium.yml'
        text = workflow.read_text().split('  source-complete:', 1)[1].split('  runtime:', 1)[0]
        gate = textwrap.dedent(text.split('        run: |\n', 1)[1])
        for complete, failure, expected in [('true','false',0),('false','false',1),('true','true',1)]:
            result = subprocess.run(['bash','-e','-c',gate], env={**os.environ,'COMPLETE':complete,'FAILURE':failure})
            self.assertEqual(result.returncode, expected)

    def test_verified_host_sdk_links_are_recreated_only_after_extract(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sdk = base / 'Xcode/Platforms/MacOSX.platform'
            sdk.mkdir(parents=True)
            header = sdk / 'header.h'
            header.write_text('host SDK unchanged')
            root = base / 'build'
            relative = 'chromium/src/out/Release_GN_arm64/sdk/xcode_links/MacOSX.platform'
            link = root / relative
            link.parent.mkdir(parents=True)
            link.symlink_to(sdk, target_is_directory=True)
            identity = {'hostSdkLinks': {relative: str(sdk.resolve())}}
            module.validate_links(root, identity)
            archive = base / 'checkpoint/workspace.tar.gz'
            module.save(root, archive, identity)
            with tarfile.open(archive) as bundle:
                self.assertNotIn('workspace/' + relative, bundle.getnames())
            shutil.rmtree(root)
            module.restore(root, archive, identity)
            self.assertTrue(link.is_symlink())
            self.assertEqual((link / 'header.h').read_text(), 'host SDK unchanged')
            self.assertEqual(header.read_text(), 'host SDK unchanged')
            # An altered manifest cannot point the re-created link at arbitrary
            # host paths, even though the archive itself still has its valid hash.
            receipt_path = archive.with_suffix('.json')
            receipt = json.loads(receipt_path.read_text())
            receipt['hostLinks'][relative] = '/etc'
            receipt_path.write_text(json.dumps(receipt))
            shutil.rmtree(root)
            with self.assertRaisesRegex(ValueError, 'host SDK link'):
                module.restore(root, archive, identity)
            self.assertFalse(root.exists())

            # A hostile archive cannot write through the pinned external link:
            # it is absent until extraction has finished, then occupied paths fail.
            with tarfile.open(archive, 'w:gz') as bundle:
                entry = tarfile.TarInfo('workspace/' + relative + '/header.h')
                entry.size = 6
                bundle.addfile(entry, io.BytesIO(b'poison'))
            receipt['hostLinks'][relative] = str(sdk.resolve())
            receipt['sha256'] = module.digest(archive)
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'occupied'):
                module.restore(root, archive, identity)
            self.assertEqual(header.read_text(), 'host SDK unchanged')
