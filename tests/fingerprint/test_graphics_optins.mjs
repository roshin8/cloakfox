import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const modules = new URL('../../additions/browser/components/cloakfox/', import.meta.url);
const overridesSource = fs.readFileSync(new URL('CloakfoxOverrides.sys.mjs', modules), 'utf8');
const syncSource = fs.readFileSync(new URL('CloakfoxSeedSync.sys.mjs', modules), 'utf8');
const canvasPref = 'cloakfox.opt.canvas_render_privacy';
const gpuPref = 'cloakfox.opt.gpu_backend_profiles';

test('settings headline describes the active compatible profile without losing saved identity', () => {
  const source = fs.readFileSync(new URL('content/settings.js', modules), 'utf8');
  const headline = { textContent: '' };
  const context = vm.createContext({ document: { getElementById: () => headline }, shortSeedTag: () => '' });
  vm.runInContext(declaration(source, 'updateHeadline'), context);
  const cfg = { 'navigator.platform': 'Win32', 'webGl:renderer': 'Saved NVIDIA renderer' };
  context.updateHeadline({ ...cfg, 'webGl:backend_profile': true }, '');
  assert.match(headline.textContent, /WebGL compatible profile/);
  assert.doesNotMatch(headline.textContent, /NVIDIA/);
  context.updateHeadline({ ...cfg, 'webGl:backend_profile': false }, '');
  assert.match(headline.textContent, /Saved NVIDIA renderer/);
  assert.equal(cfg['webGl:renderer'], 'Saved NVIDIA renderer');
});
function declaration(source, name, prefix = 'function') {
  const begin = source.indexOf(`${prefix} ${name}`);
  assert.ok(begin >= 0, `Missing ${name}`);
  const open = source.indexOf('{', begin);
  let depth = 1, end = open + 1;
  for (; depth; end++) {
    if (source[end] === '{') depth++;
    if (source[end] === '}') depth--;
    assert.ok(end < source.length, `Unbalanced ${name}`);
  }
  return source.slice(begin, end);
}
function fixture(entries = []) {
  const values = new Map(entries);
  const writes = [];
  const context = vm.createContext({
    Services: {prefs: {
      getBoolPref(name, fallback) {
        const value = values.get(name);
        if (value === undefined) return fallback;
        if (typeof value !== 'boolean') throw new Error('Wrong pref type');
        return value;
      },
      getStringPref: (name, fallback) => values.get(name) ?? fallback,
      getChildList: prefix => [...values.keys()].filter(key => key.startsWith(prefix)),
      setStringPref(name, value) { values.set(name, value); writes.push(name); },
    }},
    applyPrivacyPolicy: (_id, config) => config,
    applyRegion: (_id, config) => config,
  });
  // Exercise the complete policy module, including its native-mode validators.
  // Function-only extraction omitted dependencies and hid backfill failures.
  vm.runInContext(overridesSource.replace(/^import .*\n/gm, '').replace(/export /g, '') + '\n' +
    declaration(syncSource, 'applyGraphicsOptInPolicy'), context);
  return {context, values, writes};
}
const plain = value => JSON.parse(JSON.stringify(value));

test('opt-ins default off and reject malformed pref types', () => {
  const {context, values} = fixture();
  for (const bad of [undefined, 'true', 1, null]) {
    if (bad === undefined) {values.delete(canvasPref); values.delete(gpuPref);}
    else {values.set(canvasPref, bad); values.set(gpuPref, bad);}
    assert.deepEqual(plain(context.applyGraphicsPolicy({})), {
      'canvas:render_privacy': false, 'webGl:backend_profile': false, 'canvas:canonical_2d': false, 'canvas:canonical_gpu': false,
    });
  }
});

test('authoritative flags override stale unknown overrides independently', () => {
  const {context, values} = fixture([[canvasPref, true]]);
  const overrides = {'canvas:render_privacy': false, 'webGl:backend_profile': true};
  assert.deepEqual(plain(context.applyOverrides(2, {sentinel: 'keep'}, overrides)), {
    sentinel: 'keep', 'canvas:render_privacy': true, 'webGl:backend_profile': false, 'canvas:canonical_2d': false, 'canvas:canonical_gpu': false,
  });
  values.set(canvasPref, false); values.set(gpuPref, true);
  assert.deepEqual(plain(context.applyOverrides(2, {}, overrides)), {
    'canvas:render_privacy': false, 'webGl:backend_profile': true, 'canvas:canonical_2d': false, 'canvas:canonical_gpu': false,
  });
});

