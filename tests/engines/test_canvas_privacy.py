"""Native Canvas2D privacy checks against an owned loopback fixture."""
import http.server
import os
from pathlib import Path
import tempfile
import threading
import unittest

from probe_cef_isolation import Companion

DRAW = """function draw(c) {
 c.width=32;c.height=24;const x=c.getContext('2d',{willReadFrequently:true});
 x.fillStyle='rgb(72,108,144)';x.fillRect(0,0,32,24);
 x.fillStyle='rgb(141,79,203)';x.fillRect(3,4,17,9);
 return x;
} function pixels(x){return Array.from(x.getImageData(0,0,32,24).data)}"""
READ = "(() => {" + DRAW + "const c=document.createElement('canvas');return pixels(draw(c));})()"

class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/worker.js':
            body = DRAW + "onmessage=()=>{const c=new OffscreenCanvas(32,24);postMessage(pixels(draw(c)))};"
        elif self.path == '/worker-export.js':
            body = DRAW + "onmessage=async()=>{const c=new OffscreenCanvas(32,24);const x=draw(c);const png=new FileReaderSync().readAsDataURL(await c.convertToBlob());postMessage({pixels:pixels(x),png})};"
        elif self.path == '/nested.js':
            body = "onmessage=()=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();postMessage(e.data)};w.postMessage(1)}"
        elif self.path == '/frame':
            body = '<!doctype html><script>' + DRAW + "const c=document.createElement('canvas');parent.postMessage(pixels(draw(c)),'*');</script>"
        else:
            body = '<!doctype html><title>Owned canvas fixture</title>'
        raw = body.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript' if self.path.endswith('.js') else 'text/html')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def log_message(self, *args):
        pass

class CanvasPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get('CLOAKFOX_CHROMIUM_BIN')
        if not binary:
            raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN to source-built companion')
        cls.binary = Path(binary)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(prefix='cloakfox-canvas-')
        self.app = Companion(self.binary, Path(self.root.name))
    def tearDown(self):
        self.app.close()
        self.root.cleanup()
    def test_native_readback_is_container_bound_and_repeatable(self):
        a = self.app.open('101', self.url)
        b = self.app.open('102', self.url)
        first = self.app.evaluate(a, READ)
        self.assertEqual(first, self.app.evaluate(a, READ))
        self.assertFalse(first == self.app.evaluate(b, READ), 'Native canvas output is not container-bound')
    def test_explicit_disable_is_accepted_and_context_conflicts_fail(self):
        opened = self.app.rpc('open', container='101', url=self.url, privacy={'canvas':False})
        self.assertTrue(opened['ok'], opened)
        self.assertFalse(opened['canvasEnabled'])
        a = self.app.open('101', self.url)
        raw = self.app.evaluate(a, READ)
        expected = []
        for y in range(24):
            for x in range(32):
                expected.extend([141,79,203,255] if 3 <= x < 20 and 4 <= y < 13 else [72,108,144,255])
        self.assertEqual(raw, expected, 'Disabled policy still transformed pixels')
        enabled = self.app.open('102', self.url)
        self.assertFalse(raw == self.app.evaluate(enabled, READ))
        conflict = self.app.rpc('open', container='101', url=self.url, privacy={'canvas':True})
        self.assertFalse(conflict['ok'], conflict)
    def test_same_schemeful_site_ignores_port(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            a = self.app.open('101', self.url)
            b = self.app.open('101', f'http://127.0.0.1:{server.server_port}/')
            self.assertEqual(self.app.evaluate(a, READ), self.app.evaluate(b, READ))
        finally:
            server.shutdown()
            server.server_close()
    def test_invalid_canvas_policies_fail(self):
        for policy in ({}, {'canvas':'false'}, {'canvas':1}, {'canvas':True,'unknown':True}, None):
            result = self.app.rpc('open', container='101', url=self.url, privacy=policy)
            self.assertFalse(result['ok'], result)
    def test_site_binding_and_persistent_restart(self):
        a = self.app.open('101', self.url)
        first = self.app.evaluate(a, READ)
        other_site = self.url.replace('127.0.0.1', 'localhost')
        b = self.app.open('101', other_site)
        self.assertFalse(first == self.app.evaluate(b, READ), 'Different top-level sites shared canvas output')
        self.app.close()
        self.app = Companion(self.binary, Path(self.root.name))
        reopened = self.app.open('101', self.url)
        self.assertEqual(first, self.app.evaluate(reopened, READ), 'Persistent key changed after restart')
    def test_private_identity_differs_and_is_recreated(self):
        keeper = self.app.open('101', self.url)
        persistent = self.app.evaluate(keeper, READ)
        private = self.app.open('101', self.url, private=True)
        first = self.app.evaluate(private, READ)
        self.assertFalse(first == self.app.evaluate(keeper, READ))
        self.assertTrue(self.app.rpc('close', browser=private)['ok'])
        self.app.wait(lambda value: value.get('event') == 'closed' and value.get('browser') == private)
        reopened = self.app.open('101', self.url, private=True)
        self.assertFalse(first == self.app.evaluate(reopened, READ), 'Private key survived context destruction')
        self.assertEqual(persistent, self.app.evaluate(keeper, READ), 'Private context changed persistent identity')
    def test_png_exports_match_readback(self):
        a = self.app.open('101', self.url)
        result = self.app.evaluate(a, "(async () => {" + DRAW + """
const c=document.createElement('canvas');const x=draw(c);
const asURL=blob=>new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob)});
const url=c.toDataURL();const blob=await asURL(await new Promise(resolve=>c.toBlob(resolve)));
const off=new OffscreenCanvas(32,24);draw(off);const offscreen=await asURL(await off.convertToBlob());
return {expected:pixels(x),exports:[url,blob,offscreen]};})()""")
        worker = self.app.evaluate(a, "new Promise((resolve,reject)=>{const w=new Worker('/worker-export.js');w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage(1)})")
        self.assertEqual(result['expected'], worker['pixels'])
        result['exports'].append(worker['png'])
        opened = self.app.rpc('open', container='103', url=self.url, privacy={'canvas':False})
        self.assertTrue(opened['ok'], opened)
        # Decode in an explicitly unprotected context. Re-reading in the same
        # protected context would hide a missing export hook: T(raw)==T(T(raw)).
        decoder = self.app.open('103', self.url)
        import json
        expression = "(async () => {const results=[];for(const url of " + json.dumps(result['exports']) + """ ) {
const bitmap=await createImageBitmap(await (await fetch(url)).blob());
const c=document.createElement('canvas');c.width=32;c.height=24;const x=c.getContext('2d');
x.drawImage(bitmap,0,0);bitmap.close();results.push(Array.from(x.getImageData(0,0,32,24).data));
}return results;})()"""
        for decoded in self.app.evaluate(decoder, expression):
            self.assertEqual(result['expected'], decoded)
    def test_dedicated_worker_matches_document(self):
        a = self.app.open('101', self.url)
        self.assertEqual(self.app.evaluate(a, READ), self.app.evaluate(a, "new Promise((resolve,reject)=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage(1)})"))
    def test_nested_worker_inherits_identity(self):
        a = self.app.open('101', self.url)
        worker = "new Promise((resolve,reject)=>{const w=new Worker('/nested.js');w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage(1)})"
        self.assertEqual(self.app.evaluate(a, READ), self.app.evaluate(a, worker))
    def test_cross_origin_frame_uses_top_level_site(self):
        a = self.app.open('101', self.url)
        frame_url = self.url.replace('127.0.0.1', 'localhost') + 'frame'
        expression = "new Promise(resolve=>{const f=document.createElement('iframe');addEventListener('message',function receive(e){if(e.source===f.contentWindow){removeEventListener('message',receive);f.remove();resolve(e.data)}});f.src=" + repr(frame_url) + ";document.body.append(f)})"
        self.assertEqual(self.app.evaluate(a, READ), self.app.evaluate(a, expression))
        b = self.app.open('101', self.url.replace('127.0.0.1','localhost'))
        self.assertFalse(self.app.evaluate(a, READ) == self.app.evaluate(b, READ))
    def test_detached_frame_preserves_native_surface_shutdown(self):
        a = self.app.open('101', self.url)
        value = self.app.evaluate(a, "(async () => {" + DRAW + """
const f=document.createElement('iframe');f.src='/';document.body.append(f);
await new Promise(resolve=>f.onload=resolve);
const c=f.contentDocument.createElement('canvas');const x=draw(c);
const before=pixels(x);f.remove();return {before,after:pixels(x)};})()""")
        self.assertEqual(value['before'], self.app.evaluate(a, READ))
        # The unpatched source baseline stops this rendering context and clears
        # its surface on frame removal. Preserve that native lifecycle behavior.
        self.assertTrue(all(pixel == 0 for pixel in value['after']))
    def test_readback_does_not_change_drawing_surface(self):
        a = self.app.open('101', self.url)
        result = self.app.evaluate(a, "(() => {" + DRAW + """
const c=document.createElement('canvas');const x=draw(c);pixels(x);c.toDataURL();
const g=document.createElement('canvas').getContext('webgl2');
const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);
g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,c);
const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);
g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,t,0);
const out=new Uint8Array(4);g.readPixels(0,0,1,1,g.RGBA,g.UNSIGNED_BYTE,out);
return {pixel:Array.from(out),error:g.getError()};})()""")
        self.assertEqual(result, {'pixel':[72,108,144,255],'error':0})
    def test_crop_matches_full_read_and_transparent_pixels_stay_zero(self):
        a = self.app.open('101', self.url)
        result = self.app.evaluate(a, "(() => {" + DRAW + "const c=document.createElement('canvas');const x=draw(c);const full=pixels(x);const crop=Array.from(x.getImageData(3,4,17,9).data);const expected=[];for(let y=4;y<13;y++)for(let x=3;x<20;x++)expected.push(...full.slice((y*32+x)*4,(y*32+x+1)*4));x.clearRect(0,0,32,24);return {same:JSON.stringify(crop)===JSON.stringify(expected),blank:pixels(x).every(v=>v===0)};})()")
        self.assertEqual(result, {'same':True,'blank':True})

if __name__ == '__main__':
    unittest.main()
