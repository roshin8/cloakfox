import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {confirmConsistencyChange} from '../../additions/browser/components/cloakfox/CloakfoxInspector.sys.mjs';
const source=readFileSync(new URL('../../additions/browser/components/cloakfox/content/settings.js',import.meta.url),'utf8');
function extract(start,end){return source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));}
const base={'navigator.userAgent':'Windows Firefox/158.0','headers.User-Agent':'Windows Firefox/158.0','navigator.platform':'Win32','window.devicePixelRatio':1};
function runtime(accept){
 const prefs=new Map([['seed.7','original-seed'],['cloakfox.container.7.persona_browser','firefox']]);
 const originalPrefs=[...prefs],overrides={'window.devicePixelRatio':1},writes=[];
 const node=()=>({value:'auto',disabled:false,checked:false,textContent:'',classList:{add(){},remove(){}},setAttribute(){},removeAttribute(){},append(){},remove(){},addEventListener(){},matches(){return false;}});
 const elements=new Map();
 const document={getElementById:id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id);},querySelectorAll:()=>[],querySelector:()=>null,createElement:node,body:node()};
 document.getElementById('cfx-persona-version').value='158';
 document.getElementById('cfx-persona-source').value='fpgen';
 let cfg={...base};
 const build=(_seed,_id,clear=false)=>JSON.stringify({...base,...(clear?{}:overrides)});
 const sandbox=vm.createContext({confirmConsistencyChange,window:{confirm:()=>accept},document,
 KEY_TYPES:{'window.devicePixelRatio':'float'},readOverrides:()=>({...overrides}),
 applyOverrides:(_id,b,o)=>({...b,...o}),buildCloakCfg:build,getCloakCfg:()=>cfg,
 masterSeedPref:id=>'seed.'+id,personaModePref:id=>`cloakfox.container.${id}.persona_os_mode`,personaIndexPref:id=>`cloakfox.container.${id}.persona_index`,
 setOverrides:(_id,changes)=>{writes.push('override');for(const [k,v]of Object.entries(changes)){if(v===null||v==='')delete overrides[k];else overrides[k]=Number(v);}},
 Services:{prefs:{PREF_BOOL:128,PREF_INT:64,
 getStringPref:(k,f='')=>prefs.get(k)??f,getChildList:p=>[...prefs.keys()].filter(k=>k.startsWith(p)),prefHasUserValue:k=>prefs.has(k),getPrefType:()=>32,
 setStringPref:(k,v)=>prefs.set(k,v),setIntPref:(k,v)=>prefs.set(k,v),clearUserPref:k=>prefs.delete(k),savePrefFile:()=>writes.push('save')}},
 selectedOSMode:()=> 'windows',selectedBrowser:()=> 'firefox',browserCapabilities:()=>({}),normalizeBrowserSelection:v=>v,
 randomSeedB64:()=> 'new-seed',persistCloakCfg:(_id,seed,clear)=>{writes.push('publish');cfg=JSON.parse(build(seed,7,clear));},
 refreshContainer(){},showAppliedIdentity(){},renderPersonaSimilarity(){},getContainers:()=>[],findSimilarPersonas:()=>[],shortSeedTag:()=> 'tag',
 Cu:{reportError:e=>{throw Error(e)}},requestAnimationFrame:cb=>cb(),setTimeout(){},
 selectEl:{value:'7'},generateNew:node(),regenBtn:node(),identityChoice:{value:'-1'}});
 vm.runInContext(extract('function applySettingChanges(', '// ── container enumeration')+'\nlet identityBusy=false;\n'+extract('async function applyIdentity(', '  const forgetBtn')+'\nthis.api={applySettingChanges,applyIdentity};',sandbox);
 return {sandbox,prefs,originalPrefs,overrides,writes,elements};
}
test('real settings edit cancels before override writes and preserves seed',()=>{
 const r=runtime(false);assert.equal(r.sandbox.api.applySettingChanges(7,{'window.devicePixelRatio':'0'}),false);
 assert.deepEqual(r.writes,[]);assert.equal(r.overrides['window.devicePixelRatio'],1);assert.equal(r.prefs.get('seed.7'),'original-seed');
});
test('real settings edit accepts exact custom value without rotating seed',()=>{
 const r=runtime(true);assert.equal(r.sandbox.api.applySettingChanges(7,{'window.devicePixelRatio':'0'}),true);
 assert.equal(r.overrides['window.devicePixelRatio'],0);assert.equal(r.prefs.get('seed.7'),'original-seed');
});
test('real generation cancellation restores identity prefs and keeps seed/config/overrides',async()=>{
 const r=runtime(false);r.overrides['window.devicePixelRatio']=0;
 await r.sandbox.api.applyIdentity(-1);
 assert.deepEqual([...r.prefs],r.originalPrefs);assert.deepEqual(r.writes,[]);assert.equal(r.overrides['window.devicePixelRatio'],0);
 assert.match(r.elements.get('cfx-identity-status').textContent,/canceled/);
});
test('real generation acceptance retains overrides and publishes the new identity',async()=>{
 const r=runtime(true);r.overrides['window.devicePixelRatio']=0;
 await r.sandbox.api.applyIdentity(-1);
 assert.equal(r.prefs.get('seed.7'),'new-seed');assert.equal(r.overrides['window.devicePixelRatio'],0);
 assert.deepEqual(r.writes,['publish','save']);
});

