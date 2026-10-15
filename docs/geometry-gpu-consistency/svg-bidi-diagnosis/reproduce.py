import base64,json,sys,tempfile,threading,time,os
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
ROOT=Path('/Users/zeus/.codex/worktrees/firefox-158-port/cloakfox')
OUT=ROOT/'docs/geometry-gpu-consistency/svg-bidi-diagnosis';OUT.mkdir(parents=True,exist_ok=True)
class Page(BaseHTTPRequestHandler):
 def do_GET(self):
  b=b'<!doctype html><title>Bidi comparison</title>';self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*_):pass
SCRIPT=r'''const done=arguments[arguments.length-1];(async()=>{
const text='abc שלום 123 سلام',W=400,H=100;
const source=`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="5" y="65" font-family="sans-serif" font-size="32" fill="#303030">${text}</text></svg>`;
const ref=document.createElement('canvas');ref.width=W;ref.height=H;const x=ref.getContext('2d');x.font='32px sans-serif';x.fillStyle='#303030';x.fillText(text,5,65);
const expected=x.getImageData(0,0,W,H).data;let result={width:x.measureText(text).width,em:x.measureText('A').emHeightAscent,A40:(()=>{x.font='40px sans-serif';return x.measureText('A').width})(),expectedPNG:ref.toDataURL(),sources:{}};
function bounds(a){let b=[W,H,-1,-1],ink=0;for(let y=0;y<H;y++)for(let xx=0;xx<W;xx++)if(a[(y*W+xx)*4+3]){b=[Math.min(b[0],xx),Math.min(b[1],y),Math.max(b[2],xx),Math.max(b[3],y)];ink++;}return {bounds:b,ink};}
result.expected=bounds(expected);
for(const kind of ['data','blob']){const url=kind==='data'?'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source):URL.createObjectURL(new Blob([source],{type:'image/svg+xml'}));const img=new Image();await new Promise((r,j)=>{img.onload=r;img.onerror=j;img.src=url;});await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);const c=document.createElement('canvas');c.width=W;c.height=H;const cx=c.getContext('2d');cx.drawImage(img,0,0);const a=cx.getImageData(0,0,W,H).data;let diff=0,pixels=0,maxDelta=0,first=[],bbox=[W,H,-1,-1];for(let i=0;i<a.length;i+=4){let changed=false;for(let j=0;j<4;j++)if(a[i+j]!==expected[i+j]){diff++;maxDelta=Math.max(maxDelta,Math.abs(a[i+j]-expected[i+j]));changed=true;}if(changed){pixels++;const xx=(i/4)%W,y=Math.floor(i/4/W);bbox=[Math.min(bbox[0],xx),Math.min(bbox[1],y),Math.max(bbox[2],xx),Math.max(bbox[3],y)];if(first.length<8)first.push([xx,y,Array.from(expected.slice(i,i+4)),Array.from(a.slice(i,i+4))]);}}
result.sources[kind]={...bounds(a),diff,pixels,maxDelta,diffBounds:bbox,first,PNG:c.toDataURL()};if(kind==='blob')URL.revokeObjectURL(url);}
return result;})().then(done,e=>done({error:String(e),stack:e.stack}));'''
server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
report=[]
try:
 for name,binary in [('new','/Applications/Cloakfox.app/Contents/MacOS/cloakfox'),('old','/Users/zeus/Library/Application Support/cloakfox/app-backups/Cloakfox-before-geometry-consistency-20261015-161123.app/Contents/MacOS/cloakfox')]:
  with tempfile.TemporaryDirectory(prefix='cfx-svg-bidi-diagnosis-')as profile:
   o=Options();o.binary_location=binary
   for a in ['-headless','-purgecaches','-profile',profile]:o.add_argument(a)
   o.set_preference('cloakfox.experimental.canvas_pipeline',True);o.set_preference('cloakfox.opt.canvas_render_privacy',False)
   Path(profile,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
   d=webdriver.Firefox(options=o,service=Service(service_args=['--allow-system-access'],log_output=str(OUT/f'{name}-gecko.log')))
   try:
    d.set_script_timeout(90);d.set_context('chrome');runtime=d.execute_script('return {buildID:Services.appinfo.appBuildID,full:Services.prefs.getBoolPref("cloakfox.experimental.canvas_pipeline")}');d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');time.sleep(.7)
    for seed in [None,0,1,42,123456789,4000000000]:
     d.set_context('chrome');cfg=d.execute_script('''const p='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(p,'{}'));if(arguments[0]!==null){cfg['fonts:spacing_seed']=arguments[0];cfg['canvas:seed']=1234567;cfg['fingerprint:secret']='Z'.repeat(43)+'=';Services.prefs.setStringPref(p,JSON.stringify(cfg));}return {'fonts:spacing_seed':cfg['fonts:spacing_seed'],'canvas:seed':cfg['canvas:seed'],'fingerprint:secret':cfg['fingerprint:secret']};''',seed)
     d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/?seed={seed}');time.sleep(.15)
     result=d.execute_async_script(SCRIPT)
     for field in ['expectedPNG']:
      if field in result:
       png=OUT/f'{name}-{seed}-{field}.png';png.write_bytes(base64.b64decode(result.pop(field).split(',',1)[1]));result[field]=str(png)
     for kind,v in result.get('sources',{}).items():
      png=OUT/f'{name}-{seed}-{kind}.png';png.write_bytes(base64.b64decode(v.pop('PNG').split(',',1)[1]));v['PNG']=str(png)
     item={'build':name,'seed':seed,'runtime':runtime,'cfg':cfg,'result':result};report.append(item);(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in item.items()if k!='result'}),result.get('width'),[(k,v['pixels'],v['diffBounds'])for k,v in result.get('sources',{}).items()],flush=True)
   finally:d.quit()
finally:server.shutdown()
