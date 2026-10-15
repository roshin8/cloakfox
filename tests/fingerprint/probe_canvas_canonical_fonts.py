"""Installed canonical font corpus: custom bytes/URL, bidi, script fallback, emoji.

Runs the same inputs in HTMLCanvasElement, OffscreenCanvas and worker contexts.
This is a runtime corpus, not a claim of complete SVG/font-format coverage.
"""
import base64
import json
import os
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''const done=arguments[arguments.length-1], encoded=arguments[0];
async function sample(makeCanvas, encoded) {
 const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
 const face=await new FontFace('CanonicalBuffer',bytes).load();
 const url=URL.createObjectURL(new Blob([bytes],{type:'font/ttf'}));
 const urlFace=await new FontFace('CanonicalURL',`url(${url})`).load();
 const fonts=globalThis.fonts||document.fonts;fonts.add(face);fonts.add(urlFace);
 const corpus=[['Latin','AV a\u0301',false],['Arabic','سلام',true],
  ['Hebrew','שלום',true],['Bidi','abc שלום 123 سلام',false],
  ['Indic','कर्म বাংলা',false],['Thai','ภาษาไทย',false],['CJK','中文',false],
  ['Emoji','😀 👨‍👩‍👧‍👦 🇺🇸',false],['Mixed','A😀B',false],['Bold','Abc مرحبا',false,'bold 32px sans-serif'],
  ['Oblique','Abc',false,'italic 32px sans-serif'],
  ['SmallCaps','aBc',false,'32px sans-serif','small-caps'],
  ['Spaced','A V שלום',false,'32px sans-serif','normal',true]];
 const result={};
 for(const [name,text,rtl,font,caps,spaced] of corpus){
  const c=makeCanvas();c.width=400;c.height=100;const x=c.getContext('2d');
  x.font=font||'32px sans-serif';x.fontVariantCaps=caps||'normal';if(spaced){x.letterSpacing='3px';x.wordSpacing='5px';x.fontKerning='none';}x.direction=rtl?'rtl':'ltr';x.fillStyle='#303030';
  const metrics=x.measureText(text);x.fillText(text,rtl?390:5,65);
  const data=x.getImageData(0,0,c.width,c.height).data;
  let ink=0,color=0;for(let i=0;i<data.length;i+=4)if(data[i+3]>128){ink++;if(Math.max(data[i],data[i+1],data[i+2])-Math.min(data[i],data[i+1],data[i+2])>30)color++;}
  result[name]={width:metrics.width,left:metrics.actualBoundingBoxLeft,right:metrics.actualBoundingBoxRight,ink,color,bytes:Array.from(data)};
 }
 const c=makeCanvas(),x=c.getContext('2d');
 x.font='40px CanonicalBuffer';const bufferWidth=x.measureText('A').width;
 x.font='40px CanonicalURL';const urlWidth=x.measureText('A').width;
 x.letterSpacing='3px';const spaced=x.measureText('A').width;
 result.custom={bufferWidth,urlWidth,spaced};
 URL.revokeObjectURL(url);return result;
}
async function sampleSVGs(encoded){
 const variants=[['Latin','AV a\u0301',false],['Bidi','abc שלום 123 سلام',false],
  ['Emoji','😀 👨‍👩‍👧‍👦 🇺🇸',false],['Custom','A',false]];
 const results={};
 const equal=(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i]);
 const pixels=c=>Array.from(c.getContext('2d').getImageData(0,0,400,100).data);
 for(const [name,text,rtl] of variants){
  const family=name==='Custom'?'CanonicalSVG':'sans-serif';
  const face=name==='Custom'?`<style>@font-face{font-family:CanonicalSVG;src:url(data:font/ttf;base64,${encoded})}</style>`:'';
  const source=`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">${face}<text x="5" y="65" font-family="${family}" font-size="32" fill="#303030">${text}</text></svg>`;
  const blob=new Blob([source],{type:'image/svg+xml'});
  const reference=document.createElement('canvas');reference.width=400;reference.height=100;
  const x=reference.getContext('2d');x.font=`32px ${name==='Custom'?'CanonicalBuffer':'sans-serif'}`;x.fillStyle='#303030';x.fillText(text,5,65);
  const expected=pixels(reference), result={};
  for(const kind of ['data','blob']){
   const url=kind==='data'?'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source):URL.createObjectURL(blob);
   try{
    const image=new Image();await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('SVG image load failed'));image.src=url;});
    await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);
    const c=document.createElement('canvas');c.width=400;c.height=100;c.getContext('2d').drawImage(image,0,0);
    const actual=pixels(c);result[kind]={equal:equal(actual,expected),ink:actual.filter((v,i)=>i%4===3&&v>128).length};
    const bitmap=await createImageBitmap(image);
    const off=new OffscreenCanvas(400,100);off.getContext('2d').drawImage(bitmap,0,0);
    result[kind].offscreenEqual=equal(pixels(off),actual);
    const transferWorker=new Worker(URL.createObjectURL(new Blob([`onmessage=e=>{try{const c=new OffscreenCanvas(400,100);c.getContext('2d').drawImage(e.data,0,0);e.data.close();postMessage(Array.from(c.getContext('2d').getImageData(0,0,400,100).data));}catch(error){postMessage({error:String(error)})}};`],{type:'text/javascript'})));
    const transferred=await new Promise((resolve,reject)=>{transferWorker.onmessage=e=>resolve(e.data);transferWorker.onerror=e=>reject(Error(e.message));transferWorker.postMessage(bitmap,[bitmap]);});transferWorker.terminate();
    result[kind].workerEqual=Array.isArray(transferred)&&equal(transferred,actual);
   }finally{if(kind==='blob')URL.revokeObjectURL(url);}
  }
  const worker=new Worker(URL.createObjectURL(new Blob([`onmessage=async e=>{try{const bitmap=await createImageBitmap(e.data);const c=new OffscreenCanvas(400,100);c.getContext('2d').drawImage(bitmap,0,0);bitmap.close();postMessage({supported:true,bytes:Array.from(c.getContext('2d').getImageData(0,0,400,100).data)});}catch(error){postMessage({supported:false,error:String(error)});}};`],{type:'text/javascript'})));
  const bitmap=await new Promise((resolve,reject)=>{worker.onmessage=e=>resolve(e.data);worker.onerror=e=>reject(Error(e.message));worker.postMessage(blob)});worker.terminate();
  result.workerBitmap=bitmap.supported?{supported:true,equal:equal(bitmap.bytes,expected)}:bitmap;
  results[name]=result;
 }
 return results;
}
(async()=>{
 const html=await sample(()=>document.createElement('canvas'),encoded);
 const offscreen=await sample(()=>new OffscreenCanvas(1,1),encoded);
 const worker=new Worker(URL.createObjectURL(new Blob([`const sample=${sample};onmessage=async e=>{try{let transferred=e.data.canvas;postMessage(await sample(()=>{if(transferred){const c=transferred;transferred=null;return c;}return new OffscreenCanvas(1,1);},e.data.encoded))}catch(error){postMessage({error:String(error)})}};`],{type:'text/javascript'})));
 const unused=document.createElement('canvas').transferControlToOffscreen();
 const remote=await new Promise((r,j)=>{worker.onmessage=e=>r(e.data);worker.onerror=e=>j(Error(e.message));worker.postMessage({encoded,canvas:unused},[unused])});worker.terminate();
 const svg=await sampleSVGs(encoded);
 done({html,offscreen,worker:remote,svg});
})().catch(e=>done({error:String(e),stack:e.stack}));'''


def main():
    out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-canonical-fonts'));out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Page)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[];report={'checks':checks}
    def check(ok,name):
        checks.append({'pass':bool(ok),'name':name})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='cfx-canonical-fonts-') as profile:
            opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
            for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
            opts.set_preference('cloakfox.experimental.canvas_pipeline',True)
            opts.set_preference('cloakfox.opt.canvas_render_privacy',False)
            Path(profile,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
            d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
            try:
                d.set_script_timeout(90);d.set_context('chrome')
                report['runtime']=d.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
                d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/')
                encoded=base64.b64encode((ROOT/'bundle/fonts/macos/DejaVuSansMono.ttf').read_bytes()).decode()
                results=d.execute_async_script(SCRIPT,encoded)
                check('error' not in results,'font corpus completes')
                if 'error' not in results:
                    for realm in ['html','offscreen','worker']:
                        result=results[realm]
                        check('error' not in result,realm+' font loading succeeds')
                        if 'error' in result:continue
                        custom=result['custom']
                        check(abs(custom['bufferWidth']-24.08203125)<.01,realm+' custom font table metrics are used')
                        check(custom['bufferWidth']==custom['urlWidth'],realm+' FontFace URL and buffer agree')
                        check(abs(custom['spaced']-custom['urlWidth']-3)<.001,realm+' custom spacing and measurement agree')
                        for name,value in result.items():
                            if name=='custom':continue
                            check(value['ink']>0 and value['width']>0,realm+' '+name+' has measurable ink')
                        check(result['Emoji']['color']>20,realm+' pinned emoji producer paints color')
                    for name,value in results['svg'].items():
                        for kind in ['data','blob']:
                            check(value[kind]['ink']>0,'SVG '+name+' '+kind+' paints text')
                            check(value[kind]['equal'],'SVG '+name+' '+kind+' agrees with canvas text')
                            check(value[kind]['offscreenEqual'],'SVG '+name+' '+kind+' ImageBitmap agrees across canvases')
                            check(value[kind]['workerEqual'],'SVG '+name+' '+kind+' transferred ImageBitmap agrees in worker')
                        if value['workerBitmap']['supported']:
                            check(value['workerBitmap']['equal'],'SVG '+name+' worker Blob ImageBitmap agrees')
                    for name in results['html']:
                        if name=='custom':continue
                        check(results['html'][name]==results['offscreen'][name]==results['worker'][name],name+' pixels and metrics agree across realms')
                    for result in results.values():
                        for value in result.values():
                            if isinstance(value,dict):value.pop('bytes',None)
                report['results']=results
            finally:d.quit()
    finally:
        server.shutdown();server.server_close()
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(any(not c['pass'] for c in checks))

if __name__=='__main__':raise SystemExit(main())
