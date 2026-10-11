"""Live template isolation/persistence probe. Run sequentially after rebuilding.

Uses real native APIs and a loopback fixture in a disposable profile. Requires
CLOAKFOX_BIN and geckodriver. Native file pickers are not exercised.
"""
import http.server
import json
import tempfile
import threading
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
from probe_container_workflows import chrome, async_chrome, open_site, content_handles, switch_content, wait_new_site

IMPORTS = """
const templates=ChromeUtils.importESModule('resource:///modules/CloakfoxTemplates.sys.mjs');
const regions=ChromeUtils.importESModule('resource:///modules/CloakfoxRegions.sys.mjs');
const privacy=ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs');
"""
SNAPSHOT = """
return arguments[0].map(id=>{
 const prefix=`cloakfox.container.${id}.`;
 return {id,seed:Services.prefs.getStringPref(prefix+'math_seed'),
 keyboard:Services.prefs.getStringPref(prefix+'keyboard_seed'),timing:Services.prefs.getStringPref(prefix+'timing_seed'),
 index:Services.prefs.getIntPref(prefix+'persona_index'),region:regions.getRegion(id),policy:privacy.getPrivacyPolicy(id),
 cfg:JSON.parse(Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${id}`))};
});
"""
CREATE = """
const value={...arguments[0],startPages:[arguments[1]]};
const win=Services.wm.getMostRecentWindow('navigator:browser'),original=win.gBrowser.addTrustedTab;
let checked=false;
win.gBrowser.addTrustedTab=function(url,options){
 const id=options.userContextId,prefix=`cloakfox.container.${id}.`;
 const seed=Services.prefs.getStringPref(prefix+'math_seed');
 const cfg=JSON.parse(Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${id}`));
 if(cfg['fingerprint:secret']!==seed||cfg['navigator.language']!=='de-DE'||cfg['privacy:policy'].preset!=='compatibility')throw Error('Configuration missing before opening');
 if(Services.prefs.getIntPref(prefix+'persona_index')!==5)throw Error('Pinned constraint missing');
 // Read the actual preference file synchronously before native tab creation.
 const file=Services.dirsvc.get('ProfD',Ci.nsIFile);file.append('prefs.js');
 const input=Cc['@mozilla.org/network/file-input-stream;1'].createInstance(Ci.nsIFileInputStream);input.init(file,0x01,0,0);
 const stream=Cc['@mozilla.org/scriptableinputstream;1'].createInstance(Ci.nsIScriptableInputStream);stream.init(input);
 let text;try{text=stream.read(stream.available());}finally{stream.close();}
 if(!text.includes(seed)||!text.includes(prefix+'privacy_policy')||!text.includes(prefix+'region')||!text.includes(prefix+'persona_index'))throw Error('Settings not persisted before opening');
 checked=true;return original.call(this,url,options);
};
let id;try{id=await templates.createFromTemplate(value,win);}finally{win.gBrowser.addTrustedTab=original;}
if(!checked)throw Error('Opening hook not exercised');
return id;
"""

