import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const page=fs.readFileSync(new URL('./manual_real_media.py',import.meta.url),'utf8');
const source=page.slice(page.indexOf('async function inspect('),page.indexOf('\nfor(const [id,request]'));

for(const stall of ['play','resume','recorder-stop']){
 test(`physical streams stop independently when ${stall} stalls`,async()=>{
  let stopped=0,token=0;
  const timers=new Map();
  const track={readyState:'live',muted:false,stop(){stopped++;this.readyState='ended'}};
  const never=new Promise(()=>{});
  const video={play:()=>stall==='play'?never:Promise.resolve(),pause(){},remove(){},requestVideoFrameCallback(){},videoWidth:640,videoHeight:480};
  class AudioContext{resume(){return stall==='resume'?never:Promise.resolve()}close(){return Promise.resolve()}createMediaStreamSource(){return{connect(){}}}createAnalyser(){return{getFloatTimeDomainData(){}}}}
  class MediaRecorder{constructor(){this.state='inactive'}start(){this.state='recording'}stop(){this.state='inactive';/* deliberately no onstop event */}}
  const context={document:{createElement:()=>video,body:{append(){}}},AudioContext,MediaRecorder,Float32Array,
   setTimeout:(callback,delay)=>{timers.set(++token,{callback,delay});return token},clearTimeout:id=>timers.delete(id),
   setInterval:()=>0,clearInterval(){}};
  vm.createContext(context);vm.runInContext(source,context);
  const stream={getTracks:()=>[track],getVideoTracks:()=>[track],getAudioTracks:()=>[track]};
  const pending=context.inspect(stream,stall==='resume').then(()=>false,()=>true);
  for(let i=0;i<10;i++)await Promise.resolve();
  for(const [id,timer]of [...timers].sort((a,b)=>a[1].delay-b[1].delay)){
   if(timers.has(id)){timer.callback();for(let i=0;i<10;i++)await Promise.resolve();}
  }
  assert.ok(stopped>0,'an independent watchdog must stop the physical tracks');
  assert.equal(await pending,true,'stalled capture must reject rather than report success');
 });
}

test('late playback resolution cannot recreate audio resources after cancellation',async()=>{
 let resolvePlay,createdAudio=0,createdIntervals=0;
 const play=new Promise(resolve=>{resolvePlay=resolve});
 const timers=new Map();let token=0;
 const track={stop(){},readyState:'ended',muted:false};
 const video={play:()=>play,remove(){},requestVideoFrameCallback(){}};
 class AudioContext{constructor(){createdAudio++}resume(){return Promise.resolve()}close(){return Promise.resolve()}createMediaStreamSource(){return{connect(){}}}createAnalyser(){return{getFloatTimeDomainData(){}}}}
 class MediaRecorder{constructor(){this.state='inactive'}start(){this.state='recording'}stop(){this.state='inactive'}}
 const context={document:{createElement:()=>video,body:{append(){}}},AudioContext,MediaRecorder,Float32Array,
  setTimeout:(callback,delay)=>{timers.set(++token,{callback,delay});return token},clearTimeout:id=>timers.delete(id),
  setInterval:()=>{createdIntervals++;return 1},clearInterval(){}};
 vm.createContext(context);vm.runInContext(source,context);
 const pending=context.inspect({getTracks:()=>[track],getVideoTracks:()=>[track],getAudioTracks:()=>[track]},true).catch(()=>{});
 for(let i=0;i<10;i++)await Promise.resolve();
 [...timers.values()].find(t=>t.delay===8000).callback();await pending;
 resolvePlay();for(let i=0;i<15;i++)await Promise.resolve();
 assert.equal(createdAudio,0,'cancelled playback must not create a new AudioContext');
 assert.equal(createdIntervals,0,'cancelled capture must not create a new interval');
});

test('successful capture returns metrics then stops its streams and deadline',async()=>{
 let stopped=0,token=0;
 const timers=new Map();
 const track={readyState:'live',muted:false,stop(){stopped++;this.readyState='ended'}};
 const video={play:()=>Promise.resolve(),remove(){},requestVideoFrameCallback(){},videoWidth:640,videoHeight:480};
 class MediaRecorder{constructor(){this.state='inactive';this.mimeType='video/webm'}start(){this.state='recording'}stop(){this.state='inactive';this.ondataavailable?.({data:{size:128}});this.onstop?.()}}
 const context={document:{createElement:()=>video,body:{append(){}}},MediaRecorder,
  setTimeout:(callback,delay)=>{timers.set(++token,{callback,delay});return token},clearTimeout:id=>timers.delete(id),setInterval(){},clearInterval(){}};
 vm.createContext(context);vm.runInContext(source,context);
 const pending=context.inspect({getTracks:()=>[track],getVideoTracks:()=>[track],getAudioTracks:()=>[]},false);
 for(let i=0;i<10;i++)await Promise.resolve();
 const duration=[...timers].find(([,t])=>t.delay===3000);timers.delete(duration[0]);duration[1].callback();
 const result=await pending;
 assert.equal(result.recordedBytes,128);assert.equal(result.liveUnmuted,true);
 assert.equal(stopped,1);assert.equal(timers.size,0);
});
