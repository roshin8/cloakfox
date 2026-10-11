"""Disposable live coverage for native routing, encrypted identities and temporary cleanup.

Run sequentially with CLOAKFOX_BIN after rebuilding. Uses only a loopback server
and local DNS mappings. A persisted pending-cleanup marker is injected after the
first clean shutdown to deterministically simulate interrupted temporary cleanup;
this is not a claim to simulate an OS crash. Native file pickers are not exercised.
"""
import http.server
import json
import sqlite3
import tempfile
import threading
from pathlib import Path

from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

from probe_daily_defaults import launch

IMPORTS = """
const api = ChromeUtils.importESModule('resource:///modules/CloakfoxContainerWorkflows.sys.mjs');
const { ContextualIdentityService: cis } = ChromeUtils.importESModule(
  'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
"""


class Handler(http.server.BaseHTTPRequestHandler):
    requests_seen = []
    lock = threading.Lock()

    def do_GET(self):
        with self.lock:
            self.requests_seen.append({"host": self.headers.get("Host"),
                                       "path": self.path, "cookie": self.headers.get("Cookie", "")})
        body = b'<!doctype html><title>Local workflow probe</title><p>Local workflow probe</p>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def chrome(driver, script, *args):
    driver.set_context("chrome")
    return driver.execute_script(IMPORTS + script, *args)


def async_chrome(driver, script, *args):
    driver.set_context("chrome")
    result = driver.execute_async_script(IMPORTS + """
const done = arguments[arguments.length - 1];
(async () => {
""" + script + """
})().then(done, error => done({ error: error.message, stack: error.stack }));
""", *args)
    assert not (isinstance(result, dict) and "error" in result), result
    return result


def content_handles(driver):
    # In chrome context window_handles enumerates browser windows, not tabs.
    driver.set_context("content")
    return set(driver.window_handles)


def switch_content(driver, handle):
    driver.set_context("content")
    driver.switch_to.window(handle)


def open_site(driver, url, container_id):
    before = content_handles(driver)
    chrome(driver, """
const win = Services.wm.getMostRecentWindow('navigator:browser');
win.gBrowser.selectedTab = win.gBrowser.addTab(arguments[0], {
  userContextId: arguments[1],
  triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal() });
""", url, container_id)

    return wait_new_site(driver, url, before)


def wait_new_site(driver, url, before):
    def loaded(d):
        for handle in content_handles(d) - before:
            try:
                switch_content(d, handle)
                if d.current_url == url and d.execute_script("return document.readyState") == "complete":
                    return handle
            except (NoSuchWindowException, WebDriverException):
                continue
        return False

    handle = WebDriverWait(driver, 25).until(loaded)
    actual = chrome(driver, """
for (const win of Services.wm.getEnumerator('navigator:browser')) {
  const tab = Array.from(win.gBrowser.tabs).find(tab => tab.linkedBrowser.currentURI?.spec === arguments[0]);
  if (tab) return tab.linkedBrowser.browsingContext.originAttributes.userContextId;
}
return -1;
""", url)
    switch_content(driver, handle)
    return handle, actual


