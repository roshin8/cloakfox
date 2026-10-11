"""Native query stripping and scoped bounce purging in a disposable profile.

Run sequentially with CLOAKFOX_BIN after rebuilding. Query checks navigate real
cross-site links and inspect loopback HTTP requests. Bounce checks inject native
test candidates/activation, then run the real purge over real native cookies;
this does not claim to test heuristic bounce classification or elapsed timers.
"""
import contextlib
import html
import http.server
import json
import tempfile
import threading
import urllib.parse
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch


class Handler(http.server.BaseHTTPRequestHandler):
    seen = []
    lock = threading.Lock()

    def do_GET(self):
        with self.lock:
            self.seen.append({'host': self.headers.get('Host'), 'path': self.path})
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == '/source':
            case = urllib.parse.parse_qs(parsed.query).get('case', ['strip'])[0]
            query = urllib.parse.urlencode({'utm_source': 'fixture', 'utm_campaign': 'campaign',
                'fbclid': 'tracking-id', 'state': 'csrf-state-123', 'code': 'oauth-code-456',
                'redirect_uri': 'https://client.example/callback', 'case': case})
            target = f'http://target-tracking.test:{self.server.server_port}/landing?{query}'
            body = f'<!doctype html><title>Tracking source</title><a id="go" href="{html.escape(target, quote=True)}">Continue</a>'.encode()
        else:
            body = b'<!doctype html><title>Tracking destination</title><p>Arrived</p>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def chrome(driver, script, *args):
    driver.set_context('chrome')
    return driver.execute_script(script, *args)


def async_chrome(driver, script, *args):
    driver.set_context('chrome')
    result = driver.execute_async_script("""
      const done=arguments[arguments.length-1];
      (async()=>{ SCRIPT })().then(done,error=>done({error:error.message,stack:error.stack}));
    """.replace('SCRIPT', script), *args)
    assert not isinstance(result, dict) or 'error' not in result, result
    return result


