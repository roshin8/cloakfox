import hashlib,json,os,tarfile,subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path('../controller/scripts/ci').resolve()))
from sdk_client import digest,sdk_filter
root=Path.cwd();work=Path(os.environ['RUNNER_TEMP'])/'reused-locale-apps'
record=json.loads(Path('evidence/original/sdk-verification.json').read_text())
archive=Path('artifacts/apps/clients.tar.gz')
assert digest(archive)==record['appsArchiveSha256']=='e373a70c143493d831361fdd5e5bc541a17ad181a1b6c16fe80cf9b2f4128191'
assert archive.stat().st_size==record['appsArchiveBytes']==378681176
assert record['clientRevision']=='a06a95168d462024d274570ab73f5b8c535ca103'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==record['clientRevision']
with tarfile.open(archive) as t:t.extractall(work,filter=sdk_filter)
app=work/'patched-client/Release/CloakfoxChromium.app'
assert digest(app/'Contents/Frameworks/Chromium Embedded Framework.framework/Versions/A/Chromium Embedded Framework')==record['frameworkSha256']=='f03b85fdad197673fdf8ee055269dfdf5a730c139b418e7f52834ad2271eb33d'
with open(os.environ['GITHUB_ENV'],'a') as f:
 for key,value in {'CLOAKFOX_CHROMIUM_BIN':app/'Contents/MacOS/CloakfoxChromium','CLOAKFOX_UNPATCHED_CHROMIUM_BIN':work/'baseline-client/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium','CLOAKFOX_NATIVE_SURFACE_PROBE':work/'patched-client/Release/host_surface_probe'}.items():
  assert value.is_file();print(f'{key}={value}',file=f)
Path('evidence/reused-apps.json').write_text(json.dumps(record,indent=2))
