// Exercise the actual privileged module's response parser without native UI.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxEngineHost.sys.mjs',import.meta.url),'utf8')
  .replace(/^import .*;\n/gm,'').replace('export const CloakfoxEngineHost','const CloakfoxEngineHost');
const services={focus:{activeWindow:null}};
const nativeService={};
const Session=vm.runInNewContext(source+'\nFixtureSession;', {ChromeUtils:{generateQI:()=>()=>{}},Services:services,setTimeout,Cc:{"@cloakfox.org/engine-host;1":{getService:()=>nativeService}},Ci:{nsICloakfoxEngineHost:{}}});
const limit=1024*1024;
function reader(chunks){const s=new Session(null,null);s.process={stdout:{async readString(){return chunks.shift()??''}}};return s;}
test('a valid response can span reads',async()=>{
  const s=reader(['{"event":','"ready","version":1}','\n']);
  assert.equal(JSON.stringify(await s.line()),'{"event":"ready","version":1}');
});
test('buffered responses remain independently framed',async()=>{
  const s=reader(['{"id":1}\n{"id":2}\n']);
  assert.equal((await s.line()).id,1);assert.equal((await s.line()).id,2);
});
test('EOF cannot be mistaken for an acknowledgement',async()=>{await assert.rejects(reader(['{"id":']).line(),/disconnected/)});
test('valid JSON over the limit is rejected even with a newline in the same read',async()=>{
  await assert.rejects(reader(['{"event":"ready","padding":"'+'x'.repeat(limit)+'"}\n']).line(),/Oversized native response/);
});
test('an unterminated oversized response is rejected',async()=>{await assert.rejects(reader(['x'.repeat(limit+1)]).line(),/Oversized native response/)});
test('the exact permitted line size remains usable',async()=>{
  const prefix='{"padding":"',suffix='"}';const n=limit-prefix.length-suffix.length;
  assert.equal((await reader([prefix+'x'.repeat(n)+suffix+'\n']).line()).padding.length,n);
});
function ownedSession(){
  let selected=0,inputs=0;
  const document={documentElement:{hasAttribute(){return false}}};
  const browser={isConnected:true,ownerDocument:document,hasAttribute(){return false}};
  document.activeElement=browser;
  const window={closed:false,document,gBrowser:{selectedBrowser:browser},
    windowUtils:{isInModalState(){return false}},gURLBar:{select(){selected++}},removeEventListener(){}};
  services.focus.activeWindow=window;
  const s=new Session(window,browser);
  s.route={token:'owned',configRevision:1,viewportRevision:2};
  s.request=()=>{inputs++;return Promise.resolve()};
  const deliver=kind=>s.observe(null,'cloakfox-engine-input',JSON.stringify({...s.route,kind}));
  return {s,window,browser,document,deliver,selected:()=>selected,inputs:()=>inputs};
}
test('a location shortcut targets chrome, without sending page input',()=>{
  const f=ownedSession();f.deliver('focusLocation');
  assert.equal(f.selected(),1);assert.equal(f.inputs(),0);
});
test('stale or closed owners cannot focus the address bar',()=>{
  const f=ownedSession();const {s}=f;
  for(const stale of [{token:'other'},{configRevision:2},{viewportRevision:1}])
    s.observe(null,'cloakfox-engine-input',JSON.stringify({...s.route,...stale,kind:'focusLocation'}));
  s.closed=true;f.deliver('focusLocation');
  assert.equal(f.selected(),0);
});
for(const [name,change] of [
  ['tab selection',f=>f.window.gBrowser.selectedBrowser={}],
  ['disconnection',f=>f.browser.isConnected=false],
  ['owner document replacement',f=>f.browser.ownerDocument={}],
  ['window closure',f=>f.window.closed=true],
  ['chrome focus change',f=>f.document.activeElement={}],
  ['window deactivation',()=>services.focus.activeWindow={}],
  ['window modal',f=>f.window.windowUtils.isInModalState=()=>true],
  ['tab modal',f=>f.browser.hasAttribute=name=>name==='tabmodalPromptShowing'],
]) test(`queued input is discarded after ${name} without a route revision change`,()=>{
  const f=ownedSession();change(f);
  f.deliver('focusLocation');f.deliver('char');
  assert.equal(f.selected(),0);assert.equal(f.inputs(),0);
});

