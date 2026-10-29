import os,subprocess,shutil,json
from pathlib import Path
root=Path.cwd();controller=Path('../controller').resolve();assets=Path(os.environ['RUNNER_TEMP'])/'replay-assets';assets.mkdir()
subprocess.run(['gh','release','download','sdk-import-locale-f03b85fd-20261029','--repo','roshin8/cloakfox','--pattern','locale-source-replay-a06a951.*','--pattern','sdk-import-portable.json','--dir',str(assets)],check=True)
destination=Path(os.environ['RUNNER_TEMP'])/'source-replay'
subprocess.run(['python3',str(controller/'scripts/ci/verify_replay_fixture.py'),'--repo',str(root),'--assets',str(assets),'--destination',str(destination)],check=True)
with open(os.environ['GITHUB_ENV'],'a') as f:print('CLOAKFOX_CHROMIUM_SOURCE='+str(destination/'chromium-source'),file=f)
for name in ['test_offscreen_rendering.py','test_native_host_surface.py','test_display_privacy.py']:
 shutil.copyfile(controller/'tests/fixtures/chromium-sdk-a06'/name,root/'tests/engines'/name)

import hashlib
record={name:hashlib.sha256((controller/'tests/fixtures/chromium-sdk-a06'/name).read_bytes()).hexdigest() for name in ['test_offscreen_rendering.py','test_native_host_surface.py','test_display_privacy.py']}
Path('evidence/recheck-test-inputs.json').write_text(json.dumps(record,indent=2))
