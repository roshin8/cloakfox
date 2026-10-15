"""Owned loopback tests for native shared/service-worker canvas ownership."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from probe_cef_isolation import Companion
from test_canvas_privacy import DRAW, READ
from test_webgl_privacy import WORK as WEBGL_WORK
from test_webgpu_privacy import WORKLOAD as WEBGPU_WORK


WORKER_READ = """async function workerRead(kind, command=1) {
 const request=port=>new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error(kind+' reply timed out')),10000);
   port.onmessage=e=>{clearTimeout(timer);resolve(e.data)};
   port.onmessageerror=()=>{clearTimeout(timer);reject(Error(kind+' message error'))};
   port.start?.();port.postMessage(command);
 });
 if(kind==='shared') {
   const worker=new SharedWorker('/shared.js','cloakfox-worker-privacy');
   (globalThis.privacyWorkerPorts??=[]).push(worker.port);
   return request(worker.port);
 }
 const registration=await navigator.serviceWorker.register('/sw.js');
 const worker=registration.installing||registration.waiting||registration.active;
 if(worker.state!=='activated') await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('service activation timed out')),10000);
   worker.addEventListener('statechange',()=>{
     if(worker.state==='activated'){clearTimeout(timer);resolve()}
     if(worker.state==='redundant'){clearTimeout(timer);reject(Error('service redundant'))}
   });
 });
 const channel=new MessageChannel();const result=request(channel.port1);
 worker.postMessage(command,[channel.port2]);return result;
}"""
WORKER_SCRIPT = DRAW + WEBGL_WORK + WEBGPU_WORK + """
// This snapshot must run before install/connect/message callbacks exist.
const first=pixels(draw(new OffscreenCanvas(32,24)));
async function answer(command){
 if(command==='webgl')return readGL('webgl2',true,true);
 if(command==='webgpu')return workload();
 return {first,current:pixels(draw(new OffscreenCanvas(32,24)))}
}
"""


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/shared.js':
            body = WORKER_SCRIPT + "onconnect=e=>{const port=e.ports[0];port.onmessage=async event=>{try{port.postMessage(await answer(event.data))}catch(error){port.postMessage({failure:String(error)})}};port.start()};"
        elif self.path == '/sw.js':
            body = WORKER_SCRIPT + """
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('message',e=>e.waitUntil(answer(e.data).then(value=>e.ports[0].postMessage(value),error=>e.ports[0].postMessage({failure:String(error)}))));
"""
        elif self.path == '/frame':
            body = '<!doctype html><script>' + DRAW + WORKER_READ + """
(async()=>{try{parent.postMessage({document:pixels(draw(document.createElement('canvas'))),
 shared:await workerRead('shared'),service:await workerRead('service')},'*')}
 catch(error){parent.postMessage({error:String(error)},'*')}})();</script>
