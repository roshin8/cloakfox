"""Download a repository-owned checkpoint to disk and verify it before handoff."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,zipfile
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
  with bundle.open('wb') as output:
   subprocess.run(['gh','api',f'repos/{repository}/actions/artifacts/{artifact["id"]}/zip'],stdout=output,check=True)
  if bundle.stat().st_size!=artifact['size_in_bytes']:raise ValueError('Truncated artifact ZIP download')
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
