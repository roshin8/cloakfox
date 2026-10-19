"""Full diagnostic orchestration uses real tiny archives, no compiler execution."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]

class Roundtrip(unittest.TestCase):
    def test_manifest_and_result_cover_full_legacy_to_native_restore(self):
        with patch.object(sys,'path',[str(ROOT/'scripts/ci'),*sys.path]):
            spec=importlib.util.spec_from_file_location('roundtrip',ROOT/'scripts/ci/checkpoint_roundtrip.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);original=base/'original';original.mkdir()
            (original/'object').write_bytes(b'compiler object')
            os.link(original/'object',original/'hardlink')
            (original/'relative').symlink_to('object')
            archive=base/'incoming/workspace.tar.gz'
            diagnostic=base/'checkpoint-roundtrip';diagnostic.mkdir()
            capacity=SimpleNamespace(free=20*m.checkpoint.GIB)
            with patch.object(m.checkpoint.shutil,'disk_usage',return_value=capacity):
                m.checkpoint.save(original,archive,{'gitSha':m.PRODUCER})
                with patch.object(m,'ARCHIVE_SHA',m.checkpoint.digest(archive)),patch.object(m,'ARCHIVE_BYTES',archive.stat().st_size),patch.dict(os.environ,{'RUNNER_TEMP':str(base),'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted'}):
                    m.run(diagnostic,archive.parent)
            result=json.loads((diagnostic/'result.json').read_text())
            self.assertTrue(result['verified'])
            self.assertFalse(result['compilerExecuted'])
            self.assertEqual((diagnostic/'before.jsonl').read_bytes(),(diagnostic/'after.jsonl').read_bytes())
            self.assertEqual((original/'object').read_bytes(),b'compiler object')
            self.assertTrue(archive.is_file())
