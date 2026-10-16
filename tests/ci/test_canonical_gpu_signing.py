import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CanonicalSigning(unittest.TestCase):
    def test_signing_refreshes_only_verified_bundle_then_seals_app(self):
        module = load(ROOT / 'scripts/ci/sign_canonical_gpu.py')
        build = module.builder()
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / 'Cloakfox.app'
            bundle = app / 'Contents/Resources/canonical-gpu'
            bundle.mkdir(parents=True)
            for name in build.LIBRARIES:
                (bundle / name).write_bytes(b'original')
            build.write_integrity_manifest(bundle, {
                'rendererVersion': 1, 'platform': 'macos-arm64',
                'hostRendererFallback': False, 'driverEnvironmentMutation': False,
                'revisions': {'.': build.ANGLE_REVISION,
                              'third_party/SwiftShader': build.SWIFTSHADER_REVISION}})
            commands = []

            def signer(command, **kwargs):
                commands.append(command)
                target = Path(command[-1])
                if '--verify' in command:
                    build.verify_integrity_manifest(bundle)
                elif '--deep' in command:
                    for name in build.LIBRARIES:
                        (bundle / name).write_bytes(b'app signed')
                elif target.suffix == '.dylib':
                    target.write_bytes(b'leaf signed')
                else:
                    # An outer resource seal must see the final leaf hashes.
                    build.verify_integrity_manifest(bundle)

            module.sign_bundle(bundle, 'commit', signer)
            self.assertEqual(module.verify(bundle, 'commit')['gitSha'], 'commit')
            module.sign_app(app, 'commit', signer)
            self.assertEqual(commands[-2], ['codesign', '--force', '--sign', '-', str(app)])
            self.assertIn('--verify', commands[-1])
            self.assertTrue(all((bundle / name).read_bytes() == b'app signed' for name in build.LIBRARIES))
            with self.assertRaises(ValueError):
                module.verify(bundle, 'wrong')
            (bundle / build.LIBRARIES[0]).write_bytes(b'tampered')
            previous = len(commands)
            with self.assertRaises(ValueError):
                module.sign_app(app, 'commit', signer)
            self.assertEqual(len(commands), previous)
