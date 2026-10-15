#!/usr/bin/env python3
"""Disposable-profile WebGL rollout/semantics regression; requires rebuilt binary.

CLOAKFOX_BIN=... REPORT_DIR=... python probe_webgl_consistency.py
Does not require detector hash membership. Checks reported capacities against
master-off native values and bounded allocations at the advertised width.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE = r"""
return ['webgl','webgl2'].map(kind=>{
  const gl=document.createElement('canvas').getContext(kind);
  if(!gl)return {kind,missing:true};
  const extensions=gl.getSupportedExtensions()||[];
  const working=extensions.filter(name=>!!gl.getExtension(name));
  const caps={};
  for(const name of ['MAX_TEXTURE_SIZE','MAX_CUBE_MAP_TEXTURE_SIZE','MAX_RENDERBUFFER_SIZE',
    'MAX_VERTEX_ATTRIBS','MAX_TEXTURE_IMAGE_UNITS','MAX_VERTEX_TEXTURE_IMAGE_UNITS',
    'MAX_COMBINED_TEXTURE_IMAGE_UNITS','MAX_VERTEX_UNIFORM_VECTORS','MAX_FRAGMENT_UNIFORM_VECTORS',
    'MAX_VARYING_VECTORS','MAX_3D_TEXTURE_SIZE','MAX_ELEMENTS_VERTICES','MAX_ELEMENTS_INDICES',
    'MAX_ARRAY_TEXTURE_LAYERS','MAX_PROGRAM_TEXEL_OFFSET','MAX_VERTEX_UNIFORM_BLOCKS',
    'MAX_FRAGMENT_UNIFORM_BLOCKS','MAX_COMBINED_UNIFORM_BLOCKS','MAX_UNIFORM_BUFFER_BINDINGS',
    'MAX_UNIFORM_BLOCK_SIZE','MAX_COMBINED_VERTEX_UNIFORM_COMPONENTS','MAX_COMBINED_FRAGMENT_UNIFORM_COMPONENTS',
    'MAX_VERTEX_UNIFORM_COMPONENTS','MAX_FRAGMENT_UNIFORM_COMPONENTS','MAX_VARYING_COMPONENTS',
    'MAX_TRANSFORM_FEEDBACK_SEPARATE_COMPONENTS','MAX_TRANSFORM_FEEDBACK_INTERLEAVED_COMPONENTS',
    'MAX_TRANSFORM_FEEDBACK_SEPARATE_ATTRIBS','MAX_SAMPLES','MAX_ELEMENT_INDEX',
    'MAX_VERTEX_OUTPUT_COMPONENTS','MAX_FRAGMENT_INPUT_COMPONENTS','MAX_DRAW_BUFFERS','MAX_COLOR_ATTACHMENTS']) {
    if(typeof gl[name]==='number')caps[gl[name]]=gl.getParameter(gl[name]);
  }
  const vectors=gl.getParameter(gl.MAX_VERTEX_UNIFORM_VECTORS);
  const fragmentVectors=gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_VECTORS);
  const varying=gl.getParameter(gl.MAX_VARYING_VECTORS);
  const components=kind==='webgl2'?{
    vertex:gl.getParameter(gl.MAX_VERTEX_UNIFORM_COMPONENTS),
    fragment:gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_COMPONENTS),
    input:gl.getParameter(gl.MAX_FRAGMENT_INPUT_COMPONENTS)}:null;
  while(gl.getError()){}
  const invalid=kind==='webgl'?gl.getParameter(35658):null;
  const invalidError=kind==='webgl'?gl.getError():null;
  gl.clearColor(.25,.5,.75,1);
  const color=Array.from(gl.getParameter(gl.COLOR_CLEAR_VALUE));
  gl.activeTexture(gl.TEXTURE1);
  const activeTexture=gl.getParameter(gl.ACTIVE_TEXTURE);
  const maxTexture=gl.getParameter(gl.MAX_TEXTURE_SIZE);
  const cube=gl.getParameter(gl.MAX_CUBE_MAP_TEXTURE_SIZE);
  const renderbuffer=gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
  const viewportValue=gl.getParameter(gl.MAX_VIEWPORT_DIMS);
  // WebDriver executes in a separate realm; instanceof rejects native page
  // arrays even with masking disabled. Check the intrinsic cross-realm brand.
  const viewportIsTyped=ArrayBuffer.isView(viewportValue) &&
    Object.prototype.toString.call(viewportValue)==='[object Int32Array]';
  const viewport=Array.from(viewportValue);
  const pointRange=Array.from(gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE));
  const lineRange=Array.from(gl.getParameter(gl.ALIASED_LINE_WIDTH_RANGE));
  const samples=kind==='webgl2'?gl.getParameter(gl.MAX_SAMPLES):null;
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
  while(gl.getError()){}
  // Only one row (~64 KiB for a 16384-wide RGBA texture), never a huge square.
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,maxTexture,1,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
  const allocationError=gl.getError();gl.deleteTexture(texture);
  return {kind,caps,extensions,working,vectors,fragmentVectors,varying,components,
    invalid,invalidError,color,activeTexture,maxTexture,cube,renderbuffer,viewport,viewportIsTyped,pointRange,lineRange,samples,allocationError,
    unknown:gl.getExtension('CLOAKFOX_nonexistent_extension')};
});
"""


def legacy_tables(renderer):
    table = {'3379':16384,'34076':16384,'34024':16384,'3386':[32768,32768],
             '34921':16,'36347':4096,'36348':30,'36349':1024,'34930':16,
             '35660':16,'35661':32,'33902':[1,1],'33901':[1,1024],
             '36183':8,'7936':'Mozilla','7937':renderer}
    return {'webGl:parameters':table,
            'webGl2:parameters':{**table,'35375':24,'35380':256,'32883':2048,'35071':256}}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    report = Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-webgl-consistency-'))
    report.mkdir(parents=True, exist_ok=True)
    results = {'checks':[], 'measurements':{}}
    def check(value, label):
        results['checks'].append({'label':label,'pass':bool(value)})
        print(('PASS ' if value else 'FAIL ')+label, flush=True)
    with tempfile.TemporaryDirectory(prefix='cloakfox-webgl-consistency-profile-') as temporary:
        base=Path(temporary);profile=base/'profile';profile.mkdir()
        (base/'index.html').write_text('<!doctype html><title>WebGL consistency</title>')
        handler=functools.partial(QuietHandler,directory=str(base))
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}/index.html'
        (profile/'user.js').write_text('user_pref("cloakfox.enabled", true);\n')
        launches=0
        def launch():
            nonlocal launches
            launches+=1
            options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
            options.add_argument('-headless');options.add_argument('-purgecaches')
            options.add_argument('-profile');options.add_argument(str(profile))
            return webdriver.Firefox(options=options,service=Service(
                service_args=['--allow-system-access'],log_output=str(report/f'gecko-{launches}.log')))
        driver=launch()
        def chrome(script,*args):
            driver.set_context('chrome')
            try:return driver.execute_script(script,*args)
            finally:driver.set_context('content')
        def measure():
            driver.get(url)
            return driver.execute_script(PROBE)
        try:
            chrome('Services.prefs.setBoolPref("cloakfox.enabled",false);')
            native=measure();results['measurements']['native']=native
            renderer='ANGLE (NVIDIA, NVIDIA GeForce GTX 980 Direct3D11 vs_5_0 ps_5_0), or similar'
            saved=chrome(r"""
              const pref='cloakfox.s.cloak_cfg_0';
              const cfg=JSON.parse(Services.prefs.getStringPref(pref));
              Object.assign(cfg,arguments[0],{'webGl:renderer':arguments[1],
                'webGl:vendor':'Google Inc. (NVIDIA)','gpu:migrationSentinel':'retained'});
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));
              Services.prefs.setIntPref('cloakfox.container.0.override.canvas:seed',789);
              Services.prefs.setBoolPref('cloakfox.enabled',true);
              Services.prefs.savePrefFile(null);
              return {cfg,seeds:['math_seed','keyboard_seed','timing_seed'].map(k=>
                Services.prefs.getStringPref('cloakfox.container.0.'+k,''))};
            """,legacy_tables(renderer),renderer)
            driver.quit();driver=launch()
            migrated=chrome(r"""return {
              cfg:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0')),
              seeds:['math_seed','keyboard_seed','timing_seed'].map(k=>
                Services.prefs.getStringPref('cloakfox.container.0.'+k,''))};""")
            results['measurements']['migration']=migrated
            cfg=migrated['cfg'];gl1=cfg['webGl:parameters'];gl2=cfg['webGl2:parameters']
            check(gl1['36347']==1024 and gl2['35658']==4096 and gl2['35657']==4096 and gl2['37157']==120,
                  'saved legacy GPU tables migrate on browser restart')
            check(migrated['seeds']==saved['seeds'] and cfg.get('gpu:migrationSentinel')=='retained' and cfg.get('canvas:seed')==789,
                  'migration preserves secrets, unrelated fields, and explicit scalar override')
            masked=measure();results['measurements']['masked']=masked
            for item, baseline in zip(masked,native):
                kind=item['kind'];check(not item.get('missing'),kind+' available')
                if item.get('missing'):continue
                check(item['extensions']==item['working'] and len(item['extensions'])==len(set(item['extensions'])) and item['unknown'] is None,
                      kind+' enumeration agrees with getExtension')
                allowed=cfg['webGl2:supportedExtensions' if kind=='webgl2' else 'webGl:supportedExtensions']
                check(set(item['extensions'])<=set(allowed) and set(item['extensions'])<=set(baseline['extensions']),
                      kind+' extensions stay within persona and real backend support')
                check(item['color']==[.25,.5,.75,1] and item['activeTexture']==33985,
                      kind+' mutable GL state remains live')
                if kind=='webgl2':
                    c=item['components']
                    check(item['vectors']*4==c['vertex'] and item['fragmentVectors']*4==c['fragment'] and item['varying']*4==c['input'],
                          'WebGL2 uniform/varying component relationships agree')
                else:
                    check(item['invalid'] is None and item['invalidError']==1280,
                          'WebGL1 rejects WebGL2-only component enum')
                configured=cfg['webGl2:parameters' if kind=='webgl2' else 'webGl:parameters']
                check(all(value<=baseline['caps'][key] for key,value in item['caps'].items()
                          if key in configured),kind+' every configured integer upper-bound capacity stays within backend')
                check(item['allocationError']==0,
                      kind+' advertised maximum texture width allocates as a bounded single row')
                check(all(item[key]<=baseline[key] for key in ['maxTexture','cube','renderbuffer']) and
                      all(a<=b for a,b in zip(item['viewport'],baseline['viewport'])) and
                      (kind!='webgl2' or item['samples']<=baseline['samples']),
                      kind+' advertised texture/cube/renderbuffer/sample/viewport capacities stay within backend')
                check(all(item[key][0]>=baseline[key][0] and item[key][1]<=baseline[key][1]
                          for key in ['pointRange','lineRange']),kind+' point/line ranges stay within native range')
            # Exercise actual native getter integration with ceilings well above
            # this backend, then invalid scalar input. Never allocate at an
            # unchecked custom width: GetParameter must clamp before measure().
            chrome(r"""
              const pref='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(pref));
              for(const name of ['webGl:parameters','webGl2:parameters']) {
                const p=cfg[name];p['36347']=10000000;p['36349']=10000000;p['36348']=10000000;
                p['3386']=[2147483647,2147483647];
              }
              cfg['webGl2:parameters']['35658']=40000000;
              cfg['webGl2:parameters']['35657']=40000000;
              cfg['webGl2:parameters']['37157']=40000000;
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));
            """)
            oversized=measure();results['measurements']['oversizedConfig']=oversized
            check(all(a['vectors']==b['vectors'] and a['fragmentVectors']==b['fragmentVectors'] and
                      a['varying']==b['varying'] and a['viewport']==b['viewport']
                      for a,b in zip(oversized,native)),
                  'oversized paired uniform/varying and viewport config clamps to native ceilings')
            for invalid in [-1,1.5]:
                chrome(r"""
                  const pref='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(pref));
                  for(const name of ['webGl:parameters','webGl2:parameters'])cfg[name]['3379']=arguments[0];
                  Services.prefs.setStringPref(pref,JSON.stringify(cfg));
                """,invalid)
                fallback=measure();results['measurements']['invalidConfig'+str(invalid)]=fallback
                check(all(a['maxTexture']==b['maxTexture'] and a['allocationError']==0
                          for a,b in zip(fallback,native)),
                      'invalid capacity '+str(invalid)+' falls back to working native texture ceiling')
            for malformed in [16384,[100,-1],[100,1.5],['wrong',100]]:
                chrome(r"""
                  const pref='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(pref));
                  for(const name of ['webGl:parameters','webGl2:parameters']) {
                    cfg[name]['3386']=arguments[0];cfg[name]['33901']=arguments[0];cfg[name]['33902']=arguments[0];
                  }
                  Services.prefs.setStringPref(pref,JSON.stringify(cfg));
                """,malformed)
                fallback=measure();results['measurements']['malformedArray'+json.dumps(malformed)]=fallback
                # Fractional [100,1.5] is invalid as a viewport pair, and is
                # reversed as a float range; all fixtures must fall back whole.
                check(all(a['viewportIsTyped'] and a['viewport']==b['viewport'] and
                          a['pointRange']==b['pointRange'] and a['lineRange']==b['lineRange']
                          for a,b in zip(fallback,native)),
                      'malformed viewport/range '+json.dumps(malformed)+' retains native typed arrays')
            for vectors_only in [True,False]:
                chrome(r"""
                  const pref='cloakfox.s.cloak_cfg_0';const cfg=arguments[0];
                  for(const name of ['webGl:parameters','webGl2:parameters']) {
                    if(arguments[1])cfg[name]['36347']=13;else delete cfg[name]['36347'];
                  }
                  if(arguments[1])delete cfg['webGl2:parameters']['35658'];
                  else cfg['webGl2:parameters']['35658']=51;
                  Services.prefs.setStringPref(pref,JSON.stringify(cfg));
                """,cfg,vectors_only)
                partial=measure();results['measurements']['vectorsOnly' if vectors_only else 'componentsOnly']=partial
                wanted=13 if vectors_only else 12
                check(all(a['vectors']==wanted for a in partial) and partial[1]['components']['vertex']==4*wanted,
                      'one-sided '+('vector' if vectors_only else 'component')+' override keeps paired getters coherent')
            chrome('Services.prefs.setStringPref("cloakfox.s.cloak_cfg_0",JSON.stringify(arguments[0]));',cfg)
            # Add an impossible advertised value to distinguish native master-off
            # getters even when a host happens to equal the repaired profile.
            chrome(r"""
              const pref='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(pref));
              cfg['webGl:parameters']['36347']=13;cfg['webGl2:parameters']['36347']=13;
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));
              Services.prefs.setBoolPref('cloakfox.enabled',false);
            """)
            unmasked=measure();results['measurements']['masterOff']=unmasked
            check(all(a.get('vectors')==b.get('vectors') and a.get('vectors')!=13 and a.get('extensions')==b.get('extensions')
                      for a,b in zip(unmasked,native)), 'master-off retains native GPU getters and extensions')
        finally:
            driver.quit();server.shutdown();server.server_close()
            (report/'result.json').write_text(json.dumps(results,indent=2)+'\n')
            print('Report: '+str(report),flush=True)
    return 0 if all(c['pass'] for c in results['checks']) else 1


if __name__=='__main__':
    raise SystemExit(main())
