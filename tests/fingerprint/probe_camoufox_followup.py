"""Local/disposable-profile regressions for the audited Camoufox follow-ups.
No challenge or assessment sites are contacted. WebGL/audio probes adapted
from upstream Camoufox d01b8b9, retaining Cloakfox's own privacy policies.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from probe_daily_defaults import launch
from probe_webgl_tables import PROBE as DRAW

AUDIO = "async () => {\n  const ctx = new OfflineAudioContext(1, 44100, 44100);\n  const osc = ctx.createOscillator();\n  osc.frequency.value = 1000;\n  const raw = ctx.createAnalyser();\n  raw.smoothingTimeConstant = 0;\n  const smoothed = ctx.createAnalyser();\n  osc.connect(raw);\n  osc.connect(smoothed);\n  raw.connect(ctx.destination);\n  smoothed.connect(ctx.destination);\n  osc.start();\n  await ctx.startRendering();\n  // Firefox analyses on every read, so the reads below converge on the\n  // rendered audio's last block.\n  const out = {state: ctx.state};\n  const a = new Float32Array(raw.frequencyBinCount);\n  const b = new Float32Array(smoothed.frequencyBinCount);\n  for (let i = 0; i < 200; i++) smoothed.getFloatFrequencyData(b);\n  raw.getFloatFrequencyData(a);\n  let worst = 0, peak = -Infinity;\n  for (let i = 0; i < a.length; i++) {\n    peak = Math.max(peak, a[i]);\n    if (a[i] > -100) worst = Math.max(worst, Math.abs(a[i] - b[i]));\n  }\n  out.floatDb = worst;\n  out.peakDb = peak;\n  const ab = new Uint8Array(raw.frequencyBinCount);\n  const bb = new Uint8Array(smoothed.frequencyBinCount);\n  for (let i = 0; i < 200; i++) smoothed.getByteFrequencyData(bb);\n  raw.getByteFrequencyData(ab);\n  let worstByte = 0;\n  for (let i = 0; i < ab.length; i++) worstByte = Math.max(worstByte, Math.abs(ab[i] - bb[i]));\n  out.byteSteps = worstByte;\n  return out;\n}"
LIVE = "(kind) => {\n  const gl = document.createElement('canvas').getContext(kind);\n  if (!gl) return null;\n  gl.colorMask(false, true, false, true);\n  gl.viewport(1, 2, 3, 4);\n  gl.scissor(5, 6, 7, 8);\n  gl.clearColor(0.25, 0.5, 0.75, 1);\n  gl.blendColor(0.5, 0.25, 0.125, 0.5);\n  gl.depthRange(0.25, 0.75);\n  gl.depthMask(false);\n  gl.frontFace(gl.CW);\n  const read = p => {\n    const v = gl.getParameter(p);\n    return typeof v === 'object' ? Array.from(v) : [v];\n  };\n  return {\n    COLOR_WRITEMASK: read(gl.COLOR_WRITEMASK),\n    VIEWPORT: read(gl.VIEWPORT),\n    SCISSOR_BOX: read(gl.SCISSOR_BOX),\n    COLOR_CLEAR_VALUE: read(gl.COLOR_CLEAR_VALUE),\n    BLEND_COLOR: read(gl.BLEND_COLOR),\n    DEPTH_RANGE: read(gl.DEPTH_RANGE),\n    DEPTH_WRITEMASK: read(gl.DEPTH_WRITEMASK),\n    FRONT_FACE: read(gl.FRONT_FACE),\n  };\n}"
EXPECTED = {'COLOR_WRITEMASK': [False, True, False, True], 'VIEWPORT': [1, 2, 3, 4], 'SCISSOR_BOX': [5, 6, 7, 8], 'COLOR_CLEAR_VALUE': [0.25, 0.5, 0.75, 1], 'BLEND_COLOR': [0.5, 0.25, 0.125, 0.5], 'DEPTH_RANGE': [0.25, 0.75], 'DEPTH_WRITEMASK': [False], 'FRONT_FACE': [2304]}

def main():
    class Page(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers()
            self.wfile.write(b'<title>local native regression</title>')
        def log_message(self, *args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Page)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    failures = []
    def check(ok, label, got):
        print(('PASS' if ok else 'FAIL') + ': ' + label + ' ' + json.dumps(got))
        if not ok: failures.append(label)
    with tempfile.TemporaryDirectory(prefix='cloakfox-camoufox-followup-') as tmp:
        profile = Path(tmp) / 'profile'
        profile.mkdir()
        d = launch(profile, Path(tmp) / 'gecko.log')
        try:
            # The configured capacity must remain bounded by this backend. Measure
            # a native control in this disposable loopback-only profile, rather
            # than assuming every supported GPU can advertise eight samples.
            d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled', false)")
            d.set_context('content')
            d.get('http://127.0.0.1:' + str(server.server_port))
            native_samples = d.execute_script("const gl=document.createElement('canvas').getContext('webgl2'); return gl && gl.getParameter(gl.MAX_SAMPLES);")
            assert isinstance(native_samples, int) and native_samples > 0, native_samples
            print('CONTROL native WebGL2 MAX_SAMPLES', native_samples)
            d.set_context('chrome')
            d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled', true)")
            cfg = {'fingerprint:secret': 'A'*43 + '=', 'audio:seed': 12345, 'webGl:renderer': 'local-owner-renderer',
                   'webGl:vendor': 'local-owner-vendor'}
            params = {'3107': [True]*4, '2978': [0,0,300,150],
                      '3088': [0,0,300,150], '3106': [0,0,0,0],
                      '32773': [0,0,0,0], '2928': [0,1], '2930': True,
                      '2886': 2305, '3379': 4096, '36183': 8,
                      '34047': 16, '34921': None}
            for prefix in ['webGl', 'webGl2']:
                cfg[prefix + ':parameters'] = params
                cfg[prefix + ':parameters:blockIfNotDefined'] = True
                cfg[prefix + ':contextAttributes'] = {'alpha': True, 'depth': True,
                    'stencil': False, 'preserveDrawingBuffer': False}
            d.execute_script("Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0', JSON.stringify(arguments[0]));", cfg)
            d.set_context('content')
            d.get('http://127.0.0.1:' + str(server.server_port))
            for kind in ['webgl', 'webgl2']:
                got = d.execute_script('return (' + LIVE + ')(arguments[0])', kind)
                check(got == EXPECTED, kind + ' mutable render state', got)
                pair=d.execute_script('''const gl=document.createElement('canvas').getContext(arguments[0]);
                  const ext=gl.getExtension('WEBGL_debug_renderer_info');
                  return [gl.getParameter(gl.RENDERER),gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)];''',kind)
                check(pair==['local-owner-renderer']*2, kind+' renderer strings remain coherent',pair)
                got = d.execute_script("""
                  const gl = document.createElement('canvas').getContext(arguments[0],
                    {alpha:false, depth:false, stencil:true, preserveDrawingBuffer:true});
                  if (!gl) return null;
                  const attrs=gl.getContextAttributes();
                  gl.getError(); const versionOnly=gl.getParameter(36183), versionError=gl.getError();
                  const anisotropy=gl.getParameter(34047), extError=gl.getError();
                  return {attrs, versionOnly, versionError, anisotropy, extError,
                    fixed:gl.getParameter(gl.MAX_TEXTURE_SIZE), fallback:gl.getParameter(gl.MAX_VERTEX_ATTRIBS)};
                """, kind)
                check(got and got['attrs']['alpha'] is False and got['attrs']['depth'] is False
                      and got['attrs']['stencil'] is True and got['attrs']['preserveDrawingBuffer'] is True,
                      kind + ' actual context attributes', got)
                check(got and (kind == 'webgl2' and got['versionOnly']==min(8, native_samples) and got['versionError']==0
                      or kind == 'webgl' and got['versionOnly'] is None and got['versionError']==1280),
                      kind + ' version gates', got)
                check(got and got['anisotropy'] is None and got['extError']==1280,
                      kind + ' extension gates', got)
                check(got and got['fixed']==4096 and isinstance(got['fallback'],int) and got['fallback']>0,
                      kind + ' captured fixed limit and null fallback', got)
            draw=json.loads(d.execute_script(DRAW))
            pixel=draw.get('pixel',[])
            check(draw.get('linked') and draw.get('glerror')==0 and len(pixel)==4
                  and all(abs(a-b)<=1 for a,b in zip(pixel,[51,179,77,255])),
                  'shader compile/link/draw/readback still works',draw)
            got = d.execute_async_script('const done=arguments[arguments.length-1]; ('+AUDIO+')().then(done, e=>done({error:String(e)}));')
            check('error' not in got and got['peakDb']>-60 and got['floatDb']<=0.01 and got['byteSteps']<=1,
                  'frequency reads do not accumulate noise', got)
            enabled_peak=got['peakDb']
            d.set_context('chrome')
            d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled', false)")
            d.set_context('content')
            native=d.execute_async_script('const done=arguments[arguments.length-1]; ('+AUDIO+')().then(done, e=>done({error:String(e)}));')
            check(abs(native['peakDb']-enabled_peak)>0.001 and native['floatDb']<=0.01,
                  'audio noise present when enabled and disabled by master switch', native)
            d.set_context('chrome')
            d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled', true)")
            for index in [1,2]:
                d.set_context('content')
                previous=set(d.window_handles)
                d.set_context('chrome')
                owner='local-owner-' + str(index)
                info=d.execute_script("""
                  const {ContextualIdentityService}=ChromeUtils.importESModule(
                    'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
                  const id=ContextualIdentityService.create('Local owner test','fingerprint','blue').userContextId;
                  Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+id,JSON.stringify({
                    'webGl:renderer':arguments[0], 'webGl:vendor':'local-vendor'}));
                  const win=Services.wm.getMostRecentWindow('navigator:browser');
                  const tab=win.gBrowser.addTab(arguments[1],{userContextId:id,
                    triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                  win.gBrowser.selectedTab=tab;
                  return id;
                """, owner, 'http://127.0.0.1:' + str(server.server_port))
                d.set_context('content')
                new_handles=set(d.window_handles)-previous
                assert len(new_handles)==1,new_handles
                d.switch_to.window(new_handles.pop())
                d.get('http://127.0.0.1:' + str(server.server_port))
                owned=d.execute_script("""
                  const docs=[document,document.implementation.createHTMLDocument('detached'),
                    new DOMParser().parseFromString('<html></html>','text/html')];
                  const renderer=canvas=>{const gl=canvas.getContext('webgl');
                    const ext=gl&&gl.getExtension('WEBGL_debug_renderer_info');
                    return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null;};
                  return [...docs.map(doc=>renderer(doc.createElement('canvas'))),
                    renderer(new OffscreenCanvas(2,2))];
                """)
                check(owned==[owner]*4,'container '+str(info)+' attached/detached/offscreen ownership',owned)
                worker=d.execute_async_script("""
                  const done=arguments[arguments.length-1];
                  const script=`const gl=new OffscreenCanvas(2,2).getContext('webgl');
                    const ext=gl&&gl.getExtension('WEBGL_debug_renderer_info');
                    postMessage(ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null);`;
                  const url=URL.createObjectURL(new Blob([script],{type:'text/javascript'}));
                  const worker=new Worker(url);
                  worker.onmessage=e=>{worker.terminate();URL.revokeObjectURL(url);done(e.data);};
                  worker.onerror=e=>{worker.terminate();URL.revokeObjectURL(url);done({error:e.message});};
                """)
                check(worker==owner,'container '+str(info)+' worker owner',worker)
                d.set_context('chrome')
            resources=d.execute_async_script("""
              const done=arguments[arguments.length-1];
              Promise.all(['html','js','css'].map(ext=>fetch('chrome://global/content/crashes.'+ext)
                .then(r=>r.ok&&r.text()).then(text=>!!text).catch(()=>false))).then(done);
            """)
            check(resources==[True]*3,'packaged crash-page resources',resources)
            startup=d.execute_script("""
              const win=Services.wm.getMostRecentWindow('navigator:browser');
              return {ready:win.gBrowserInit.delayedStartupFinished,
                helper:typeof win.DevelopmentHelpers};
            """)
            check(startup=={'ready':True,'helper':'undefined'},'startup without development helper',startup)
        finally:
            d.quit()
    server.shutdown(); server.server_close()
    if failures: raise AssertionError('Regressions: ' + ', '.join(failures))

if __name__ == '__main__': main()
