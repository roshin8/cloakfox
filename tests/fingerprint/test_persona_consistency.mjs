import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePersona,compareRealmSignals} from '../../additions/browser/components/cloakfox/content/persona-consistency.mjs';
const valid={'navigator.userAgent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/146.0','headers.User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/146.0','navigator.platform':'Win32','navigator.oscpu':'Windows NT 10.0; Win64; x64','screen.width':1920,'screen.height':1080,'screen.availWidth':1920,'screen.availHeight':1040,'window.innerWidth':1200,'window.outerWidth':1200,'window.innerHeight':800,'window.outerHeight':900,'window.devicePixelRatio':1,'navigator.language':'en-US','headers.Accept-Language':'en-US,en;q=0.5','locale:language':'en','locale:region':'US','webGl:renderer':'NVIDIA GeForce GTX 980'};
test('coherent configuration is accepted without mutation',()=>{const cfg=structuredClone(valid);assert.deepEqual(validatePersona(cfg),[]);assert.deepEqual(cfg,valid)});
test('reports independent identity, GPU, geometry and locale contradictions',()=>{
 const issues=validatePersona({...valid,'headers.User-Agent':'Other','navigator.platform':'MacIntel','webGl:renderer':'Apple M2','screen.availWidth':2000,'window.innerHeight':1000,'window.devicePixelRatio':0,'locale:region':'JP'});
 for(const code of ['ua-header','platform-os','gpu-os','available-width','viewport-height','dpr','locale-region'])assert(issues.some(i=>i.code===code),code);
});
test('partial configurations and unfamiliar hardware do not invent conflicts',()=>assert.deepEqual(validatePersona({'webGl:renderer':'Unknown experimental GPU'}),[]));
test('GL renderer table contradictions are reported',()=>assert(validatePersona({...valid,'webGl:parameters':{7937:'Other GPU'}}).some(i=>i.code==='gl-renderer')));
test('realm comparisons flag only shared signals actually observed',()=>{
 assert.deepEqual(compareRealmSignals({userAgent:'A',language:'en'},{userAgent:'A'}),[]);
 assert.equal(compareRealmSignals({userAgent:'A',language:'en'},{userAgent:'B',language:'ja'}).length,2);
});

test('appVersion is checked against the configured identity',()=>assert(validatePersona({...valid,'navigator.appVersion':'5.0 (Macintosh; Intel Mac OS X)' }).some(i=>i.code==='app-version')));

test('reduced Firefox appVersion is not treated as a contradiction',()=>assert.deepEqual(validatePersona({...valid,'navigator.appVersion':'5.0 (Windows)'}),[]));
