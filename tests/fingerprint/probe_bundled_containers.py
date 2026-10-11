"""Verify genuine signed container extensions install from the browser distribution."""
import tempfile,json
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
IDS=['@testpilot-containers','{c607c8df-14a7-4f28-894f-29e8722976af}']
def main():
 with tempfile.TemporaryDirectory(prefix='cfx-bundled-containers-') as temp:
  root=Path(temp);profile=root/'profile';profile.mkdir()
  for run in range(2):
   d=launch(profile,root/f'gecko-{run}.log',distro_addons=True)
   try:
    def addons():
     return d.execute_async_script("const done=arguments[arguments.length-1];const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');Promise.all(arguments[0].map(id=>AddonManager.getAddonByID(id))).then(items=>done(items.map(a=>a?{id:a.id,version:a.version,active:a.isActive,signed:a.signedState,path:a.getResourceURI('').spec}:null)));",IDS)
    rows=WebDriverWait(d,30).until(lambda d: (r if all(a and a['active'] for a in r) else False) if (r:=addons()) else False)
    assert [r['version'] for r in rows]==['8.3.8','1.9.2'],rows
    assert all(r['signed']>0 for r in rows),rows
    assert all(str(profile) in r['path'] for r in rows),rows
    print(json.dumps({'restart':bool(run),'addons':rows}))
   finally:d.quit()
if __name__=='__main__':main()
