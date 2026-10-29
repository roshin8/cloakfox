#!/usr/bin/env python3
"""Unmodified pinned CreepJS/FingerprintJS across the complete observed GPU catalog.

One disposable headless Firefox159 profile; loopback fixtures only. No installed
application, personal profile, or upstream library is modified. GPU warnings are
retained and fail checks rather than being normalized away.
"""
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from library_audit_common import ROOT, CREEP, Handler, stable_hash, verify_fixtures, observed_gpu_recognized
from probe_container_workflows import chrome, open_site
from probe_container_gpu_profiles import GPU

CONFIGURE = r'''
const owner=arguments[0],ref=arguments[1],key='cloakfox.s.cloak_cfg_'+owner;
const old=JSON.parse(Services.prefs.getStringPref(key));
const personas=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
const seed=Services.prefs.getStringPref('cloakfox.container.'+owner+'.math_seed');
const os={win:'windows',mac:'macos',lin:'linux'}[ref.os];if(!os)throw Error('Unknown catalog OS');
const next=personas.fillPersonaKeys(seed,owner,{os,hardware:ref.family});
for(const [k,v] of Object.entries(old))if(/seed|secret/i.test(k))next[k]=v;
Object.assign(next,{'webGl:renderer':ref.renderer,'webGl:vendor':ref.vendor,
 'rendering:gpu_reference':true,'rendering:gpu_observed':true,
 'geometry:canonical':true,'navigator:webgpu:disabled':false});
const result=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').applyGraphicsPolicy(next,owner);
Services.prefs.setStringPref(key,JSON.stringify(result));return result;
'''
LIBRARIES = [
    ('fingerprintjs','/fp.html','return !!window.libraryResult','return window.libraryResult'),
    ('creepjs','/index.html','return !!window.Fingerprint&&!!window.Creep',
     'return {fingerprint:window.Fingerprint,creep:window.Creep}'),
]
NATIVE_GPU_IDENTITY = r'''return ['webgl','webgl2'].map(kind=>{const gl=document.createElement('canvas').getContext(kind);if(!gl)return {kind,missing:true};const ext=gl.getExtension('WEBGL_debug_renderer_info');const result={kind,identity:ext?[gl.getParameter(ext.UNMASKED_VENDOR_WEBGL),gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)]:null};gl.getExtension('WEBGL_lose_context')?.loseContext();return result;});'''

CAP_KEYS = ['MAX_TEXTURE_SIZE','MAX_VIEWPORT_DIMS','MAX_VERTEX_ATTRIBS',
            'MAX_VERTEX_UNIFORM_VECTORS','MAX_FRAGMENT_UNIFORM_VECTORS',
            'MAX_VARYING_VECTORS','MAX_TEXTURE_IMAGE_UNITS',
            'MAX_COMBINED_TEXTURE_IMAGE_UNITS','MAX_RENDERBUFFER_SIZE',
            'MAX_ELEMENT_INDEX','MAX_TEXTURE_LOD_BIAS','MAX_SAMPLES']


def canvas_evidence(library, value):
    """Hash only collected image evidence; absent/sentinel values are failures."""
    if library == 'creepjs':
        fingerprint = value.get('fingerprint')
        canvas = fingerprint.get('canvas2d') if isinstance(fingerprint, dict) else None
        images = {'dataURI':canvas.get('dataURI') if isinstance(canvas, dict) else None}
    elif library == 'fingerprintjs':
        canvas = value.get('rawCanvas', {})
        images = {key:canvas.get(key) for key in ['geometry', 'text']} if isinstance(canvas, dict) else {}
    else:
        raise ValueError('Unknown library: '+library)
    valid = bool(images) and all(isinstance(image, str) and image.startswith('data:image/')
                                 and ',' in image and bool(image.split(',', 1)[1].strip())
                                 for image in images.values())
    return {'collected':valid,'sha256':stable_hash(images) if valid else None}


def expected_caps(profile):
    # CreepJS merges WebGL2 over WebGL1, except its explicit WebGL1 viewport.
    values = {entry['name']:entry['value'] for kind in ['webgl','webgl2']
              for entry in profile['contexts'][kind]['parameters'].values()}
    values['MAX_VIEWPORT_DIMS'] = profile['contexts']['webgl']['parameters']['3386']['value']
    return {key:values[key] for key in CAP_KEYS}


