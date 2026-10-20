import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('chromium_clients',ROOT/'scripts/ci/chromium_clients.py')
api=importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

class ChromiumClients(unittest.TestCase):
    def fixture(self, root, escape=False):
        root.mkdir()
        sdk=root/'source-sdk.tar.gz'
        data=b'real framework fixture bytes'
        with tarfile.open(sdk,'w:gz') as t:
            name='source-sdk/Release/Chromium Embedded Framework.framework/Chromium Embedded Framework'
            info=tarfile.TarInfo('../../escape' if escape else name); info.size=len(data)
            t.addfile(info,io.BytesIO(data))
        record={'gitSha':'producer','sourceFrameworkSha256':api.hashlib.sha256(data).hexdigest(),
                'sdkFrameworkSha256':api.hashlib.sha256(data).hexdigest(), 'sdkArchiveSha256':api.digest(sdk)}
        (root/'source-provenance.json').write_text(json.dumps(record))
        return record

    def test_restored_sdk_preserves_producer_and_validates_source_sdk_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); package=root/'package'; original=self.fixture(package)
            sdk,record=api.restore_sdk(package,root/'restored','producer')
            self.assertEqual(record,original)
            self.assertTrue((sdk/'Release/Chromium Embedded Framework.framework/Chromium Embedded Framework').is_file())
            with self.assertRaises(ValueError):api.restore_sdk(package,root/'wrong','wrong')
            original['sourceFrameworkSha256']='0'*64
            (package/'source-provenance.json').write_text(json.dumps(original))
            with self.assertRaises(ValueError):api.restore_sdk(package,root/'tampered','producer')

    def test_continued_sdk_source_requires_sealed_controller_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); package=root/'package';self.fixture(package)
            manifest={'producerSha':'controller','producerRun':'12','key':'key'}
            (package/'engine-artifact.json').write_text(json.dumps(manifest))
            lineage={'sourceSha':'producer','workflowSha':'controller','run':12,'key':'key'}
            (package/'checkpoint-producer.json').write_text(json.dumps(lineage))
            api.restore_sdk(package,root/'restored','controller',manifest)
            lineage['workflowSha']='foreign'
            (package/'checkpoint-producer.json').write_text(json.dumps(lineage))
            with self.assertRaises(ValueError):api.restore_sdk(package,root/'wrong','controller',manifest)

    def test_current_app_binding_preserves_original_engine_commit_and_rejects_changed_embedding(self):
        record={'gitSha':'producer','sourceFrameworkSha256':'hash','sdkFrameworkSha256':'hash'}
        current=api.app_provenance(record,'hash','consumer','key','123')
        self.assertEqual(current['gitSha'],'producer')
        self.assertEqual(current['appGitSha'],'consumer')
        self.assertEqual(current['engineProducerSha'],'producer')
        self.assertNotIn('appGitSha',record)
        with self.assertRaises(ValueError):api.app_provenance(record,'wrong','consumer','key','123')

    def test_archive_checksum_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';self.fixture(package,escape=True)
            with self.assertRaises((ValueError,tarfile.FilterError)):api.restore_sdk(package,root/'restored','producer')
            self.assertFalse((root/'escape').exists())
            (package/'source-sdk.tar.gz').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):api.restore_sdk(package,root/'other','producer')

if __name__=='__main__':unittest.main()
