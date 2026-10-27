"""Check cache eviction in a disposable Cloakfox profile; no real websites used."""
import json
import os
import tempfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

with tempfile.TemporaryDirectory(prefix='cloakfox-cache-scope-') as profile:
    Path(profile, 'user.js').write_text('user_pref("browser.profiles.enabled",false);\n')
    options = Options()
    options.binary_location = os.environ['CLOAKFOX_BIN']
    for arg in ['-headless', '-no-remote', '-profile', profile, '-purgecaches']:
        options.add_argument(arg)
    driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access'], log_output=str(Path(profile, 'gecko.log'))))
    try:
        driver.set_context('chrome')
        driver.set_script_timeout(45)
        result = driver.execute_async_script('''const done = arguments[0];
        (async () => {
          const cases = [
            ["https://example.com/one", {userContextId:1}, false],
            ["https://sub.example.com/two", {userContextId:1}, false],
            ["https://cdn.other.test/three", {userContextId:1, partitionKey:"(https,example.com)"}, false],
            ["https://example.com/four", {userContextId:1, partitionKey:"(https,other.test)"}, false],
            ["https://example.com/other-container", {userContextId:2}, true],
            ["https://cdn.other.test/other-container", {userContextId:2, partitionKey:"(https,example.com)"}, true],
            ["https://example.com/default", {userContextId:0}, true],
            ["https://unrelated.test/keep", {userContextId:1}, true],
            ["https://example.com/private", {userContextId:1, privateBrowsingId:1}, true],
          ];
          const entries=[];
          for (const memory of [false,true]) {
            for (const [url, oa, keep] of cases) {
              const info=Services.loadContextInfo.custom(false, oa);
              const storage=memory ? Services.cache2.memoryCacheStorage(info) : Services.cache2.diskCacheStorage(info);
              const uri=Services.io.newURI(url + (memory ? '/memory' : '/disk'));
              const entry=storage.openTruncate(uri, '');
              entry.setMetaDataElement('test','cache-scope');
              const out=entry.openOutputStream(0,-1); out.write('test',4); out.close();
              entry.setValid(); entry.dismiss();
              entries.push({storage,uri,keep});
            }
          }
          // Complete the initial walk before clearing so disk entries are indexed.
          await new Promise(resolve=>Services.cache2.asyncVisitAllStorages({
            onCacheStorageInfo(){},onCacheEntryInfo(){},onCacheEntryVisitCompleted:resolve,
            QueryInterface:ChromeUtils.generateQI(['nsICacheStorageVisitor'])
          },true));
          const flags=Ci.nsIClearDataService.CLEAR_NETWORK_CACHE | Ci.nsIClearDataService.CLEAR_IMAGE_CACHE |
              Ci.nsIClearDataService.CLEAR_JS_CACHE | Ci.nsIClearDataService.CLEAR_CSS_CACHE;
          const failed=await new Promise(resolve=>Services.clearData.deleteDataFromSite('example.com',
            {userContextId:1,privateBrowsingId:0},true,flags,resolve));
          const checks=entries.map(({storage,uri,keep})=>({uri:uri.spec,keep,exists:storage.exists(uri,'')}));
          done({failed,checks});
        })().catch(e=>done({error:String(e),stack:e.stack}));''')
        assert 'error' not in result, result
        assert result['failed'] == 0, result
        mismatches = [c for c in result['checks'] if c['keep'] != c['exists']]
        assert not mismatches, mismatches
        print(json.dumps({'passed':True,'cache_checks':len(result['checks'])}))
    finally:
        driver.quit()