def summarize_library(library, value, profile, config, expected_capabilities, label, check):
    image_evidence=canvas_evidence(library,value)
    check(image_evidence['collected'],label+'/'+library+': actual nonempty canvas image evidence collected')
    if library=='creepjs':
        fingerprint=value.get('fingerprint',{})
        canvas=fingerprint.get('canvasWebgl',{})
        params=canvas.get('parameters',{})
        caps={key:params.get(key) for key in CAP_KEYS}
        warnings=[w for w in fingerprint.get('trash',{}).get('trashBin',[])
                  if w.get('value') in ['suspicious gpu','suspicious capabilities']]
        summary={'identity':[params.get('UNMASKED_VENDOR_WEBGL'),params.get('UNMASKED_RENDERER_WEBGL')],
                 'capabilities':caps,'gpuWarnings':warnings,'webglHash':canvas.get('$hash'),
                 'canvasSHA256':image_evidence['sha256'],'canvasCollected':image_evidence['collected']}
        check(summary['identity']==[profile['vendor'],profile['renderer']],label+': CreepJS collected exact GPU identity',summary['identity'])
        check(caps==expected_capabilities,label+': CreepJS collected complete numeric capability vector',caps)
        check(observed_gpu_recognized(fingerprint),label+': unmodified CreepJS recognizes GPU/capabilities',warnings)
        platform=fingerprint.get('navigator',{}).get('platform')
        check(platform==config['navigator.platform'] and fingerprint.get('workerScope',{}).get('platform')==platform,label+': CreepJS window/worker own persona platform',platform)
    else:
        components=value.get('components',{})
        basics=components.get('webGlBasics',{}).get('value',{})
        extensions=components.get('webGlExtensions',{}).get('value',{})
        params=extensions.get('parameters',[]) if isinstance(extensions,dict) else []
        expected=profile['contexts']['webgl']['parameters']
        wanted=[f"{expected[key]['name']}={key}={','.join(map(str,expected[key]['value'])) if isinstance(expected[key]['value'],list) else expected[key]['value']}" for key in ['3379','3386','34921','36347','36349','35661']]
        summary={'identity':[basics.get('vendorUnmasked'),basics.get('rendererUnmasked')],
                 'capabilities':params,'canvasSHA256':image_evidence['sha256'],'canvasCollected':image_evidence['collected']}
        # Pinned FPJS 5.3.0 shouldAvoidDebugRendererInfo() returns isGecko()
        # to avoid Firefox console warnings; its unmasked fields are empty.
        check(summary['identity']==['',''] and all(isinstance(basics.get(key),str) and basics[key] for key in ['vendor','renderer','version','shadingLanguageVersion']),label+': FingerprintJS collects masked WebGL basics and intentionally omits unmasked GPU on Gecko',basics)
        summary['identityCoverage']='Unmasked GPU intentionally omitted by pinned FingerprintJS on Gecko; separate direct native query below.'
        check(all(entry in params for entry in wanted),label+': FingerprintJS collected numeric capability vector',{'required':wanted})
    return summary