test('backfill changes only owned fields, preserves identities, skips bad configs and is idempotent', () => {
  const original = {'canvas:seed': 19, 'fingerprint:secret': 'same',
    'navigator.userAgent': 'manual', 'webrtc:ipv4': '192.0.2.8',
    'webgl:typed_readback:disabled': true, sentinel: {nested: ['keep']}};
  const entries = [[canvasPref, true], ['cloakfox.container.1.math_seed', 'same']];
  for (const id of [0, 1, 2]) entries.push([`cloakfox.s.cloak_cfg_${id}`, JSON.stringify(original)]);
  for (const [id, raw] of [[3, '{bad'], [4, 'null'], [5, '[]'], [6, '123']]) {
    entries.push([`cloakfox.s.cloak_cfg_${id}`, raw]);
  }
  entries.push(['cloakfox.s.cloak_cfg_01', JSON.stringify(original)]);
  const {context, values, writes} = fixture(entries);
  context.applyGraphicsOptInPolicy();
  for (const id of [0, 1, 2]) assert.deepEqual(JSON.parse(values.get(`cloakfox.s.cloak_cfg_${id}`)), {
    ...original, 'canvas:render_privacy': true, 'webGl:backend_profile': false, 'canvas:canonical_2d': false, 'canvas:canonical_gpu': false,
  });
  assert.equal(values.get('cloakfox.container.1.math_seed'), 'same');
  assert.equal(writes.length, 3);
  context.applyGraphicsOptInPolicy();
  assert.equal(writes.length, 3);
  for (const [pref, raw] of entries.filter(([pref]) => /cloak_cfg_(?:3|4|5|6|01)$/.test(pref))) {
    assert.equal(values.get(pref), raw);
  }
  values.set(gpuPref, true); context.applyGraphicsOptInPolicy();
  assert.equal(writes.length, 6);
  for (const id of [0, 1, 2]) assert.deepEqual(JSON.parse(values.get(`cloakfox.s.cloak_cfg_${id}`)), {
    ...original, 'canvas:render_privacy': true, 'webGl:backend_profile': true, 'canvas:canonical_2d': false, 'canvas:canonical_gpu': false,
  });
});

test('startup and each opt-in notification synchronize persisted overlays', () => {
  const calls = [];
  const context = vm.createContext({
    applyGraphicsOptInPolicy: () => calls.push('graphics'),
    applyStrictGraphicsPolicy() {}, publish() {},
  });
  vm.runInContext(declaration(syncSource, 'observer', 'const') + ';globalThis.observer = observer;', context);
  for (const pref of [canvasPref, gpuPref]) context.observer.observe(null, 'nsPref:changed', pref);
  assert.deepEqual(calls, ['graphics', 'graphics']);
  calls.length = 0;
  context.observer.observe(null, 'nsPref:changed', 'cloakfox.opt.unrelated');
  assert.deepEqual(calls, []);
  const init = declaration(syncSource, 'initCloakfoxSeedSync');
  assert.ok(init.indexOf('applyGraphicsOptInPolicy()') > init.indexOf('ensureSeedsForAllContainers()'));
});

const pipelinePref = 'cloakfox.experimental.canvas_pipeline';
test('internal canonical pipeline is strict, independently authoritative, and preserves privacy fields', () => {
  const {context, values} = fixture();
  const original = {'canvas:seed':77,'canvas:canonical_2d':true,'webgl:typed_readback:disabled':true,sentinel:'keep'};
  for (const bad of [undefined, 'true', 1, false]) {
    if (bad === undefined) values.delete(pipelinePref); else values.set(pipelinePref,bad);
    const result=plain(context.applyGraphicsPolicy(original));
    assert.equal(result['canvas:canonical_2d'],false);
    assert.equal(result['canvas:seed'],77);
    assert.equal(result['webgl:typed_readback:disabled'],true);
  }
  values.set(pipelinePref,true);
  const result=plain(context.applyGraphicsPolicy(original));
  assert.equal(result['canvas:canonical_2d'],true);
  assert.equal(result['canvas:render_privacy'],false);
  assert.equal(result['webGl:backend_profile'],true);
  assert.equal(result.sentinel,'keep');
});
test('internal pipeline backfills a stale field even if public graphics fields are already current', () => {
  const original={'canvas:render_privacy':false,'webGl:backend_profile':false,'canvas:canonical_2d':false,'canvas:seed':19};
  const {context,values,writes}=fixture([[pipelinePref,true],['cloakfox.s.cloak_cfg_7',JSON.stringify(original)]]);
  context.applyGraphicsOptInPolicy();
  assert.deepEqual(JSON.parse(values.get('cloakfox.s.cloak_cfg_7')),{...original,'canvas:canonical_2d':true,'canvas:canonical_gpu':true,'webGl:backend_profile':true,'webgl:typed_readback:disabled':true});
  assert.deepEqual(writes,['cloakfox.s.cloak_cfg_7']);
});

test('complete pipeline atomically selects canonical 2D and GPU while preserving readback guards',()=>{
 const {context,values,writes}=fixture([[pipelinePref,true],['cloakfox.s.cloak_cfg_0',JSON.stringify({'canvas:canonical_2d':true,'canvas:canonical_gpu':false,'webgl:typed_readback:disabled':true})]]);
 context.applyGraphicsOptInPolicy();
 const cfg=JSON.parse(values.get('cloakfox.s.cloak_cfg_0'));
 assert.equal(cfg['canvas:canonical_gpu'],true);
 assert.equal(cfg['canvas:canonical_2d'],true);
 assert.equal(cfg['webGl:backend_profile'],true);
 assert.equal(cfg['webgl:typed_readback:disabled'],true);
 values.set(pipelinePref,false);const disabled=plain(context.applyGraphicsPolicy(cfg));
 assert.equal(disabled['canvas:canonical_gpu'],false);
 assert.equal(disabled['webgl:typed_readback:disabled'],true);
});

test('canonical renderer cannot inherit a disabled precise GPU readback guard',()=>{
 const original={'canvas:render_privacy':false,'canvas:canonical_2d':true,'canvas:canonical_gpu':true,'webGl:backend_profile':true,'webgl:typed_readback:disabled':false};
 const {context,values,writes}=fixture([[pipelinePref,true],['cloakfox.s.cloak_cfg_0',JSON.stringify(original)]]);
 context.applyGraphicsOptInPolicy();
 assert.equal(JSON.parse(values.get('cloakfox.s.cloak_cfg_0'))['webgl:typed_readback:disabled'],true);
 assert.deepEqual(writes,['cloakfox.s.cloak_cfg_0']);
});
