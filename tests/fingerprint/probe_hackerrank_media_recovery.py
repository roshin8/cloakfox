"""Test the installed HackerRank recovery actor over isolated loopback HTTPS.

The real registration and built module are used without replacing either.
DNS is local, and this fixture opens no meeting and captures no devices.
"""
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'network'))
from h3_fixture import create_certificates

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
        self.send_header('Content-Type','text/html')
        self.end_headers()
        self.wfile.write(HTML)
    def log_message(self,*_): pass


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-media-actor-') as temp:
        _,cert,key=create_certificates(Path(temp),['www.hackerrank.com','media-scope.test'])
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key)
        server.socket=ctx.wrap_socket(server.socket,server_side=True)
        Thread(target=server.serve_forever,daemon=True).start()
        options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
        options.add_argument('-headless');options.add_argument('-purgecaches')
        options.accept_insecure_certs=True
        options.set_preference('network.dns.localDomains','www.hackerrank.com,media-scope.test')
        options.set_preference('network.trr.mode',5)
        driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access']))
        results=[]
        url=f'https://www.hackerrank.com:{server.server_port}'
        try:
            for excluded in [url+'/outside',f'https://media-scope.test:{server.server_port}/pair/test']:
                driver.get(excluded)
                # Reconcile happens synchronously once bound. No actor match means
                # the ID remains stale and no callbacks or capture calls exist.
                driver.execute_script('window.reconnect(52)')
                assert driver.execute_script('return snapshot().idMatches') is False
                assert driver.execute_script('return bound()') is not True
                results.append({'excluded':excluded,'bound':False})
            for load in range(2):
                driver.get(url+'/pair/test')
                WebDriverWait(driver,10).until(lambda d:d.execute_script('return bound()'))
                for next_id in [52,63]:
                    driver.execute_script('window.reconnect(arguments[0])',next_id)
                    WebDriverWait(driver,5).until(lambda d:d.execute_script('return snapshot().idMatches'))
                result=driver.execute_script('return snapshot()')
                assert result=={'idMatches':True,'visible':True,'writes':2,'renders':2,'captures':0,'readiness':False},result
                results.append({'load':load,**result})
            driver.set_context('chrome')
            driver.execute_script("Services.prefs.setBoolPref('cloakfox.compat.hackerrank_media',false)")
            driver.set_context('content');driver.get(url+'/pair/test')
            driver.execute_script('window.reconnect(52)')
            result=driver.execute_script('return snapshot()')
            assert result['idMatches'] is False and result['writes']==0 and result['captures']==0,result
            results.append('opt-out leaves cached ID unchanged')
            print(json.dumps(results,indent=2));print('PASS: installed HackerRank recovery registration, two reloads, scope and opt-out')
        finally:
            driver.quit();server.shutdown();server.server_close()


if __name__=='__main__':main()
