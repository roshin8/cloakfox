"""Manual external-site audit of /Applications/Cloakfox.app in disposable profiles.

Preserves raw website reports and reload checks; an incomplete or blocked page is
not a passing verdict. Run explicitly, outside the default local regression suite.
"""
from pathlib import Path
import os,sys,json,time,tempfile,hashlib,traceback
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
R=Path(__file__).resolve().parents[2];OUT=Path(os.environ.get('REPORT_DIR',str(R/'tests/fingerprint/reports/installed-sites-audit')));OUT.mkdir(exist_ok=True,parents=True)
SITES=[('browserleaks-js','https://browserleaks.com/javascript'),('browserleaks-canvas','https://browserleaks.com/canvas'),('browserleaks-webgl','https://browserleaks.com/webgl'),('browserleaks-fonts','https://browserleaks.com/fonts'),('browserleaks-webrtc','https://browserleaks.com/webrtc'),('browserleaks-hints','https://browserleaks.com/client-hints'),('browserleaks-tls','https://browserleaks.com/tls'),('creepjs','https://abrahamjuliot.github.io/creepjs/'),('fingerprintjs','https://fingerprint.com/demo/'),('tls-peet','https://tls.peet.ws/api/all')]
# Marionette has a separate Intl realm. Treat website-rendered and worker timezone
# values as authoritative; sandbox timezone is diagnostic metadata only.
if os.environ.get('AUDIT_SITES'):
 SITES=[x for x in SITES if x[0] in os.environ['AUDIT_SITES'].split(',')]

