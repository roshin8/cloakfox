"""Native permissions and real-profile workspaces in isolated app-data directories.

Run sequentially after packaging with CLOAKFOX_BIN set. MOZ_APP_DATA and
MOZ_LOCAL_APP_DATA isolate profiles.ini; -profile alone is insufficient. Runtime
path checks run before profile creation. Browser processes are Selenium-owned
and closed in finally blocks. A native-launch child is matched by exact executable,
parent PID and a unique profile name; only that owned PID may be terminated.
All permission/password/cookie/add-on fixtures are disposable and test-only.
"""
import contextlib
import json
import os
import shutil
import signal
import subprocess
import time
import uuid
import zipfile
import tempfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


class NativeChildCleanupError(RuntimeError):
    """Cleanup ownership or profile unlock could not be proved."""


@contextlib.contextmanager
def isolated_probe_directory():
    # Preserve files if a native child cannot be identified/stopped; deleting a
    # live profile underneath it would make a diagnostic failure destructive.
    directory = tempfile.mkdtemp(prefix='cloakfox-permissions-workspaces-')
    cleanup = True
    try:
        yield directory
    except NativeChildCleanupError:
        cleanup = False
        print('Native child cleanup is incomplete; disposable data preserved at ' + directory)
        raise
    finally:
        if cleanup:
            shutil.rmtree(directory)


def launch(profile, log, app_data, local_data):
    options = Options()
    options.binary_location = os.environ['CLOAKFOX_BIN']
    options.add_argument('--headless')
    options.add_argument('-profile')
    options.add_argument(str(profile))
    options.set_preference('remote.prefs.recommended', False)
    options.set_preference('xpinstall.signatures.required', False)
    env = dict(os.environ)
    env.update(MOZ_APP_DATA=str(app_data), MOZ_LOCAL_APP_DATA=str(local_data), MOZ_HEADLESS='1')
    driver = webdriver.Firefox(options=options, service=Service(
        executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
        service_args=['--allow-system-access'], log_output=str(log), env=env))
    try:
        driver.set_context('chrome')
        driver.set_script_timeout(45)
        actual = driver.execute_script("""
          const service=Cc['@mozilla.org/toolkit/profile-service;1'].getService(Ci.nsIToolkitProfileService);
          return {appData:Services.dirsvc.get('UAppData',Ci.nsIFile).path,
            root:Services.dirsvc.get('ProfD',Ci.nsIFile).path,
            profiles:Array.from(service.profiles,p=>({root:p.rootDir.path,local:p.localDir.path}))};
        """)
        assert Path(actual['appData']).resolve() == app_data.resolve(), actual
        assert Path(actual['root']).resolve() == profile.resolve(), actual
        for item in actual['profiles']:
            assert Path(item['root']).resolve().is_relative_to(app_data.resolve()), actual
            assert any(Path(item['local']).resolve().is_relative_to(base.resolve())
                       for base in [app_data, local_data]), actual
        return driver
    except BaseException:
        driver.quit()
        raise


def async_chrome(driver, script, *args):
    value = driver.execute_async_script("""
      const done=arguments[arguments.length-1];
      (async()=>{ SCRIPT })().then(done,error=>done({error:error.message,stack:error.stack}));
    """.replace('SCRIPT', script), *args)
    assert not isinstance(value, dict) or 'error' not in value, value
    return value

IMPORTS = """
const api = ChromeUtils.importESModule('resource:///modules/CloakfoxPermissions.sys.mjs');
const manager = Services.perms;
const principal = (id, pb=0) => Services.scriptSecurityManager.createContentPrincipal(
  Services.io.newURI('https://permission-fixture.example'), {userContextId:id,privateBrowsingId:pb});
const read = (id,type,pb=0) => manager.testPermissionFromPrincipal(principal(id,pb),type);
"""



def matching_native_children(executable, parent_pid, workspace_name):
    """Read command lines only, never environment; never use a broad kill match."""
    expected = f'{executable} -P {workspace_name}'
    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,args='], check=True,
                            capture_output=True, text=True, timeout=10)
    matches = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            if int(parts[1]) == parent_pid and parts[2] == expected:
                matches.append(int(parts[0]))
    return matches


