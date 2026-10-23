import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('policy',ROOT/'scripts/ci/chromium_cache_policy.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CachePolicy(unittest.TestCase):
    def test_module_cache_binds_source_host_identity_not_changing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);receipt=p/'receipt.json';context=p/'context.json'
            record={'schemaVersion':1,'sha256':'first','identity':{'gitSha':'source','hostBuildInputs':{'sdk':'one'}}}
            receipt.write_text(json.dumps(record));env=m.settings(receipt,context,'key','source');first=context.read_bytes()
            self.assertEqual(env['CCACHE_SLOPPINESS'],'modules')
            self.assertEqual(env['CCACHE_COMPILERCHECK'],'content')
            self.assertEqual(env['CCACHE_DEPEND'],'true')
            record['sha256']='second';receipt.write_text(json.dumps(record));m.settings(receipt,context,'key','source');self.assertEqual(context.read_bytes(),first)
            record['identity']['hostBuildInputs']['sdk']='two';receipt.write_text(json.dumps(record));m.settings(receipt,context,'key','source');self.assertNotEqual(context.read_bytes(),first)
            with self.assertRaises(ValueError):m.settings(receipt,context,'key','wrong-source')

    def test_missing_host_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=p/'receipt';r.write_text(json.dumps({'schemaVersion':1,'identity':{'gitSha':'source'}}))
            with self.assertRaises(ValueError):m.settings(r,p/'out','key','source')
            self.assertFalse((p/'out').exists())

    def test_fourth_worker_requires_high_memory_and_available_cpu(self):
        self.assertEqual(m.compile_jobs(4,14*1024**3),4)
        self.assertEqual(m.compile_jobs(4,12*1024**3),3)
        self.assertEqual(m.compile_jobs(2,14*1024**3),2)
        self.assertEqual(m.compile_jobs(16,32*1024**3),4)