def main():
    fixtures = verify_fixtures()
    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    out = Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-full-gpu-libraries-159')).resolve()
    out.mkdir(parents=True,exist_ok=True)
    catalog = json.loads((ROOT/'additions/cloakcfg/gpu-reference-executable.json').read_text())
    profiles = catalog['observedProfiles']
    assert profiles and len({p['code'] for p in profiles}) == len(profiles)
    report = {'binary':str(binary),'fixtures':fixtures,'profileCount':len(profiles),
              'sourceArchiveSha256':catalog['sourceArchiveSha256'],
              'xulSHA256':hashlib.sha256((binary.parent/'XUL').read_bytes()).hexdigest(),
              'scope':'One sample per library and observed identity; first identity repeated and exercised in a second independent owner. GPU-specific checks only; unrelated upstream warnings retained in raw evidence.',
              'checks':[],'cases':[],'inconclusive':[]}
    def save():
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def check(ok,name,detail=None):
        row={'pass':bool(ok),'name':name}
        if detail is not None:row['detail']=detail
        report['checks'].append(row)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(CREEP/'docs')))
    server.requests=[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-full-gpu-libraries-159-') as tmp:
            options=Options();options.binary_location=str(binary)
            for arg in ['-headless','-profile',tmp,'-purgecaches']:options.add_argument(arg)
            for key,value in [('cloakfox.enabled',True),('cloakfox.experimental.canvas_pipeline',True),
                              ('dom.webgpu.enabled',True),('layers.gpu-process.allow-headless',True)]:
                options.set_preference(key,value)
            driver=webdriver.Firefox(options=options,service=Service(
                os.environ.get('GECKODRIVER','/opt/homebrew/bin/geckodriver'),
                service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
            try:
                driver.set_script_timeout(90)
                report['runtime']=chrome(driver,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,os:Services.appinfo.OS};')
                check(report['runtime']['version'].startswith('159.'),'actual Firefox159 runtime')
                owners=chrome(driver,"Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',true);return Array.from({length:arguments[0]},(_,i)=>cis.create('Full GPU libraries '+i,'fingerprint','blue').userContextId);",len(profiles)+1)
                driver.set_context('content');base=driver.current_window_handle
                definitions=[(p,owners[i],2 if i==0 else 1) for i,p in enumerate(profiles)]
                definitions.append((profiles[0],owners[-1],1))
                for profile,owner,repeats in definitions:
                    label=f"{profile['code']}:{profile['renderer']}/{owner}"
                    config=chrome(driver,CONFIGURE,owner,profile)
                    descriptor=config.get('rendering:gpu_profile',{})
                    check(descriptor.get('owner')==owner and descriptor.get('catalog')==[profile['code']] and descriptor.get('version')==4,label+': exact owned observed descriptor')
                    case={'code':profile['code'],'renderer':profile['renderer'],'vendor':profile['vendor'],
                          'os':profile['os'],'family':profile['family'],'owner':owner,'descriptor':descriptor,
                          'sourceRecords':profile.get('sourceRecords',[profile['record']]),
                          'persona':{key:config.get(key) for key in ['navigator.platform','navigator.oscpu','navigator.userAgent']},
                          'secretSHA256':hashlib.sha256(config['fingerprint:secret'].encode()).hexdigest(),
                          'libraries':{},'rawFiles':{},'expectedCapabilities':expected_caps(profile)}
                    report['cases'].append(case)
                    _,actual=open_site(driver,f'http://127.0.0.1:{server.server_port}/fp.html',owner)
                    check(actual==owner,label+': actual tab owner')
                    for library,path,ready,result in LIBRARIES:
                        samples=[];case['libraries'][library]=samples;case['rawFiles'][library]=[]
                        for repeat in range(repeats):
                            print(f'RUN {label}/{library}/{repeat}',flush=True)
                            driver.set_context('content');driver.get(f'http://127.0.0.1:{server.server_port}{path}')
                            WebDriverWait(driver,90).until(lambda d:d.execute_script(ready))
                            value=driver.execute_script(result)
                            filename=f'{profile["code"]}-{owner}-{library}-{repeat}.json'
                            (out/filename).write_text(json.dumps(value,indent=2)+'\n')
                            case['rawFiles'][library].append(filename)
                            check(isinstance(value,dict) and 'error' not in value,label+'/'+library+': upstream collection completed')
                            summary=summarize_library(library,value,profile,config,case['expectedCapabilities'],label,check)
                            native_identity=driver.execute_script(NATIVE_GPU_IDENTITY)
                            summary['directNativeIdentity']=native_identity
                            check(isinstance(native_identity,list) and len(native_identity)==2 and all(row.get('identity')==[profile['vendor'],profile['renderer']] for row in native_identity),label+'/'+library+': separate direct native WebGL1/2 GPU identity',native_identity)
                            samples.append(summary);save()
                        if repeats>1:
                            check(all(sample['canvasCollected'] for sample in samples) and all(sample==samples[0] for sample in samples),label+'/'+library+': GPU and canonical canvas repeat exactly')
                    driver.set_context('content');case['webgpu']=driver.execute_async_script(GPU)
                    gpu=case['webgpu']
                    if gpu.get('available'):
                        check(gpu['aboveRejected'] and gpu['allocationRejected'] and gpu['maxBufferSize']==268435456 and gpu['maxStorageBufferBindingSize']==134217728,label+': actual protected WebGPU bounds')
                    elif gpu.get('error'):check(False,label+': WebGPU collection error',gpu)
                    else:report['inconclusive'].append({'name':label+': WebGPU','result':gpu})
                    save();driver.set_context('content');driver.close();driver.switch_to.window(base)
                first,second=report['cases'][0],report['cases'][-1]
                check(first['owner']!=second['owner'] and first['secretSHA256']!=second['secretSHA256'],'same GPU retains distinct owners and independent private secrets')
                report['canonicalCrossOwnerPixels']={library:{'collected':first['libraries'][library][0]['canvasCollected'] and second['libraries'][library][0]['canvasCollected'],'equal':(first['libraries'][library][0]['canvasSHA256']==second['libraries'][library][0]['canvasSHA256']) if first['libraries'][library][0]['canvasCollected'] and second['libraries'][library][0]['canvasCollected'] else None,'policy':'Equal canonical authored pixels are allowed; ownership and secrets are checked independently.'} for library,_,_,_ in LIBRARIES}
                check({case['code'] for case in report['cases']}=={p['code'] for p in profiles},'all observed catalog identities collected by both unmodified libraries')
            finally:driver.quit()
    except Exception as error:
        report['exception']={'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        server.shutdown();server.server_close();report['requests']=server.requests;save()
    if any(not row['pass'] for row in report['checks']):return 1
    return 2 if report['inconclusive'] else 0


if __name__=='__main__':raise SystemExit(main())
