"""Real WebGPU render/compute regression checks against the source-built companion.

Pixel privacy must not alter compute results. Readback denial is separately
opted into and deliberately rejects all READ mapping, including compute output.
"""
import http.server
import os
from pathlib import Path
import tempfile
import threading
import unittest

from probe_cef_isolation import Companion

WORKLOAD = r"""async function workload() {
 const adapter=await navigator.gpu.requestAdapter();
 if(!adapter) throw new Error('No WebGPU adapter');
 const device=await adapter.requestDevice();
 device.pushErrorScope('validation');
 const errors=[];device.addEventListener('uncapturederror',e=>errors.push(e.error.message));
 const info=x=>Object.fromEntries(['vendor','architecture','device','description',
 'driver','backend','type','powerPreference'].filter(k=>k in x).map(k=>[k,x[k]]));
 const canvas=typeof document==='undefined'?new OffscreenCanvas(8,8):document.createElement('canvas');
 canvas.width=8;canvas.height=8;
 const context=canvas.getContext('webgpu');
 const format=navigator.gpu.getPreferredCanvasFormat();
 context.configure({device,format,usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
 const shader=device.createShaderModule({code:`
 @vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {
 let p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}
 @fragment fn fs()->@location(0) vec4f{return vec4f(0.25,0.5,0.75,1);}`});
 const render=device.createRenderPipeline({layout:'auto',vertex:{module:shader,entryPoint:'vs'},
 fragment:{module:shader,entryPoint:'fs',targets:[{format}]},primitive:{topology:'triangle-list'}});
 const compute=device.createComputePipeline({layout:'auto',compute:{module:device.createShaderModule({code:`
 @group(0) @binding(0) var<storage,read_write> data:array<u32>;
 @compute @workgroup_size(64) fn main(@builtin(global_invocation_id) id:vec3u){
 if(id.x<256u){data[id.x]=id.x*17u+23u;}}`}),entryPoint:'main'}});
 const storage=device.createBuffer({size:1024,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC});
 const staging=device.createBuffer({size:1024,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
 const pixels=device.createBuffer({size:2048,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
 const encoder=device.createCommandEncoder();const texture=context.getCurrentTexture();
 const pass=encoder.beginRenderPass({colorAttachments:[{view:texture.createView(),clearValue:[0,0,0,1],loadOp:'clear',storeOp:'store'}]});
 pass.setPipeline(render);pass.draw(3);pass.end();
 encoder.copyTextureToBuffer({texture},{buffer:pixels,bytesPerRow:256},{width:8,height:8});
 const cp=encoder.beginComputePass();cp.setPipeline(compute);cp.setBindGroup(0,device.createBindGroup({layout:compute.getBindGroupLayout(0),entries:[{binding:0,resource:{buffer:storage}}]}));
 cp.dispatchWorkgroups(4);cp.end();encoder.copyBufferToBuffer(storage,0,staging,0,1024);
 device.queue.submit([encoder.finish()]);await device.queue.onSubmittedWorkDone();
 const caps=x=>({subgroupMinSize:x.subgroupMinSize,subgroupMaxSize:x.subgroupMaxSize,isFallbackAdapter:x.isFallbackAdapter});
 const output={adapter:info(adapter.info),device:info(device.adapterInfo),adapterCapabilities:caps(adapter.info),deviceCapabilities:caps(device.adapterInfo),renderSubmitted:true,format,errors};
 for(const [name,buffer,Type] of [['compute',staging,Uint32Array],['pixels',pixels,Uint8Array]]){
 try{await buffer.mapAsync(GPUMapMode.READ);output[name]=Array.from(new Type(buffer.getMappedRange()));buffer.unmap();}
 catch(e){output[name+'Error']={name:e.name,message:e.message};}}
 const upload=device.createBuffer({size:16,usage:GPUBufferUsage.MAP_WRITE|GPUBufferUsage.COPY_SRC});
 await upload.mapAsync(GPUMapMode.WRITE);new Uint32Array(upload.getMappedRange())[0]=42;upload.unmap();
 const initial=device.createBuffer({size:16,usage:GPUBufferUsage.COPY_SRC,mappedAtCreation:true});
 new Uint32Array(initial.getMappedRange())[0]=43;initial.unmap();output.writeAllowed=true;
 const validationError=await device.popErrorScope();output.validationError=validationError?validationError.message:null;
 device.destroy();return output;
}"""


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (WORKLOAD + "onmessage=async()=>{try{postMessage(await workload())}catch(e){postMessage({failure:String(e)})}}" if self.path == '/worker.js' else '<!doctype html><title>Owned WebGPU fixture</title>').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript' if self.path.endswith('.js') else 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass


