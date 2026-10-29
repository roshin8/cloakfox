import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / 'scripts/ci/sdk_client.py'

class SDKTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'SDK verifier is missing')
        spec = importlib.util.spec_from_file_location('sdk_client', MODULE)
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'source'; self.source.mkdir()
        subprocess.run(['git','init','-q',str(self.source)],check=True)
        p = self.source/'engines/chromium'; p.mkdir(parents=True)
        (p/'last.json').write_text(json.dumps({'inputs':[{'path':'engine.cc','afterSha256':'abc'}]}))
        subprocess.run(['git','-C',str(self.source),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.source),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
        rev = subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip()
        self.package = self.root/'package'; self.package.mkdir()
        sdk = self.root/'sdk'; sdk.mkdir(); (sdk/'engine').write_bytes(b'engine'); (sdk/'engine').chmod(0o644)
        (sdk/'link').symlink_to('engine')
        archive = self.package/'sdk.tar.gz'
        with tarfile.open(archive,'w:gz') as t: t.add(sdk,arcname='sdk')
        self.record = {'schema':1,'origin':'locally-built-sdk-import','clientRevision':rev,'sdkRoot':'sdk',
          'archiveSha256':self.m.digest(archive),'archiveBytes':archive.stat().st_size,
          'frameworkSha256':self.m.digest(sdk/'engine'),'patchLocks':{'last.json':self.m.digest(p/'last.json')},
          'sourceFiles':{'engine.cc':'abc'},'entries':self.m.inventory(sdk),'knownValidationFailures':[]}
        self.manifest = self.package/'sdk-import.json'
        self.lock = {'clientRevision':rev,'sdkSourceRevision':rev,'archiveName':'sdk.tar.gz','manifestSha256':'','archiveSha256':self.record['archiveSha256'],
          'archiveBytes':self.record['archiveBytes'],'frameworkSha256':self.record['frameworkSha256'],
          'patchLock':'last.json','frameworkPath':'engine'}
        self.save_manifest()

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.record)); self.lock['manifestSha256'] = self.m.digest(self.manifest)

    def verify(self):
        return self.m.verify_sdk(self.package,self.lock,self.source,self.root/'extract')

    def test_valid_archive_and_internal_symlink(self):
        sdk, record = self.verify()
        self.assertEqual((sdk/'link').read_bytes(),b'engine')
        self.assertEqual(record,self.record)

    def test_new_client_revision_can_reuse_unchanged_engine_contract(self):
        (self.source/'client.txt').write_text('compatible client update')
        subprocess.run(['git','-C',str(self.source),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.source),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','client'],check=True)
        self.lock['clientRevision']=subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip()
        sdk,record=self.verify()
        self.assertEqual(record['clientRevision'],self.lock['sdkSourceRevision'])
        self.assertEqual((sdk/'engine').read_bytes(),b'engine')

    def test_added_native_patch_cannot_reuse_old_sdk(self):
        (self.source/'engines/chromium/new-patch-lock.json').write_text('{}')
        subprocess.run(['git','-C',str(self.source),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.source),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','native change'],check=True)
        self.lock['clientRevision']=subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip()
        with self.assertRaisesRegex(ValueError,'native inputs'):self.verify()

    def commit_file(self,path):
        p=self.source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('changed')
        subprocess.run(['git','-C',str(self.source),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.source),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','change'],check=True)
        return subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip()

    def test_changed_compiler_recipe_rejects_sdk_reuse(self):
        self.lock['clientRevision']=self.commit_file('scripts/ci/chromium_source.py')
        with self.assertRaisesRegex(ValueError,'native inputs'):self.verify()

    def test_caller_shared_policy_cannot_test_old_pin(self):
        self.commit_file('engines/shared/privacy_contract.json')
        with self.assertRaisesRegex(ValueError,'differ'):self.m.verify_caller(self.source,self.lock)

    def test_caller_fingerprint_fixture_cannot_test_old_pin(self):
        self.commit_file('tests/fingerprint/library_audit_common.py')
        with self.assertRaisesRegex(ValueError,'differ'):self.m.verify_caller(self.source,self.lock)

    def test_caller_matching_inputs_pass(self):
        self.m.verify_caller(self.source,self.lock)

    def test_manifest_tampering_rejected(self):
        self.manifest.write_text('{}')
        with self.assertRaisesRegex(ValueError,'manifest'): self.verify()
        self.assertFalse((self.root/'extract').exists())

    def test_archive_tampering_rejected_before_extraction(self):
        with (self.package/'sdk.tar.gz').open('ab') as f:f.write(b'tamper')
        with self.assertRaisesRegex(ValueError,'archive'): self.verify()
        self.assertFalse((self.root/'extract').exists())

    def test_mismatched_client_revision(self):
        self.lock['clientRevision']='0'*40
        with self.assertRaisesRegex(ValueError,'revision'): self.verify()

    def test_changed_source_lock(self):
        (self.source/'engines/chromium/last.json').write_text('{}')
        with self.assertRaises((ValueError,KeyError)): self.verify()

    def test_wrong_file_inventory(self):
        self.record['entries']['engine']['sha256']='0'*64; self.save_manifest()
        with self.assertRaisesRegex(ValueError,'inventory'): self.verify()

    def test_read_only_sdk_resource_mode_is_preserved(self):
        (self.root/'sdk/engine').chmod(0o444)
        archive=self.package/'sdk.tar.gz'
        with tarfile.open(archive,'w:gz') as t:t.add(self.root/'sdk',arcname='sdk')
        self.record['archiveSha256']=self.lock['archiveSha256']=self.m.digest(archive)
        self.record['archiveBytes']=self.lock['archiveBytes']=archive.stat().st_size
        self.record['entries']=self.m.inventory(self.root/'sdk');self.save_manifest()
        sdk,_=self.verify()
        self.assertEqual((sdk/'engine').stat().st_mode & 0o777,0o444)

    def test_escaping_archive_rejected(self):
        import io
        archive=self.package/'sdk.tar.gz'
        with tarfile.open(archive,'w:gz') as t:
            item=tarfile.TarInfo('../escape');item.size=1;t.addfile(item,io.BytesIO(b'x'))
        self.record['archiveSha256']=self.lock['archiveSha256']=self.m.digest(archive)
        self.record['archiveBytes']=self.lock['archiveBytes']=archive.stat().st_size;self.save_manifest()
        with self.assertRaisesRegex(ValueError,'archive path'): self.verify()
        self.assertFalse((self.root/'escape').exists())

if __name__=='__main__':unittest.main()
