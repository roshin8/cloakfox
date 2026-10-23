"""Download a repository-owned checkpoint to disk and verify it before handoff."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,zipfile,time,urllib.request,urllib.error,http.client
from pathlib import Path

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def extract_verified(bundle,destination,expected_digest,source_sha):
 if digest(bundle)!=expected_digest:raise ValueError('Artifact ZIP SHA256 mismatch')
 destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(bundle) as z:
  entries=z.infolist()
  if sorted(i.filename for i in entries)!=['workspace.tar.json','workspace.tar.zst']:raise ValueError('Checkpoint must contain exactly archive and receipt')
  info=z.getinfo('workspace.tar.json')
  if info.file_size>1024*1024:raise ValueError('Oversized checkpoint receipt')
  receipt=json.loads(z.read(info))
  if receipt.get('schemaVersion')!=1 or receipt.get('identity',{}).get('gitSha')!=source_sha:raise ValueError('Checkpoint original source mismatch')
  with tempfile.TemporaryDirectory(prefix='.verified-',dir=destination) as tmp:
   staged=Path(tmp)
   with z.open('workspace.tar.zst') as src,(staged/'workspace.tar.zst').open('wb') as out:shutil.copyfileobj(src,out,8*1024*1024)
   if digest(staged/'workspace.tar.zst')!=receipt['sha256']:raise ValueError('Checkpoint archive SHA256 mismatch')
   (staged/'workspace.tar.json').write_text(json.dumps(receipt)+'\n')
   for name in ['workspace.tar.zst','workspace.tar.json']:os.replace(staged/name,destination/name)
 return {'verified':True,'sourceSha':source_sha,'artifactSha256':expected_digest,'archiveSha256':receipt['sha256'],'archiveBytes':(destination/'workspace.tar.zst').stat().st_size}

def signed_url(repository,artifact_id):
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args):return None
 token=os.environ.get('GH_TOKEN') or subprocess.check_output(['gh','auth','token'],text=True).strip()
 request=urllib.request.Request(f'https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip',headers={'Authorization':'Bearer '+token})
 try:
  with urllib.request.build_opener(NoRedirect).open(request,timeout=30):
   raise ValueError('Expected artifact redirect')
 except urllib.error.HTTPError as e:
  if e.code!=302:raise
  location=e.headers['Location']
  if not location.startswith('https://'):raise ValueError('Non-HTTPS artifact redirect')
  return location

def transfer(repository,artifact_id,bundle,total):
 # Bounded ranges keep a timeout from discarding the entire multi-GB transfer.
 # Fresh signed URLs avoid retrying expired redirects; credentials stay on api.github.com.
 bundle=Path(bundle);bundle.touch(exist_ok=False);started=time.monotonic();last_log=started
 with bundle.open('r+b') as output:
  while output.tell()<total:
   end=min(output.tell()+256*1024*1024,total)-1
   for attempt in range(5):
    start=output.tell()
    try:
     request=urllib.request.Request(signed_url(repository,artifact_id),headers={'Range':f'bytes={start}-{end}'})
     with urllib.request.urlopen(request,timeout=30) as response:
      if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{total}':raise ValueError('Artifact range response mismatch')
      remaining=end-start+1
      while remaining:
       chunk=response.read(min(8*1024*1024,remaining))
       if not chunk:raise OSError('Truncated artifact range')
       output.write(chunk);remaining-=len(chunk)
       now=time.monotonic()
       if now-last_log>=30:
        print(json.dumps({'phase':'download','bytes':output.tell(),'totalBytes':total,'elapsedSeconds':round(now-started,1)}),flush=True);last_log=now
     print(json.dumps({'phase':'download','bytes':output.tell(),'totalBytes':total,'elapsedSeconds':round(time.monotonic()-started,1)}),flush=True)
     break
    except (OSError,http.client.HTTPException) as e:
     print(json.dumps({'phase':'download-retry','bytes':output.tell(),'totalBytes':total,'attempt':attempt+1,'errorType':type(e).__name__}),flush=True)
     if attempt==4:raise
     # If a timeout arrived after the last byte, the full ZIP hash still validates it.
     if output.tell()>end:break
     time.sleep(min(2**attempt,8))

def api(path):return json.loads(subprocess.check_output(['gh','api',path],text=True))
def download(repository,run_id,artifact_id,name,destination,source_sha):
 run=api(f'repos/{repository}/actions/runs/{run_id}')
 if artifact_id:
  artifact=api(f'repos/{repository}/actions/artifacts/{artifact_id}')
 else:
  rows=[]
  for page in range(1,11):
   batch=api(f'repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100&page={page}')['artifacts'];rows+=batch
   if len(batch)<100:break
  matches=[a for a in rows if a['name']==name]
  if len(matches)!=1:raise ValueError('Missing or ambiguous checkpoint artifact')
  artifact=matches[0]
 owner=artifact.get('workflow_run',{})
 if artifact.get('expired') or owner.get('id')!=int(run_id) or owner.get('head_sha')!=run['head_sha'] or artifact['name']!=name:raise ValueError('Checkpoint artifact ownership mismatch')
 expected=artifact.get('digest','')
 if not expected.startswith('sha256:') or len(expected)!=71:raise ValueError('Missing immutable artifact SHA256')
 destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
 # File-backed ZIP plus extracted archive coexist; preserve the normal 10 GiB reserve.
 if shutil.disk_usage(destination).free<2*artifact['size_in_bytes']+10*1024**3:raise ValueError('Insufficient download/extraction reserve')
 with tempfile.TemporaryDirectory(prefix='.download-',dir=destination) as tmp:
  bundle=Path(tmp)/'artifact.zip'
  transfer(repository,artifact['id'],bundle,artifact['size_in_bytes'])
  if bundle.stat().st_size!=artifact['size_in_bytes']:raise ValueError('Truncated artifact ZIP download')
  print(json.dumps({'phase':'verify-zip-and-archive','bytes':bundle.stat().st_size}),flush=True)
  result=extract_verified(bundle,destination,expected[7:],source_sha)
 result.update({'artifactId':artifact['id'],'producerRun':int(run_id)})
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['repository','run','name','destination','source-sha','report']:p.add_argument('--'+name,required=True)
 p.add_argument('--artifact-id',default='');a=p.parse_args()
 report=Path(a.report);report.parent.mkdir(parents=True,exist_ok=True)
 try:
  result=download(a.repository,a.run,a.artifact_id,a.name,a.destination,a.source_sha);report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
 except Exception as e:
  report.write_text(json.dumps({'verified':False,'error':str(e)},indent=2)+'\n');raise