test('a browser is reserved during startup and cancellation releases that owner',async()=>{
  let resolveProcess,launches=0,unload;
  const services={prefs:{getBoolPref(){return true}}};
  const nativeService={createLaunch(){launches++;return 'owned-launch'},closeLaunch(){}};
  const pending=new Promise(resolve=>{resolveProcess=resolve});
  const host=vm.runInNewContext(source+'\nCloakfoxEngineHost;',{
    ChromeUtils:{generateQI:()=>()=>{}},Services:services,URL,
    Cc:{'@cloakfox.org/engine-host;1':{getService:()=>nativeService}},
    Ci:{nsICloakfoxEngineHost:{}},Subprocess:{call:()=>pending},
  });
  const document={nodePrincipal:{isSystemPrincipal:true}};
  const window={document,closed:false,gBrowser:{tabContainer:{addEventListener(){},removeEventListener(){}}},
    addEventListener(name,callback){if(name==='unload')unload=callback},removeEventListener(){}};
  document.defaultView=window;
  const browser={ownerDocument:document,isConnected:true};
  const args=[window,browser,'helper','profile','{}','http://127.0.0.1:1234/'];
  const first=host.openFixture(...args);
  await assert.rejects(host.openFixture(...args),/already owns/);
  assert.equal(launches,1);
  unload();
  resolveProcess({stdin:{close:async()=>{}},kill:async()=>{}});
  await assert.rejects(first,/owner closed/);
  // An unloaded browser fails ownership checks before a reservation is created.
  window.closed=true;
  await assert.rejects(host.openFixture(...args),/unavailable/);
});

for(const [name,change] of [
  ['tab',f=>f.window.gBrowser.selectedBrowser={}],
  ['viewport',f=>f.s.route={...f.s.route,viewportRevision:3}],
  ['configuration',f=>f.s.route={...f.s.route,configRevision:2}],
  ['token',f=>f.s.route={...f.s.route,token:'replacement'}],
]) test(`input queued behind an RPC is revalidated after a ${name} change`,async()=>{
  const f=ownedSession();let release,writes=0;
  const pending=new Promise(resolve=>{release=resolve});
  f.s.queue=pending;
  f.s.process={stdin:{write:async()=>{writes++}},stdout:{readString:async()=>'{"version":1,"id":1,"ok":true}\n'}};
  const operation=Session.prototype.request.call(f.s,'input',{...f.s.route,kind:'char'});
  change(f);
  release();
  // A dropped queued input is a benign cancellation, not a helper failure.
  await operation;
  assert.equal(writes,0);
});

test('hiding a tab preserves its renderer size and does not resize it to one pixel',async()=>{
  const f=ownedSession();f.browser.getBoundingClientRect=()=>({x:0,y:0,width:0,height:0});
  f.window.gBrowser.selectedBrowser={};
  f.s.route={...f.s.route,width:1200,height:800};let dimensions;
  nativeService.updateViewport=(token,x,y,width,height,visible)=>{
    dimensions={width,height,visible};
    return JSON.stringify({...f.s.route,width,height,viewportRevision:width===1200?2:3});
  };
  await f.s.resize();
  assert.deepEqual(dimensions,{width:1200,height:800,visible:false});
  assert.equal(f.inputs(),0);
});