"""
        else:
            body = '<!doctype html><title>Owned worker privacy fixture</title>'
        raw = body.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript' if self.path.endswith('.js') else 'text/html')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class WorkerPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get('CLOAKFOX_CHROMIUM_BIN')
        if not binary:
            raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN to source-built companion')
        cls.binary = Path(binary)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.other_site = cls.url.replace('127.0.0.1', 'localhost')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.root = tempfile.TemporaryDirectory(prefix='cloakfox-worker-privacy-')
        self.app = Companion(self.binary, Path(self.root.name))
        self.close_serial = 0

    def tearDown(self):
        try:
            self.close_app()
        finally:
            self.root.cleanup()

    def close_app(self):
        # Companion.close() intentionally reports abnormal native exits. Keep
        # its full stderr as well as that failure's abbreviated diagnostic.
        self.close_serial += 1
        path = Path(tempfile.gettempdir()) / f'cloakfox-worker-{self._testMethodName}-{self.close_serial}.stderr.log'
        with os.fdopen(os.dup(self.app.log.fileno())) as diagnostic:
            try:
                self.app.close()
            finally:
                diagnostic.seek(0)
                path.write_text(diagnostic.read())
                print(f'Native worker diagnostic: {path}', flush=True)

    def worker(self, browser, kind, command=1):
        return self.app.evaluate(browser, '(async()=>{' + WORKER_READ + 'return workerRead(' + json.dumps(kind) + ',' + json.dumps(command) + ')})()')

    def digest(self, pixels):
        self.assertEqual(len(pixels), 32 * 24 * 4)
        return hashlib.sha256(bytes(pixels)).hexdigest()

    def assert_worker_matches(self, expected, actual):
        expected = self.digest(expected)
        self.assertEqual(expected, self.digest(actual['first']), 'First script evaluation has the wrong partition owner')
        self.assertEqual(expected, self.digest(actual['current']), 'Message-time canvas has the wrong partition owner')

    def test_first_script_readback_matches_document(self):
        browser = self.app.open('101', self.url)
        expected = self.app.evaluate(browser, READ)
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                self.assert_worker_matches(expected, self.worker(browser, kind))

    def test_workers_separate_containers_and_top_level_sites(self):
        a = self.app.open('101', self.url)
        b = self.app.open('102', self.url)
        c = self.app.open('101', self.other_site)
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                first = self.worker(a, kind)
                second = self.worker(b, kind)
                other = self.worker(c, kind)
                self.assertNotEqual(self.digest(first['current']), self.digest(second['current']), 'Workers shared canvas across containers')
                self.assertNotEqual(self.digest(first['current']), self.digest(other['current']), 'Workers shared canvas across sites')
                for browser, result in ((a, first), (b, second), (c, other)):
                    self.assert_worker_matches(self.app.evaluate(browser, READ), result)

    def test_third_party_workers_use_top_level_partition(self):
        top = self.app.open('101', self.url)
        standalone = self.app.open('101', self.other_site)
        expression = """new Promise((resolve,reject)=>{
 const frame=document.createElement('iframe');
 const timer=setTimeout(()=>reject(Error('frame timed out')),15000);
 addEventListener('message',function receive(e){if(e.source===frame.contentWindow){
  removeEventListener('message',receive);clearTimeout(timer);
  e.data.error?reject(Error(e.data.error)):resolve(e.data)
 }});frame.src=""" + json.dumps(self.other_site + 'frame') + ";document.body.append(frame)})"
        result = self.app.evaluate(top, expression)
        expected = self.app.evaluate(top, READ)
        self.assertEqual(self.digest(expected), self.digest(result['document']))
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                self.assert_worker_matches(expected, result[kind])
                self.assertNotEqual(self.digest(result[kind]['current']), self.digest(self.worker(standalone, kind)['current']), 'Third-party worker joined a first-party partition')

    def test_worker_identity_survives_browser_restart(self):
        browser = self.app.open('101', self.url)
        expected = self.app.evaluate(browser, READ)
        before = {kind: self.worker(browser, kind) for kind in ('shared', 'service')}
        self.close_app()
        self.app = Companion(self.binary, Path(self.root.name))
        browser = self.app.open('101', self.url)
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                result = self.worker(browser, kind)
                self.assertEqual(before[kind], result, 'Worker identity changed after browser restart')
                self.assert_worker_matches(expected, result)

    def test_private_workers_regenerate_after_last_window(self):
        persistent = self.app.open('101', self.url)
        private = self.app.open('101', self.url, private=True)
        before = {kind: self.worker(private, kind) for kind in ('shared', 'service')}
        self.assertTrue(self.app.rpc('close', browser=private)['ok'])
        self.app.wait(lambda value: value.get('event') == 'closed' and value.get('browser') == private)
        private = self.app.open('101', self.url, private=True)
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                result = self.worker(private, kind)
                self.assertNotEqual(self.digest(before[kind]['current']), self.digest(result['current']), 'Private worker identity survived context destruction')
                self.assertNotEqual(self.digest(result['current']), self.digest(self.worker(persistent, kind)['current']), 'Private and persistent workers shared identity')
                self.assert_worker_matches(self.app.evaluate(private, READ), result)

    def test_shared_service_gpu_workloads_and_metadata(self):
        browser = self.app.open('105', self.url)
        expected = self.digest(self.app.evaluate(browser, READ))
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                gl = self.worker(browser, kind, 'webgl')
                self.assertNotIn('failure', gl, gl)
                self.assertEqual(gl['error'], 0)
                self.assertTrue(gl['padding'] and gl['crop'] and gl['copied'])
                self.assertFalse(gl['debug'] or gl['supportedDebug'])
                self.assertEqual(self.digest(gl['pixels']), expected)
                gpu = self.worker(browser, kind, 'webgpu')
                self.assertNotIn('failure', gpu, gpu)
                self.assertTrue(gpu['renderSubmitted'] and gpu['writeAllowed'])
                self.assertEqual(gpu['compute'], [i*17+23 for i in range(256)])
                self.assertEqual(gpu['adapter'], gpu['device'])
                self.assertTrue(all(value == '' for value in gpu['adapter'].values()))
                self.assertEqual(gpu['errors'], [])
                self.assertIsNone(gpu['validationError'])
    def test_shared_service_explicit_webgpu_readback_block(self):
        opened = self.app.rpc('open', container='106', url=self.url,
                              privacy={'blockWebGPUReadback':True})
        self.assertTrue(opened['ok'], opened)
        browser = self.app.open('106', self.url)
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                gpu = self.worker(browser, kind, 'webgpu')
                self.assertNotIn('failure', gpu, gpu)
                self.assertTrue(gpu['renderSubmitted'] and gpu['writeAllowed'])
                self.assertEqual(gpu['computeError']['name'], 'NotAllowedError')
                self.assertEqual(gpu['pixelsError']['name'], 'NotAllowedError')
                self.assertEqual(gpu['errors'], [])
                self.assertIsNone(gpu['validationError'])
    def test_explicit_disable_preserves_raw_worker_pixels(self):
        opened = self.app.rpc('open', container='101', url=self.url, privacy={'canvas': False})
        self.assertTrue(opened['ok'], opened)
        browser = self.app.open('101', self.url)
        raw = []
        for y in range(24):
            for x in range(32):
                raw.extend([141, 79, 203, 255] if 3 <= x < 20 and 4 <= y < 13 else [72, 108, 144, 255])
        self.assertEqual(self.digest(raw), self.digest(self.app.evaluate(browser, READ)))
        for kind in ('shared', 'service'):
            with self.subTest(kind=kind):
                self.assert_worker_matches(raw, self.worker(browser, kind))


if __name__ == '__main__':
    unittest.main()