class WebGPUPrivacy(unittest.TestCase):
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
        self.root = tempfile.TemporaryDirectory(prefix='cloakfox-webgpu-')
        self.app = Companion(self.binary, Path(self.root.name))
    def tearDown(self):
        self.app.close()
        self.root.cleanup()
    def run_workload(self, browser, worker=False):
        if worker:
            expression = "new Promise((resolve,reject)=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage(1)})"
        else:
            expression = '(async()=>{' + WORKLOAD + 'return await workload()})()'
        value = self.app.evaluate(browser, expression)
        self.assertNotIn('failure', value, value)
        self.assertTrue(value['renderSubmitted'])
        self.assertTrue(value['writeAllowed'])
        self.assertEqual(value['errors'], [])
        self.assertIsNone(value['validationError'])
        self.assertEqual(value['adapterCapabilities'], value['deviceCapabilities'])
        self.assertIsInstance(value['adapterCapabilities']['isFallbackAdapter'], bool)
        self.assertLessEqual(value['adapterCapabilities']['subgroupMinSize'], value['adapterCapabilities']['subgroupMaxSize'])
        return value
    def assert_raw_work(self, value, protected=True):
        self.assertEqual(value['compute'], [i*17+23 for i in range(256)])
        expected = [64,128,191,255] if value['format']=='rgba8unorm' else [191,128,64,255]
        self.assertIn(value['format'], ['rgba8unorm','bgra8unorm'])
        changed = False
        for y in range(8):
            for x in range(8):
                offset=y*256+x*4
                pixel = value['pixels'][offset:offset+4]
                self.assertEqual(pixel[3], 255)
                if protected:
                    self.assertTrue(all(abs(actual-raw) <= 1 for actual,raw in zip(pixel[:3], expected[:3])))
                    changed |= pixel != expected
                else:
                    self.assertEqual(pixel, expected)
        if protected:
            self.assertTrue(changed, 'Opaque WebGPU pixels were not protected')
    def assert_masked(self, value):
        self.assertTrue(all(v=='' for v in value['adapter'].values()), value['adapter'])
        self.assertEqual(value['adapter'], value['device'])
    def test_default_metadata_reduction_preserves_actual_render_and_compute(self):
        browser = self.app.open('201', self.url)
        value = self.run_workload(browser)
        self.assert_raw_work(value)
        self.assert_masked(value)
        self.assertEqual(self.app.ready.get('webgpuPrivacyVersion'), 1)
    def test_native_disable_restores_metadata_without_altering_work(self):
        result = self.app.rpc('open', container='202', url=self.url, privacy={'canvas':False})
        self.assertTrue(result['ok'], result)
        browser = self.app.open('202', self.url)
        value = self.run_workload(browser)
        self.assert_raw_work(value, protected=False)
        self.assertTrue(value['adapter']['vendor'] or value['adapter']['architecture'], value)
        self.assertEqual(value['adapter'], value['device'])
    def test_worker_offscreen_render_compute_and_metadata(self):
        browser = self.app.open('203', self.url)
        value = self.run_workload(browser, worker=True)
        self.assert_raw_work(value)
        self.assert_masked(value)
    def test_readback_policy_is_strict_and_inherited(self):
        for policy in ({'blockWebGPUReadback':1}, {'blockWebGPUReadback':'true'},
                       {'blockWebGPUReadback':True,'unknown':False}):
            self.assertFalse(self.app.rpc('open', container='205', url=self.url, privacy=policy)['ok'])
        first = self.app.rpc('open', container='205', url=self.url, privacy={'blockWebGPUReadback':True})
        self.assertTrue(first['ok'], first)
        self.assertTrue(first['webgpuReadbackBlocked'])
        inherited = self.app.rpc('open', container='205', url=self.url, privacy={'canvas':True})
        self.assertTrue(inherited['ok'], inherited)
        self.assertTrue(inherited['webgpuReadbackBlocked'])
        conflict = self.app.rpc('open', container='205', url=self.url, privacy={'blockWebGPUReadback':False})
        self.assertFalse(conflict['ok'], conflict)
    def test_metadata_disable_and_readback_block_are_independent(self):
        opened=self.app.rpc('open',container='206',url=self.url,
                            privacy={'canvas':False,'blockWebGPUReadback':True})
        self.assertTrue(opened['ok'],opened)
        self.assertFalse(opened['canvasEnabled'])
        self.assertTrue(opened['webgpuReadbackBlocked'])
        value=self.run_workload(self.app.open('206',self.url))
        self.assertTrue(value['adapter']['vendor'] or value['adapter']['architecture'])
        self.assertEqual(value['adapter'],value['device'])
        self.assertEqual(value['computeError']['name'],'NotAllowedError')
        self.assertEqual(value['pixelsError']['name'],'NotAllowedError')
    def test_opt_in_blocks_read_maps_but_preserves_render_and_write_maps(self):
        result = self.app.rpc('open', container='204', url=self.url,
                              privacy={'canvas':True,'blockWebGPUReadback':True})
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['webgpuReadbackBlocked'])
        browser = self.app.open('204', self.url)
        for worker in (False, True):
            value = self.run_workload(browser, worker=worker)
            self.assert_masked(value)
            for name in ('compute', 'pixels'):
                self.assertNotIn(name, value)
                self.assertEqual(value[name+'Error']['name'], 'NotAllowedError')
                self.assertIn('privacy', value[name+'Error']['message'].lower())


if __name__ == '__main__':
    unittest.main()
