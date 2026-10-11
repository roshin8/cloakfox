import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sampleHostFingerprint, normalizeHostOS} from '../../additions/browser/components/cloakfox/CloakfoxHostPersona.sys.mjs';
test('host selection retains complete correlated tuple without mutation',()=>{
 const foreign={userAgent:'Windows NT',gpu:'foreign'}, native={userAgent:'Macintosh',gpu:'native',screen:{width:1440}};
 let n=0;
 assert.equal(sampleHostFingerprint(()=>0,()=>++n===1?foreign:native,'Darwin'),native);
 assert.equal(n,2); assert.equal(foreign.gpu,'foreign');
});
test('reject unsupported hosts and absent host distribution',()=>{
 assert.throws(()=>normalizeHostOS('Android'));
 assert.throws(()=>sampleHostFingerprint(()=>0,()=>({userAgent:'Windows NT'}),'Linux'),/No linux persona/);
});
test('host aliases normalize consistently',()=>{
 assert.equal(normalizeHostOS('WINNT'),'windows'); assert.equal(normalizeHostOS('macos'),'macos');
});

test('real Bayesian tuples select every supported OS deterministically',async()=>{
 const {readFile}=await import('node:fs/promises');
 const source=await readFile(new URL('../../additions/browser/components/cloakfox/CloakfoxBayesianNetwork.sys.mjs',import.meta.url),'utf8');
 const networkURL=new URL('../../additions/browser/components/cloakfox/CloakfoxBFNetwork.sys.mjs',import.meta.url).href;
 const {sampleFingerprint}=await import('data:text/javascript;base64,'+Buffer.from(source.replace('resource:///modules/CloakfoxBFNetwork.sys.mjs',networkURL)).toString('base64'));
 const random=seed=>()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;};
 for(const os of ['macos','windows','linux']) for(let seed=1;seed<=20;seed++) {
  const a=sampleHostFingerprint(random(seed),sampleFingerprint,os);
  const b=sampleHostFingerprint(random(seed),sampleFingerprint,os);
  assert.deepEqual(a,b);assert.ok(a.screen);assert.ok(a.videoCard);
 }
});
