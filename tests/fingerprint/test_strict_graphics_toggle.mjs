import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';

function harness(entries) {
  const values = new Map(Object.entries(entries));
  const writes = [], publications = [], intWrites = [];
  let observer;
  const prefs = {
    PREF_STRING: 32, PREF_BOOL: 128, PREF_INT: 64,
    getBoolPref: (k, fallback) => values.get(k) ?? fallback,
    getStringPref: (k, fallback) => values.get(k) ?? fallback,
    getIntPref: (k, fallback) => values.get(k) ?? fallback,
    getChildList: prefix => [...values.keys()].filter(k => k.startsWith(prefix)),
    getBranch: prefix => ({getChildList: () => prefs.getChildList(prefix).map(k => k.slice(prefix.length))}),
    getPrefType: k => typeof values.get(k) === 'boolean' ? 128 : typeof values.get(k) === 'number' ? 64 : 32,
    setIntPref(k, value) {values.set(k,value);intWrites.push(k);},
    setStringPref(k, value) {values.set(k, value);writes.push(k);observer.observe(null, 'nsPref:changed', k);},
  };
  const context=vm.createContext({crypto:webcrypto,btoa,atob,Services:{prefs,ppmm:{sharedData:{set(k,v){publications.push(v)},flush(){}}}}});
  const source=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs',import.meta.url),'utf8')
    .replace(/import\s+[\s\S]*?from\s+"[^"]+";/g,'').replaceAll('export function ','function ');
  vm.runInContext(source+'\nglobalThis.testObserver=observer;',context);observer=context.testObserver;
  return {values,writes,publications,intWrites,change(k,value){values.set(k,value);observer.observe(null,'nsPref:changed',k)}};
}
const opt='cloakfox.opt.webgl_typed_readback_disabled';
const field='webgl:typed_readback:disabled';
const pref=id=>'cloakfox.s.cloak_cfg_'+id;

test('global strict toggle updates only its field in every canonical existing config',()=>{
  const cfg={fonts:['Arial'],'fonts:spacing_seed':3,'canvas:seed':11,
    'navigator.userAgent':'pinned-UA','webrtc:ipv4':'192.0.2.4',sentinel:{nested:[1,2]},[field]:true};
  const h=harness({[pref(0)]:JSON.stringify(cfg),[pref(2)]:JSON.stringify({...cfg,[field]:false}),
    [pref(123)]:JSON.stringify({...cfg,sentinel:'other'}),
    'cloakfox.container.2.math_seed':'stable-seed', [opt]:true,
    'cloakfox.s.cloak_cfg_02':'{"sentinel":"noncanonical"}',
    'cloakfox.s.cloak_cfg_2_backup':'{"sentinel":"backup"}'});
  const before=new Map(h.values);
  for(const disabled of [false,true]){
    h.change(opt,disabled);
    for(const id of [0,2,123]){
      assert.deepEqual(JSON.parse(h.values.get(pref(id))),{...JSON.parse(before.get(pref(id))),[field]:disabled});
    }
  }
  for(const key of ['cloakfox.container.2.math_seed','cloakfox.s.cloak_cfg_02','cloakfox.s.cloak_cfg_2_backup']){
    assert.equal(h.values.get(key),before.get(key));
  }
  assert.ok(h.writes.every(k=>[pref(0),pref(2),pref(123)].includes(k)));
  assert.ok(h.writes.length<=6,'config observer recursion never writes configs again');
  const last=h.publications.at(-1);
  assert.equal(JSON.parse(last[pref(2)])[field],true);
});

test('unrelated writes do not rewrite strict policy; malformed configs remain intact',()=>{
  const h=harness({[pref(0)]:'{"sentinel":1}',[pref(1)]:'bad', [pref(2)]:'null',
    [pref(3)]:'[1,2]',[pref(4)]:'123',[opt]:true});
  h.change('cloakfox.opt.webgl_typed_readback_disabled_extra',false);
  h.change(pref(0),'{"sentinel":2}');
  assert.deepEqual(h.writes,[]);
  h.change(opt,false);
  assert.deepEqual(JSON.parse(h.values.get(pref(0))),{sentinel:2,[field]:false});
  assert.deepEqual(h.writes,[pref(0)]);
  assert.equal(h.values.get(pref(1)),'bad');assert.equal(h.values.get(pref(2)),'null');
  assert.equal(h.values.get(pref(3)),'[1,2]');assert.equal(h.values.get(pref(4)),'123');
  h.change(opt,false);assert.deepEqual(h.writes,[pref(0)],'no-op toggles leave serialized configs unchanged');
});


test('language cache epochs follow mirror refresh and remain scoped to canonical owners',()=>{
  const h=harness({[pref(0)]:'{"navigator.language":"en-US"}',[pref(2)]:'{"navigator.language":"de-DE"}',
    'cloakfox.language_identity_epoch.0':4,'cloakfox.language_identity_epoch.2':8});
  h.change(pref(2),'{"navigator.language":"fr-FR"}');
  assert.deepEqual(h.intWrites,['cloakfox.font_identity_epoch','cloakfox.language_identity_epoch.2']);
  assert.equal(h.values.get('cloakfox.language_identity_epoch.2'),9);
  assert.equal(h.values.get('cloakfox.language_identity_epoch.0'),4);
  h.intWrites.length=0;
  h.change('cloakfox.s.cloak_cfg_02','{"navigator.language":"es-ES"}');
  assert.ok(h.intWrites.every(k=>k==='cloakfox.font_identity_epoch'));
  assert.equal(h.values.get('cloakfox.language_identity_epoch.2'),9);
  h.intWrites.length=0;
  h.values.set('cloakfox.language_identity_epoch.0',0x7fffffff);
  h.change(pref(0),'{"navigator.language":"it-IT"}');
  assert.deepEqual(h.intWrites,['cloakfox.font_identity_epoch','cloakfox.language_identity_epoch.0']);
  assert.equal(h.values.get('cloakfox.language_identity_epoch.0'),0);
  assert.equal(h.values.get('cloakfox.language_identity_epoch.2'),9);
});
