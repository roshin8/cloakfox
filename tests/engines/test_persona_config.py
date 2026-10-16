"""Portable persona ownership, revision and persistence behavior."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

class PersonaConfig(unittest.TestCase):
    def api(self):
        path = ROOT / 'engines/shared/persona_config.py'
        self.assertTrue(path.is_file(), 'Shared persona/config model is missing')
        from engines.shared.persona_config import PersonaStore, validate_snapshot
        return PersonaStore, validate_snapshot

    def test_persist_regenerate_and_clear_overrides(self):
        Store, validate = self.api()
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root))
            original = store.get('1', 'chromium')
            self.assertEqual(original['revision'], 1)
            self.assertEqual(validate(original), original)
            overridden = store.update(original, overrides={'canvas': False})
            self.assertEqual(overridden['revision'], 2)
            self.assertEqual(overridden['persona']['seed'], original['persona']['seed'])
            regenerated = store.regenerate(overridden, clear_overrides=False)
            self.assertNotEqual(regenerated['persona']['seed'], original['persona']['seed'])
            self.assertEqual(regenerated['persona']['overrides'], {'canvas': False})
            self.assertEqual(Store(Path(root)).get('1', 'chromium'), regenerated)
            cleared = store.regenerate(regenerated, clear_overrides=True)
            self.assertEqual(cleared['persona']['overrides'], {})
            self.assertEqual(cleared['revision'], 4)
            with self.assertRaisesRegex(ValueError, 'Stale'):
                store.update(original, enabled=False)
            self.assertEqual(store.get('1', 'chromium'), cleared)

    def test_private_and_engine_ownership_and_defensive_copies(self):
        Store, _ = self.api()
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root))
            private = store.get('1', 'chromium', private=True)
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertNotEqual(private['persona']['seed'], Store(Path(root)).get('1', 'chromium', private=True)['persona']['seed'])
            public = store.get('1', 'chromium')
            gecko = store.get('1', 'gecko')
            self.assertNotEqual(public['persona']['seed'], gecko['persona']['seed'])
            changed = store.get('1', 'chromium')
            changed['persona']['seed'] = '0' * 64
            self.assertEqual(store.get('1', 'chromium'), public)
            with self.assertRaises(ValueError):
                store.update(private, private=False, enabled=False)

    def test_validation_rejects_unknown_and_malformed_values(self):
        Store, validate = self.api()
        with tempfile.TemporaryDirectory() as root:
            base = Store(Path(root)).get('1', 'chromium')
            for key, bad in [('schemaVersion', 2), ('revision', True), ('revision', 0),
                             ('revision', 2**31), ('enabled', 1), ('engine', 'chrome'),
                             ('containerId', '../1'), ('private', 1), ('unknown', True)]:
                value = copy.deepcopy(base); value[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    validate(value)
            for key, bad in [('seed', 'a'*63), ('seed', 'g'*64), ('seed', 'A'*64),
                             ('options', {'canvas': 'false'}), ('options', {'navigator': True}),
                             ('overrides', {'canvas': 0}), ('unknown', True)]:
                value = copy.deepcopy(base); value['persona'][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    validate(value)

    def test_unsafe_or_corrupt_persistence_is_not_silently_replaced(self):
        Store, _ = self.api()
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            store = Store(folder); store.get('1', 'chromium')
            record = next(folder.glob('*.json'))
            record.chmod(0o644)
            with self.assertRaises(ValueError): Store(folder).get('1', 'chromium')
            record.chmod(0o600); record.write_text('{}')
            with self.assertRaises(ValueError): Store(folder).get('1', 'chromium')
            record.unlink(); record.symlink_to(folder / 'outside')
            with self.assertRaises(ValueError): Store(folder).get('1', 'chromium')

    def test_independent_store_updates_cannot_lose_revisions(self):
        Store, _ = self.api()
        with tempfile.TemporaryDirectory() as root:
            first = Store(Path(root)); second = Store(Path(root))
            a = first.get('1', 'chromium'); b = second.get('1', 'chromium')
            changed = first.update(a, enabled=False)
            with self.assertRaisesRegex(ValueError, 'Stale'):
                second.regenerate(b)
            self.assertEqual(second.get('1', 'chromium'), changed)

    def test_fifo_record_is_rejected_without_blocking(self):
        import os
        import subprocess
        Store, _ = self.api()
        with tempfile.TemporaryDirectory() as root:
            os.mkfifo(Path(root) / 'chromium-1.json', 0o600)
            child = subprocess.Popen([sys.executable, '-c',
                'from pathlib import Path; from engines.shared.persona_config import PersonaStore; '
                'import sys; '
                's=PersonaStore(Path(sys.argv[1])); '
                's.get("1", "chromium")', root], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                try: _, err = child.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    self.fail('FIFO persona file blocked the store')
                self.assertNotEqual(child.returncode, 0)
                self.assertIn('Unsafe persona file', err)
            finally:
                if child.poll() is None: child.kill(); child.communicate()

    def test_directory_permissions_revalidated_for_each_operation(self):
        Store, _ = self.api()
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root); store = Store(folder)
            folder.chmod(0o777)
            try:
                with self.assertRaisesRegex(ValueError, 'directory'):
                    store.get('1', 'chromium')
            finally: folder.chmod(0o700)
