import hashlib,importlib.util,io,json,re,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[2]/'scripts/ci/chromium_checkpoint_download.py'
s=importlib.util.spec_from_file_location('download',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ParallelDownload(unittest.TestCase):
 def test_disjoint_ranges_complete_out_of_order_and_resume_only_failed_range(self):
  data=b'0123456789abcdefghij';requests=[];lock=threading.Lock();active=0;peak=0;failed=False
  def open_(request,timeout):
   nonlocal active,peak,failed
   match=re.fullmatch(r'bytes=(\d+)-(\d+)',request.get_header('Range'));start,end=map(int,match.groups())
   with lock:requests.append((start,end));active+=1;peak=max(peak,active)
   class Response:
    status=206;headers={'Content-Range':f'bytes {start}-{end}/{len(data)}'}
    def __enter__(self):time.sleep(.01);self.pos=start;return self
    def __exit__(self,*a):
     nonlocal active
     with lock:active-=1
    def read(self,n):
     nonlocal failed
     if start==0 and self.pos==2 and not failed:
      failed=True;raise TimeoutError('fixture')
     if self.pos>end:return b''
     n=min(n,2);out=data[self.pos:min(self.pos+n,end+1)];self.pos+=len(out);return out
   return Response()
  with tempfile.TemporaryDirectory() as d,patch.object(m,'signed_url',return_value='https://blob.invalid'),patch.object(m.urllib.request,'urlopen',side_effect=open_):
   out=Path(d)/'zip';m.transfer('o/r',1,out,len(data),workers=4,range_bytes=5)
   self.assertEqual(out.read_bytes(),data);self.assertGreater(peak,1);self.assertLessEqual(peak,4)
   self.assertIn((2,4),requests);self.assertEqual(requests.count((0,4)),1)
 def test_archive_hash_is_computed_while_copying_not_rereading(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);bundle=root/'zip';data=b'objects'*1024
   receipt={'schemaVersion':1,'identity':{'gitSha':'s'},'sha256':hashlib.sha256(data).hexdigest()}
   with zipfile.ZipFile(bundle,'w') as z:
    z.writestr('workspace.tar.zst',data);z.writestr('workspace.tar.json',json.dumps(receipt))
   original=m.digest;seen=[]
   def digest(path):seen.append(Path(path));return original(path)
   with patch.object(m,'digest',side_effect=digest):m.extract_verified(bundle,root/'out',original(bundle),'s',receipt['sha256'])
   self.assertEqual(seen,[bundle])
 def test_failed_range_cannot_publish_sparse_or_partial_archive(self):
  class Response:
   status=206
   headers={'Content-Range':'bytes 0-9/10'}
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):raise TimeoutError('stalled range')
  with tempfile.TemporaryDirectory() as d,patch.object(m,'signed_url',return_value='https://blob.invalid'),patch.object(m.urllib.request,'urlopen',return_value=Response()) as calls,patch.object(m.threading.Event,'wait',return_value=False):
   with self.assertRaises(TimeoutError):m.transfer('o/r',1,Path(d)/'zip',10)
   self.assertEqual(calls.call_count,5)
 def test_positive_download_preserves_verified_lineage_and_reports_phases(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);z=root/'fixture.zip';data=b'objects'
   sha=hashlib.sha256(data).hexdigest();receipt={'schemaVersion':1,'identity':{'gitSha':'source'},'sha256':sha}
   with zipfile.ZipFile(z,'w') as archive:
    archive.writestr('workspace.tar.zst',data);archive.writestr('workspace.tar.json',json.dumps(receipt))
   artifact={'id':5,'name':'chromium-workspace-21','expired':False,'workflow_run':{'id':1,'head_sha':'controller'},'digest':'sha256:'+hashlib.sha256(z.read_bytes()).hexdigest(),'size_in_bytes':z.stat().st_size}
   def transport(repository,artifact_id,bundle,total):Path(bundle).write_bytes(z.read_bytes());return {'downloadWorkers':4,'downloadBytes':total}
   with patch.object(m,'api',side_effect=[{'id':1,'head_sha':'controller'},artifact]),patch.object(m,'producer_hash',return_value=sha),patch.object(m,'transfer',side_effect=transport),patch.object(m.shutil,'disk_usage',return_value=type('Usage',(),{'free':100*1024**3})):
    result=m.download('o/r','1','5','chromium-workspace-21',root/'out','source')
   self.assertTrue(result['verified']);self.assertEqual(result['archiveSha256'],sha);self.assertEqual(result['downloadWorkers'],4)
   self.assertIn('zipVerificationSeconds',result);self.assertIn('archiveExtractionAndVerificationSeconds',result)
 def test_crc_failure_not_hidden_by_stream_hash(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);z=root/'bad.zip';data=b'unique-object-payload'
   receipt={'schemaVersion':1,'identity':{'gitSha':'s'},'sha256':hashlib.sha256(data).hexdigest()}
   with zipfile.ZipFile(z,'w') as archive:
    archive.writestr('workspace.tar.zst',data);archive.writestr('workspace.tar.json',json.dumps(receipt))
   raw=z.read_bytes().replace(data,b'X'+data[1:]);z.write_bytes(raw)
   with self.assertRaises(zipfile.BadZipFile):m.extract_verified(z,root/'out',hashlib.sha256(raw).hexdigest(),'s')
   self.assertFalse((root/'out/workspace.tar.zst').exists())
 def test_invalid_range_cancels_another_active_download_before_handoff(self):
  first_entered=threading.Event();invalid_returned=threading.Event()
  def open_(request,timeout):
   start,end=map(int,re.fullmatch(r'bytes=(\d+)-(\d+)',request.get_header('Range')).groups())
   class Response:
    status=206
    headers={'Content-Range':f'bytes {start}-{end}/10' if start==0 else 'bytes 999-999/10'}
    def __enter__(self):
     if start==0:first_entered.set()
     else:
      self_wait=first_entered.wait(2);invalid_returned.set()
     return self
    def __exit__(self,*a):pass
    def read(self,n):
     if not invalid_returned.wait(2):raise AssertionError('Second range never started')
     time.sleep(.02);return b'x'
   return Response()
  with tempfile.TemporaryDirectory() as d,patch.object(m,'signed_url',return_value='https://blob.invalid'),patch.object(m.urllib.request,'urlopen',side_effect=open_):
   with self.assertRaisesRegex(ValueError,'range response'):m.transfer('o/r',1,Path(d)/'zip',10,workers=2,range_bytes=5)
   self.assertTrue(first_entered.is_set());self.assertTrue(invalid_returned.is_set())
if __name__=='__main__':unittest.main()
