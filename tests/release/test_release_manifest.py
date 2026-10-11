"""Offline release verification, using ephemeral TEST-ONLY signing keys."""
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / 'scripts/release_manifest.py'


class ReleaseVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory()
        cls.private = pathlib.Path(cls.keys.name) / 'test-only.pem'
        cls.public = pathlib.Path(cls.keys.name) / 'test-only.pub'
        subprocess.run(['openssl', 'genrsa', '-out', str(cls.private), '2048'], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(cls.private), '-pubout', '-out', str(cls.public)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name)
        self.package = self.directory / 'Cloakfox.tar.xz'
        self.package.write_bytes(b'test package bytes')
        self.manifest = self.directory / 'release.json'
        self.signature = self.directory / 'release.sig'
        self.now = int(time.time())

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def create(self):
        result = self.run_cli('create', '--package', self.package, '--output', self.manifest,
                              '--version', '155.0.1', '--sequence', 12, '--platform', 'linux-x86_64',
                              '--channel', 'release', '--expires-at', self.now + 3600)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.sign()

    def sign(self):
        subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(self.private), '-out', str(self.signature), str(self.manifest)], check=True, capture_output=True)

    def verify(self, **changes):
        args = dict(manifest=self.manifest, signature=self.signature, public_key=self.public,
                    package=self.package, platform='linux-x86_64', channel='release', minimum_sequence=12)
        args.update(changes)
        return self.run_cli('verify', *[part for key, value in args.items() for part in ('--' + key.replace('_', '-'), value)])

    def reject(self, word, **changes):
        result = self.verify(**changes)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(word, result.stderr.lower())

    def test_valid_release(self):
        self.create()
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('verified', result.stdout)

    def test_tampered_package(self):
        self.create()
        self.package.write_bytes(b'tampered package!!')
        self.reject('package')

    def test_tampered_metadata(self):
        self.create()
        self.manifest.write_bytes(self.manifest.read_bytes() + b' ')
        self.reject('signature')

    def test_tampered_signature(self):
        self.create()
        self.signature.write_bytes(b'invalid')
        self.reject('signature')

    def test_missing_trust_root(self):
        self.create()
        self.reject('public key', public_key=self.directory / 'missing.pem')

    def test_wrong_valid_signing_key(self):
        self.create()
        other_private = self.directory / 'other-test-only.pem'
        other_public = self.directory / 'other-test-only.pub'
        subprocess.run(['openssl', 'genrsa', '-out', str(other_private), '2048'], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(other_private), '-pubout', '-out', str(other_public)], check=True, capture_output=True)
        self.reject('signature', public_key=other_public)

    def test_wrong_channel_platform_and_old_sequence(self):
        self.create()
        self.reject('channel', channel='nightly')
        self.reject('platform', platform='macos-arm64')
        self.reject('sequence', minimum_sequence=13)

    def test_signed_invalid_metadata(self):
        self.create()
        original = json.loads(self.manifest.read_text())
        for key, value, error in [('expires_at', self.now - 1, 'expired'),
                                   ('issued_at', self.now + 300, 'future'),
                                   ('filename', '../escape', 'filename'),
                                   ('sequence', True, 'sequence')]:
            with self.subTest(key=key):
                self.manifest.write_text(json.dumps(dict(original, **{key: value})))
                self.sign()
                self.reject(error)

    def test_symlink_package_rejected(self):
        self.create()
        target = self.directory / 'elsewhere'
        self.package.rename(target)
        self.package.symlink_to(target)
        self.reject('regular file')

    def test_unsigned_duplicate_fields_rejected_after_signature(self):
        self.create()
        self.manifest.write_text(self.manifest.read_text().rstrip()[:-1] + ', "sequence": 100}')
        self.sign()
        self.reject('duplicate')

    def test_creator_never_overwrites_manifest(self):
        self.create()
        result = self.run_cli('create', '--package', self.package, '--output', self.manifest,
                              '--version', '155.0.1', '--sequence', 12, '--platform', 'linux-x86_64',
                              '--channel', 'release', '--expires-at', self.now + 3600)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
