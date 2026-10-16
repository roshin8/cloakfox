"""Selective native WebGPU pixel readback; arbitrary GPU data remains exact.

These probes render real WGSL into owned textures. Padding and non-pixel
writes deliberately contain nonzero bytes to expose overbroad buffer masking.
"""
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from probe_cef_isolation import Companion


WORK = r"""async function pixelWork(options={}) {
 const adapter=await navigator.gpu.requestAdapter();
 if(!adapter) throw Error('No WebGPU adapter');
 const device=await adapter.requestDevice();
 const errors=[];device.addEventListener('uncapturederror',e=>errors.push(e.error.message));
 device.pushErrorScope('validation');
 const format=options.format||'rgba8unorm', width=16, height=12, size=4096;
 const usage=GPUBufferUsage;
 const buffer=()=>device.createBuffer({size,usage:usage.COPY_SRC|usage.COPY_DST});
 const staging=new WeakMap();
 const read=async(b,offset=0,length=size)=>{
  let mapped=staging.get(b);
  if(!mapped){mapped=device.createBuffer({size,usage:usage.COPY_DST|usage.MAP_READ});staging.set(b,mapped)}
  const transfer=device.createCommandEncoder();transfer.copyBufferToBuffer(b,0,mapped,0,size);
  device.queue.submit([transfer.finish()]);
  await mapped.mapAsync(GPUMapMode.READ,offset,length);
  const result=Array.from(new Uint8Array(mapped.getMappedRange(offset,length)));mapped.unmap();return result;
 };
 const texture=device.createTexture({size:[width,height,options.action==='layers'?3:1],format,
  usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
 const shader=device.createShaderModule({code:`
 @vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {
  let p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}
 @fragment fn fs()->@location(0) vec4f {return vec4f(0.25,0.5,0.75,${options.alpha??1});}`});
 const pipeline=device.createRenderPipeline({layout:'auto',vertex:{module:shader,entryPoint:'vs'},
  fragment:{module:shader,entryPoint:'fs',targets:[{format}]}});
 const render=(encoder,target,layer=0)=>{
  const pass=encoder.beginRenderPass({colorAttachments:[{view:target.createView({dimension:'2d',baseArrayLayer:layer,arrayLayerCount:1}),
   clearValue:[0,0,0,1],loadOp:'clear',storeOp:'store'}]});
  pass.setPipeline(pipeline);pass.draw(3);pass.end();
 };
 const target=buffer();device.queue.writeBuffer(target,0,new Uint8Array(size).fill(90));
 let encoder=device.createCommandEncoder();render(encoder,texture);
 encoder.copyTextureToBuffer({texture},{buffer:target,offset:256,bytesPerRow:256},[width,height]);
 device.queue.submit([encoder.finish()]);await device.queue.onSubmittedWorkDone();
 const result={format,errors};
 if(options.action==='layers') {
  const layered=buffer();device.queue.writeBuffer(layered,0,new Uint8Array(size).fill(90));
  encoder=device.createCommandEncoder();render(encoder,texture,1);render(encoder,texture,2);
  encoder.copyTextureToBuffer({texture,origin:[3,4,1]},
   {buffer:layered,offset:512,bytesPerRow:256,rowsPerImage:8},[7,5,2]);
  device.queue.submit([encoder.finish()]);result.bytes=await read(layered);
 } else if(options.action==='overwrite') {
  // Every source has previously carried pixels, even for a partial overwrite.
  if(options.method==='compute') {
   const storage=device.createBuffer({size,usage:usage.STORAGE|usage.COPY_SRC|usage.COPY_DST});
   encoder=device.createCommandEncoder();encoder.copyBufferToBuffer(target,0,storage,0,size);
   const compute=device.createComputePipeline({layout:'auto',compute:{entryPoint:'main',
    module:device.createShaderModule({code:`
    @group(0) @binding(0) var<storage,read_write> data:array<u32>;
    @compute @workgroup_size(64) fn main(@builtin(global_invocation_id) id:vec3u){
     if(id.x<1024u){data[id.x]=id.x*17u+23u;}}`})}});
   const pass=encoder.beginComputePass();pass.setPipeline(compute);
   pass.setBindGroup(0,device.createBindGroup({layout:compute.getBindGroupLayout(0),
    entries:[{binding:0,resource:{buffer:storage}}]}));pass.dispatchWorkgroups(16);pass.end();
   encoder.copyBufferToBuffer(storage,0,target,0,size);device.queue.submit([encoder.finish()]);
  } else if(options.method==='clear') {
   encoder=device.createCommandEncoder();encoder.clearBuffer(target,256,64);
   device.queue.submit([encoder.finish()]);
  } else {
   device.queue.writeBuffer(target,256,new Uint8Array(64).fill(77));
  }
  result.bytes=await read(target);
 } else if(options.action==='invalid') {
  // Failed texture copies must not label existing ordinary bytes as pixels.
  const ordinary=buffer();device.queue.writeBuffer(ordinary,0,new Uint8Array(size).fill(37));
  device.pushErrorScope('validation');encoder=device.createCommandEncoder();
  if(options.method==='invalid-copy') {
   encoder.copyTextureToBuffer({texture,origin:[15,0]},
    {buffer:ordinary,offset:256,bytesPerRow:256},[16,12]);
  } else {
   encoder.copyTextureToBuffer({texture},{buffer:ordinary,offset:256,bytesPerRow:256},[16,12]);
  }
  const commands=encoder.finish();
  // Finish valid commands first, then force native queue-submit validation to
  // reject their destroyed source. No encoded pixel operation may execute.
  if(options.method==='rejected-submit') texture.destroy();
  device.queue.submit([commands]);await device.queue.onSubmittedWorkDone();
  result.rejected=!!(await device.popErrorScope());result.bytes=await read(ordinary);
 } else {
  result.first=await read(target);result.again=await read(target);
  result.mappedRange=await read(target,256,3072);
  const cropped=buffer();device.queue.writeBuffer(cropped,0,new Uint8Array(size).fill(90));
  const copied=buffer();device.queue.writeBuffer(copied,0,new Uint8Array(size).fill(90));
  encoder=device.createCommandEncoder();
  encoder.copyTextureToBuffer({texture,origin:[3,4]},
   {buffer:cropped,offset:512,bytesPerRow:256},[7,5]);
  encoder.copyBufferToBuffer(target,256,copied,512,3072);
  device.queue.submit([encoder.finish()]);
  result.crop=await read(cropped);result.copied=await read(copied);
  if(options.canvas) {
   const canvas=document.createElement('canvas');canvas.width=16;canvas.height=12;
   const context=canvas.getContext('webgpu');context.configure({device,format,
    usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC,alphaMode:'opaque'});
   document.body.style.margin='0';canvas.style.display='block';document.body.append(canvas);
   encoder=device.createCommandEncoder();const surface=context.getCurrentTexture();
   render(encoder,surface);encoder.copyTextureToBuffer({texture:surface},
    {buffer:target,offset:256,bytesPerRow:256},[width,height]);
   device.queue.submit([encoder.finish()]);await read(target);
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  }
 }
 result.validationError=(await device.popErrorScope())?.message||null;
 // Keep a displayed canvas's device alive until the compositor captures it.
 if(options.canvas) globalThis.pixelDevice=device;else device.destroy();return result;
}"""


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        script = self.path == '/worker.js'
        body = (WORK + "onmessage=async e=>{try{postMessage(await pixelWork(e.data))}catch(e){postMessage({failure:String(e)})}}" if script else '<!doctype html><title>Owned WebGPU pixel fixture</title>').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript' if script else 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class WebGPUPixelPrivacy(unittest.TestCase):
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
        self.root = tempfile.TemporaryDirectory(prefix='cloakfox-webgpu-pixels-')
        self.app = Companion(self.binary, Path(self.root.name))

    def tearDown(self):
        self.app.close()
        self.root.cleanup()

    def work(self, browser, worker=False, **options):
        if worker:
            expression = "new Promise((resolve,reject)=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage(" + json.dumps(options) + ")})"
        else:
            expression = '(async()=>{' + WORK + 'return pixelWork(' + json.dumps(options) + ')})()'
        result = self.app.evaluate(browser, expression)
        self.assertNotIn('failure', result, result)
        self.assertEqual(result['errors'], [])
        self.assertIsNone(result['validationError'])
        return result

    @staticmethod
    def pixels(data, offset=256, width=16, height=12):
        return [data[offset+y*256+x*4:offset+y*256+x*4+4]
                for y in range(height) for x in range(width)]

    def assert_pixels(self, result, noisy=True):
        rgba = [137,188,225,255] if result['format'].endswith('-srgb') else [64,128,191,255]
        raw = [rgba[2],rgba[1],rgba[0],rgba[3]] if result['format'].startswith('bgra') else rgba
        pixels = self.pixels(result['first'])
        self.assertTrue(all(pixel[3] == 255 for pixel in pixels), 'Opaque alpha changed')
        if noisy:
            self.assertTrue(all(all(abs(v-r) <= 1 for v,r in zip(pixel[:3], raw[:3])) for pixel in pixels))
            self.assertTrue(any(pixel != raw for pixel in pixels), 'Rendered image readback lacks pixel privacy noise')
        else:
            self.assertEqual(pixels, [raw]*192)

    def test_opaque_rgba_and_bgra_are_noised_and_repeatable(self):
        browser = self.app.open('301', self.url)
        for format in ('rgba8unorm', 'bgra8unorm', 'rgba8unorm-srgb', 'bgra8unorm-srgb'):
            with self.subTest(format=format):
                result = self.work(browser, format=format)
                self.assert_pixels(result)
                self.assertEqual(result['first'], result['again'])
                self.assertEqual(result['mappedRange'], result['first'][256:3328])
                self.assertEqual(result['first'], self.work(browser, format=format)['first'])

    def canonical_canvas_pixels(self, browser, srgb=False):
        color = '137,188,225' if srgb else '64,128,191'
        values = self.app.evaluate(browser, "(() => {const c=document.createElement('canvas');c.width=16;c.height=12;"
                                   "const x=c.getContext('2d');x.fillStyle='rgb(" + color + ")';x.fillRect(0,0,16,12);"
                                   "return Array.from(x.getImageData(0,0,16,12).data)})()")
        return [values[i:i+4] for i in range(0,len(values),4)]

    def test_pixels_match_native_canvas2d_canonical_rgb(self):
        browser = self.app.open('301', self.url)
        for format in ('rgba8unorm', 'bgra8unorm', 'rgba8unorm-srgb', 'bgra8unorm-srgb'):
            with self.subTest(format=format):
                result = self.work(browser, format=format)
                actual = self.pixels(result['first'])
                if format.startswith('bgra'):
                    actual = [[p[2],p[1],p[0],p[3]] for p in actual]
                self.assertEqual(actual, self.canonical_canvas_pixels(browser, format.endswith('-srgb')),
                                 'WebGPU and Canvas2D disagree on the native pixel transform')
                self.assert_pixels(result)

    def test_persistent_pixel_identity_survives_browser_restart(self):
        before = self.work(self.app.open('301', self.url))['first']
        self.app.close()
        self.app = Companion(self.binary, Path(self.root.name))
        self.assertEqual(before, self.work(self.app.open('301', self.url))['first'])

    def test_private_pixels_regenerate_after_last_private_window(self):
        keeper = self.app.open('301', self.url)
        persistent = self.work(keeper)['first']
        private = self.app.open('301', self.url, private=True)
        before = self.work(private)['first']
        self.assertNotEqual(before, persistent)
        self.assertTrue(self.app.rpc('close', browser=private)['ok'])
        self.app.wait(lambda value: value.get('event') == 'closed' and value.get('browser') == private)
        reopened = self.app.open('301', self.url, private=True)
        self.assertNotEqual(before, self.work(reopened)['first'])
        self.assertEqual(persistent, self.work(keeper)['first'])

    def test_multilayer_copy_respects_origin_rowsperimage_and_padding(self):
        browser = self.app.open('301', self.url)
        expected = self.canonical_canvas_pixels(browser)
        for format in ('rgba8unorm', 'bgra8unorm'):
            with self.subTest(format=format):
                data = self.work(browser, action='layers', format=format)['bytes']
                occupied = set()
                for layer in range(2):
                    for y in range(5):
                        for x in range(7):
                            offset = 512 + layer*8*256 + y*256 + x*4
                            pixel = data[offset:offset+4]
                            if format.startswith('bgra'):
                                pixel = [pixel[2],pixel[1],pixel[0],pixel[3]]
                            self.assertEqual(pixel, expected[(y+4)*16+x+3])
                            occupied.update(range(offset,offset+4))
                self.assertTrue(all(value == 90 for i,value in enumerate(data) if i not in occupied),
                                'Layer copy altered padding, gaps, or bytes outside the destination')

    def test_nonopaque_pixels_are_untouched(self):
        browser = self.app.open('301', self.url)
        for format in ('rgba8unorm', 'bgra8unorm'):
            for alpha, byte in ((0,0), (0.5,128)):
                with self.subTest(format=format, alpha=alpha):
                    result = self.work(browser, format=format, alpha=alpha)
                    raw = [64,128,191,byte] if format.startswith('rgba') else [191,128,64,byte]
                    self.assertEqual(self.pixels(result['first']), [raw]*192)
                    self.assertEqual(result['first'], result['again'])

    def test_container_and_top_level_site_separate_pixels(self):
        first = self.work(self.app.open('301', self.url))['first']
        self.assertNotEqual(first, self.work(self.app.open('302', self.url))['first'])
        self.assertNotEqual(first, self.work(self.app.open('301', self.url.replace('127.0.0.1', 'localhost')))['first'])

    def test_disable_keeps_rendered_pixels_exact(self):
        opened = self.app.rpc('open', container='303', url=self.url, privacy={'canvas': False})
        self.assertTrue(opened['ok'], opened)
        browser = self.app.open('303', self.url)
        for format in ('rgba8unorm', 'bgra8unorm', 'rgba8unorm-srgb', 'bgra8unorm-srgb'):
            with self.subTest(format=format):
                self.assert_pixels(self.work(browser, format=format), noisy=False)

    def test_padding_offsets_crop_coordinates_and_buffer_copy(self):
        result = self.work(self.app.open('301', self.url))
        first = result['first']
        self.assertEqual(first[:256], [90]*256)
        for y in range(12):
            self.assertEqual(first[256+y*256+64:512+y*256], [90]*192)
        self.assertEqual(first[3328:], [90]*768)
        expected = [first[256+y*256+x*4:256+y*256+x*4+4] for y in range(4,9) for x in range(3,10)]
        self.assertEqual(self.pixels(result['crop'], 512, 7, 5), expected)
        self.assertEqual(result['copied'][512:3584], first[256:3328])
        self.assertEqual(result['copied'][:512], [90]*512)
        self.assertEqual(result['copied'][3584:], [90]*512)
        self.assert_pixels(result)

    def test_dedicated_worker_uses_document_pixel_identity(self):
        browser = self.app.open('301', self.url)
        document = self.work(browser)
        worker = self.work(browser, worker=True)
        self.assertEqual(document['first'], worker['first'])
        self.assert_pixels(worker)

    def test_integer_texture_readback_is_exact(self):
        browser = self.app.open('301', self.url)
        pixels = self.app.evaluate(browser, """(async()=>{
const adapter=await navigator.gpu.requestAdapter(),device=await adapter.requestDevice();
device.pushErrorScope('validation');
const texture=device.createTexture({size:[16,12],format:'rgba8uint',usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
const shader=device.createShaderModule({code:`
@vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {
let p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}
@fragment fn fs()->@location(0) vec4u{return vec4u(64,128,191,255);}`});
const pipeline=device.createRenderPipeline({layout:'auto',vertex:{module:shader,entryPoint:'vs'},fragment:{module:shader,entryPoint:'fs',targets:[{format:'rgba8uint'}]}});
const buffer=device.createBuffer({size:3072,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
const encoder=device.createCommandEncoder(),pass=encoder.beginRenderPass({colorAttachments:[{view:texture.createView(),clearValue:[0,0,0,0],loadOp:'clear',storeOp:'store'}]});
pass.setPipeline(pipeline);pass.draw(3);pass.end();encoder.copyTextureToBuffer({texture},{buffer,bytesPerRow:256},[16,12]);device.queue.submit([encoder.finish()]);
await buffer.mapAsync(GPUMapMode.READ);const bytes=Array.from(new Uint8Array(buffer.getMappedRange()));buffer.unmap();
const error=await device.popErrorScope();device.destroy();return {bytes,error:error?.message||null}})()""")
        self.assertIsNone(pixels['error'])
        self.assertEqual(self.pixels(pixels['bytes'], 0), [[64,128,191,255]]*192)

    def test_integer_compute_overwriting_pixels_stays_exact(self):
        result = self.work(self.app.open('301', self.url), action='overwrite', method='compute')
        expected = b''.join((i*17+23).to_bytes(4, 'little') for i in range(1024))
        self.assertEqual(bytes(result['bytes']), expected, 'Pixel provenance leaked onto ordinary integer compute')

    def test_partial_clear_and_writebuffer_remove_pixel_provenance(self):
        browser = self.app.open('301', self.url)
        for method, byte in (('clear', 0), ('write', 77)):
            with self.subTest(method=method):
                result = self.work(browser, action='overwrite', method=method)
                self.assertEqual(result['bytes'][256:320], [byte]*64)
                self.assertEqual(result['bytes'][:256], [90]*256)
                remaining = self.pixels(result['bytes'])[16:]
                self.assertTrue(all(pixel[3] == 255 for pixel in remaining))
                self.assertTrue(any(pixel != [64,128,191,255] for pixel in remaining),
                                'Partial overwrite discarded attribution for untouched rows')

    def test_invalid_copy_and_rejected_submission_leave_ordinary_data_exact(self):
        browser = self.app.open('301', self.url)
        for method in ('invalid-copy', 'rejected-submit'):
            with self.subTest(method=method):
                result = self.work(browser, action='invalid', method=method)
                self.assertTrue(result['rejected'], 'Probe did not exercise WebGPU validation failure')
                self.assertEqual(result['bytes'], [37]*4096)

    def test_readback_does_not_modify_presented_canvas(self):
        browser = self.app.open('301', self.url)
        self.assertTrue(self.app.rpc('open', container='303', url=self.url, privacy={'canvas':False})['ok'])
        control = self.app.open('303', self.url)

        def capture(target):
            metrics = self.app.rpc('cdp', browser=target, method='Emulation.setDeviceMetricsOverride',
                                   params={'width':800,'height':600,'deviceScaleFactor':1,'mobile':False})
            self.assertTrue(metrics['ok'], metrics)
            self.work(target, canvas=True)
            screenshot = self.app.rpc('cdp', browser=target, method='Page.captureScreenshot',
                                      params={'format':'png','clip':{'x':0,'y':0,'width':16,'height':12,'scale':1}})
            self.assertTrue(screenshot['ok'], screenshot)
            png = 'data:image/png;base64,' + screenshot['result']['data']
            return self.app.evaluate(control, '(async()=>{const bitmap=await createImageBitmap(await(await fetch(' + json.dumps(png) + ")).blob());const c=document.createElement('canvas');c.width=16;c.height=12;const x=c.getContext('2d');x.drawImage(bitmap,0,0);bitmap.close();return Array.from(x.getImageData(0,0,16,12).data)})()")

        # The native compositor can convert [64,128,191] to [64,129,191].
        # Paired old/new-engine controls show the same conversion even with
        # privacy disabled and with no canvas image readback. Compare against
        # the actual unprotected presentation so a one-bit privacy mutation
        # cannot be hidden inside a screenshot color-conversion tolerance.
        baseline = capture(control)
        baseline_pixel = baseline[:4]
        self.assertEqual(baseline, baseline_pixel*192)
        self.assertIn(baseline_pixel, ([64,128,191,255], [64,129,191,255]))
        self.assertEqual(capture(browser), baseline,
                         'WebGPU pixel privacy changed the composited canvas')


if __name__ == '__main__':
    unittest.main()
