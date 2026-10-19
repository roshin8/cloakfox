"""Real BSD tar/zstd handoff, with the production safe extractor."""
import importlib.util
import io
import subprocess
import tarfile
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

PATH=Path(__file__).resolve().parents[2]/'scripts/ci/chromium_checkpoint.py'
def load():
    spec=importlib.util.spec_from_file_location('checkpoint',PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class NativeCheckpoint(unittest.TestCase):
    def test_native_roundtrip_preserves_nanoseconds_modes_hardlinks_and_absolute_links(self):
        m=load()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'source workspace';root.mkdir()
            obj=root/'compiled.o';obj.write_bytes(b'object');obj.chmod(0o755)
            os.link(obj,root/'hardlink');(root/'absolute').symlink_to(obj)
            stamp=1700000000123456789;os.utime(obj,ns=(stamp,stamp))
            archive=base/'out/workspace.tar.zst'
            with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20*m.GIB)):
                m.save(root,archive,{'root':str(root)})
                receipt=json.loads(archive.with_suffix('.json').read_text())
                self.assertEqual(receipt['compression'],'zstd')
                self.assertEqual(archive.read_bytes()[:4],b'\x28\xb5\x2f\xfd')
                shutil.rmtree(root)
                m.restore(root,archive,{'root':str(root)})
            self.assertEqual(obj.read_bytes(),b'object')
            self.assertEqual(obj.stat().st_mtime_ns,stamp)
            self.assertEqual(obj.stat().st_mode&0o777,0o755)
            self.assertEqual(obj.stat().st_ino,(root/'hardlink').stat().st_ino)
            self.assertFalse(Path(os.readlink(root/'absolute')).is_absolute())
            self.assertEqual((root/'absolute').read_bytes(),b'object')

    def test_native_excludes_only_verified_external_sdk_links(self):
        m=load()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);sdk=base/'SDK';sdk.mkdir();(sdk/'header').write_text('host')
            root=base/'workspace';relative=m.HOST_LINK_DIR/'SDK';link=root/relative
            link.parent.mkdir(parents=True);link.symlink_to(sdk)
            stamp=1700000000000000000
            os.utime(link.parent,ns=(stamp,stamp))
            identity={'hostSdkLinks':{str(relative):str(sdk.resolve())}}
            archive=base/'out/workspace.tar.zst'
            with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20*m.GIB)):
                m.save(root,archive,identity);shutil.rmtree(root);m.restore(root,archive,identity)
            self.assertEqual((link/'header').read_text(),'host')
            self.assertEqual(link.parent.stat().st_mtime_ns,stamp)
            (root/'bad').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError,'external symlink'):
                m.save(root,base/'bad/workspace.tar.zst',identity)

    def test_native_pipeline_failure_never_writes_receipt(self):
        m=load()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'workspace';root.mkdir();archive=base/'out/workspace.tar.zst'
            with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20*m.GIB)),patch.object(m,'ZSTD','/usr/bin/false'):
                with self.assertRaises(RuntimeError):m.save(root,archive,{})
            self.assertFalse(archive.with_suffix('.json').exists())

    def test_native_rejects_tamper_identity_and_escaping_members(self):
        m=load()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);archive=base/'workspace.tar.zst'
            raw=base/'hostile.tar'
            with tarfile.open(raw,'w') as bundle:
                entry=tarfile.TarInfo('workspace/../../escape');entry.size=1
                bundle.addfile(entry,io.BytesIO(b'x'))
            with archive.open('wb') as out:
                subprocess.run(['zstd','-q','-c',str(raw)],stdout=out,check=True)
            receipt={'schemaVersion':1,'compression':'zstd','archivePrefix':'workspace','identity':{},'sha256':m.digest(archive)}
            archive.with_suffix('.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'identity'):
                m.restore(base/'build',archive,{'changed':True})
            self.assertFalse((base/'build').exists())
            with self.assertRaises((ValueError,tarfile.FilterError)):
                m.restore(base/'build',archive,{})
            self.assertFalse((base/'escape').exists())
            archive.write_bytes(archive.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError,'SHA256'):
                m.restore(base/'build2',archive,{})
            self.assertFalse((base/'build2').exists())
