"""A capability label or unrelated golden image must never certify emulation."""
import copy
import unittest
from gpu_reference_evidence import validate_reference, compare_reference


def reference():
    return {
        'schemaVersion': 1,
        'source': {'url': 'https://example.org/reference.json', 'sha256': 'a' * 64},
        'target': {'family': 'apple', 'model': 'Apple test model', 'driver': 'test-driver',
                   'backend': 'Metal', 'os': 'macos', 'browserEngine': 'gecko', 'browserVersion': '159.0'},
        'corpus': {'sha256': 'b' * 64, 'cases': ['gradient', 'texture']},
        'capabilities': {'MAX_TEXTURE_SIZE': 8192},
        'outputs': {'gradient': {'width': 1, 'height': 1, 'rgba': [1, 2, 3, 255]},
                    'texture': {'width': 1, 'height': 1, 'rgba': [4, 5, 6, 255]}},
    }


class GPUReferenceEvidence(unittest.TestCase):
    def test_complete_corpus_compares_exact_pixels_and_limits(self):
        r = reference()
        result = compare_reference(r, copy.deepcopy(r))
        self.assertTrue(result['corpusMatches'])
        self.assertFalse(result['fullEmulationValidated'])

    def test_capability_only_reports_are_not_rendering_evidence(self):
        r = reference(); del r['outputs']
        with self.assertRaises(ValueError): validate_reference(r)

    def test_missing_cases_and_truncated_pixels_fail(self):
        for change in ('case', 'pixels'):
            r = reference()
            if change == 'case': del r['outputs']['texture']
            else: r['outputs']['texture']['rgba'].pop()
            with self.assertRaises(ValueError): validate_reference(r)

    def test_unknown_driver_and_unsafe_source_do_not_qualify(self):
        for field, value in [('driver', ''), ('model', 'unknown'), ('backend', '')]:
            r = reference(); r['target'][field] = value
            with self.assertRaises(ValueError): validate_reference(r)
        r = reference(); r['source']['url'] = 'file:///private/reference'
        with self.assertRaises(ValueError): validate_reference(r)

    def test_different_corpus_or_browser_is_not_comparable(self):
        for mutate in ('hash', 'browser', 'version', 'model'):
            r = reference(); candidate = reference()
            if mutate == 'hash': candidate['corpus']['sha256'] = 'c' * 64
            elif mutate == 'browser': candidate['target']['browserEngine'] = 'chromium'
            elif mutate == 'version': candidate['target']['browserVersion'] = '158.0'
            else: candidate['target']['model'] = 'Different GPU'
            with self.assertRaises(ValueError): compare_reference(r, candidate)

    def test_mismatched_pixels_or_caps_never_pass(self):
        for mutate in ('pixel', 'caps'):
            candidate = reference()
            if mutate == 'pixel': candidate['outputs']['texture']['rgba'][0] += 1
            else: candidate['capabilities']['MAX_TEXTURE_SIZE'] = 6144
            result = compare_reference(reference(), candidate)
            self.assertFalse(result['corpusMatches'])
            self.assertFalse(result['fullEmulationValidated'])

    def test_invalid_pixel_types_duplicates_and_nonfinite_caps_fail(self):
        for mutate in ('boolean', 'range', 'duplicate', 'nan'):
            r = reference()
            if mutate == 'boolean': r['outputs']['texture']['rgba'][0] = True
            elif mutate == 'range': r['outputs']['texture']['rgba'][0] = 256
            elif mutate == 'duplicate': r['corpus']['cases'].append('texture')
            else: r['capabilities']['MAX_TEXTURE_SIZE'] = float('nan')
            with self.assertRaises(ValueError): validate_reference(r)
