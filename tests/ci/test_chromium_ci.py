import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/ci' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CiInputs(unittest.TestCase):
    def test_cleanup_refuses_local_machine_and_preserves_selected_xcode(self):
        api = load('prepare_macos')
        with self.assertRaises(RuntimeError):
            api.require_hosted({})
        api.require_hosted({'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted'})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            selected = root / 'Xcode_26.6.app'
            selected.mkdir()
            older = root / 'Xcode_26.5.app'
            older.mkdir()
            alias = root / 'Xcode.app'
            alias.symlink_to(selected)
            self.assertEqual(api.unused_xcodes(root, selected / 'Contents/Developer'), [older])

    def test_archive_rejects_digest_mismatch_and_path_escape(self):
        api = load('chromium_source')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'source.tar.xz'
            with tarfile.open(archive, 'w:xz') as bundle:
                info = tarfile.TarInfo('chromium-154/../../escape')
                info.size = 1
                bundle.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                api.verify_archive(archive, {'archiveSize': archive.stat().st_size, 'archiveSha256': '0' * 64})
            with self.assertRaises((ValueError, tarfile.FilterError)):
                api.extract_source(archive, root / 'src')
            self.assertFalse((root.parent / 'escape').exists())

    def test_patch_receipt_checks_latest_hash_for_overlapping_inputs(self):
        api = load('chromium_source')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a').write_bytes(b'new')
            locks = [{'inputs': [{'path': 'a', 'afterSha256': 'old'}]},
                     {'inputs': [{'path': 'a', 'afterSha256': api.digest(root / 'a')}]}]
            api.verify_chain(root, locks)
            (root / 'a').write_bytes(b'drift')
            with self.assertRaises(ValueError):
                api.verify_chain(root, locks)

    def test_missing_native_tests_cannot_pass_runtime_gate(self):
        api = load('run_engine_tests')
        suite = unittest.TestSuite()
        class MissingNative(unittest.TestCase):
            @unittest.skip('Set CLOAKFOX_CHROMIUM_BIN')
            def test_native(self):
                pass
        suite.addTest(MissingNative('test_native'))
        self.assertFalse(api.run_suite(suite, io.StringIO()))

    def test_sdk_refresh_reads_chromium_transfer_headers(self):
        api = load('chromium_source')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, sdk, out = root / 'src', root / 'sdk', root / 'out'
            for directory in (source / 'cef/tools/distrib', source / 'net/base', sdk / 'include/base/internal', sdk / 'libcef_dll', out):
                directory.mkdir(parents=True, exist_ok=True)
            (source / 'cef/tools/distrib/transfer.cfg').write_text(repr([
                {'source': '../net/base/net_error_list.h', 'target': 'include/base/internal/cef_net_error_list.h'}]))
            (source / 'net/base/net_error_list.h').write_text('native-source-header')
            target = sdk / 'include/base/internal/cef_net_error_list.h'
            target.write_text('stale-template-header')
            (sdk / 'include/TRANSFER-README.txt').write_text('distribution mapping notice')
            api.refresh_sdk(source, out, sdk)
            self.assertEqual(target.read_text(), 'native-source-header')

    def test_artifact_rejects_wrong_commit_and_changed_embedded_framework(self):
        import json
        api = load('verify_chromium_artifact')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'input/patched-client/Release/CloakfoxChromium.app/Contents/Frameworks/Chromium Embedded Framework.framework/Versions/A'
            app.mkdir(parents=True)
            binary = app / 'Chromium Embedded Framework'
            binary.write_bytes(b'compiled-framework')
            archive = root / 'chromium-apps.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                bundle.add(root / 'input/patched-client', arcname='patched-client')
            evidence = root / 'evidence'
            evidence.mkdir()
            receipt = {'gitSha': 'expected', 'sourceFrameworkSha256': api.digest(binary),
                       'sdkFrameworkSha256': api.digest(binary), 'embeddedFrameworkSha256': api.digest(binary)}
            (evidence / 'source-provenance.json').write_text(json.dumps(receipt))
            (evidence / 'chromium-apps.sha256').write_text(api.digest(archive) + '  chromium-apps.tar.gz')
            with self.assertRaises(ValueError):
                api.verify(archive, evidence, root / 'bad', 'other-commit')
            api.verify(archive, evidence, root / 'valid', 'expected')
            reusable = {**receipt, 'engineProducerSha': 'expected', 'appGitSha': 'consumer',
                        'engineKey': load('engine_artifact').input_key(ROOT, 'chromium')}
            (evidence / 'source-provenance.json').write_text(json.dumps(reusable))
            api.verify(archive, evidence, root / 'current-app', 'consumer')
            for field, value in [('appGitSha', 'other'), ('engineKey', 'wrong'), ('engineProducerSha', 'other')]:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    (evidence / 'source-provenance.json').write_text(json.dumps({**reusable, field: value}))
                    api.verify(archive, evidence, root / ('invalid-' + field), 'consumer')
            receipt['sourceFrameworkSha256'] = '0' * 64
            (evidence / 'source-provenance.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                api.verify(archive, evidence, root / 'drift', 'expected')

    def test_upstream_tarball_patches_apply_without_a_b_prefix(self):
        api = load('chromium_source')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'DEPS').write_text('old\n')
            patch = root / 'tarball_deps.patch'
            patch.write_text('diff --git DEPS DEPS\n--- DEPS\n+++ DEPS\n@@ -1 +1 @@\n-old\n+new\n')
            api.Pipeline(root).apply_archive_patch(patch, root)
            self.assertEqual((root / 'DEPS').read_text(), 'new\n')
