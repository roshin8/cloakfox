import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {sampleFPGenFingerprint} from '../../additions/browser/components/cloakfox/CloakfoxFPGenSampler.sys.mjs';
import {sampleHostFingerprint} from '../../additions/browser/components/cloakfox/CloakfoxHostPersona.sys.mjs';
const root=new URL('../../additions/browser/components/cloakfox/',import.meta.url);
const bfSource=readFileSync(new URL('CloakfoxBayesianNetwork.sys.mjs',root),'utf8').replace('resource:///modules/CloakfoxBFNetwork.sys.mjs',new URL('CloakfoxBFNetwork.sys.mjs',root).href);
const {sampleFingerprint,samplePersonaFingerprint}=await import(`data:text/javascript;base64,${Buffer.from(bfSource).toString('base64')}`);
const source=readFileSync(new URL('CloakfoxPersonas.sys.mjs',root),'utf8');
function runtime(text=source) {
 const prefs=new Map(),get=(key,fallback)=>prefs.has(key)?prefs.get(key):fallback;
 const context=vm.createContext({atob,btoa,AppConstants:{MOZ_APP_VERSION:'159.0'},sampleFingerprint,samplePersonaFingerprint,sampleFPGenFingerprint,sampleHostFingerprint,
  Services:{appinfo:{OS:'Darwin'},prefs:{getStringPref:get,getIntPref:get,getBoolPref:get}},writeNetworkProfile(){}});
 vm.runInContext(text.replace(/^import .*;\n/gm,'').replace(/^export /gm,''),context);
 return {prefs,sample:(seed,filters)=>sampleFPGenFingerprint(context.makeSeededPRNG(seed),filters),fill:(seed,id)=>JSON.parse(JSON.stringify(context.fillPersonaKeys(seed,id)))};
}
const seed=Buffer.alloc(32,19).toString('base64');
const hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');

// Expected hashes were recorded from the pre-fpgen production mapper (c80a898c21)
// with the same real BrowserForge model, build version and preferences.
test('missing-source BrowserForge identities preserve full mapped output and PRNG order',()=>{
 const cases=[
  [{}, '0d9c498d9d5fbd9099a09e9f2a0284a3e266889b17821f270322331061c660a4'],
  [{persona_os_mode:'host'},'4ed1e6c60cf4d2a0e15a685dc603c74c0669b1f569dd92b9014648d6d89f4116'],
  [{persona_os_mode:'windows',persona_index:3},'be185f6847023969c7adc11720c1a5895100ce9652a964c0e9d20bf3cc8f754b'],
  [{persona_os:'linux',persona_hardware:'intel',persona_browser:'firefox',persona_version:'158'},'92fc71cc93f9266b122549e037b8790d91609a1473749d9463bc1ffbcc878665'],
 ];
 for(const [settings,expected] of cases) {
  const r=runtime();for(const [key,value] of Object.entries(settings))r.prefs.set('cloakfox.container.7.'+key,value);
  assert.equal(hash(r.fill(seed,7)),expected);
  r.prefs.set('cloakfox.container.7.persona_source','browserforge');assert.equal(hash(r.fill(seed,7)),expected);
 }
});
test('real fpgen passes through the native mapper deterministically without changing policy flags',()=>{
 const r=runtime();r.prefs.set('cloakfox.container.7.persona_source','fpgen');
 r.prefs.set('cloakfox.container.7.persona_os','macos');r.prefs.set('cloakfox.container.7.persona_hardware','apple');
 r.prefs.set('cloakfox.opt.webgl_typed_readback_disabled',true);r.prefs.set('cloakfox.opt.mediadevices_disabled',true);
 const cfg=r.fill(seed,7);assert.deepEqual(r.fill(seed,7),cfg);
 assert.match(cfg['navigator.userAgent'],/Macintosh.*Firefox\/159\.0/);
 assert.match(cfg['webGl:renderer'],/Apple/);assert.equal(cfg['webgl:typed_readback:disabled'],true);
 assert.equal(cfg['mediaDevices:enabled'],false);
 assert.notDeepEqual(r.fill(Buffer.alloc(32,20).toString('base64'),7),cfg);
 assert.notDeepEqual(r.fill(seed,8),cfg);
 r.prefs.set('cloakfox.container.7.persona_os','windows');assert.throws(()=>r.fill(seed,7),/fpgen/);
});


test('fpgen automatic and random versions use the selected browser family',()=>{
 const patterns={firefox:/Firefox\/(\d+)/,chrome:/Chrome\/(\d+)/,edge:/Edg\/(\d+)/,safari:/Version\/(\d+)/};
 for(const [browser,pattern] of Object.entries(patterns)) {
  for(const version of ['auto','random-recent','42']) {
   for(const byte of [19,20,21]) {
    const currentSeed=Buffer.alloc(32,byte).toString('base64');
    const r=runtime();
    for(const [key,value] of Object.entries({source:'fpgen',browser,version}))r.prefs.set('cloakfox.container.7.persona_'+key,value);
    const observed=Number(pattern.exec(r.sample(currentSeed,{browser,version}).userAgent)?.[1]);
    assert.ok(observed>0);
    const cfg=r.fill(currentSeed,7),major=Number(pattern.exec(cfg['navigator.userAgent'])?.[1]);
    if(version==='42')assert.equal(major,42);
    else if(browser!=='firefox')assert.equal(major,observed,`${browser} ${version} must use its observed family version`);
    else if(version==='auto')assert.equal(major,159);
    else assert.ok(major>=157&&major<=159);
    assert.equal(cfg['headers.User-Agent'],cfg['navigator.userAgent']);
    assert.equal(cfg['navigator.appVersion'],cfg['navigator.userAgent'].replace(/^Mozilla\//,''));
    assert.deepEqual(r.fill(currentSeed,7),cfg);
   }
  }
 }
 const r=runtime();r.prefs.set('cloakfox.container.7.persona_source','fpgen');r.prefs.set('cloakfox.container.7.persona_browser','chromium');
 for(const version of ['auto','random-recent']) {r.prefs.set('cloakfox.container.7.persona_version',version);assert.throws(()=>r.fill(seed,7),/unsupported browser/);}
});
