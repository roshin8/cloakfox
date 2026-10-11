import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import release_config as config
class ReleaseConfig(unittest.TestCase):
    def test_reject_unsafe_hosts(self):
        for value in ['http://updates.example.com','localhost','evil.test/path','x.mozilla.org','x.invalid','a.test\nexport EVIL=1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                config.validate_host(value)
    def test_owner_hostname(self):
        self.assertEqual(config.validate_host('updates.owner.net'), 'updates.owner.net')

class PrepareRelease(unittest.TestCase):
    def test_real_certificates_and_private_provider_file(self):
        import argparse
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            certdir = source / 'toolkit/mozapps/update/updater'
            certdir.mkdir(parents=True)
            (source / 'build').mkdir()
            (source / 'mozconfig').write_text('ac_add_options --disable-updater\n')
            (source / 'build/application.ini.in').write_text('URL=https://@MOZ_APPUPDATE_HOST@/update/6/update.xml\n')
            bundled = root / 'bundled.der'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root / 'bundled.pem'),'-outform','DER','-out',str(bundled),'-days','365','-subj','/CN=BUNDLED TEST ONLY'], check=True, capture_output=True)
            certs = []
            for name in ('primary', 'secondary'):
                cert = root / (name + '.der')
                subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root / (name + '.pem')),'-outform','DER','-out',str(cert),'-days','365','-subj','/CN=TEST ONLY'], check=True, capture_output=True)
                certs.append(cert)
                (certdir / ('release_' + name + '.der')).write_bytes(bundled.read_bytes())
            key = root / 'provider.txt'
            key.write_text('TEST_ONLY_NOT_A_REAL_KEY_12345')
            key.chmod(0o600)
            args = argparse.Namespace(source=source, platform='linux', host='updates.owner.net', primary=certs[0], secondary=certs[1], provider_key=key)
            config.prepare(args)
            text = (source / 'mozconfig').read_text()
            self.assertIn('--disable-unverified-updates', text)
            self.assertNotIn('TEST_ONLY_NOT_A_REAL_KEY', text)
            self.assertEqual((certdir / 'release_primary.der').read_bytes(), certs[0].read_bytes())
            self.assertIn('https://updates.owner.net/', (source / 'build/application.ini.in').read_text())
            args.platform = 'macos'
            with self.assertRaisesRegex(ValueError, 'Team ID'):
                config.prepare(args)

class MacOwnerPin(unittest.TestCase):
    def test_actual_native_requirements_keep_owner_and_apple_constraints(self):
        import ast
        path = Path(__file__).resolve().parents[2] / 'firefox-src/build/moz.configure/update-programs.configure'
        if not path.exists():
            self.skipTest('Native source unavailable in source-less unit CI; patch checked in native build')
        tree = ast.parse(path.read_text())
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'mac_prod_requirements_string']
        namespace = {}
        exec(compile(ast.Module(body=funcs, type_ignores=[]), str(path), 'exec'), namespace)
        requirement = namespace['mac_prod_requirements_string']('org.mozilla.updater', 'A1B2C3D4E5')
        self.assertIn('subject.OU] = "A1B2C3D4E5"', requirement)
        self.assertIn('anchor apple generic', requirement)
        self.assertIn('certificate leaf[field.1.2.840.113635.100.6.1.13]', requirement)
        self.assertNotIn('43AQ936H96', requirement)

    def test_missing_foreign_and_malformed_mac_identity_fail_before_source_mutation(self):
        import argparse
        for team, identity, error in [(None,None,'Team ID'), ('43AQ936H96','Developer ID Application: Mozilla (43AQ936H96)','Team ID'), ('A1B2C3D4E5',None,'signing identity'), ('A1B2C3D4E5','Developer ID Application: Owner (Z1Z2Z3Z4Z5)','signing identity')]:
            args = argparse.Namespace(platform='macos', mac_team_id=team, mac_signing_identity=identity)
            with self.subTest(team=team, identity=identity), self.assertRaisesRegex(ValueError, error):
                config.prepare(args)


class PublicKeyTrust(unittest.TestCase):
    def issue(self, root, name, key=None):
        import subprocess
        path = root / (name + '.der')
        command = ['openssl', 'req', '-x509', '-nodes', '-outform', 'DER',
                   '-out', str(path), '-days', '365', '-subj', '/CN=' + name]
        if key is None:
            key = root / (name + '.pem')
            command += ['-newkey', 'rsa:2048', '-keyout', str(key)]
        else:
            command += ['-key', str(key)]
        subprocess.run(command, check=True, capture_output=True)
        return path, key

    def test_different_certificates_with_same_key_are_not_rotation_keys(self):
        import argparse
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary, key = self.issue(root, 'primary')
            secondary, _ = self.issue(root, 'secondary', key)
            self.assertNotEqual(primary.read_bytes(), secondary.read_bytes())
            self.assertEqual(config.certificate_spki(primary.read_bytes()), config.certificate_spki(secondary.read_bytes()))
            args = argparse.Namespace(platform='linux', host='updates.owner.net', primary=primary, secondary=secondary)
            with self.assertRaisesRegex(ValueError, 'distinct.*public keys'):
                config.prepare(args)

    def test_reissued_bundled_key_is_rejected_before_any_source_mutation(self):
        import argparse
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundled, key = self.issue(root, 'bundled')
            primary, _ = self.issue(root, 'reissued', key)
            secondary, _ = self.issue(root, 'independent')
            source = root / 'source'
            certdir = source / 'toolkit/mozapps/update/updater'
            certdir.mkdir(parents=True)
            (source / 'build').mkdir()
            files = {source / 'mozconfig': b'ac_add_options --disable-updater\n',
                     source / 'build/application.ini.in': b'URL=https://@MOZ_APPUPDATE_HOST@/update/6/update.xml\n',
                     certdir / 'release_primary.der': bundled.read_bytes(),
                     certdir / 'release_secondary.der': bundled.read_bytes()}
            for path, raw in files.items():
                path.write_bytes(raw)
            provider = root / 'provider.txt'
            provider.write_text('TEST_ONLY_NOT_A_REAL_KEY_12345')
            provider.chmod(0o600)
            args = argparse.Namespace(source=source, platform='linux', host='updates.owner.net',
                                      primary=primary, secondary=secondary, provider_key=provider)
            self.assertNotEqual(primary.read_bytes(), bundled.read_bytes())
            with self.assertRaisesRegex(ValueError, 'bundled upstream or test trust roots'):
                config.prepare(args)
            for path, raw in files.items():
                self.assertEqual(path.read_bytes(), raw)
            self.assertFalse((source / 'cloakfox-release-inputs.json').exists())