test('fresh generation saves the chosen provider while pinned previews always select BrowserForge',async()=>{
 const r=runtime(true);await r.sandbox.api.applyIdentity(-1);
 assert.equal(r.prefs.get('cloakfox.container.7.persona_source'),'fpgen');
 assert.equal(r.prefs.get('cloakfox.container.7.persona_os'),'windows');
 assert.equal(r.prefs.get('cloakfox.container.7.persona_hardware'),'auto');
 await r.sandbox.api.applyIdentity(3);
 assert.equal(r.prefs.get('cloakfox.container.7.persona_source'),'browserforge');
 assert.equal(r.prefs.has('cloakfox.container.7.persona_os'),false);
});
test('unsupported provider filter errors preserve all prior preference and published identity state',async()=>{
 const r=runtime(true);r.sandbox.Cu.reportError=()=>{};
 r.sandbox.buildCloakCfg=()=>{throw Error('Unsupported fpgen hardware');};
 await r.sandbox.api.applyIdentity(-1);
 assert.deepEqual([...r.prefs],r.originalPrefs);assert.deepEqual(r.writes,[]);
 assert.match(r.elements.get('cfx-identity-status').textContent,/Unsupported fpgen hardware/);
});

test('real settings refresh retains saved provider across owner selection and restart',async()=>{
 const loadSource=r=>vm.runInContext('{const ucid=Number(selectEl.value);'+extract('    const mode = personaOSMode(ucid);','    const osLabels =')+'}',r.sandbox);
 const r=runtime(true);r.sandbox.personaOSMode=()=> 'legacy';
 loadSource(r);assert.equal(r.elements.get('cfx-persona-source').value,'fpgen');
 assert.equal(r.elements.get('cfx-persona-source-current').textContent,'BrowserForge generated');
 r.elements.get('cfx-persona-source').value='browserforge';await r.sandbox.api.applyIdentity(-1);
 loadSource(r);assert.equal(r.elements.get('cfx-persona-source').value,'browserforge');
 const persisted=JSON.stringify([...r.prefs]);
 const restarted=runtime(true);restarted.sandbox.personaOSMode=()=> 'legacy';restarted.prefs.clear();
 for(const [key,value] of JSON.parse(persisted))restarted.prefs.set(key,value);
 loadSource(restarted);assert.equal(restarted.elements.get('cfx-persona-source').value,'browserforge');
 restarted.prefs.set('cloakfox.container.8.persona_source','fpgen');restarted.sandbox.selectEl.value='8';loadSource(restarted);
 assert.equal(restarted.elements.get('cfx-persona-source').value,'fpgen');
 assert.equal(restarted.elements.get('cfx-persona-source-current').textContent,'fpgen generated');
 restarted.sandbox.selectEl.value='7';loadSource(restarted);assert.equal(restarted.elements.get('cfx-persona-source').value,'browserforge');
});
