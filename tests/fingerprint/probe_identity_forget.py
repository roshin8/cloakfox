"""Exercise container forgetting with cookies/localStorage and tabs in a disposable profile.

Run sequentially after rebuild with CLOAKFOX_BIN. No real profile or external
website is used. Native dialog confirmation is exercised by the UI manually;
this probe calls the privileged service with explicit confirmation.
"""
import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix="cloakfox-forget-") as temp:
        root = Path(temp)
        (root / "index.html").write_text('<!doctype html><title>Container forget probe</title>Probe')
        (root / "sw.js").write_text("self.addEventListener('install', e => self.skipWaiting()); self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
            functools.partial(QuietHandler, directory=temp))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        options = Options()
        options.binary_location = os.environ["CLOAKFOX_BIN"]
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options, service=Service(
            executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
            service_args=["--allow-system-access"], log_output=str(root / "geckodriver.log")))
        driver.set_script_timeout(45)
        try:
            driver.get("about:cloakfox")
            settings_handle = driver.current_window_handle
            driver.set_context("chrome")
            ids = driver.execute_script("""
              const { ContextualIdentityService: cis } = ChromeUtils.importESModule(
                'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              return [cis.create('Forget target', 'fingerprint', 'blue').userContextId,
                      cis.create('Keep control', 'fingerprint', 'green').userContextId];
            """)
            url = f"http://127.0.0.1:{server.server_port}/index.html"

            def open_site(ucid):
                driver.set_context("content")
                old = set(driver.window_handles)
                driver.set_context("chrome")
                driver.execute_script("""
                  const win = Services.wm.getMostRecentWindow('navigator:browser');
                  win.gBrowser.selectedTab = win.gBrowser.addTab(arguments[0], {
                    userContextId: arguments[1],
                    triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal() });
                """, url, ucid)
                driver.set_context("content")
                handle = WebDriverWait(driver, 15).until(lambda d: next(iter(set(d.window_handles) - old), None))
                driver.switch_to.window(handle)
                driver.set_context("content")
                WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState === 'complete' && location.href === arguments[0]", url))
                return handle

            def seed_storage(marker):
                result = driver.execute_async_script("""
                  const marker=arguments[0], done=arguments[arguments.length-1];
                  (async () => {
                    document.cookie=`session=${marker};path=/`;
                    localStorage.setItem('marker',marker);
                    await new Promise((resolve,reject) => {
                      const request=indexedDB.open('forget-probe',1);
                      request.onupgradeneeded=()=>request.result.createObjectStore('data');
                      request.onerror=()=>reject(request.error);
                      request.onsuccess=()=>{const db=request.result, tx=db.transaction('data','readwrite');
                        tx.objectStore('data').put(marker,'marker');
                        tx.oncomplete=()=>{db.close();resolve();}; tx.onerror=()=>reject(tx.error);};
                    });
                    const cache=await caches.open('forget-probe');
                    await cache.put('/cached',new Response(marker));
                    await navigator.serviceWorker.register('/sw.js');
                    await navigator.serviceWorker.ready;
                    return true;
                  })().then(done, e=>done({error:String(e)}));
                """, marker)
                assert result is True, result

            def read_storage():
                return driver.execute_async_script("""
                  const done=arguments[arguments.length-1];
                  (async()=>({cookie:document.cookie,storage:localStorage.getItem('marker'),
                    idb:await new Promise((resolve,reject)=>{
                      let missing=false;
                      const request=indexedDB.open('forget-probe');
                      request.onupgradeneeded=()=>{missing=true;request.transaction.abort();};
                      request.onerror=()=>missing?resolve(null):reject(request.error);
                      request.onsuccess=()=>{const db=request.result;
                        if(!db.objectStoreNames.contains('data')){db.close();resolve(null);return;}
                        const tx=db.transaction('data'), get=tx.objectStore('data').get('marker');
                        get.onsuccess=()=>resolve(get.result ?? null);
                        get.onerror=()=>reject(get.error);tx.oncomplete=()=>db.close();};
                    }),
                    caches:await caches.keys(), workers:(await navigator.serviceWorker.getRegistrations()).length
                  }))().then(done,e=>done({error:String(e)}));
                """)

            for target in [ids[0], 0]:
                control = ids[1]
                target_handle = open_site(target)
                seed_storage('target')
                control_handle = open_site(control)
                seed_storage('control')
                assert read_storage()['idb'] == 'control', 'IDB control was not seeded'
                driver.switch_to.window(settings_handle)
                driver.set_context("chrome")
                before = driver.execute_script("""
                  const { SessionStore, _LastSession } = ChromeUtils.importESModule(
                    'resource:///modules/sessionstore/SessionStore.sys.mjs');
                  const record = userContextId => ({ userContextId, entries: [{ url: 'https://restore.example/' }] });
                  _LastSession.setState({ windows: [{ tabs: [record(arguments[0]), record(arguments[1])], selected: 2 }] });
                  SessionStore.savedGroups.push({ id: 'forget-probe-group', name: 'Probe mixed group',
                    tabs: [{ state: record(arguments[0]) }, { state: record(arguments[1]) }] });
                  const prefix = `cloakfox.container.${arguments[0]}.`;
                  Services.prefs.setStringPref(prefix + 'math_seed', btoa('a'.repeat(32)));
                  Services.prefs.setIntPref(prefix + 'network_mode', 2);
                  return Services.prefs.getStringPref(prefix + 'math_seed');
                """, target, control)
                result = driver.execute_async_script("""
                  const [id, done] = arguments;
                  const { forgetContainerData } = ChromeUtils.importESModule(
                    'resource:///modules/CloakfoxIdentityActions.sys.mjs');
                  forgetContainerData(id, { confirmed: true }).then(done,
                    error => done({ error: error.message, stack: error.stack }));
                """, target)
                assert result.get("cleared"), result
                driver.set_context("content")
                assert target_handle not in driver.window_handles
                assert control_handle in driver.window_handles
                driver.set_context("chrome")
                after = driver.execute_script("""
                  const id = arguments[0];
                  const { ContextualIdentityService: cis } = ChromeUtils.importESModule(
                    'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
                  const { SessionStore, _LastSession } = ChromeUtils.importESModule(
                    'resource:///modules/sessionstore/SessionStore.sys.mjs');
                  const restored = _LastSession.getState().windows.flatMap(win => win.tabs);
                  const group = SessionStore.savedGroups.find(group => group.id === 'forget-probe-group');
                  const restorePruned = restored.length === 1 && restored[0].userContextId === arguments[1] &&
                    group.tabs.length === 1 && group.tabs[0].state.userContextId === arguments[1];
                  SessionStore.forgetSavedTabGroup('forget-probe-group');
                  return { restorePruned, seed: Services.prefs.getStringPref(`cloakfox.container.${id}.math_seed`),
                    mode: Services.prefs.getIntPref(`cloakfox.container.${id}.network_mode`),
                    identityRetained: id === 0 || !!cis.getPublicIdentityFromId(id) };
                """, target, control)
                assert after["restorePruned"], after
                assert after["seed"] != before, after
                assert after["identityRetained"] and after["mode"] == 2, after
                # Allow local test navigation again only after checking the connection policy was retained.
                driver.execute_script("Services.prefs.setIntPref(`cloakfox.container.${arguments[0]}.network_mode`, 0)", target)
                open_site(target)
                data = read_storage()
                assert "session=target" not in data["cookie"] and data["storage"] is None, data
                assert data['idb'] is None and 'forget-probe' not in data['caches'] and data['workers'] == 0, data
                driver.switch_to.window(control_handle)
                driver.set_context("content")
                data = read_storage()
                assert "session=control" in data["cookie"] and data["storage"] == "control", data
                assert data['idb'] == 'control' and 'forget-probe' in data['caches'] and data['workers'] == 1, data
                driver.switch_to.window(settings_handle)
                driver.set_context("chrome")
                print(json.dumps({"target": target, "cleared": True, "otherContainerRetained": True}))
            print("PASS: named/default data and tabs cleared; control data, identity and network policy retained")
        finally:
            driver.quit()
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