// Pixel presentation and native input must use exactly the same geometry.
for (const [width,height] of [[2560,1440],[4096,2160],[1200.4,800.4]]) {
  test(`large viewport ${width}x${height} preserves presentation/input coordinates`,async()=>{
    const f=ownedSession();
    const r={x:20,y:85,width,height,right:20+width,bottom:85+height};
    f.browser.getBoundingClientRect=()=>r;
    f.s.canvas={style:{}};
    f.s.canvasStack={getBoundingClientRect:()=>r};
    f.s.updateCanvas();
    let nativeSize;
    nativeService.updateViewport=(token,x,y,w,h,visible)=>{
      nativeSize=[w,h];
      return JSON.stringify({...f.s.route,width:w,height:h});
    };
    await f.s.resize();
    assert.deepEqual(nativeSize,[Math.round(width),Math.round(height)]);
    assert.equal(f.s.canvas.style.width,`${nativeSize[0]}px`);
    assert.equal(f.s.canvas.style.height,`${nativeSize[1]}px`);
  });
}
test('oversized surfaces fail before native allocation instead of stretching',async()=>{
  const f=ownedSession();f.browser.getBoundingClientRect=()=>({x:0,y:85,width:4097,height:800});
  await assert.rejects(f.s.resize(),/viewport.*bounds/i);
});

test('unknown presentation modes reject before launching a helper',async()=>{
  let launched=0;
  const host=vm.runInNewContext(source+'\nCloakfoxEngineHost;',{
    ChromeUtils:{generateQI:()=>()=>{}},Services:{prefs:{getBoolPref:()=>true}},URL,
    Subprocess:{call(){launched++;throw new Error('launched')}},
  });
  const document={nodePrincipal:{isSystemPrincipal:true}};
  const window={document,closed:false};document.defaultView=window;
  const browser={ownerDocument:document,isConnected:true};
  for(const mode of ['automatic',true,1,{},null]) {
    await assert.rejects(host.openFixture(window,browser,'helper','profile','{}','http://127.0.0.1:1234/',false,mode),/presentation mode/i);
  }
  assert.equal(launched,0);
});