COLLECT=r'''const done=arguments[arguments.length-1]; (async()=>{
const out={}, read=(key,fn)=>{try{out[key]=fn()}catch(e){out[key]={error:e.name}}};
read('identity',()=>({ua:navigator.userAgent,appVersion:navigator.appVersion,platform:navigator.platform,oscpu:navigator.oscpu,cores:navigator.hardwareConcurrency,memory:navigator.deviceMemory,touch:navigator.maxTouchPoints,languages:navigator.languages,language:navigator.language,webdriver:navigator.webdriver,automationRealmTimezone:Intl.DateTimeFormat().resolvedOptions().timeZone,automationRealmOffset:new Date().getTimezoneOffset(),vendor:navigator.vendor}));
read('screen',()=>({width:screen.width,height:screen.height,availWidth:screen.availWidth,availHeight:screen.availHeight,colorDepth:screen.colorDepth,pixelDepth:screen.pixelDepth,dpr:devicePixelRatio,inner:[innerWidth,innerHeight],outer:[outerWidth,outerHeight],orientation:screen.orientation.type}));
read('media',()=>Object.fromEntries(['(color-gamut: p3)','(color-gamut: srgb)','(dynamic-range: high)','(prefers-reduced-motion: reduce)','(forced-colors: active)','(color: 8)','(color: 10)','(hover: hover)','(pointer: fine)'].map(q=>[q,matchMedia(q).matches])));
read('css',()=>{const style=document.createElement('style'),div=document.createElement('div');div.id='cfx-audit-css';div.style.cssText='position:fixed;left:-999px';style.textContent='#cfx-audit-css{--p3:no;--forced:no;--reduce:no;--c8:no;--c10:no}@media(color-gamut:p3){#cfx-audit-css{--p3:yes}}@media(forced-colors:active){#cfx-audit-css{--forced:yes}}@media(prefers-reduced-motion:reduce){#cfx-audit-css{--reduce:yes}}@media(color:8){#cfx-audit-css{--c8:yes}}@media(color:10){#cfx-audit-css{--c10:yes}}';document.documentElement.append(style,div);const cs=getComputedStyle(div),r=Object.fromEntries(['p3','forced','reduce','c8','c10'].map(k=>[k,cs.getPropertyValue('--'+k).trim()]));div.remove();style.remove();return r});
const hash=async data=>{const bytes=typeof data==='string'?new TextEncoder().encode(data):data;return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('')};
try{const c=document.createElement('canvas');c.width=240;c.height=70;const x=c.getContext('2d');x.fillStyle='#f3a';x.fillRect(1,1,238,68);x.fillStyle='#123';x.font='17px Arial';x.fillText('Fingerprint privacy 🌍 Ω ffi',4,31);out.canvas=await hash(c.toDataURL());}catch(e){out.canvas={error:e.name}}
read('webgl',()=>{const g=document.createElement('canvas').getContext('webgl2')||document.createElement('canvas').getContext('webgl');if(!g)return null;const e=g.getExtension('WEBGL_debug_renderer_info');return {vendor:e?g.getParameter(e.UNMASKED_VENDOR_WEBGL):g.getParameter(g.VENDOR),renderer:e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),version:g.getParameter(g.VERSION),shading:g.getParameter(g.SHADING_LANGUAGE_VERSION),extensions:g.getSupportedExtensions()}});
try {if(navigator.userAgentData)out.hints=await navigator.userAgentData.getHighEntropyValues(['architecture','bitness','model','platformVersion','uaFullVersion','fullVersionList']);else out.hints=null;}catch(e){out.hints={error:e.name}}
try{out.devices=await navigator.mediaDevices.enumerateDevices();out.devices=out.devices.map(d=>({kind:d.kind,label:d.label,id:d.deviceId,group:d.groupId}));}catch(e){out.devices={error:e.name}}
read('apis',()=>({gpu:!!navigator.gpu,VideoEncoder:typeof VideoEncoder,VideoDecoder:typeof VideoDecoder,oscpu:'oscpu'in navigator,mozInnerScreenX:'mozInnerScreenX'in window,chrome:'chrome'in window,InstallTrigger:typeof InstallTrigger,audioWorklet:typeof AudioWorkletNode,IdleDetector:typeof IdleDetector,fontsQuery:typeof queryLocalFonts}));
try{out.codecs=[];if(typeof VideoEncoder==='function')for(const codec of ['av01.0.08M.08','vp09.00.10.08','avc1.42001e'])for(const hardwareAcceleration of ['prefer-hardware','prefer-software']){const config={codec,width:640,height:480,hardwareAcceleration};try{const r=await VideoEncoder.isConfigSupported(config);out.codecs.push({...config,supported:r.supported})}catch(e){out.codecs.push({...config,error:e.name})}}}catch(e){out.codecsError=e.name}
try{out.worker=await new Promise(resolve=>{const url=URL.createObjectURL(new Blob([`onmessage=async()=>{let h=null;try{h=navigator.userAgentData?await navigator.userAgentData.getHighEntropyValues(['architecture','bitness','platformVersion']):null}catch{};postMessage({ua:navigator.userAgent,platform:navigator.platform,cores:navigator.hardwareConcurrency,languages:navigator.languages,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,hints:h,gpu:!!navigator.gpu})}`],{type:'text/javascript'}));const w=new Worker(url),t=setTimeout(()=>{w.terminate();URL.revokeObjectURL(url);resolve({timeout:true})},4000);w.onmessage=e=>{clearTimeout(t);w.terminate();URL.revokeObjectURL(url);resolve(e.data)};w.onerror=()=>{clearTimeout(t);w.terminate();URL.revokeObjectURL(url);resolve({error:'worker error'})};w.postMessage(1)});}catch(e){out.worker={error:e.name}}
try{const c=new OfflineAudioContext(1,44100,44100),o=c.createOscillator(),compress=c.createDynamicsCompressor();o.type='triangle';o.frequency.value=10000;o.connect(compress);compress.connect(c.destination);o.start();const b=await c.startRendering();out.audio=await hash(new Uint8Array(b.getChannelData(0).buffer));}catch(e){out.audio={error:e.name}}
done(out)})().catch(e=>done({error:String(e)}));'''

