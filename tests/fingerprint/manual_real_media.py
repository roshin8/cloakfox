"""Manual physical-media regression, explicitly opted in with disposable profiles.

Set ALLOW_PHYSICAL_MEDIA=1, CLOAKFOX_BIN and REPORT_DIR. Media stays in memory
for three seconds; only scalar metrics are saved. Native permissions/source
selection remain real. No physical-media test is part of automatic discovery.
"""
import os,json,tempfile,time,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from real_media_checks import validate_report

PAGE=r'''<!doctype html><meta charset="utf-8"><title>Cloakfox 159 — local media verification</title>
<style>body{font:20px system-ui;padding:40px;background:#e6f0ff;color:#123}button{font:inherit;padding:20px;margin:15px}#marker{width:300px;height:80px;background:#4588e8}</style>
<h1>Cloakfox 159 — local media verification</h1><p>No media is uploaded or saved. Share only this test window.</p>
<button id="camera">Test real camera and microphone</button><button id="screen">Test sharing this window</button><p id="state">Ready</p><div id="marker"></div>
<script>
window.results={};window.activeStreams=new Set();window.stopCapture=()=>{for(const s of window.activeStreams)s.getTracks().forEach(t=>t.stop());window.activeStreams.clear()};setInterval(()=>document.getElementById('marker').style.background=`hsl(${Date.now()/20%360} 80% 50%)`,100);
async function inspect(stream,needAudio){
 let video=null,frames=0,audio=null,context=null,recorder=null,chunks=[],timer,watchdog,stopped=false;
 const stop=()=>{
  if(stopped)return;stopped=true;
  stream.getTracks().forEach(t=>t.stop());if(timer)clearInterval(timer);
  if(recorder){recorder.ondataavailable=null;if(recorder.state==='recording')try{recorder.stop()}catch{}}
  if(video){video.srcObject=null;video.remove()}if(context)context.close().catch(()=>{});chunks=[];
 };
 const deadline=new Promise((_,reject)=>{watchdog=setTimeout(()=>{stop();reject(Error('CaptureDeadlineExceeded'))},8000)});
 async function collect(){
 video=document.createElement('video');video.muted=true;video.playsInline=true;video.style='width:1px;height:1px;opacity:0';document.body.append(video);video.srcObject=stream;
 const next=()=>{frames++;if(!stopped)video.requestVideoFrameCallback(next)};video.requestVideoFrameCallback(next);
  await video.play();if(stopped)throw Error('CaptureCancelled');
  if(needAudio){context=new AudioContext();await context.resume();if(stopped)throw Error('CaptureCancelled');const source=context.createMediaStreamSource(stream),a=context.createAnalyser();source.connect(a);a.fftSize=256;audio={min:1,max:-1,nonzero:0};const data=new Float32Array(a.fftSize);timer=setInterval(()=>{a.getFloatTimeDomainData(data);for(const x of data){audio.min=Math.min(audio.min,x);audio.max=Math.max(audio.max,x);if(x!==0)audio.nonzero++}},50);}
  const done=new Promise((resolve,reject)=>{recorder=new MediaRecorder(stream);recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};recorder.onerror=e=>reject(new Error(e.error?.name||'recorder error'));recorder.onstop=resolve;});
  recorder.start(250);await new Promise(r=>setTimeout(r,3000));if(stopped)throw Error('CaptureCancelled');recorder.stop();await done;if(stopped)throw Error('CaptureCancelled');
  const result={videoTracks:stream.getVideoTracks().length,audioTracks:stream.getAudioTracks().length,frames,videoWidth:video.videoWidth,videoHeight:video.videoHeight,liveUnmuted:stream.getTracks().every(t=>t.readyState==='live'&&!t.muted),recordedBytes:chunks.reduce((n,b)=>n+b.size,0),mimeType:recorder.mimeType,audioSamplesObserved:audio?audio.nonzero:0,audioVaries:audio?audio.max>audio.min:null};
  return result;

 }
 try{return await Promise.race([collect(),deadline])}finally{clearTimeout(watchdog);stop()}
}
for(const [id,request]of [['camera',()=>navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480}},audio:true})],['screen',()=>navigator.mediaDevices.getDisplayMedia({video:true,audio:false})]]){
 document.getElementById(id).onclick=async()=>{document.getElementById('state').textContent=id+': waiting for permission';try{const stream=await request();window.activeStreams.add(stream);try{window.results[id]=await inspect(stream,id==='camera')}finally{window.activeStreams.delete(stream)};document.getElementById('state').textContent=id+': complete'}catch(e){window.results[id]={error:e.name,message:e.message};document.getElementById('state').textContent=id+': '+e.name}};
}
</script>'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=PAGE.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*_):pass

def main():
 if os.environ.get('ALLOW_PHYSICAL_MEDIA') != '1':
  raise SystemExit('Explicit ALLOW_PHYSICAL_MEDIA=1 is required; real capture and native sharing UI may open.')
 BIN=Path(os.environ['CLOAKFOX_BIN']).resolve()
 OUT=Path(os.environ['REPORT_DIR']);OUT.mkdir(parents=True,exist_ok=True)
 os.environ['MOZ_REMOTE_ALLOW_SYSTEM_ACCESS']='1';os.environ.pop('MOZ_HEADLESS',None)
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 report={'binary':str(BIN),'origin':f'http://127.0.0.1:{server.server_port}','mediaSavedOrUploaded':False,'results':{}}
 try:
  with tempfile.TemporaryDirectory(prefix='cloakfox159-real-media-') as p:
   options=Options();options.binary_location=str(BIN);options.add_argument('-profile');options.add_argument(p);options.add_argument('-no-remote')
   options.set_preference('cloakfox.enabled',True)
   options.set_preference('media.navigator.streams.fake',False)
   options.set_preference('media.navigator.permission.disabled',False)
   d=webdriver.Firefox(options=options,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(OUT/'gecko.log')))
   try:
    d.set_context('chrome');report['runtime']=d.execute_script("return {version:Services.appinfo.version,pid:Services.appinfo.processID,enabled:Services.prefs.getBoolPref('cloakfox.enabled'),fake:Services.prefs.getBoolPref('media.navigator.streams.fake'),permissionBypass:Services.prefs.getBoolPref('media.navigator.permission.disabled')}")
    assert report['runtime']['version'].startswith('159.') and report['runtime']['enabled'] and not report['runtime']['fake'] and not report['runtime']['permissionBypass']
    d.set_context('content');d.get(report['origin']);(OUT/'session.json').write_text(json.dumps(report,indent=2)+'\n')
    for name in ['camera','screen']:
     d.find_element('id',name).click();print('WAITING',name,report['origin'],flush=True)
     end=time.monotonic()+240
     while time.monotonic()<end:
      value=d.execute_script('return window.results[arguments[0]]||null',name)
      if value is not None:break
      time.sleep(.5)
     else:value={'error':'Timeout','message':'Awaiting native permissions/chooser'}
     report['results'][name]=value;(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(name,json.dumps(value),flush=True)
     if value.get('error')=='Timeout':
      d.execute_script('window.stopCapture?.()')
      break
   finally:d.quit()
 finally:server.shutdown();server.server_close()
 validate_report(report)
 print('PASS: real camera, microphone and display capture with protection enabled')

if __name__=='__main__':main()
