import importlib.util,json,tempfile,unittest,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('download',ROOT/'scripts/ci/chromium_checkpoint_download.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Download(unittest.TestCase):
 def fixture(self,p,missing=False,bad=False,extra=False):
  archive=b'checkpoint objects';receipt={'schemaVersion':1,'sha256':hashlib.sha256(archive).hexdigest(),'identity':{'gitSha':'source'}}
  z=p/'artifact.zip'
  with zipfile.ZipFile(z,'w') as f:
   f.writestr('workspace.tar.zst',archive+b'x' if bad else archive)
   if not missing:f.writestr('workspace.tar.json',json.dumps(receipt))
   if extra:f.writestr('../escape',b'bad')
  return z,hashlib.sha256(z.read_bytes()).hexdigest()
 def test_complete_archive_verified_and_published(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);z,h=self.fixture(p);m.extract_verified(z,p/'out',h,'source');self.assertEqual((p/'out/workspace.tar.zst').read_bytes(),b'checkpoint objects')
 def test_incomplete_successful_download_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);z,h=self.fixture(p,missing=True)
   with self.assertRaises(ValueError):m.extract_verified(z,p/'out',h,'source')
   self.assertFalse((p/'out/workspace.tar.zst').exists())
 def test_wrong_digest_archive_source_and_extra_entry_rejected(self):
  for mode in ['digest','archive','source','extra','truncated']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    p=Path(d);z,h=self.fixture(p,bad=mode=='archive',extra=mode=='extra')
    if mode=='truncated':z.write_bytes(z.read_bytes()[:40]);h=hashlib.sha256(z.read_bytes()).hexdigest()
    with self.assertRaises((ValueError,zipfile.BadZipFile)):m.extract_verified(z,p/'out','0'*64 if mode=='digest' else h,'wrong' if mode=='source' else 'source')
    self.assertFalse((p/'out/workspace.tar.zst').exists())
 def test_download_rejects_wrong_ownership_before_transport(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   artifact={'id':5,'name':'chromium-workspace-15','expired':False,'workflow_run':{'id':99,'head_sha':'controller'}}
   with patch.object(m,'api',side_effect=[{'head_sha':'controller'},artifact]),patch.object(m.subprocess,'run') as transport:
    with self.assertRaises(ValueError):m.download('owner/repo','1','5','chromium-workspace-15',Path(d),'source')
    transport.assert_not_called()
 def test_successful_transport_with_truncated_bytes_rejected(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   artifact={'id':5,'name':'chromium-workspace-15','expired':False,'workflow_run':{'id':1,'head_sha':'controller'},'digest':'sha256:'+'0'*64,'size_in_bytes':100}
   def transport(repository,artifact_id,bundle,total):Path(bundle).write_bytes(b'partial')
   with patch.object(m,'api',side_effect=[{'head_sha':'controller'},artifact]),patch.object(m.shutil,'disk_usage',return_value=type('Usage',(),{'free':100*1024**3})()),patch.object(m,'transfer',side_effect=transport):
    with self.assertRaisesRegex(ValueError,'Truncated'):m.download('owner/repo','1','5','chromium-workspace-15',Path(d),'source')
    self.assertFalse((Path(d)/'workspace.tar.zst').exists())
 def test_range_transfer_resumes_after_timeout_and_validates_range(self):
  from unittest.mock import patch
  class Response:
   status=206
   def __init__(self,start,end,fail=False):self.headers={'Content-Range':f'bytes {start}-{end}/10'};self.body=b'0123456789'[start:end+1];self.fail=fail
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):
    if self.body:b=self.body[:3];self.body=self.body[3:];return b
    if self.fail:raise TimeoutError('fixture connection stalled')
    return b''
  requests=[]
  def open_(req,timeout):
   start,end=map(int,req.get_header('Range').split('=')[1].split('-'));requests.append((start,end))
   r=Response(start,end)
   if len(requests)==1:r.body=b'012';r.fail=True
   return r
  with tempfile.TemporaryDirectory() as d,patch.object(m,'signed_url',return_value='https://example.invalid/blob'),patch.object(m.urllib.request,'urlopen',side_effect=open_),patch.object(m.time,'sleep'):
   p=Path(d)/'zip';m.transfer('owner/repo',5,p,10);self.assertEqual(p.read_bytes(),b'0123456789');self.assertEqual(requests,[(0,9),(3,9)])
 def test_full_response_to_range_fails_closed(self):
  from unittest.mock import patch
  class Response:
   status=200;headers={}
   def __enter__(self):return self
   def __exit__(self,*a):pass
  with tempfile.TemporaryDirectory() as d,patch.object(m,'signed_url',return_value='https://example.invalid/blob'),patch.object(m.urllib.request,'urlopen',return_value=Response()):
   with self.assertRaises(ValueError):m.transfer('owner/repo',5,Path(d)/'zip',10)
