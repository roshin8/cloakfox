import test from 'node:test';
import assert from 'node:assert/strict';
import {comparePersonaTraits,findSimilarPersonas} from '../../additions/browser/components/cloakfox/content/persona-similarity.mjs';
const cfg={"navigator.userAgent":"Firefox Windows","navigator.platform":"Win32","webGl:vendor":"Intel","webGl:renderer":"Intel GPU","screen.width":1920,"screen.height":1080,"window.devicePixelRatio":1,"navigator.hardwareConcurrency":8,fonts:['Arial','Calibri']};
test('identical visible traits warn even with different fingerprint seeds',()=>{
 assert.equal(comparePersonaTraits({...cfg,'canvas:seed':1},{...cfg,'canvas:seed':2}).score,100);
 assert.equal(comparePersonaTraits(cfg,{...cfg,fonts:['Calibri','Arial']}).tooClose,true);
});
test('CPU or font variation alone does not hide a near duplicate',()=>{
 assert.equal(comparePersonaTraits(cfg,{...cfg,'navigator.hardwareConcurrency':16}).tooClose,true);
 assert.equal(comparePersonaTraits(cfg,{...cfg,fonts:['Arial']}).tooClose,true);
});
test('distinct GPU or screen avoids high-overlap warning',()=>{
 assert.equal(comparePersonaTraits(cfg,{...cfg,'webGl:renderer':'AMD GPU'}).tooClose,false);
 assert.equal(comparePersonaTraits(cfg,{...cfg,'screen.width':2560}).tooClose,false);
});
test('missing values do not count as shared traits',()=>{
 assert.equal(comparePersonaTraits({},{}).tooClose,false);
 assert.equal(comparePersonaTraits(cfg,{'navigator.userAgent':cfg['navigator.userAgent']}).tooClose,false);
});
test('exclude own container and missing identities; include default and manual overrides',()=>{
 const matches=findSimilarPersonas(cfg,[{ucid:1,name:'Self',cfg},{ucid:0,name:'Default',cfg},{ucid:2,name:'Empty',cfg:null},{ucid:3,name:'Other',cfg:{...cfg,'screen.width':2560}}],1);
 assert.deepEqual(matches.map(x=>x.ucid),[0]);
});
