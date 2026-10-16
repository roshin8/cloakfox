import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def api():
    spec = importlib.util.spec_from_file_location('library_common', HERE / 'library_audit_common.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample(library):
    if library == 'fingerprintjs':
        return {'visitorId': 'a' * 32, 'rawCanvas': {'geometry': 'data:image/png;a', 'text': 'data:image/png;b'},
                'components': {key: {'value': value} for key, value in
                               [('canvas', {'geometry': 'stable'}), ('audio', 12.5), ('timezone', 'UTC'),
                                ('platform', 'MacIntel'), ('screenResolution', [1280, 720])]}}
    fingerprint = {key: {'$hash': key} for key in
                   ['canvas2d', 'offlineAudioContext', 'cssMedia', 'screen', 'navigator', 'workerScope']}
    for field in ['dataURI', 'paintURI', 'paintCpuURI', 'textURI', 'emojiURI']:
        fingerprint['canvas2d'][field] = 'data:image/png;' + field
    for key in ['navigator', 'workerScope']:
        fingerprint[key].update(platform='MacIntel', hardwareConcurrency=8)
    values = {'color-gamut': 'srgb', 'device-screen': '720x1280', 'prefers-reduced-motion': False, 'forced-colors': False}
    fingerprint['cssMedia'].update(mediaCSS=values, matchMediaCSS=dict(values))
    return {'fingerprint': fingerprint, 'creep': {'lies': {'unmodified-detector-warning': True}}}


class LibraryContract(unittest.TestCase):
    def test_missing_samples_collection_errors_and_instability_fail(self):
        contract = api()
        for library in ('fingerprintjs', 'creepjs'):
            good = sample(library)
            self.assertTrue(all(item['pass'] for item in contract.validate_samples(library, [good, copy.deepcopy(good), copy.deepcopy(good)])))
            self.assertFalse(all(item['pass'] for item in contract.validate_samples(library, [good])))
            self.assertFalse(all(item['pass'] for item in contract.validate_samples(library, [good, {'error': 'collection failed'}, good])))
            changed = copy.deepcopy(good)
            if library == 'fingerprintjs':
                changed['rawCanvas']['geometry'] = 'data:image/png;different'
            else:
                changed['fingerprint']['canvas2d']['dataURI'] = 'data:image/png;different'
            self.assertFalse(all(item['pass'] for item in contract.validate_samples(library, [good, good, changed])))

    def test_worker_disagreement_fails_but_detector_warnings_are_retained(self):
        contract = api()
        good = sample('creepjs')
        before = copy.deepcopy(good)
        self.assertTrue(all(item['pass'] for item in contract.validate_samples('creepjs', [good, good, good])))
        self.assertEqual(good, before)
        changed = copy.deepcopy(good)
        changed['fingerprint']['workerScope']['platform'] = 'Linux x86_64'
        self.assertFalse(all(item['pass'] for item in contract.validate_samples('creepjs', [changed, changed, changed])))

    def test_audio_failure_sentinels_are_not_real_collections(self):
        contract = api()
        for value in (-1, -2, -3, 0, True, float('nan'), float('inf')):
            changed = sample('fingerprintjs')
            changed['components']['audio']['value'] = value
            with self.subTest(value=value):
                self.assertFalse(all(item['pass'] for item in contract.validate_samples('fingerprintjs', [changed, changed, changed])))

    def test_native_controls_must_ignore_different_container_seeds(self):
        contract = api()
        first = {library: [sample(library)] for library in ('fingerprintjs', 'creepjs')}
        second = copy.deepcopy(first)
        self.assertTrue(all(item['pass'] for item in contract.validate_native_controls(first, second)))
        second['fingerprintjs'][0]['rawCanvas']['geometry'] = 'data:image/png;still-masked'
        second['creepjs'][0]['fingerprint']['canvas2d']['dataURI'] = 'data:image/png;still-masked'
        self.assertFalse(all(item['pass'] for item in contract.validate_native_controls(first, second)))