def assert_temporary_removed(driver, container_id, cookie_name):
    def removed(d):
        return chrome(d, """
const id = arguments[0];
return !api.getTemporaryContainers().includes(id) && !cis.getPublicIdentityFromId(id);
""", container_id)
    try:
        WebDriverWait(driver, 65, poll_frequency=0.5).until(removed)
    except Exception as error:
        detail = chrome(driver, """
return { tracked: api.getTemporaryContainers(),
  lastError: Services.prefs.getStringPref('cloakfox.workflows.last_error', '') };
""")
        raise AssertionError(detail) from error
    assert chrome(driver, """
return !Services.cookies.cookieExists('temporary.test', '/', arguments[1], { userContextId: arguments[0] });
""", container_id, cookie_name), "Temporary cookie survived cleanup"


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    driver = None
    try:
        with tempfile.TemporaryDirectory(prefix="cloakfox-workflows-") as temp:
            root = Path(temp)
            profile = root / "profile"
            profile.mkdir()
            driver = launch(profile, root / "first.log")
            driver.set_script_timeout(60)
            chrome(driver, """
Services.prefs.setBoolPref('dom.security.https_only_mode', false);
Services.prefs.setStringPref('network.dns.localDomains',
  'route.test,child.route.test,notroute.test,distinct.test,temporary.test');
Services.prefs.setIntPref('network.proxy.type', 0);
""")
            driver.set_context("content")
            driver.get("about:cloakfox")
            settings_handle = driver.current_window_handle
            ids = chrome(driver, """
return [cis.create('Routing target', 'fingerprint', 'blue').userContextId,
  cis.create('Untouched control', 'fingerprint', 'green').userContextId];
""")
            target, control = ids
            base = lambda host, path: f"http://{host}:{server.server_port}/{path}"
            _, actual = open_site(driver, base("route.test", "seed-target"), target)
            assert actual == target, actual
            driver.execute_script("document.cookie='route_identity=target;path=/';")
            _, actual = open_site(driver, base("route.test", "seed-default"), 0)
            assert actual == 0, actual
            driver.execute_script("document.cookie='route_identity=default;path=/';")
            chrome(driver, "api.setSiteRule('ROUTE.TEST.', arguments[0]);", target)
            routing_url = base("route.test", "exact-routing-check")
            _, actual = open_site(driver, routing_url, 0)
            assert actual == target, {"url": routing_url, "actual": actual, "expected": target}
            with Handler.lock:
                matching = [entry for entry in Handler.requests_seen if entry["path"] == "/exact-routing-check"]
            assert matching and all("route_identity=target" in row["cookie"] and "route_identity=default" not in row["cookie"] for row in matching), matching
            negatives = {}
            for host in ["child.route.test", "notroute.test", "distinct.test"]:
                _, actual = open_site(driver, base(host, "negative-" + host), 0)
                assert actual == 0, {"host": host, "actual": actual}
                negatives[host] = actual
            # Native routing intentionally preserves opener/named-target groups.
            # Verify the exception instead of claiming that every top-level load routes.
            opener_handle, actual = open_site(driver, base("distinct.test", "opener-fixture"), 0)
            assert actual == 0, actual
            chrome(driver, "Services.prefs.setBoolPref('dom.disable_open_during_load', false);")
            switch_content(driver, opener_handle)
            before_popup = content_handles(driver)
            related_url = base("route.test", "related-popup-routing-exception")
            opened = driver.execute_script("return !!window.open(arguments[0], 'workflow-related');", related_url)
            assert opened, "Local opener fixture was blocked"
            popup_handle, actual = wait_new_site(driver, related_url, before_popup)
            assert actual == 0, {"nativeOpenerExceptionExpectedDefault": actual}
            with Handler.lock:
                related = [row for row in Handler.requests_seen if row["path"] == "/related-popup-routing-exception"]
            assert related and all("route_identity=default" in row["cookie"] for row in related), related
            switch_content(driver, popup_handle)
            driver.close()
            switch_content(driver, opener_handle)
            print(json.dumps({"nativeExactHostRouting": True, "serverSawOnlyTargetCookie": True,
                              "negativeHostsKeptDefault": negatives,
                              "nativeOpenerExceptionKeptDefault": True}), flush=True)

            switch_content(driver, settings_handle)
            backup = async_chrome(driver, """
const v2Source = cis.create('Backup v2 fixture','fingerprint','blue').userContextId;
const v2Prefix = `cloakfox.container.${v2Source}.`;
for (const key of ['math_seed','keyboard_seed','timing_seed']) {
  if (!Services.prefs.getStringPref(v2Prefix+key,''))
    Services.prefs.setStringPref(v2Prefix+key,btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))));
}
Services.prefs.setStringPref(v2Prefix+'persona_os_mode','legacy');
Services.prefs.setStringPref(v2Prefix+'region',JSON.stringify({version:1,locale:'de-DE',languages:['de-DE','en-US'],timezone:'Europe/Berlin',geolocation:null}));
Services.prefs.setStringPref(v2Prefix+'privacy_policy',JSON.stringify({version:1,preset:'strict',exceptions:[]}));
Services.prefs.setStringPref(v2Prefix+'start_pages',JSON.stringify(['https://example.com/start']));
Services.prefs.setIntPref(v2Prefix+'network_mode',2);
const missingRef='11111111-1111-1111-1111-111111111111';
Services.prefs.setStringPref(v2Prefix+'proxy_ref',missingRef);
ChromeUtils.importESModule('resource:///modules/CloakfoxSeedSync.sys.mjs').refreshContainerConfig(v2Source);
const v2Config=Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${v2Source}`);
const payload = api.captureIdentityBackup();
if(payload.version!==2)throw Error('Backup export did not use v2');
const original = new Map(payload.containers.map(record => [record.sourceId, record.seeds]));
const encrypted = await api.encryptIdentityBackup(payload, 'disposable test password 123');
const serialized = JSON.stringify(encrypted);
if (payload.containers.some(record => serialized.includes(record.seeds.math_seed))) throw Error('Plaintext seed in encrypted output');
await IOUtils.writeUTF8(arguments[0], serialized);
const decoded = await api.decryptIdentityBackup(JSON.parse(await IOUtils.readUTF8(arguments[0])), 'disposable test password 123');
const beforeCount = cis.getPublicIdentities().length;
let conflictRejected = false;
try { await api.restoreIdentityBackup(decoded); } catch (error) { conflictRejected = /already exists/.test(error.message); }
if (!conflictRejected || cis.getPublicIdentities().length !== beforeCount) throw Error('Conflicting import changed existing containers');
api.removeSiteRule('route.test');
api.setSiteRule('untouched.test', arguments[1]);
const imported = await api.restoreIdentityBackup(decoded);
for (const record of imported) {
  if (original.has(record.userContextId)) throw Error('Import reused an existing ID');
  for (const [key, value] of Object.entries(original.get(record.sourceId))) {
    if (Services.prefs.getStringPref(`cloakfox.container.${record.userContextId}.${key}`) !== value) throw Error('Imported seed changed');
    if (Services.prefs.getStringPref(`cloakfox.container.${record.sourceId}.${key}`) !== value) throw Error('Original seed changed');
  }
}
const v2Restored=imported.find(record=>record.sourceId===v2Source);
const restoredPrefix=`cloakfox.container.${v2Restored.userContextId}.`;
if(v2Restored.bindingRequired!==missingRef||Services.prefs.getIntPref(restoredPrefix+'network_mode')!==2||
  Services.prefs.getStringPref(restoredPrefix+'proxy_ref')!==missingRef)throw Error('Missing proxy reference was not visibly blocked');
for(const key of ['region','privacy_policy','start_pages','persona_os_mode'])
  if(Services.prefs.getStringPref(restoredPrefix+key)!==Services.prefs.getStringPref(v2Prefix+key))throw Error('v2 field changed: '+key);
if(Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${v2Restored.userContextId}`)!==v2Config)throw Error('v2 full config changed');
const legacyRecord=JSON.parse(JSON.stringify(payload.containers.find(record=>record.sourceId===v2Source)));
delete legacyRecord.region;delete legacyRecord.policy;delete legacyRecord.startPages;delete legacyRecord.settings.persona_os_mode;
legacyRecord.network={mode:0,proxyURL:'',webrtcMode:0};
const legacyImported=await api.restoreIdentityBackup({format:payload.format,version:1,containers:[legacyRecord],rules:[]});
if(Services.prefs.getStringPref(`cloakfox.container.${legacyImported[0].userContextId}.persona_os_mode`)!=='legacy')throw Error('v1 restore changed OS mode');
const importedTarget = imported.find(record => record.sourceId === arguments[2]).userContextId;
if (cis.getSiteAssociation('route.test') !== importedTarget || cis.getSiteAssociation('untouched.test') !== arguments[1]) throw Error('Rule mapping or existing rule changed');
return { encryptedFileRoundtrip: true, backupV2FieldsAndFullConfig: true, missingProxyBlocked: true, legacyBackupReadable: true, conflictRejected, freshIDs: true,
  seedsRetained: true, originalSeedsRetained: true, unrelatedRuleRetained: true,
  importedCount: imported.length, nativeBackup: api.nativeBackupAvailability() };
""", str(root / "identities.cloakfox-identities"), control, target)
            print(json.dumps(backup), flush=True)

            before = content_handles(driver)
            temp_id = async_chrome(driver, "return await api.createTemporaryContainer(Services.wm.getMostRecentWindow('navigator:browser'));")
            new_handles = content_handles(driver) - before
            assert len(new_handles) == 1, new_handles
            blank_handle = new_handles.pop()
            site_handle, actual = open_site(driver, base("temporary.test", "temporary-live"), temp_id)
            assert actual == temp_id, actual
            driver.execute_script("document.cookie='temporary_live=yes;path=/;max-age=3600'; localStorage.setItem('temporary','live');")
            switch_content(driver, blank_handle)
            driver.close()
            switch_content(driver, settings_handle)
            assert chrome(driver, "return api.getTemporaryContainers().includes(arguments[0]) && !!cis.getPublicIdentityFromId(arguments[0]);", temp_id)
            switch_content(driver, site_handle)
            driver.close()
            switch_content(driver, settings_handle)
            assert_temporary_removed(driver, temp_id, "temporary_live")
            print(json.dumps({"lastTabCleanup": True, "earlierTabCloseRetainedContainer": True}), flush=True)

            # Window teardown does not emit TabClose. Keep the settings window
            # alive while closing a second window containing the final temp tabs.
            window_temp_id = async_chrome(driver, """
const parent = Services.wm.getMostRecentWindow('navigator:browser');
const win = parent.OpenBrowserWindow();
await new Promise((resolve, reject) => {
  const timeout = setTimeout(() => {
    Services.obs.removeObserver(observer, 'browser-delayed-startup-finished');
    reject(Error('Temporary fixture window did not finish startup'));
  }, 15000);
  const observer = subject => {
    if (subject !== win) return;
    clearTimeout(timeout);
    Services.obs.removeObserver(observer, 'browser-delayed-startup-finished');
    resolve();
  };
  Services.obs.addObserver(observer, 'browser-delayed-startup-finished');
});
const id = await api.createTemporaryContainer(win);
win.__workflowTemporaryFixture = id;
return id;
""")
            _, actual = open_site(driver, base("temporary.test", "temporary-whole-window"), window_temp_id)
            assert actual == window_temp_id, actual
            driver.execute_script("document.cookie='temporary_window=yes;path=/;max-age=3600';")
            switch_content(driver, settings_handle)
            chrome(driver, """
for (const win of Services.wm.getEnumerator('navigator:browser')) {
  if (win.__workflowTemporaryFixture === arguments[0]) { win.close(); return; }
}
throw Error('Temporary fixture window was not found');
""", window_temp_id)
            switch_content(driver, settings_handle)
            assert_temporary_removed(driver, window_temp_id, "temporary_window")
            print(json.dumps({"wholeWindowCleanup": True, "settingsWindowRetained": True}), flush=True)

            # Persist a named fixture and cookie without a temporary marker so
            # clean shutdown cannot perform the cleanup we want to test at startup.
            recovery_id = async_chrome(driver, """
const identity = cis.create('Pending temporary recovery fixture', 'fingerprint', 'gray');
cis._saver.disarm();
await cis.save();
return identity.userContextId;
""")
            _, actual = open_site(driver, base("temporary.test", "temporary-recovery"), recovery_id)
            assert actual == recovery_id, actual
            driver.execute_script("document.cookie='temporary_recovery=yes;path=/;max-age=3600';")
            switch_content(driver, settings_handle)
            chrome(driver, "Services.prefs.savePrefFile(null);")
            driver.quit()
            driver = None
            stored = json.loads((profile / "containers.json").read_text())
            assert any(record["userContextId"] == recovery_id for record in stored["identities"])
            with sqlite3.connect(f"file:{profile / 'cookies.sqlite'}?mode=ro", uri=True) as db:
                count = db.execute("SELECT count(*) FROM moz_cookies WHERE name=? AND originAttributes LIKE ?",
                                   ("temporary_recovery", f"%userContextId={recovery_id}%")).fetchone()[0]
            assert count > 0, "Recovery cookie fixture did not persist before restart"
            # This disposable-only marker simulates interrupted previous cleanup.
            with (profile / "prefs.js").open("a") as prefs:
                prefs.write('\nuser_pref("cloakfox.temporary_containers", ' + json.dumps(json.dumps([recovery_id])) + ');\n')
            driver = launch(profile, root / "second.log")
            driver.set_script_timeout(60)
            driver.set_context("content")
            driver.get("about:cloakfox")
            assert_temporary_removed(driver, recovery_id, "temporary_recovery")
            retained = chrome(driver, "return !!cis.getPublicIdentityFromId(arguments[0]) && cis.getSiteAssociation('untouched.test') === arguments[0];", control)
            assert retained, "Startup cleanup changed an unrelated identity/rule"
            print(json.dumps({"startupRecoveryMarkerCleanup": True, "persistedCookieRemoved": True,
                              "unrelatedIdentityAndRuleRetained": True}), flush=True)
            print("PASS: native routing, encrypted identity import, last-tab cleanup and persisted startup recovery", flush=True)
    finally:
        if driver:
            driver.quit()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
