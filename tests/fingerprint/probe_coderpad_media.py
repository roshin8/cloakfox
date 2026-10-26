"""Exercise installed CoderPad compatibility with synthetic local-only video.

Loopback HTTPS, local DNS, disposable profile. Never opens a real meeting or
requests camera/microphone/screen access. Requires tests/network dependencies.
"""
import json
import os
from pathlib import Path
import shutil
import ssl
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'network'))
from h3_fixture import create_certificates

HTML = b'''<!doctype html><title>Local CoderPad media fixture</title>
<video-player node-id="41" style="display:block;position:relative;width:160px;height:90px"></video-player>
<video-player node-id="52"></video-player><script>
const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;
canvas.getContext('2d').fillRect(0,0,160,90);
const stream=canvas.captureStream(5);let captures=0;
const pipeline={isSupportVideoShare:true,isSupportMediaStreamTrackProcessor:false,
 isVideoTagFrameAccessible:true,videoCaptureValue:{videoCtrl:{srcObject:stream}}};
const inner={[Symbol('context')]:{mediaAgent:{instance:pipeline}}};
const client={stream:{[Symbol('stream')]:inner},getCurrentUserInfo:()=>({userId:41,bVideoOn:!!pipeline.videoCaptureValue})};
const sdk={VERSION:'2.5.0',videoClient:client,createClient(){captures++;throw Error('Unexpected client creation')}};
function req(){return {changedExport:sdk}}
req.m={916:function sdkFactory(){return 'createLocalVideoTrack preloadDependentAssets'}};
window.JsMediaSDK_Instance={pkgVersion:'7.1.0.15306'};
window.webpackChunkcoderpad=[];window.webpackChunkcoderpad.push=e=>e[2]?.(req);
window.snapshot=()=>{const v=document.querySelector('[data-cloakfox-camera-preview]');return {
 fallback:!pipeline.isVideoTagFrameAccessible,preview:!!v,ready:v?.readyState||0,
 sameStream:v?.srcObject===stream,muted:v?.muted||false,captures,
 remoteChildren:document.querySelector('video-player[node-id="52"]').children.length}};
window.stopCamera=()=>{pipeline.videoCaptureValue=null};
</script>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (f'<!doctype html><iframe src="/test/zoom_room"></iframe>'.encode()
                if self.path == '/host' else HTML)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-coderpad-media-') as temp:
        _, cert, key = create_certificates(Path(temp), ['app.coderpad.io', 'media-scope.test'])
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        Thread(target=server.serve_forever, daemon=True).start()
        options = Options()
        options.binary_location = os.environ['CLOAKFOX_BIN']
        options.add_argument('-headless')
        options.add_argument('-purgecaches')
        options.accept_insecure_certs = True
        options.set_preference('network.dns.localDomains', 'app.coderpad.io,media-scope.test')
        options.set_preference('network.trr.mode', 5)
        driver = webdriver.Firefox(options=options, service=Service(
            executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
            service_args=['--allow-system-access'], log_output=str(Path(temp) / 'gecko.log')))
        results = []
        url = f'https://app.coderpad.io:{server.server_port}'
        try:
            for excluded in [url + '/outside', f'https://media-scope.test:{server.server_port}/test/zoom_room']:
                driver.get(excluded)
                result = driver.execute_script('return snapshot()')
                assert not result['fallback'] and not result['preview'], result
                results.append({'excluded': excluded, 'unchanged': True})
            for load in range(2):
                driver.get(url + '/host')
                driver.switch_to.frame(driver.find_element('tag name', 'iframe'))
                WebDriverWait(driver, 10).until(lambda d: d.execute_script('return snapshot().ready===4'))
                result = driver.execute_script('return snapshot()')
                assert result == dict(fallback=True, preview=True, ready=4, sameStream=True,
                                     muted=True, captures=0, remoteChildren=0), result
                results.append({'load': load, **result})
                driver.execute_script('window.stopCamera()')
                WebDriverWait(driver, 5).until(lambda d: not d.execute_script('return snapshot().preview'))
                driver.switch_to.default_content()
            driver.set_context('chrome')
            driver.execute_script("Services.prefs.setBoolPref('cloakfox.compat.coderpad_media',false)")
            driver.set_context('content')
            driver.get(url + '/test/zoom_room')
            result = driver.execute_script('return snapshot()')
            assert not result['fallback'] and not result['preview'] and result['captures'] == 0, result
            results.append({'optOutUnchanged': True})
            print(json.dumps(results, indent=2))
        finally:
            driver.quit()
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
