"""Observed TestDome codec order and synthetic recording, no device capture."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from screen_management_fixture import ScreenManagementFixture

PROFILES=Path(__file__).with_name('fixtures')/'testdome_codec_profiles.json'

def validate_recording(value):
    assert isinstance(value,dict) and not value.get('error'),value
    for name in ('screen','webcam'):
        row=value[name]
        assert row['bytes']>0,(name,'empty output',row)
        assert row['ebml']==[26,69,223,163],(name,'invalid WebM header',row)
    assert value['cleanup']['tracksStopped'] and value['cleanup']['contextsClosed'],value['cleanup']

RECORD=r'''const [profiles,done]=arguments;
window.synth={progress:'starting',out:{}};
(async()=>{
 const out={ua:navigator.userAgent,selected:{},support:{}};
 const streams=[],contexts=[],oscillators=[],canvases=[],timers=new Set(),recorders=[];
 let deadline,cancelled=false;
 const active=()=>{if(cancelled)throw Error('Recording was cancelled')};
 const timeout=new Promise((_,reject)=>{deadline=setTimeout(()=>reject(Error('45-second recording deadline: '+synth.progress)),43000)});
 async function work(){
  for(const [name,settings] of Object.entries(profiles.targets)){
   active();const candidates=[];
   synth.progress=name+':codec support';
   for(const profile of profiles.order){for(const codec of profiles.codecs[profile.family]){
    const c=codec.replace(/^vp09\./,'vp9.');
    const bpp=name==='webcam'&&profile.family==='av1'?profiles.webcamAv1Bpp:settings.bpp;
    const config={codec,width:settings.width,height:settings.height,framerate:settings.framerate,
      bitrate:settings.width*settings.height*settings.framerate*bpp,hardwareAcceleration:profile.acceleration};
    const encoder=await VideoEncoder.isConfigSupported(config).then(r=>r.supported,()=>false);active();
    const container=['vp8','vp9'].includes(profile.family)?'video/webm':'video/mp4';
    const mimes=name==='webcam'?['opus','mp4a.40.2'].map(a=>container+';codecs='+c+','+a):[container+';codecs='+c];
    const supported=mimes.filter(m=>MediaRecorder.isTypeSupported(m));
    candidates.push({family:profile.family,codec,acceleration:profile.acceleration,encoder,mimes:supported});
   }}
   out.support[name]=candidates;
   out.selected[name]=candidates.find(c=>c.encoder&&c.mimes.length);
   if(!out.selected[name])throw Error('No supported '+name+' profile');
   // Explicitly preserve the observed software fallback even if an earlier
   // profile is supported on this machine. Recording below exercises VP8.
   const fallback=candidates.find(c=>c.codec==='vp8'&&c.acceleration==='no-preference'&&c.encoder&&c.mimes.length);
   if(!fallback)throw Error('Observed VP8 fallback is unsupported for '+name);
   active();const canvas=document.createElement('canvas');canvases.push(canvas);
   canvas.width=settings.width;canvas.height=settings.height;document.body.append(canvas);
   const ctx=canvas.getContext('2d');let frame=0;
   const draw=()=>{ctx.fillStyle=frame++%2?'#22bb33':'#1133bb';ctx.fillRect(0,0,canvas.width,canvas.height)};draw();
   const stream=canvas.captureStream(settings.framerate);streams.push(stream);
   if(name==='webcam'){
    const ac=new AudioContext();contexts.push(ac);const oscillator=ac.createOscillator();oscillators.push(oscillator);
    const destination=ac.createMediaStreamDestination();streams.push(destination.stream);
    oscillator.connect(destination);oscillator.start();synth.progress=name+':audio resume';await ac.resume();active();
    stream.addTrack(destination.stream.getAudioTracks()[0]);
   }
   const mime='video/webm;codecs=vp8'+(name==='webcam'?',opus':'');
   const recorder=new MediaRecorder(stream,{mimeType:mime,
     videoBitsPerSecond:settings.width*settings.height*settings.framerate*settings.bpp,
     ...(name==='webcam'?{audioBitsPerSecond:profiles.audioBitrate}:{})});recorders.push(recorder);
   const chunks=[];
   const blob=await new Promise((resolve,reject)=>{
    recorder.ondataavailable=e=>chunks.push(e.data);recorder.onerror=e=>reject(e.error);
    recorder.onstop=()=>resolve(new Blob(chunks,{type:mime}));recorder.start(100);synth.progress=name+':recording';
    const drawTimer=setInterval(draw,60);timers.add(drawTimer);
    const stopTimer=setTimeout(()=>{timers.delete(stopTimer);clearInterval(drawTimer);timers.delete(drawTimer);
      synth.progress=name+':stopping';recorder.stop()},650);timers.add(stopTimer);
   });
   active();out[name]={mime:recorder.mimeType,bytes:blob.size,ebml:Array.from(new Uint8Array(await blob.slice(0,4).arrayBuffer()))};
   synth.out=out;
  }
  return out;
 }
 try{return await Promise.race([work(),timeout])}
 finally{
  cancelled=true;clearTimeout(deadline);for(const timer of timers){clearTimeout(timer);clearInterval(timer)}
  for(const recorder of recorders){if(recorder.state!=='inactive')recorder.stop()}
  streams.forEach(stream=>stream.getTracks().forEach(track=>track.stop()));
  oscillators.forEach(oscillator=>{try{oscillator.stop()}catch{}});
  await Promise.all(contexts.map(context=>context.close()));canvases.forEach(canvas=>canvas.remove());
  out.cleanup={tracksStopped:streams.every(stream=>stream.getTracks().every(track=>track.readyState==='ended')),
    contextsClosed:contexts.every(context=>context.state==='closed')};synth.progress='cleaned';
 }
})().then(done,e=>done({error:e.name,message:e.message,diagnostic:synth}));'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--empty-output',action='store_true');args=parser.parse_args()
    if args.empty_output:
        validate_recording({'screen':{'bytes':0,'ebml':[]},'webcam':{'bytes':0,'ebml':[]}})
        return
    profiles=json.loads(PROFILES.read_text())
    with ScreenManagementFixture(headful=True) as f:
        d=f.open()
        f.pref('media.autoplay.block-webaudio',False)
        try:result=d.execute_async_script(RECORD,profiles)
        except Exception:
            (f.report_path/'recording-timeout.json').write_text(json.dumps(d.execute_script('return window.synth'),indent=2))
            raise
        (f.report_path/'recording.json').write_text(json.dumps(result,indent=2))
        validate_recording(result)
        print('TESTDOME SYNTHETIC RECORDING PASS',result['screen']['bytes'],result['webcam']['bytes'],flush=True)

if __name__=='__main__':main()
