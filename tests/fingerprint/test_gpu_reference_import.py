"""Offline import safety and pairing tests using actual fpgen Firefox observations."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import zstandard

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from test_gpu_reference_import_fixture import PATHS


def compact_model():
    """Reindex real values; preserve conditional ownership and probabilities."""
    names = ["browser", "platformInfo", "gpu", "webgl", "webgl2"]
    nodes = {name: {"name": name, "parentNames": names[:i],
                    "possibleValues": [], "conditionalProbabilities": {}}
             for i, name in enumerate(names)}
    index, data, lookup = {}, bytearray(), {}
    for path in PATHS:
        tokens = {}
        for name in names:
            raw = json.dumps(path["values"][name], separators=(",", ":")).encode()
            if raw not in lookup:
                token = base64.b85encode(len(index).to_bytes(2, "big")).decode()
                lookup[raw] = token
                index[f"{len(data):x}"] = len(raw)
                data.extend(raw)
            tokens[name] = lookup[raw]
            if tokens[name] not in nodes[name]["possibleValues"]:
                nodes[name]["possibleValues"].append(tokens[name])
            branch = nodes[name]["conditionalProbabilities"]
            for parent in nodes[name]["parentNames"]:
                branch = branch.setdefault(tokens[parent], {})
            branch[tokens[name]] = path["probabilities"][name]
    return {"fingerprint-network.json": json.dumps({"nodes": list(nodes.values())}).encode(),
            "values.json": json.dumps(index).encode(), "values.dat": bytes(data)}


def archive(directory, blobs, names=None):
    pin = {"tag": "test-real-subset", "url": "offline-fixture", "files": {},
           "archive": {}, "license": {"spdx": "Apache-2.0"}}
    target = Path(directory) / "fixture.zip"
    with zipfile.ZipFile(target, "w") as zf:
        for name, raw in blobs.items():
            member = (names or {}).get(name, name + ".zst")
            compressed = zstandard.ZstdCompressor().compress(raw)
            zf.writestr(member, compressed)
            pin["files"][member] = {"sha256": hashlib.sha256(compressed).hexdigest(),
                "size": len(compressed), "decompressed_sha256": hashlib.sha256(raw).hexdigest(),
                "decompressed_size": len(raw)}
    pin["archive"] = {"size": target.stat().st_size,
                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    return target, pin


class ReferenceGPUImport(unittest.TestCase):
    def setUp(self):
        script = ROOT / "scripts/reference_gpu_import.py"
        self.assertTrue(script.exists(), "offline reference importer is missing")
        spec = importlib.util.spec_from_file_location("reference_gpu_import", script)
        self.importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.importer)

    def test_real_paired_records_preserve_caps_precision_extensions_and_probability(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, compact_model())
            catalog = self.importer.import_archive(path, pin)
        self.assertEqual({r["family"] for r in catalog["records"]}, {"apple", "intel", "amd", "nvidia"})
        self.assertEqual(len(catalog["records"]), 4)
        apple = next(r for r in catalog["records"] if r["family"] == "apple")
        self.assertEqual(apple["platform"], "Macintosh; Intel Mac OS X 10.15; rv:145.0")
        self.assertEqual(apple["gpu"]["renderer"], "Apple M1, or similar")
        gl2 = catalog["contexts"][apple["webgl2"]]
        self.assertEqual(gl2["observed"], PATHS[0]["values"]["webgl2"])
        self.assertEqual(gl2["staticCapabilities"]["parameters"]["35375"]["value"], 80)
        self.assertEqual(gl2["staticCapabilities"]["parameters"]["35076"]["value"], -8)
        self.assertEqual(gl2["staticCapabilities"]["parameters"]["35380"]["value"], 256)
        self.assertNotIn("2978", gl2["staticCapabilities"]["parameters"])
        self.assertIn("2978", gl2["observed"]["params"])
        self.assertEqual(apple["probabilities"]["webgl2"], PATHS[0]["probabilities"]["webgl2"])
        self.assertEqual(apple["admission"], "unvalidated-reference")
        self.assertEqual(apple["os"], "mac")

    def test_corrupt_archive_and_member_digest_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, compact_model())
            bad = copy.deepcopy(pin)
            bad["archive"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "archive.*sha256"):
                self.importer.import_archive(path, bad)
            bad = copy.deepcopy(pin)
            bad["files"]["values.json.zst"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "member.*sha256"):
                self.importer.import_archive(path, bad)

    def test_path_traversal_and_decompression_overrun_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, compact_model(), {"values.dat": "../values.dat.zst"})
            with self.assertRaisesRegex(ValueError, "member.*name"):
                self.importer.import_archive(path, pin)
            path, pin = archive(tmp, compact_model())
            pin["files"]["values.dat.zst"]["decompressed_size"] = 12
            with self.assertRaisesRegex(ValueError, "decompress.*(size|bound)"):
                self.importer.import_archive(path, pin)

    def test_oversized_decoder_window_is_rejected_before_output(self):
        # Pinned zstandard0.25.0 cext treats max_window_size as bytes. A small
        # frame declaring a64MiB window must fail the16MiB decoder guard even
        # though its decoded output fits the ordinary member byte bounds.
        blobs = compact_model()
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, blobs)
            with zipfile.ZipFile(path) as source:
                members = {name: source.read(name) for name in source.namelist()}
            frame = bytearray(zstandard.ZstdCompressor(write_content_size=False).compress(blobs['fingerprint-network.json']))
            self.assertEqual(frame[4] & 0x20, 0, 'fixture must include a window descriptor')
            frame[5] = 0x80
            self.assertEqual(zstandard.get_frame_parameters(frame).window_size, 64 << 20)
            name = 'fingerprint-network.json.zst'
            members[name] = bytes(frame)
            pin['files'][name]['sha256'] = hashlib.sha256(frame).hexdigest()
            pin['files'][name]['size'] = len(frame)
            with zipfile.ZipFile(path, 'w') as target:
                for name, raw in members.items():
                    target.writestr(name, raw)
            pin['archive'] = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(ValueError, 'bounded zstd'):
                self.importer.import_archive(path, pin)

    def test_decompressed_digest_and_invalid_offset_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, compact_model())
            pin["files"]["values.dat.zst"]["decompressed_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "decompress.*sha256"):
                self.importer.import_archive(path, pin)
            blobs = compact_model()
            pairs = json.loads(blobs["values.json"])
            pairs["ffffffff"] = 100
            blobs["values.json"] = json.dumps(pairs).encode()
            path, pin = archive(tmp, blobs)
            with self.assertRaisesRegex(ValueError, "offset|bounds"):
                self.importer.import_archive(path, pin)

    def test_cross_paired_gpu_and_gl2_are_rejected_even_with_valid_archive_hashes(self):
        blobs = compact_model()
        network = json.loads(blobs["fingerprint-network.json"])
        node = next(n for n in network["nodes"] if n["name"] == "webgl2")
        firefox = next(iter(node["conditionalProbabilities"].values()))
        mac = next(iter(firefox.values()))
        apple = next(iter(mac.values()))
        apple_gl1 = next(iter(apple))
        # Substitute a valid Intel GL2 leaf under the Apple GPU/GL1 path.
        intel = list(firefox.values())[1]
        intel_leaf = next(iter(next(iter(intel.values())).values()))
        apple[apple_gl1] = intel_leaf
        blobs["fingerprint-network.json"] = json.dumps(network).encode()
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, blobs)
            with self.assertRaisesRegex(ValueError, "GPU.*(owner|pair)"):
                self.importer.import_archive(path, pin)

    def test_deterministic_render_and_checked_in_catalog_reproduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, compact_model())
            first = self.importer.render(self.importer.import_archive(path, pin))
            second = self.importer.render(self.importer.import_archive(path, pin))
            self.assertEqual(first, second)
        source = ROOT / "firefox-src/.tools159/reference-gpu-research/model-release.zip"
        if source.exists():
            actual = self.importer.render(self.importer.import_archive(source))
            self.assertEqual(actual, (ROOT / "additions/cloakcfg/gpu-reference-records.json").read_text())

    def test_scalar_screen_preserves_required_values_and_does_not_admit_apple(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, pin = archive(tmp, compact_model())
            catalog = self.importer.import_archive(path, pin)
        matrix = self.importer.scalar_screen(catalog)
        self.assertEqual(matrix["backendBounds"]["webgl"]["36347"], 4096)
        self.assertEqual(matrix["backendBounds"]["webgl2"]["35658"], 16384)
        self.assertEqual(matrix["backendBounds"]["webgl"]["36348"], 31)
        self.assertEqual(matrix["backendProvenance"]["reportSha256"], "4db8606c68760562ab157c91074eea1d22315954ade1b0ef2f294b6f2694f308")
        apple = next(r for r in catalog["records"] if r["family"] == "apple")
        outcome = matrix["records"][apple["id"]]
        self.assertEqual(outcome["status"], "unsupported-scalar-requirement")
        ubo = next(b for b in outcome["blockers"] if b["pname"] == "35375")
        self.assertEqual(ubo["required"], 80)
        self.assertEqual(ubo["available"], 72)
        self.assertEqual(catalog["contexts"][apple["webgl2"]]["observed"]["params"]["35375"]["value"], 80)
        self.assertEqual(matrix["families"]["apple"]["webgl2"]["35375"], {"minimum": 80, "maximum": 80})
        self.assertTrue(all(r["admitted"] is False for r in matrix["records"].values()))

    def test_unrecognized_parent_order_and_invalid_probability_are_rejected(self):
        for defect in ("parents", "probability"):
            blobs = compact_model()
            network = json.loads(blobs["fingerprint-network.json"])
            node = next(n for n in network["nodes"] if n["name"] == "webgl2")
            if defect == "parents":
                node["parentNames"][-2:] = ["webgl", "gpu"]
            else:
                branch = node["conditionalProbabilities"]
                for _ in range(4):
                    branch = next(iter(branch.values()))
                branch[next(iter(branch))] = -0.1
            blobs["fingerprint-network.json"] = json.dumps(network).encode()
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as tmp:
                path, pin = archive(tmp, blobs)
                with self.assertRaisesRegex(ValueError, "parent order|probability"):
                    self.importer.import_archive(path, pin)


if __name__ == "__main__":
    unittest.main()
