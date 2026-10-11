"""Verify the Firefox 157 patch stack in an isolated selective-source fixture.
Does not mutate firefox-src or its build output.
"""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,tarfile,tempfile
r=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(r/'scripts')); from _mixin import list_patches
patches=[Path(p) for p in list_patches(str(r/'patches'))]
rels=set()
for p in patches:
 for name in re.findall(r'^\+\+\+ (\S+)',p.read_text(),re.M):
  if name!='/dev/null': rels.add('/'.join(name.split('/')[1:]))
# Additional staging inputs not touched by patches.
rels.update(['browser/app/firefox.exe.manifest','browser/fonts/moz.build'])
with tempfile.TemporaryDirectory(prefix='cloakfox157-followup-replay-') as tmp:
 fixture=Path(tmp); found=set()
 (fixture/'build/vs').mkdir(parents=True); (fixture/'browser/config').mkdir(parents=True)
 with tarfile.open(r/'firefox-157.0.1.source.tar.xz',mode='r|xz') as archive:
  for member in archive:
   rel=member.name.removeprefix('firefox-157.0.1/').removeprefix('firefox/')
   if rel in rels and member.isfile():
    dest=fixture/rel; dest.parent.mkdir(parents=True,exist_ok=True)
    with archive.extractfile(member) as f,dest.open('wb') as out: shutil.copyfileobj(f,out)
    found.add(rel)
 with (r/'docs/firefox-157-port/upstream-followup-staging.log').open('w') as log:
  subprocess.run(['bash',str(r/'scripts/copy-additions.sh'),'157.0.1','beta.25',str(r)],cwd=fixture,stdout=log,stderr=subprocess.STDOUT,check=True)
 results=[]
 for p in patches:
  out=subprocess.run(['patch','-p1','--batch','--forward','-l','--binary','-i',str(p)],cwd=fixture,capture_output=True,text=True)
  log=out.stdout+out.stderr; results.append({'patch':p.name,'exit':out.returncode,'log':log})
  assert out.returncode==0 and not re.search(r'fuzz|offset|Skipping|Ignoring previously',log,re.I),(p.name,log)
 hashes={rel:hashlib.sha256((fixture/rel).read_bytes()).hexdigest() for rel in rels if (fixture/rel).exists()}
 drift=[rel for rel,h in hashes.items() if not (r/'firefox-src'/rel).exists() or hashlib.sha256((r/'firefox-src'/rel).read_bytes()).hexdigest()!=h]
 report={'patches':len(patches),'pristineTargets':len(found),'drift':drift,'targetHashes':hashes,'results':results}
 (r/'docs/firefox-157-port/upstream-followup-replay.json').write_text(json.dumps(report,indent=2))
 assert not drift,drift
 print(f'PASS: {len(patches)} patches; {len(found)} pristine targets; no offset, fuzz or native source drift')