def main():
 with tempfile.TemporaryDirectory(prefix='cloakfox-fingerprint-audit-') as tmp:
  opts=Options();opts.binary_location='/Applications/Cloakfox.app/Contents/MacOS/cloakfox';opts.add_argument('-profile');opts.add_argument(tmp);opts.add_argument('-no-remote');opts.set_preference('remote.prefs.recommended',False);opts.set_preference('devtools.jsonview.enabled',False)
  d=webdriver.Firefox(options=opts,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(OUT/'geckodriver.log')));d.set_page_load_timeout(35);d.set_script_timeout(25)
  results=[]
  def chrome(js,*args):
   d.set_context('chrome')
   try:return d.execute_script(js,*args)
   finally:d.set_context('content')
  def visit(label,slug,url,repeat=False):
   dest=OUT/(label+'-'+slug);dest.mkdir(exist_ok=True);start=time.monotonic();result={'case':label,'site':slug,'url':url}
   print('RUN',label,slug,flush=True)
   try:
    try:d.get(url)
    except TimeoutException:result['pageLoadTimeout']=True
    WebDriverWait(d,10).until(lambda d:d.execute_script('return !!document.body'))
    if slug=='creepjs':
     try:WebDriverWait(d,40).until(lambda d:d.execute_script("const t=document.body.innerText;return t.includes('FP ID:')&&!t.match(/FP ID:\\s*Computing/)&&t.length>3000"))
     except TimeoutException:result['computeTimeout']=True
    else:
     # Wait for ordinary asynchronous result tables or a ready page; capture late redraw on revisit if needed.
     try:WebDriverWait(d,8).until(lambda d:d.execute_script('return document.readyState==="complete"&&document.body.innerText.length>400'))
     except TimeoutException:pass
    if slug in ['browserleaks-fonts','browserleaks-tls','fingerprintjs']:
     try:
      if slug=='browserleaks-fonts':WebDriverWait(d,45).until(lambda d:d.execute_script("return /\\b[a-f0-9]{32}\\b/i.test(document.body.innerText)&&document.body.innerText.includes('unique metrics found')"))
      elif slug=='browserleaks-tls':WebDriverWait(d,35).until(lambda d:d.execute_script("return /\\b[a-f0-9]{32}\\b/i.test(document.body.innerText)"))
      else:WebDriverWait(d,40).until(lambda d:'Loading visitor ID' not in d.find_element('tag name','body').text and 'Loading metric value' not in d.find_element('tag name','body').text)
     except TimeoutException:result['resultTimeout']=True
    body=d.execute_script('return document.body.innerText');(dest/'body.txt').write_text(body);result.update(title=d.title,finalURL=d.current_url,bodyLength=len(body))
    result['blocked']=any(x in body.lower() for x in ['verify you are human','checking your browser','just a moment','access denied','captcha']) and len(body)<5000
    signals=d.execute_async_script(COLLECT);(dest/'signals.json').write_text(json.dumps(signals,indent=2));result['signals']=signals
    try:d.save_full_page_screenshot(str(dest/'page.png'))
    except Exception:pass
    if repeat:
     before=signals;d.refresh();WebDriverWait(d,10).until(lambda d:d.execute_script('return !!document.body'));after=d.execute_async_script(COLLECT);(dest/'reload.json').write_text(json.dumps(after,indent=2));result['reloadStable']={k:before.get(k)==after.get(k) for k in ['identity','canvas','audio','webgl','hints','worker']}
   except Exception as e:result['error']=str(e)[:400];(dest/'error.txt').write_text(traceback.format_exc())
   result['seconds']=round(time.monotonic()-start,1);results.append(result);(OUT/'results.json').write_text(json.dumps(results,indent=2));print('DONE',label,slug,'blocked='+str(result.get('blocked',False)),'error='+str(result.get('error','')),flush=True)
  try:
   metadata=chrome("return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,enabled:Services.prefs.getBoolPref('cloakfox.enabled'),os:Services.appinfo.OS,config:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'))};");metadata['config']={k:v for k,v in metadata['config'].items() if not any(s in k.lower() for s in ['seed','secret'])};(OUT/'installed.json').write_text(json.dumps(metadata,indent=2))
   for slug,url in SITES:visit('default',slug,url,repeat=slug in ['browserleaks-js','browserleaks-canvas'])
   # A complete generated Windows persona, retaining separately derived secret/seed material.
   ids=chrome("const c=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return [c.create('Audit Windows Firefox','fingerprint','blue').userContextId,c.create('Audit Windows Chrome','fingerprint','green').userContextId]")
   for index,id in enumerate(ids):
    config=chrome("const id=arguments[0],p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id));const seed=Services.prefs.getStringPref('cloakfox.container.'+id+'.math_seed');Object.assign(cfg,p.fillPersonaKeys(seed,id,{os:'windows',hardware:'nvidia'}));if(arguments[1]){const ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36';cfg['navigator.userAgent']=ua;cfg['headers.User-Agent']=ua;cfg['navigator.appVersion']=ua.slice(8)}Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+id,JSON.stringify(cfg));return cfg",id,index==1);(OUT/('windows-'+str(index)+'-config.json')).write_text(json.dumps({k:v for k,v in config.items() if not any(s in k.lower() for s in ['seed','secret'])},indent=2))
    prior_handles=set(d.window_handles)
    chrome("const w=Services.wm.getMostRecentWindow('navigator:browser');w.gBrowser.selectedTab=w.gBrowser.addTab('about:blank',{userContextId:arguments[0],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});",id);d.switch_to.window(next(h for h in d.window_handles if h not in prior_handles));label='windows-chrome' if index else 'windows-firefox'
    for slug,url in SITES:
     if slug in ['browserleaks-js','browserleaks-webgl','browserleaks-hints','creepjs','tls-peet']:visit(label,slug,url,repeat=slug=='browserleaks-js')
   chrome("Services.prefs.setBoolPref('cloakfox.enabled',false)");visit('native-control','browserleaks-js','https://browserleaks.com/javascript')
  finally:d.quit()
 print('COMPLETE',len(results),'site visits',flush=True)
if __name__=='__main__':main()
