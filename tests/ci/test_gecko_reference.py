import hashlib,importlib.util,io,json,plistlib,tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
ROOT=Path(__file__).resolve().parents[2]
def load():
 spec=importlib.util.spec_from_file_location('gecko_reference',ROOT/'scripts/ci/gecko_reference.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class Reference(unittest.TestCase):
 def test_manifest_requires_one_exact_valid_digest(self):
  m=load();rel='mac/en-US/Firefox 159.0.dmg';line='a'*128+'  '+rel
  self.assertEqual(m.expected_digest(line,rel),'a'*128)
  for text in [line+'\n'+line,'z'*128+'  '+rel,'a'*128+'  ../Firefox.dmg']:
   with self.assertRaises(ValueError):m.expected_digest(text,rel)
 def test_corrupt_archive_is_rejected_before_mount(self):
  m=load();data=b'archive';rel='mac/en-US/Firefox 159.0.dmg';manifest=('a'*128+'  '+rel).encode()
  def fetch(url):return io.BytesIO(manifest if url.endswith('SHA512SUMS') else data)
  with tempfile.TemporaryDirectory() as directory,patch.object(m.subprocess,'run') as run:
   with self.assertRaises(ValueError):m.stage_reference('159.0',Path(directory),fetch)
   run.assert_not_called()
 def test_existing_app_is_never_replaced(self):
  m=load()
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory).resolve();(root/'Firefox.app').mkdir()
   with self.assertRaises(FileExistsError):m.stage_reference('159.0',root,lambda _:self.fail('Unexpected download'))
 def test_mount_is_detached_after_copy_failure(self):
  m=load();data=b'archive';manifest=(hashlib.sha512(data).hexdigest()+'  mac/en-US/Firefox 159.0.dmg').encode();calls=[]
  def fetch(url):return io.BytesIO(manifest if url.endswith('SHA512SUMS') else data)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory).resolve()
   def run(argv,**kwargs):
    calls.append(argv)
    if argv[:2]==['hdiutil','attach']:
     info=root/'mount/Firefox.app/Contents/Info.plist';info.parent.mkdir(parents=True);info.write_bytes(plistlib.dumps({'CFBundleIdentifier':'org.mozilla.firefox','CFBundleShortVersionString':'159.0'}))
   with patch.object(m.subprocess,'run',side_effect=run),patch.object(m.shutil,'copytree',side_effect=RuntimeError('fixture copy failed')):
    with self.assertRaisesRegex(RuntimeError,'fixture copy failed'):m.stage_reference('159.0',root,fetch)
   self.assertIn(['hdiutil','detach',str(root/'mount')],calls)
