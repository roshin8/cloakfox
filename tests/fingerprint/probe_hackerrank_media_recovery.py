"""Native WindowActor regression for the recorded HackerRank failover sequence.

Uses an isolated loopback application fixture, not a real meeting or device.
The production origin match is checked first; the same actor is then registered
for loopback solely in the disposable test profile. No actor source is changed.
"""
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
ACTOR = ROOT / 'additions/browser/components/cloakfox/actors/CloakfoxHackerRankMediaChild.sys.mjs'
HTML = b'''<!doctype html><title>Media reconnect regression</title><script>
let sdkId=41,writes=0,renders=0,captures=0;
const handlers=new Map();
const client={on(n,f){if(!handlers.has(n))handlers.set(n,new Set());handlers.get(n).add(f)},off(n,f){handlers.get(n)?.delete(f)},getCurrentUserInfo(){return {userId:sdkId,bVideoOn:true}},startVideo(){captures++},startShareScreen(){captures++}};
const state={callStatus:'connected',localZoomUserId:41,isVideoDecodeReady:false,videoVisible:true,setLocalZoomUserId(id){this.localZoomUserId=id;writes++;this.videoVisible=id===sdkId},incrementVideoRenderEpoch(){renders++}};
const store=Object.assign(()=>{}, {getState:()=>state,subscribe(){throw Error('Unexpected store subscription')}});
const av={provider:{zmClient:client},getLocalParticipantId(){return sdkId}};
function getAV(){if(!av)throw Error('Call initAV(provider) before using getAV()');return av}
function req(id){return id==='981'?{changedStore:store}:{changedGetter:getAV}}
req.m={981:function(){return 'setLocalZoomUserId incrementVideoRenderEpoch'},276:function(){return 'Call initAV(provider) before using getAV()'}};
window.webpackChunk_N_E=[];window.webpackChunk_N_E.push=function(e){e[2]?.(req)};
window.bound=()=>handlers.get('connection-change')?.size===1;
window.reconnect=id=>{state.callStatus='reconnecting';sdkId=id;state.videoVisible=false;for(const fn of handlers.get('connection-change')||[])fn({state:'Reconnecting'});state.callStatus='connected';for(const fn of handlers.get('connection-change')||[])fn({state:'Connected'})};
window.snapshot=()=>({idMatches:state.localZoomUserId===sdkId,visible:state.videoVisible,writes,renders,captures,readiness:state.isVideoDecodeReady});
</script>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *_):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    options = Options()
    options.binary_location = os.environ['CLOAKFOX_BIN']
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access']))
    results = []
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        driver.set_context('chrome')
        profile = Path(driver.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path"))
        assets = profile / 'chrome' / 'media-recovery-test'
        assets.mkdir(parents=True)
        (assets / ACTOR.name).write_bytes(ACTOR.read_bytes())
        driver.execute_script("""const f=Cc['@mozilla.org/file/local;1'].createInstance(Ci.nsIFile);f.initWithPath(arguments[0]);Services.io.getProtocolHandler('resource').QueryInterface(Ci.nsISubstitutingProtocolHandler).setSubstitution('mediarecoverytest',Services.io.newURI(Services.io.newFileURI(f).spec+'/'));""",str(assets))
        def register(matches):
            driver.execute_script("""ChromeUtils.registerWindowActor('CloakfoxHackerRankMedia',{child:{esModuleURI:'resource://mediarecoverytest/CloakfoxHackerRankMediaChild.sys.mjs',events:{DOMDocElementInserted:{}}},matches:arguments[0],allFrames:false});""",matches)
        # Unregister the built-in actor when testing a binary containing the fix.
        driver.execute_script("try { ChromeUtils.unregisterWindowActor('CloakfoxHackerRankMedia'); } catch (_) {}")
        register(['https://www.hackerrank.com/pair/*'])
        driver.set_context('content')
        driver.get(url)
        driver.execute_script('window.reconnect(52)')
        assert driver.execute_script('return snapshot().idMatches') is False
        assert driver.execute_script('return bound()') is not True
        results.append('production origin scope excludes loopback')
        driver.set_context('chrome')
        driver.execute_script("ChromeUtils.unregisterWindowActor('CloakfoxHackerRankMedia')")
        register(['http://127.0.0.1/*'])
        driver.set_context('content')
        for load in range(2):
            driver.get(url)
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return bound()'))
            for next_id in [52, 63]:
                driver.execute_script('window.reconnect(arguments[0])', next_id)
                WebDriverWait(driver, 5).until(lambda d: d.execute_script('return snapshot().idMatches'))
            result = driver.execute_script('return snapshot()')
            assert result == {'idMatches':True,'visible':True,'writes':2,'renders':2,'captures':0,'readiness':False}, result
            results.append({'load':load, **result})
        driver.set_context('chrome')
        driver.execute_script("Services.prefs.setBoolPref('cloakfox.compat.hackerrank_media',false)")
        driver.set_context('content')
        driver.get(url)
        driver.execute_script('window.reconnect(52)')
        result = driver.execute_script('return snapshot()')
        assert result['idMatches'] is False and result['writes'] == 0 and result['captures'] == 0, result
        results.append('opt-out leaves cached ID unchanged')
        print(json.dumps(results, indent=2))
        print('HACKERRANK MEDIA RECONNECT ACTOR PASS')
    finally:
        driver.quit()
        server.shutdown()

if __name__ == '__main__':
    main()
