"""Canvas evidence must be collected before determinism/pixel comparisons."""
import unittest
import json
from library_audit_common import ROOT
from probe_full_gpu_libraries import canvas_evidence, summarize_library, CAP_KEYS


class CanvasEvidenceTest(unittest.TestCase):
    def test_missing_and_sentinel_images_do_not_hash(self):
        for image in [None, '', 'unsupported', 'data:image/png;base64,', 'data:image/png;base64,  ']:
            for library, sample in [
                ('creepjs', {'fingerprint': {'canvas2d': {'dataURI': image}}}),
                ('fingerprintjs', {'rawCanvas': {'geometry': image, 'text': 'data:image/png;base64,abc'}}),
                ('fingerprintjs', {'rawCanvas': {'geometry': 'data:image/png;base64,abc', 'text': image}}),
            ]:
                with self.subTest(library=library, image=image):
                    self.assertEqual(canvas_evidence(library, sample), {'collected': False, 'sha256': None})
        for sample in [{'fingerprint': None}, {'fingerprint': {'canvas2d': None}}]:
            self.assertEqual(canvas_evidence('creepjs', sample), {'collected': False, 'sha256': None})
        self.assertEqual(canvas_evidence('fingerprintjs', {'rawCanvas': None}), {'collected': False, 'sha256': None})
        for library in ['creepjs', 'fingerprintjs']:
            self.assertEqual(canvas_evidence(library, {}), {'collected': False, 'sha256': None})

    def test_creep_summary_preserves_separate_image_and_webgl_evidence(self):
        expected = dict.fromkeys(CAP_KEYS, 2)
        params = {**expected, 'UNMASKED_VENDOR_WEBGL': 'Vendor',
                  'UNMASKED_RENDERER_WEBGL': 'Renderer'}
        sample = {'fingerprint': {'canvas2d': {'dataURI': 'data:image/png;base64,abc'},
                  'canvasWebgl': {'$hash': 'actual-webgl-hash', 'parameters': params},
                  'trash': {'trashBin': []}, 'navigator': {'platform': 'Win32'},
                  'workerScope': {'platform': 'Win32'}}}
        checks = []
        summary = summarize_library('creepjs', sample,
                    {'vendor': 'Vendor', 'renderer': 'Renderer'},
                    {'navigator.platform': 'Win32'}, expected, 'fixture',
                    lambda ok, *args: checks.append(ok))
        self.assertTrue(all(checks))
        self.assertEqual(summary['webglHash'], 'actual-webgl-hash')
        self.assertTrue(summary['canvasCollected'])
        self.assertEqual(summary['canvasSHA256'], canvas_evidence('creepjs', sample)['sha256'])
        sample['fingerprint']['canvas2d'] = {}
        checks.clear()
        summary = summarize_library('creepjs', sample,
                    {'vendor': 'Vendor', 'renderer': 'Renderer'},
                    {'navigator.platform': 'Win32'}, expected, 'fixture',
                    lambda ok, *args: checks.append(ok))
        self.assertFalse(all(checks))
        self.assertIsNone(summary['canvasSHA256'])
        self.assertFalse(summary['canvasCollected'])

    def test_fingerprintjs_gecko_coverage_requires_real_basics_and_numeric_caps(self):
        profile = json.loads((ROOT/'additions/cloakcfg/gpu-reference-executable.json').read_text())['observedProfiles'][0]
        parameters = profile['contexts']['webgl']['parameters']
        collected = []
        for key in ['3379', '3386', '34921', '36347', '36349', '35661']:
            entry = parameters[key]
            value = ','.join(map(str, entry['value'])) if isinstance(entry['value'], list) else str(entry['value'])
            collected.append(f"{entry['name']}={key}={value}")
        basics = dict(vendorUnmasked='', rendererUnmasked='', vendor='masked vendor', renderer='masked renderer', version='WebGL 1', shadingLanguageVersion='GLSL')
        sample = {'rawCanvas': {'geometry': 'data:image/png;base64,abc', 'text': 'data:image/png;base64,def'},
                  'components': {'webGlBasics': {'value': basics}, 'webGlExtensions': {'value': {'parameters': collected}}}}
        checks = []
        summary = summarize_library('fingerprintjs', sample, profile, {}, {}, 'fixture', lambda ok, *args: checks.append(ok))
        self.assertTrue(all(checks))
        self.assertEqual(summary['identity'], ['', ''])
        basics['renderer'] = ''
        checks.clear()
        summarize_library('fingerprintjs', sample, profile, {}, {}, 'fixture', lambda ok, *args: checks.append(ok))
        self.assertFalse(all(checks))
        basics['renderer'] = 'masked renderer'
        sample['components']['webGlExtensions']['value']['parameters'] = []
        checks.clear()
        summarize_library('fingerprintjs', sample, profile, {}, {}, 'fixture', lambda ok, *args: checks.append(ok))
        self.assertFalse(all(checks))

    def test_real_image_evidence_is_required_and_deterministic(self):
        for library, sample in [
            ('creepjs', {'fingerprint': {'canvas2d': {'dataURI': 'data:image/png;base64,abc'}}}),
            ('fingerprintjs', {'rawCanvas': {'geometry': 'data:image/png;base64,abc', 'text': 'data:image/png;base64,def'}}),
        ]:
            evidence = canvas_evidence(library, sample)
            self.assertTrue(evidence['collected'])
            self.assertEqual(len(evidence['sha256']), 64)
            self.assertEqual(evidence, canvas_evidence(library, sample))


if __name__ == '__main__':
    unittest.main()
