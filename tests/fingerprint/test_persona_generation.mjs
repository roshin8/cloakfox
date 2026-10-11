import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
const path=new URL('../../additions/browser/components/cloakfox/',import.meta.url);
const source=(await readFile(new URL('CloakfoxBayesianNetwork.sys.mjs',path),'utf8')).replace('resource:///modules/CloakfoxBFNetwork.sys.mjs',new URL('CloakfoxBFNetwork.sys.mjs',path).href);
const sampler=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
function random(seed) {return ()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};}
test('constrained generation follows supported OS and GPU combinations',()=>{
 for(const os of ['windows','macos','linux']){
  const families=sampler.getPersonaHardwareFamilies(os);
  assert(families.length>0);
  for(const hardware of families){
   for(let seed=1;seed<=5;seed++){
    const fp=sampler.samplePersonaFingerprint(random(seed),{os,hardware});
    assert.equal(sampler.personaOS(fp.userAgent),os);
    assert.equal(sampler.personaHardware(fp.videoCard?.renderer),hardware);
    assert.deepEqual(fp,sampler.samplePersonaFingerprint(random(seed),{os,hardware}));
    assert(fp.screen.width>0 && fp.screen.height>0);
   }
  }
 }
});
test('fresh seeds generate fresh samples instead of a fixed persona pool',()=>{
 const samples=new Set(Array.from({length:50},(_,seed)=>JSON.stringify(sampler.samplePersonaFingerprint(random(seed+1),{os:'windows',hardware:'auto'}))));
 assert(samples.size>30);
});
test('automatic preserves the previous sampling path and unknown filters fail',()=>{
 assert.deepEqual(sampler.samplePersonaFingerprint(random(7),{os:'auto',hardware:'auto'}),sampler.sampleFingerprint(random(7)));
 assert.throws(()=>sampler.samplePersonaFingerprint(random(7),{os:'banana',hardware:'auto'}));
 assert.throws(()=>sampler.samplePersonaFingerprint(random(7),{os:'windows',hardware:'banana'}));
});
