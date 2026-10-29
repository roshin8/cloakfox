"""Full source traversal retains provenance without granting native admission."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from test_gpu_reference_import import archive, compact_model

spec = importlib.util.spec_from_file_location('full_gpu_import', ROOT / 'scripts/reference_gpu_import.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class FullGPUImport(unittest.TestCase):
    def test_all_browser_paths_and_legacy_output_are_reproducible(self):
        path = ROOT / 'additions/browser/components/cloakfox/fpgen-model-reference.zip'
        full = importer.import_full_archive(path)
        from collections import Counter
        self.assertEqual(Counter(r['browser'] for r in full['records']), {
            'Chrome': 642, 'Firefox': 106, 'Edge': 91, 'Opera': 38,
            'Yandex Browser': 5, 'Safari': 3, 'DuckDuckGo': 1})
        self.assertEqual(importer.render(importer.import_archive(path)), importer.OUTPUT.read_text())
        self.assertEqual(importer.compressed_full_catalog(full), importer.FULL_OUTPUT.read_bytes())
        self.assertEqual(importer.load_full_catalog(), full)
        self.assertEqual(importer.FULL_OUTPUT.read_bytes()[3:10], b'\x00' * 5 + b'\x02\xff')
        self.assertTrue(all(r['admission'] == 'unvalidated-reference' for r in full['records']))
        self.assertTrue(any(r['blockers'] for r in full['records']))
        for record in full['records']:
            self.assertEqual(set(record['sourceTokens']), set(importer.PARENTS))
            for name in ('webgl', 'webgl2'):
                observation = full['contexts'][record[name]]['observed']
                self.assertEqual(record[name], 'sha256:' + importer._digest(importer._canonical(observation)))

    def test_full_traversal_preserves_archive_and_conditional_guards(self):
        import copy
        import json
        blobs = compact_model()
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, blobs)
            bad = copy.deepcopy(pin)
            bad['archive']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'sha256'):
                importer.import_full_archive(path, bad)
            network = json.loads(blobs['fingerprint-network.json'])
            node = next(n for n in network['nodes'] if n['name'] == 'webgl2')
            node['parentNames'][-2:] = ['webgl', 'gpu']
            blobs['fingerprint-network.json'] = json.dumps(network).encode()
            path, pin = archive(tmp, blobs)
            with self.assertRaisesRegex(ValueError, 'parent order'):
                importer.import_full_archive(path, pin)

    def test_cross_owned_context_is_retained_but_path_is_blocked(self):
        import json
        blobs = compact_model()
        network = json.loads(blobs['fingerprint-network.json'])
        node = next(n for n in network['nodes'] if n['name'] == 'webgl2')
        firefox = next(iter(node['conditionalProbabilities'].values()))
        branches = list(firefox.values())
        apple = next(iter(branches[0].values()))
        intel_leaf = next(iter(next(iter(branches[1].values())).values()))
        apple[next(iter(apple))] = intel_leaf
        blobs['fingerprint-network.json'] = json.dumps(network).encode()
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, blobs)
            full = importer.import_full_archive(path, pin)
        blocked = [r for r in full['records'] if r['blockers']]
        self.assertEqual(len(blocked), 1)
        self.assertIn('owner', blocked[0]['blockers'][0]['reason'])
        self.assertEqual(blocked[0]['admission'], 'unvalidated-reference')
        self.assertEqual(len(full['records']), 4)

    def test_empty_and_invalid_context_observations_have_explicit_blockers(self):
        import json
        for replacement, reason in [([], 'not-recorded'), ({'unexpected': True}, 'incomplete recorded GL context')]:
            blobs = compact_model()
            offsets = json.loads(blobs['values.json'])
            data = blobs['values.dat']
            decoded = [json.loads(data[int(start, 16):int(start, 16) + size]) for start, size in offsets.items()]
            index = next(i for i, value in enumerate(decoded) if isinstance(value, dict) and 'params' in value)
            decoded[index] = replacement
            rebuilt, offsets = bytearray(), {}
            for value in decoded:
                raw = json.dumps(value).encode()
                offsets[f'{len(rebuilt):x}'] = len(raw)
                rebuilt.extend(raw)
            blobs['values.json'], blobs['values.dat'] = json.dumps(offsets).encode(), bytes(rebuilt)
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                path, pin = archive(tmp, blobs)
                full = importer.import_full_archive(path, pin)
                blocked = [record for record in full['records'] if record['blockers']]
                self.assertEqual(len(blocked), 1)
                self.assertEqual(blocked[0]['blockers'], [{'context': 'webgl', 'reason': reason}])
                self.assertIsNone(full['contexts'][blocked[0]['webgl']]['staticCapabilities'])

    def test_full_import_does_not_bless_incomplete_or_cross_owned_context(self):
        import json
        blobs = compact_model()
        # Keep the owner path intact while making its recorded data incomplete.
        index = json.loads(blobs['values.json'])
        data = blobs['values.dat']
        values = [json.loads(data[int(start, 16):int(start, 16) + size]) for start, size in index.items()]
        observation = next(v for v in values if isinstance(v, dict) and 'params' in v)
        del observation['params']
        rebuilt, offsets = bytearray(), {}
        for value in values:
            raw = json.dumps(value).encode()
            offsets[f'{len(rebuilt):x}'] = len(raw)
            rebuilt.extend(raw)
        blobs['values.json'], blobs['values.dat'] = json.dumps(offsets).encode(), bytes(rebuilt)
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, blobs)
            full = importer.import_full_archive(path, pin)
            blocked = [r for r in full['records'] if r['blockers']]
            self.assertEqual(len(blocked), 1)
            self.assertIn('incomplete', blocked[0]['blockers'][0]['reason'])
            self.assertIsNone(full['contexts'][blocked[0]['webgl']]['staticCapabilities'])
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                importer.import_archive(path, pin)


if __name__ == '__main__':
    unittest.main()