class Handler(http.server.BaseHTTPRequestHandler):
    seen = []
    lock = threading.Lock()
    def do_GET(self):
        with self.lock:
            self.seen.append({"path": self.path, "cookie": self.headers.get("Cookie", "")})
        body = b'<!doctype html><title>Template fixture</title><p>Template fixture</p>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_args):
        pass


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    driver = None
    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-templates-") as temporary:
            root = Path(temporary)
            profile = root / "profile"
            profile.mkdir()
            driver = launch(profile, root / "first.log")
            driver.set_script_timeout(60)
            chrome(driver, """
Services.prefs.setBoolPref('dom.security.https_only_mode',false);
Services.prefs.setStringPref('network.dns.localDomains','templates.test');
Services.prefs.setIntPref('network.proxy.type',0);
""")
            driver.set_context("content")
            driver.get("about:cloakfox")
            settings = driver.current_window_handle
            base = f"http://templates.test:{server.server_port}"
            open_site(driver, base + "/source", 0)
            driver.execute_script("document.cookie='source_login=private;path=/;max-age=3600';localStorage.setItem('source','private');")
            assert 'source_login=private' in driver.execute_script("return document.cookie"), 'Source cookie fixture failed'
            assert driver.execute_script("return localStorage.getItem('source')") == 'private'
            switch_content(driver, settings)
            template = chrome(driver, IMPORTS + """
regions.setRegion(0,{version:1,locale:'de-DE',languages:['de-DE','de'],timezone:'Europe/Berlin',geolocation:null});
privacy.setPrivacyPolicy(0,{version:1,preset:'compatibility',exceptions:[]});
Services.prefs.setIntPref('cloakfox.container.0.persona_index',5);
ChromeUtils.importESModule('resource:///modules/CloakfoxSeedSync.sys.mjs').refreshContainerConfig(0);
return templates.saveTemplate(templates.captureTemplate(0,'Disposable template',[])).settings;
""")
            ids = []
            for index in range(2):
                url = base + f"/created-{index}"
                before = content_handles(driver)
                created_id = async_chrome(driver, IMPORTS + CREATE, template, url)
                ids.append(created_id)
                _, actual = wait_new_site(driver, url, before)
                assert actual == created_id
                assert driver.execute_script("return document.cookie") == "", "Source cookies copied"
                assert driver.execute_script("return localStorage.getItem('source')") is None, "Source storage copied"
            assert ids[0] != ids[1]
            with Handler.lock:
                created = [row for row in Handler.seen if row["path"].startswith("/created-")]
            assert len(created) >= 2 and all(not row["cookie"] for row in created), created
            snapshots = chrome(driver, IMPORTS + SNAPSHOT, ids)
            seeds = [record[key] for record in snapshots for key in ["seed", "keyboard", "timing"]]
            assert len(set(seeds)) == 6, "Fingerprint secret reused"
            for key in ["navigator.userAgent", "navigator.platform", "screen.width", "screen.height"]:
                assert snapshots[0]["cfg"][key] == snapshots[1]["cfg"][key], key
            for record in snapshots:
                assert record["region"] == template["region"]
                assert record["policy"] == template["policy"]
                assert record["index"] == 5
            chrome(driver, IMPORTS + """
const text=JSON.stringify(templates.exportTemplates());
const sourceSeeds=['math_seed','keyboard_seed','timing_seed'].map(key=>Services.prefs.getStringPref('cloakfox.container.0.'+key));
if([...arguments[0],...sourceSeeds].some(seed=>seed&&text.includes(seed)))throw Error('Seed leaked in export');
for(const key of ['math_seed','masterSeed','fingerprint:secret','cookies','logins','password','credentials','proxyURL']){
 if(text.includes(JSON.stringify(key)+':'))throw Error('Forbidden export key: '+key);
}
let rejected=false;try{templates.validateTemplate({...arguments[1],password:'private-proxy-password'});}catch(_){rejected=true;}
if(!rejected)throw Error('Credential-bearing template accepted');
""", seeds, template)
            async_chrome(driver, IMPORTS + """
const before=cis.getPublicIdentities().length;let rejected=false;
try{await templates.createFromTemplate({...arguments[0],proxyRef:'missing-proxy-reference'},Services.wm.getMostRecentWindow('navigator:browser'));}
catch(error){rejected=/missing/.test(error.message);}
if(!rejected||cis.getPublicIdentities().length!==before)throw Error('Missing proxy reference created a container');
return true;
""", template)
            before = content_handles(driver)
            blocked_id = async_chrome(driver, IMPORTS + """
const value={...templates.templatePresets()[3],startPages:[arguments[0]]};
const id=await templates.createFromTemplate(value,Services.wm.getMostRecentWindow('navigator:browser'));
if(Services.prefs.getIntPref(`cloakfox.container.${id}.network_mode`)!==2)throw Error('Required proxy preset did not block');
return id;
""", base + "/must-not-arrive")
            def blocked(d):
                for handle in content_handles(d) - before:
                    switch_content(d, handle)
                    if d.execute_script("return document.documentURI").startswith("about:neterror"):
                        return True
                return False
            WebDriverWait(driver, 25).until(blocked)
            with Handler.lock:
                assert not any(row["path"] == "/must-not-arrive" for row in Handler.seen), "Required-proxy page reached direct network"
            switch_content(driver, settings)
            chrome(driver, "Services.prefs.savePrefFile(null);")
            driver.quit()
            driver = None
            driver = launch(profile, root / "second.log")
            driver.set_script_timeout(60)
            restarted = chrome(driver, IMPORTS + SNAPSHOT, ids)
            assert restarted == snapshots, "Identity/settings changed on restart"
            assert chrome(driver, "return Services.prefs.getIntPref(`cloakfox.container.${arguments[0]}.network_mode`);", blocked_id) == 2
            print(json.dumps({"freshSecrets": True, "freshIDs": True, "emptyCookiesAndStorage": True,
                              "persistedBeforePages": True, "pinnedPersonaPreserved": True,
                              "regionAndPolicyCopied": True, "missingProxyRejected": True,
                              "requiredProxyNoDirectFallback": True, "exportExcludesSecrets": True,
                              "identityStableAfterRestart": True}), flush=True)
            print("PASS: templates create fresh persistent identities without copying login state", flush=True)
    finally:
        if driver:
            driver.quit()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