def navigate_cross_site(driver, server, case, stripped):
    driver.set_context('content')
    driver.get(f'http://source-tracking.test:{server.server_port}/source?case={case}')
    driver.find_element(By.ID, 'go').click()
    WebDriverWait(driver, 20).until(lambda d: urllib.parse.urlsplit(d.current_url).hostname == 'target-tracking.test'
                                  and d.execute_script('return document.readyState') == 'complete')
    with Handler.lock:
        requests = [row for row in Handler.seen if urllib.parse.urlsplit(row['path']).path == '/landing'
                    and urllib.parse.parse_qs(urllib.parse.urlsplit(row['path']).query).get('case') == [case]]
    assert requests, {'case': case, 'currentURL': driver.current_url}
    for row in requests:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(row['path']).query)
        assert query['state'] == ['csrf-state-123'] and query['code'] == ['oauth-code-456'], row
        assert query['redirect_uri'] == ['https://client.example/callback'], row
        for key in ['utm_source', 'utm_campaign', 'fbclid']:
            assert (key not in query) == stripped, row
    return {'case': case, 'trackingRemoved': stripped, 'oauthStateCodeAndRedirectPreserved': True}


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    driver = None
    try:
        with contextlib.ExitStack() as stack:
            temp = stack.enter_context(tempfile.TemporaryDirectory(prefix='cloakfox-tracking-'))
            profile = Path(temp) / 'profile'
            profile.mkdir()
            driver = launch(profile, Path(temp) / 'geckodriver.log')
            stack.callback(driver.quit)
            driver.set_script_timeout(60)
            chrome(driver, """
              Services.prefs.setBoolPref('dom.security.https_only_mode',false);
              Services.prefs.setStringPref('network.dns.localDomains','source-tracking.test,target-tracking.test');
              Services.prefs.setIntPref('network.proxy.type',0);
              Services.prefs.setIntPref('network.trr.mode',5);
              Services.prefs.setStringPref('privacy.query_stripping.allow_list','');
              const api=ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs');
              api.setTrackingProtection({strip:true,stripPrivate:true,bounceMode:1});
              const configured=Services.prefs.getStringPref('privacy.query_stripping.strip_list','');
              if(!['utm_source','utm_campaign','fbclid'].every(key=>configured.split(' ').includes(key)))
                throw Error('Shipped tracking parameter list is missing fixture keys');
            """)
            readiness = chrome(driver, """
              const stripper=Cc['@mozilla.org/url-query-string-stripper;1'].getService(Ci.nsIURLQueryStringStripper);
              const uri=Services.io.newURI('http://target-tracking.test/landing?utm_source=x&utm_campaign=y&fbclid=z&state=keep&code=keep');
              const source=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI('http://source-tracking.test/'),{});
              const output={};
              const count=stripper.strip(uri,false,output);
              return {configured:Services.prefs.getStringPref('privacy.query_stripping.strip_list',''),
                nativeList:stripper.testGetStripList(),thirdParty:source.isThirdPartyURI(uri),
                immediateStripCount:count,immediateResult:output.value?.spec||null};
            """)
            print('Native query readiness (no init wait): '+json.dumps(readiness),flush=True)
            assert readiness['thirdParty'] and readiness['immediateStripCount']==3, readiness
            results = {'readiness':readiness,'navigation': [navigate_cross_site(driver, server, 'strip', True)]}
            chrome(driver, """
              ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs')
                .setQueryException('target-tracking.test',true);
            """)
            results['navigation'].append(navigate_cross_site(driver, server, 'exception', False))
            chrome(driver, """
              ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs')
                .setQueryException('target-tracking.test',false);
            """)
            results['navigation'].append(navigate_cross_site(driver, server, 're-enabled', True))
            results['bounce'] = async_chrome(driver, """
              const api=ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs');
              const {ContextualIdentityService:cis}=ChromeUtils.importESModule(
                'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              Services.prefs.setBoolPref('permissions.isolateBy.userContext',false);
              Services.prefs.setIntPref('privacy.bounceTrackingProtection.bounceTrackingGracePeriodSec',0);
              const btp=Cc['@mozilla.org/bounce-tracking-protection;1'].getService(Ci.nsIBounceTrackingProtection);
              btp.clearAll();
              const a=cis.create('Bounce exception fixture','fingerprint','blue').userContextId;
              const b=cis.create('Bounce purge control','fingerprint','green').userContextId;
              const exceptionHost='bounce-fixture.test', activationHost='activation-fixture.test', otherHost='unrelated-fixture.test';
              const has=(host,id)=>Services.cookies.cookieExists(host,'/','bounce-state',{userContextId:id});
              const snapshot=()=>({a,b,mode:Services.prefs.getIntPref('privacy.bounceTrackingProtection.mode'),
                cookies:Object.fromEntries([a,b].map(id=>[id,Object.fromEntries(
                  [exceptionHost,activationHost,otherHost].map(host=>[host,has(host,id)]))])),
                permissions:Services.perms.getAllByTypes([api.bouncePermissionType(a),api.bouncePermissionType(b)]).map(permission=>({
                  type:permission.type,origin:permission.principal.origin,attributes:permission.principal.originAttributes,
                  capability:permission.capability,expireType:permission.expireType,expireTime:permission.expireTime})),
                candidates:Object.fromEntries([a,b].map(id=>[id,btp.testGetBounceTrackerCandidateHosts({userContextId:id}).map(e=>e.siteHost)])),
                activations:Object.fromEntries([a,b].map(id=>[id,btp.testGetUserActivationHosts({userContextId:id}).map(e=>e.siteHost)]))});
              for(const id of [a,b]) for(const host of [exceptionHost,activationHost,otherHost]) {
                Services.cookies.add(host,'/','bounce-state','fixture',true,false,false,
                  Date.now()+86400000,{userContextId:id},Ci.nsICookie.SAMESITE_LAX,Ci.nsICookie.SCHEME_HTTPS);
                if(!has(host,id))throw Error('Cookie fixture was not stored');
                btp.testAddBounceTrackerCandidate({userContextId:id},host,1);
              }
              api.setBounceException(a,exceptionHost,Date.now()+60000);
              if(api.listBounceExceptions(a).length!==1||api.listBounceExceptions(b).length!==0)
                throw Error('Bounce exception permission leaked to another container');
              const exceptionPrincipal=Services.scriptSecurityManager.createContentPrincipal(
                Services.io.newURI('https://'+exceptionHost),{userContextId:a});
              for(const type of ['cookie','trackingprotection','trackingprotection-pb'])
                if(Services.perms.testPermissionFromPrincipal(exceptionPrincipal,type)!==Services.perms.UNKNOWN_ACTION)
                  throw Error('Narrow bounce exception created a broad permission');
              btp.testAddUserActivation({userContextId:a},activationHost,Date.now()*1000);
              if(!btp.testGetUserActivationHosts({userContextId:a}).some(item=>item.siteHost===activationHost))
                throw Error('Native user activation was not recorded');
              const beforePurge=snapshot();
              const purged=await btp.testRunPurgeBounceTrackers();
              const afterPurge=snapshot();
              const fail=message=>{throw Error(message+': '+JSON.stringify({beforePurge,purged,afterPurge}));};
              if(!has(exceptionHost,a)||has(exceptionHost,b))fail('Bounce exception was not container-scoped');
              if(!has(activationHost,a)||has(activationHost,b))fail('Native user activation protection was not scoped');
              if(has(otherHost,a)||has(otherHost,b))fail('Unrelated bounce candidate was exempted');
              // Existing typed exceptions must keep their scope if the user later
              // enables isolation for ordinary site permissions.
              Services.prefs.setBoolPref('permissions.isolateBy.userContext',true);
              Services.cookies.add(exceptionHost,'/','bounce-state','fixture',true,false,false,
                Date.now()+86400000,{userContextId:b},Ci.nsICookie.SAMESITE_LAX,Ci.nsICookie.SCHEME_HTTPS);
              for(const id of [a,b])btp.testAddBounceTrackerCandidate({userContextId:id},exceptionHost,1);
              await btp.testRunPurgeBounceTrackers();
              if(!has(exceptionHost,a)||has(exceptionHost,b))throw Error('Permission sharing toggle changed exception scope: '+JSON.stringify(snapshot()));
              api.setBounceException(a,exceptionHost,0);
              btp.testAddBounceTrackerCandidate({userContextId:a},exceptionHost,1);
              await btp.testRunPurgeBounceTrackers();
              if(has(exceptionHost,a))throw Error('Removed bounce exception still prevented purge: '+JSON.stringify(snapshot()));
              // Deleting a real native identity must clean bare-principal typed
              // grants through the startup observer, without opening settings.
              api.setBounceException(a,exceptionHost,Date.now()+60000);
              api.setBounceException(b,exceptionHost,Date.now()+60000);
              const bare=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI('https://'+exceptionHost),{});
              Services.perms.addFromPrincipal(bare,api.bouncePermissionType(a,1),Services.perms.ALLOW_ACTION,Services.perms.EXPIRE_TIME,Date.now()+60000);
              Services.perms.addFromPrincipal(bare,'camera',Services.perms.ALLOW_ACTION,Services.perms.EXPIRE_SESSION);
              if(!cis.remove(a))throw Error('Fixture identity could not be deleted');
              if(Services.perms.getAllByTypes([api.bouncePermissionType(a,0),api.bouncePermissionType(a,1)]).length)
                throw Error('Deleted identity retained typed bounce grants');
              if(api.listBounceExceptions(b).length!==1||Services.perms.testExactPermissionFromPrincipal(bare,'camera')!==Services.perms.ALLOW_ACTION)
                throw Error('Identity deletion removed another scope or ordinary permission');
              return {nativePurge:true,selectedContainerException:true,unrelatedDomainPurged:true,
                broadPermissionsUntouched:true,deletedIdentityScopesCleared:true,sharedPermissionsScoped:true,sharingTogglePreservesScope:true,userActivationProtected:true,exceptionRemovalEffective:true,
                firstPurgeReportedHosts:purged,beforePurge,afterPurge};
            """)
            print(json.dumps(results, indent=2))
            print('PASS: real query stripping preserves OAuth fields; native bounce purge respects narrow container exceptions and activation')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == '__main__':
    main()