function fixtureHandshake(capability, presentation='separate-window', extraReady={}) {
  const writes=[];let killed=0;
  const chunks=[JSON.stringify({event:'ready',windowless:presentation==='same-window',fixtureNetworkVersion:capability,...extraReady})+'\n'];
  let waiting;
  const push=data=>{if(waiting){const resolve=waiting;waiting=null;resolve(data)}else chunks.push(data)};
  const process={pid:123,wait:()=>new Promise(()=>{}),stdin:{async write(data){
    const value=JSON.parse(data);writes.push(value);
    const reply=value.command==='applyConfig'?{version:1,id:value.id,ok:true}:
      {version:1,id:value.id,ok:true,browser:1,configRevision:1,container:'1',private:false,topLevelWindow:presentation==='separate-window'};
    push(JSON.stringify(reply)+'\n');
  },async close(){}},stdout:{readString(){return chunks.length?Promise.resolve(chunks.shift()):new Promise(resolve=>{waiting=resolve})}},
    stderr:{async readString(){return ''}},async kill(){killed++;push('')}};
  const nativeService={createLaunch:()=> 'launch',acceptLaunch(){},closeLaunch(){}};
  const host=vm.runInNewContext(source+'\nCloakfoxEngineHost;',{
    ChromeUtils:{generateQI:()=>()=>{}},Services:{prefs:{getBoolPref:()=>true}},URL,
    Cc:{'@cloakfox.org/engine-host;1':{getService:()=>nativeService}},Ci:{nsICloakfoxEngineHost:{}},
    Subprocess:{call:async()=>process},crypto:{randomUUID:()=> 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'},
  });
  const document={nodePrincipal:{isSystemPrincipal:true}};
  const window={document,closed:false,gBrowser:{tabContainer:{addEventListener(){},removeEventListener(){}}},addEventListener(){},removeEventListener(){}};
  document.defaultView=window;
  const browser={ownerDocument:document,isConnected:true};
  return {host,writes,killed:()=>killed,open:()=>host.openFixture(window,browser,'helper','profile',JSON.stringify({containerId:'1',private:false,revision:1}),'http://127.0.0.1:1234/path',true,presentation)};
}
for(const mode of ['same-window','separate-window']) {
  for(const capability of [undefined,0,true,'1',2]) test(`${mode} refuses missing or invalid native fixture network capability before configuration`,async()=>{
    const f=fixtureHandshake(capability,mode);
    await assert.rejects(f.open(),/fixture network gate/);
    assert.equal(f.writes.length,0);assert.equal(f.killed(),1);
  });
}
test('the authenticated fixture origin is bound before configuration and first navigation',async()=>{
  const f=fixtureHandshake(1);
  const token=await f.open();
  assert.equal(f.writes[0].command,'applyConfig');
  assert.equal(f.writes[0].fixtureURL,'http://127.0.0.1:1234/path');
  assert.equal(f.writes[1].command,'open');
  assert.equal(f.writes[1].url,f.writes[0].fixtureURL);
  await f.host.close(token);
  assert.equal(f.killed(),1);
});

const editingState={field:{document:'a'.repeat(32),node:7},editable:true,password:false,selection:[0,0],composition:null,caret:[5,8,0,18]};
function statePacket(s,changes={}){return {version:1,event:'ownedImeState',browser:42,...s.route,state:editingState,...changes};}
function streamSession(){
  const f=ownedSession();f.s.browserId=42;
  const chunks=[];let release;
  f.push=value=>{if(release){const callback=release;release=null;callback(value)}else chunks.push(value)};
  f.s.process={stdout:{readString(){return chunks.length?Promise.resolve(chunks.shift()):new Promise(resolve=>{release=resolve})}},
    stdin:{async write(){},async close(){}},async kill(){f.push('')}};
  return f;
}
test('native focus state is received while no RPC is pending',async()=>{
  const f=streamSession();const updates=[];nativeService.setInputState=(...args)=>updates.push(args);
  f.s.startReading();f.push(JSON.stringify(statePacket(f.s))+'\n');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(updates.length,1);assert.equal(updates[0][0],f.s.route.token);
  assert.deepEqual(JSON.parse(updates[0][3]),editingState);
  await f.s.close();
});
test('an interleaved focus event cannot consume an RPC acknowledgement',async()=>{
  const f=streamSession();let updated=0;nativeService.setInputState=()=>updated++;
  const pending=Session.prototype.request.call(f.s,'frame',{browser:42});
  await new Promise(resolve=>setImmediate(resolve));
  f.push(JSON.stringify(statePacket(f.s))+'\n'+JSON.stringify({version:1,id:1,ok:true,marker:17})+'\n');
  assert.equal((await pending).marker,17);assert.equal(updated,1);
  await f.s.close();
});
test('foreign and stale editing state cannot update an owned native view',()=>{
  const f=ownedSession();f.s.browserId=42;let updated=0;nativeService.setInputState=()=>updated++;
  for(const change of [{browser:43},{token:'foreign'},{configRevision:2},{viewportRevision:1}]) f.s.applyInputState(statePacket(f.s,change));
  assert.equal(updated,0);
});
test('malformed owned editing state is rejected without native state calls',()=>{
  const f=ownedSession();f.s.browserId=42;let updated=0;nativeService.setInputState=()=>updated++;
  for(const state of [null,{...editingState,value:'secret'}, {...editingState,editable:1},
    {...editingState,field:{document:'x'.repeat(129),node:7}}, {...editingState,field:{document:'a'.repeat(32),node:true}},
    {...editingState,selection:[1,0]}, {...editingState,caret:[0,0,4097,18]},
    {...editingState,editable:false,field:null}]) {
    assert.throws(()=>f.s.applyInputState(statePacket(f.s,{state})),/editing state/);
  }
  assert.equal(updated,0);
});
test('closing the owner rejects an outstanding RPC and drains its reader',async()=>{
  const f=streamSession();const pending=Session.prototype.request.call(f.s,'frame',{browser:42});
  const rejected=assert.rejects(pending,/closed|disconnected/i);
  await new Promise(resolve=>setImmediate(resolve));await f.s.close();await rejected;
});

for (const [name,change] of [
  ['tab',f=>f.window.gBrowser.selectedBrowser={}],
  ['chrome',f=>f.document.activeElement={}],
  ['window',()=>services.focus.activeWindow={}],
]) test(`owned composition cancellation survives ${name} focus retirement without allowing text`,()=>{
  const f=ownedSession();change(f);
  f.s.observe(null,'cloakfox-engine-input',JSON.stringify({...f.s.route,kind:'ownedIme',action:'cancel',field:{document:'aa',node:1}}));
  assert.equal(f.inputs(),1);
  for(const action of ['set','commit','finish'])
    f.s.observe(null,'cloakfox-engine-input',JSON.stringify({...f.s.route,kind:'ownedIme',action,field:{document:'aa',node:1},text:'private'}));
  assert.equal(f.inputs(),1);
  f.s.observe(null,'cloakfox-engine-input',JSON.stringify({...f.s.route,viewportRevision:1,kind:'ownedIme',action:'cancel',field:{document:'aa',node:1}}));
  assert.equal(f.inputs(),1);
});
test('editing-state queries send only the owned protocol fields, without viewport dimensions',async()=>{
  const f=ownedSession();f.s.ownedIme=true;f.s.browserId=42;
  f.s.route={...f.s.route,width:1200,height:800};let request;
  f.s.request=async(command,fields)=>{request={command,fields};return {state:editingState}};
  await f.s.refreshInputState();
  assert.equal(request.command,'textInputState');
  assert.deepEqual(Object.keys(request.fields).sort(),['browser','token','configRevision','viewportRevision'].sort());
});
test('native type invalidation retires the input context and requests fresh owned metadata',async()=>{
  const f=ownedSession();f.s.browserId=42;f.s.ownedIme=true;let retired=0;let refreshed=0;
  nativeService.invalidateInputState=()=>retired++;
  f.s.refreshInputState=async()=>refreshed++;
  f.s.invalidateInputState({...statePacket(f.s),event:'ownedImeInvalidated'});
  await Promise.resolve();assert.equal(retired,1);assert.equal(refreshed,1);
  for(const change of [{token:'foreign'},{browser:43},{configRevision:2},{viewportRevision:1}])
    f.s.invalidateInputState({...statePacket(f.s,change),event:'ownedImeInvalidated'});
  assert.equal(retired,1);
});

for (const capability of [undefined,0,true,'1',2]) test(`same-window refuses an IME helper without exact state invalidation capability ${capability}`,async()=>{
  const f=fixtureHandshake(1,'same-window',{ownedImeVersion:1,ownedImeStateVersion:capability});
  await assert.rejects(f.open(),/editing-state invalidation/);
  assert.equal(f.writes.length,0);assert.equal(f.killed(),1);
});
test('repeated type invalidations coalesce metadata queries with at most one follow-up',async()=>{
  const f=ownedSession();f.s.ownedIme=true;f.s.browserId=42;let writes=0;const releases=[];
  f.s.request=async()=>{writes++;await new Promise(resolve=>releases.push(resolve));return {state:editingState};};
  const first=f.s.refreshInputState();const second=f.s.refreshInputState();
  assert.equal(writes,1);
  releases.shift()();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(writes,2);assert.equal(releases.length,1);
  releases.shift()();await Promise.all([first,second]);assert.equal(writes,2);
});
test('a current owner cannot keep using cached input type after a metadata query returns no state',async()=>{
  const f=ownedSession();f.s.ownedIme=true;f.s.browserId=42;
  let retired=0;nativeService.invalidateInputState=()=>retired++;
  f.s.request=async()=>({ok:true,applied:false});
  await assert.rejects(f.s.refreshInputState(),/editing metadata unavailable/i);
  assert.ok(retired>0 && retired<=3,'Unknown input type must retire the context during bounded retries');
});
