"""Offline importer verification; never download a model during tests."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("fpgen_import", ROOT / "scripts/generate-fpgen-network.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FPGenImportTests(unittest.TestCase):
    def test_packaged_archive_reproduces_projection_and_provenance(self):
        directory = ROOT / "additions/browser/components/cloakfox"
        output = module.generate(directory / "fpgen-model-reference.zip")
        for name, content in output.items():
            self.assertEqual(content, (directory / name).read_bytes(), name)

    def test_tampered_archive_is_rejected(self):
        source = ROOT / "additions/browser/components/cloakfox/fpgen-model-reference.zip"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tampered.zip"
            content = bytearray(source.read_bytes())
            content[-1] ^= 1
            target.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "sha256"):
                module.generate(target)

    def test_network_validation_rejects_bad_dependencies_and_probabilities(self):
        good = {"nodes":[{"name":"root", "parentNames":[], "possibleValues":["!"], "conditionalProbabilities":{"!":1.0}}]}
        module.validate_network(good)
        for replacement in [0, -1, float("nan"), 2, "1"]:
            bad = json.loads(json.dumps(good))
            bad["nodes"][0]["conditionalProbabilities"]["!"] = replacement
            with self.assertRaises(ValueError): module.validate_network(bad)
        bad = json.loads(json.dumps(good))
        bad["nodes"][0]["parentNames"] = ["missing"]
        with self.assertRaises(ValueError): module.validate_network(bad)


if __name__ == "__main__":
    unittest.main()