def exercise_native_launcher(driver, app_data):
    """Keep the owning browser alive until the unique child's profile unlocks."""
    name = 'cfx-launch-' + str(uuid.uuid4())
    state = driver.execute_script("""
      return {executable:Services.dirsvc.get('XREExeF',Ci.nsIFile).path,
        parentPID:Services.appinfo.processID};
    """)
    executable, parent_pid = state['executable'], state['parentPID']
    assert not matching_native_children(executable, parent_pid, name)
    record = async_chrome(driver, """
      return await ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs')
        .createWorkspace(arguments[0]);
    """, name)
    assert Path(record['id']).resolve().is_relative_to(app_data.resolve()), record
    owned_pid = None
    launched = False

    def available():
        return driver.execute_script("""
          const row=ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs')
            .listWorkspaces().find(item=>item.id===arguments[0]);
          return !!row?.available;
        """, record['id'])

    def owned_child(_driver):
        matches = matching_native_children(executable, parent_pid, name)
        assert len(matches) <= 1, 'More than one exact native launch child'
        return matches[0] if matches else False

    try:
        # Mark the attempted dispatch before executing: a response error can occur
        # after Firefox has already started the child.
        launched = True
        driver.execute_script("""
          ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs')
            .openWorkspace(arguments[0]);
        """, record['id'])
        owned_pid = WebDriverWait(driver, 25, poll_frequency=0.2).until(owned_child)
        WebDriverWait(driver, 25, poll_frequency=0.2).until(lambda _driver: not available())
        return {'exactExecutableAndProfileCommand': True, 'nativeProfileLockObserved': True,
                'ownedChildTerminated': True}
    finally:
        if launched:
            try:
                # Resolve a late-starting child even when the WebDriver call failed.
                if owned_pid is None:
                    matches = matching_native_children(executable, parent_pid, name)
                    assert len(matches) <= 1, 'Ambiguous native child; no process was signalled'
                    owned_pid = matches[0] if matches else None
                if owned_pid is not None:
                    # Revalidate immediately before every signal to avoid broad cleanup
                    # or signalling a PID reused by an unrelated process.
                    if owned_pid in matching_native_children(executable, parent_pid, name):
                        try:
                            os.kill(owned_pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    deadline = time.monotonic() + 15
                    while owned_pid in matching_native_children(executable, parent_pid, name) and time.monotonic() < deadline:
                        time.sleep(0.2)
                    if owned_pid in matching_native_children(executable, parent_pid, name):
                        try:
                            os.kill(owned_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                WebDriverWait(driver, 15, poll_frequency=0.2).until(lambda _driver: available())
                if owned_pid is not None:
                    assert owned_pid not in matching_native_children(executable, parent_pid, name), 'Owned child did not terminate'
                if owned_pid is None:
                    raise NativeChildCleanupError('Native launch child could not be identified with the exact command and parent PID')
            except NativeChildCleanupError:
                raise
            except BaseException as error:
                raise NativeChildCleanupError('Could not prove owned native child termination and profile unlock') from error



def main():
    with isolated_probe_directory() as temp:
        app_data = Path(temp) / 'app-data'
        local_data = Path(temp) / 'local-data'
        app_data.mkdir()
        local_data.mkdir()
        profile = app_data / 'initial-profile'
        profile.mkdir()
        driver = launch(profile, Path(temp) / 'first.log', app_data, local_data)
        try:
            result = driver.execute_script(IMPORTS + """
              Services.prefs.setBoolPref('permissions.isolateBy.userContext',true);
              Services.prefs.setBoolPref('permissions.isolateBy.privateBrowsing',true);
              for (const id of [2,3]) for (const type of ['camera','microphone','geo','desktop-notification'])
                manager.addFromPrincipal(principal(id),type,manager.ALLOW_ACTION);
              manager.addFromPrincipal(principal(2,1),'geo',manager.ALLOW_ACTION,manager.EXPIRE_SESSION);
              const grants=api.listPermissionGrants({userContextId:2,privateBrowsingId:0});
              if(grants.length!==4)throw Error('Expected four normal container grants');
              api.expirePermissionGrant(grants.find(g=>g.type==='camera'),{mode:'session'});
              api.expirePermissionGrant(grants.find(g=>g.type==='geo'),{mode:'time',expiresAt:Date.now()+1500});
              api.revokePermissionGrant(grants.find(g=>g.type==='microphone'));
              if(read(2,'microphone')!==manager.UNKNOWN_ACTION||read(3,'microphone')!==manager.ALLOW_ACTION)
                throw Error('Revocation leaked to another container');
              if(read(2,'geo',1)!==manager.ALLOW_ACTION)throw Error('Normal mutation affected private grant');
              const stale=grants.find(g=>g.type==='desktop-notification');
              manager.addFromPrincipal(principal(2),'desktop-notification',manager.DENY_ACTION);
              let rejected=false;try{api.expirePermissionGrant(stale,{mode:'session'});}catch{rejected=true;}
              if(!rejected||read(2,'desktop-notification')!==manager.DENY_ACTION)throw Error('Consent was recreated');
              const service=Cc['@mozilla.org/toolkit/profile-service;1'].getService(Ci.nsIToolkitProfileService);
              if(typeof service.createProfile!=='function'||typeof service.asyncFlush!=='function'||
                typeof Services.startup.createInstanceWithProfile!=='function')throw Error('Native profile APIs missing');
              ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs');
              return {exactRevocation:true,privateIsolation:true,staleConsentRejected:true,nativeProfileAPIs:true};
            """)
            WebDriverWait(driver, 10).until(lambda d: d.execute_script(IMPORTS + """
              return read(2,'geo')===manager.UNKNOWN_ACTION && read(3,'geo')===manager.ALLOW_ACTION;
            """))
            result['nativeTimedExpiry'] = True
            workspace_records = async_chrome(driver, """
              const api=ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs');
              const service=Cc['@mozilla.org/toolkit/profile-service;1'].getService(Ci.nsIToolkitProfileService);
              let defaultBefore=null;try{defaultBefore=service.defaultProfile?.rootDir.path||null;}catch{}
              const first=await api.createWorkspace('Isolated workspace A');
              const second=await api.createWorkspace('Isolated workspace B');
              let duplicateRejected=false;try{await api.createWorkspace('Isolated workspace A');}catch{duplicateRejected=true;}
              if(!duplicateRejected)throw Error('Duplicate profile accepted');
              let defaultAfter=null;try{defaultAfter=service.defaultProfile?.rootDir.path||null;}catch{}
              if(defaultBefore!==defaultAfter)throw Error('Workspace creation changed default profile');
              const list=api.listWorkspaces();
              if(![first,second].every(item=>list.some(row=>row.id===item.id&&row.available&&!row.current)))
                throw Error('Native workspace inventory omitted created profiles');
              return [first,second];
            """)
            for record in workspace_records:
                assert Path(record['id']).resolve().is_relative_to(app_data.resolve()), record
            assert (app_data / 'profiles.ini').exists(), 'Native profile catalog was not persisted'
            result['nativeWorkspaceCreation'] = True
        finally:
            driver.quit()
        driver = launch(profile, Path(temp) / 'restart.log', app_data, local_data)
        try:
            result['nativeSessionExpiry'] = driver.execute_script(IMPORTS + """
              return read(2,'camera')===manager.UNKNOWN_ACTION && read(3,'camera')===manager.ALLOW_ACTION &&
                read(2,'geo')===manager.UNKNOWN_ACTION && read(3,'geo')===manager.ALLOW_ACTION;
            """)
            assert result['nativeSessionExpiry'], result
            print(json.dumps({'completedBeforeWorkspaceFixtures':result}),flush=True)

        finally:
            driver.quit()


        addon_id = 'workspace-isolation@cloakfox.test'
        xpi = Path(temp) / 'workspace-test.xpi'
        with zipfile.ZipFile(xpi, 'w') as archive:
            archive.writestr('manifest.json', json.dumps({
                'manifest_version': 2, 'name': 'Disposable workspace isolation test',
                'version': '1.0', 'browser_specific_settings': {'gecko': {'id': addon_id}}}))
        first, second = [Path(item['id']) for item in workspace_records]
        driver = launch(first, Path(temp) / 'workspace-a.log', app_data, local_data)
        try:
            installed_id = driver.install_addon(str(xpi), temporary=False)
            assert installed_id == addon_id, {'installedAddonId': installed_id, 'expectedAddonId': addon_id}
            async_chrome(driver, """
              const {PlacesUtils}=ChromeUtils.importESModule('resource://gre/modules/PlacesUtils.sys.mjs');
              const info=Cc['@mozilla.org/login-manager/loginInfo;1'].createInstance(Ci.nsILoginInfo);
              info.init('https://workspace-fixture.example','https://workspace-fixture.example',null,
                'fixture-user','disposable-test-password','username','password');
              await Services.logins.addLoginAsync(info);
              await PlacesUtils.history.insert({url:'https://workspace-fixture.example/history',visits:[{date:new Date()}]});
              const cookieValidation=Services.cookies.add('workspace-fixture.example','/','workspace','A',true,false,false,
                Date.now()+86400000,{},Ci.nsICookie.SAMESITE_LAX,Ci.nsICookie.SCHEME_HTTPS);
              if(cookieValidation.result!==Ci.nsICookieValidation.eOK)throw Error('Cookie fixture rejected: '+cookieValidation.errorString);
              Services.prefs.setStringPref('cloakfox.probe.workspace-marker','A');
              Services.prefs.savePrefFile(null);
              const api=ChromeUtils.importESModule('resource:///modules/CloakfoxWorkspaces.sys.mjs');
              const current=api.listWorkspaces().filter(row=>row.current);
              if(current.length!==1||current[0].id!==arguments[0])throw Error('Current registered workspace was not identified');
              return true;
            """, str(first))
            assert_workspace_fixture(driver, addon_id, 'workspace-A-initial', {
                'cookie': True, 'login': True, 'history': True, 'addon': True, 'marker': 'A'})
        finally:
            driver.quit()
        driver = launch(second, Path(temp) / 'workspace-b.log', app_data, local_data)
        try:
            assert_workspace_fixture(driver, addon_id, 'workspace-B-empty', {
                'cookie': False, 'login': False, 'history': False, 'addon': False, 'marker': ''})
            driver.execute_script("Services.prefs.setStringPref('cloakfox.probe.workspace-marker','B'); Services.prefs.savePrefFile(null);")
            result['independentProfileStorage'] = ['cookies', 'passwords', 'history', 'extensions', 'settings']
        finally:
            driver.quit()
        driver = launch(first, Path(temp) / 'workspace-a-restart.log', app_data, local_data)
        try:
            assert_workspace_fixture(driver, addon_id, 'workspace-A-restart', {
                'cookie': True, 'login': True, 'history': True, 'addon': True, 'marker': 'A'})
            result['profileStorageSurvivesRestart'] = True
            result['nativeChildLauncher'] = exercise_native_launcher(driver, app_data)
        finally:
            driver.quit()
        result['nativeChildLauncherExercised'] = True
        print(json.dumps(result, indent=2))
        print('PASS: native permissions expiry, isolated workspace catalog/data, and actual native profile launcher')


def assert_workspace_fixture(driver, addon_id, stage, expected):
    snapshot = read_workspace_fixture(driver, addon_id)
    actual = {key: snapshot[key] for key in expected}
    report = {'stage': stage, 'actual': actual, 'expected': expected,
              'diagnostics': snapshot.get('diagnostics')}
    print(json.dumps(report), flush=True)
    assert actual == expected, report


def read_workspace_fixture(driver, addon_id):
    return async_chrome(driver, """
      const {PlacesUtils}=ChromeUtils.importESModule('resource://gre/modules/PlacesUtils.sys.mjs');
      const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
      const logins=await Services.logins.searchLoginsAsync({origin:'https://workspace-fixture.example'});
      const addon=await AddonManager.getAddonByID(arguments[0]);
      return {cookie:Services.cookies.cookieExists('workspace-fixture.example','/','workspace',{}),
        login:logins.some(login=>login.username==='fixture-user'&&login.password==='disposable-test-password'),
        history:!!(await PlacesUtils.history.fetch('https://workspace-fixture.example/history')),
        addon:!!addon?.isActive,marker:Services.prefs.getStringPref('cloakfox.probe.workspace-marker',''),
        diagnostics:{profile:Services.dirsvc.get('ProfD',Ci.nsIFile).path,
          loginCount:logins.length,loginOrigins:logins.map(item=>item.origin),
          addon:addon?{id:addon.id,isActive:addon.isActive,appDisabled:addon.appDisabled,
            userDisabled:addon.userDisabled,softDisabled:addon.softDisabled,
            signedState:addon.signedState,isCompatible:addon.isCompatible,
            temporarilyInstalled:addon.temporarilyInstalled,pendingOperations:addon.pendingOperations}:null,
          safeMode:Services.appinfo.inSafeMode,
          signaturesRequired:Services.prefs.getBoolPref('xpinstall.signatures.required',true),
          historyEnabled:Services.prefs.getBoolPref('places.history.enabled',true),
          privateAutostart:Services.prefs.getBoolPref('browser.privatebrowsing.autostart',false),
          sanitizeOnShutdown:Services.prefs.getBoolPref('privacy.sanitize.sanitizeOnShutdown',false)}};
    """, addon_id)


if __name__ == '__main__':
    main()
