import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const dir = new URL('../../additions/browser/components/cloakfox/', import.meta.url);
const seed = Buffer.alloc(32, 19).toString('base64');
const ua = version => `Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:${version}) Gecko/20100101 Firefox/${version}`;
function harness(version = '155.0.1', hostOS = 'WINNT', sampler = () => ({ userAgent: ua('146.0'), screen: {} })) {
  const prefs = new Map();
  const filters = [];
  const get = (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback;
  const context = vm.createContext({
    AppConstants: { MOZ_APP_VERSION: version }, atob, btoa, console,
    crypto: { getRandomValues: bytes => bytes.fill(19) },
    sampleFingerprint: sampler,
    samplePersonaFingerprint: (prng, constraints) => { filters.push({...constraints}); return sampler(prng); },
    ContextualIdentityService: { getPublicIdentities: () => [{ userContextId: 7 }] },
    Services: { appinfo: {OS: hostOS},
      prefs: { getStringPref: get, getIntPref: get, getBoolPref: get,
        setStringPref: (k,v) => prefs.set(k,v), setIntPref: (k,v) => prefs.set(k,v),
        setCharPref: (k,v) => prefs.set(k,v), setBoolPref: (k,v) => prefs.set(k,v),
        getBranch: prefix => ({ getChildList: () => [...prefs.keys()].filter(k => k.startsWith(prefix)).map(k => k.slice(prefix.length)) }),
        getPrefType: () => 32, PREF_STRING: 32, addObserver() {}, clearUserPref: key => prefs.delete(key),
      }, obs: { addObserver() {} }, ppmm: { sharedData: { set() {}, flush() {} } },
    },
  });
  // Evaluate full production modules; replace only Gecko imports/ESM exports.
  for (const name of ['CloakfoxRegions', 'CloakfoxPrivacyPolicy', 'CloakfoxHostPersona', 'CloakfoxPersonas', 'CloakfoxOverrides', 'CloakfoxSeedSync']) {
    const source = readFileSync(new URL(`${name}.sys.mjs`, dir), 'utf8')
      .replace(/^import\s+[\s\S]*?\s+from\s+"[^"]+";\n/gm, '')
      .replace(/^export /gm, '');
    vm.runInContext(source, context, { filename: name });
  }
  return { prefs, context, filters, start: () => context.initCloakfoxSeedSync(), cfg: () => JSON.parse(prefs.get('cloakfox.s.cloak_cfg_7')) };
}
// New region/policy metadata is validated by its own suite; this regression
// verifies every pre-existing config field remains byte-for-byte intact.
function legacyProjection(cfg) {
  for (const key of ['timezone','privacy:policy','locale:default','locale:all','navigator.languages','navigator.language']) delete cfg[key];
  return cfg;
}
function setExisting(h, cfg) {
  for (const name of ['math_seed','keyboard_seed','timing_seed']) h.prefs.set(`cloakfox.container.7.${name}`, seed);
  h.prefs.set('cloakfox.s.cloak_cfg_7', JSON.stringify(cfg));
}
const legacy = () => ({ 'navigator.userAgent': ua('146.0'), 'headers.User-Agent': ua('146.0'),
  'navigator.appVersion': ua('146.0').slice(8), fonts: ['Arial'], 'fonts:spacing_seed': 42,
  'canvas:seed': 123, 'screen.width': 1440, custom: 'retain' });
for (const version of ['155.0.1', '156.0a1', '157.0b3', '155.2.0esr']) {
  test(`fresh cfg derives Firefox major from ${version}`, () => {
    const h = harness(version); h.start(); const cfg = h.cfg(); const expected = ua(`${parseInt(version)}.0`);
    assert.equal(cfg['navigator.userAgent'], expected);
    assert.equal(cfg['headers.User-Agent'], expected);
    assert.equal(cfg['navigator.appVersion'], expected.slice(8));
  });
}
test('startup migrates legacy identity only and keeps seeds and unrelated cfg', () => {
  const h = harness(); const before = legacy(); setExisting(h, before); h.start();
  assert.deepEqual(legacyProjection(h.cfg()), { ...before, "fingerprint:secret": seed, 'navigator.userAgent': ua('155.0'), 'headers.User-Agent': ua('155.0'), 'navigator.appVersion': ua('155.0').slice(8) });
  for (const name of ['math_seed','keyboard_seed','timing_seed']) assert.equal(h.prefs.get(`cloakfox.container.7.${name}`), seed);
  const first = h.prefs.get('cloakfox.s.cloak_cfg_7'); h.start(); assert.equal(h.prefs.get('cloakfox.s.cloak_cfg_7'), first);
});
test('explicit identity overrides remain pinned while other generated fields migrate', () => {
  const h = harness(); const before = legacy();
  before['navigator.userAgent'] = 'Pinned UA';
  setExisting(h, before);
  h.prefs.set('cloakfox.container.7.override.navigator.userAgent', 'Pinned UA');
  h.prefs.set('cloakfox.container.7.override.navigator.appVersion', 'Pinned app');
  h.start();
  assert.equal(h.cfg()['navigator.userAgent'], 'Pinned UA');
  assert.equal(h.cfg()['navigator.appVersion'], 'Pinned app');
  assert.equal(h.cfg()['headers.User-Agent'], ua('155.0'));
});
test('unrecognized direct cfg identity is preserved', () => {
  const h = harness(); const before = { ...legacy(), 'navigator.userAgent': 'Custom browser', 'headers.User-Agent': 'Custom HTTP', 'navigator.appVersion': 'Custom app' };
  setExisting(h, before); h.start(); assert.deepEqual(legacyProjection(h.cfg()), { ...before, "fingerprint:secret": seed });
});
test('explicit Firefox-shaped UA and header overrides remain on their chosen version', () => {
  const h = harness(); setExisting(h, legacy());
  for (const key of ['navigator.userAgent', 'headers.User-Agent', 'navigator.appVersion']) {
    h.prefs.set(`cloakfox.container.7.override.${key}`, legacy()[key]);
  }
  h.start(); assert.deepEqual(legacyProjection(h.cfg()), { ...legacy(), "fingerprint:secret": seed });
});
test('font-key upgrade also migrates identity without losing existing values', () => {
  const h = harness(); const before = legacy(); delete before.fonts;
  setExisting(h, before); h.start();
  assert.ok(h.cfg().fonts.length > 0);
  assert.equal(h.cfg()['navigator.userAgent'], ua('155.0'));
  assert.equal(h.cfg()['canvas:seed'], 123);
  assert.equal(h.cfg().custom, 'retain');
});
test('startup repairs a saved macOS identity carrying Linux fonts', () => {
  const h = harness();
  const macUA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0';
  const before = { ...legacy(),
    'navigator.userAgent': macUA,
    'headers.User-Agent': macUA,
    'navigator.appVersion': macUA.slice(8),
    'navigator.platform': 'MacIntel',
    fonts: ['DejaVu Sans', 'DejaVu Sans Mono', 'DejaVu Serif'],
    'font:generic:serif': 'DejaVu Serif',
    'font:generic:sans-serif': 'DejaVu Sans',
    'font:generic:monospace': 'DejaVu Sans Mono',
  };
  setExisting(h, before); h.start();
  assert.equal(h.cfg()['font:generic:serif'], 'Times');
  assert.equal(h.cfg()['font:generic:sans-serif'], 'Helvetica');
  assert.equal(h.cfg()['font:generic:monospace'], 'Menlo');
  assert.ok(h.cfg().fonts.includes('Menlo'));
  assert.ok(h.cfg().fonts.includes('Helvetica'));
  assert.ok(!h.cfg().fonts.includes('DejaVu Sans Mono'));
  assert.equal(h.cfg().custom, 'retain');
  const migrated = h.prefs.get('cloakfox.s.cloak_cfg_7');
  h.start();
  assert.equal(h.prefs.get('cloakfox.s.cloak_cfg_7'), migrated);
});
test('corrupt cfg rebuilds from persisted seeds with current identity', () => {
  const h = harness(); setExisting(h, legacy());
  h.prefs.set('cloakfox.s.cloak_cfg_7', '{bad json'); h.start();
  assert.equal(h.cfg()['navigator.userAgent'], ua('155.0'));
  assert.equal(h.prefs.get('cloakfox.container.7.math_seed'), seed);
});
test('divergent navigator and HTTP overrides each retain the explicit choice', () => {
  const h = harness(); setExisting(h, legacy());
  h.prefs.set('cloakfox.container.7.override.navigator.userAgent', ua('144.0'));
  h.prefs.set('cloakfox.container.7.override.headers.User-Agent', ua('145.0'));
  h.start();
  assert.equal(h.cfg()['navigator.userAgent'], ua('144.0'));
  assert.equal(h.cfg()['headers.User-Agent'], ua('145.0'));
  assert.equal(h.cfg()['navigator.appVersion'], ua('155.0').slice(8));
});

test('first master seed selects mixed OS mode; existing seeded identity remains legacy',()=>{
 const fresh=harness();fresh.start();assert.equal(fresh.prefs.get('cloakfox.container.7.persona_os_mode'),'legacy');
 const old=harness();setExisting(old,legacy());old.start();
 assert.equal(old.prefs.has('cloakfox.container.7.persona_os_mode'),false);
 assert.equal(old.context.personaOSMode(7),'legacy');
 old.context.refreshContainerConfig(7);
 assert.equal(old.prefs.get('cloakfox.container.7.math_seed'),seed);
 assert.equal(old.context.personaOSMode(7),'legacy');
});
test('host mode flows through generated keys, pinned keys, preview labels and summary',()=>{
 const sample=prng=>prng()<0.5?{userAgent:ua('146.0'),platform:'Win32',screen:{width:1920,height:1080},videoCard:{renderer:'Windows GPU'}}:
  {userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0',platform:'MacIntel',screen:{width:1440,height:900},videoCard:{renderer:'Apple GPU'}};
 const h=harness('155.0.1','Darwin',sample);h.prefs.set('cloakfox.container.7.persona_os_mode','host');h.start();
 assert.match(h.cfg()['navigator.userAgent'],/Macintosh/);
 const previews=h.context.listPersonas('Darwin','host');
 for(let index=0;index<30;index++) {
  h.prefs.set('cloakfox.container.7.persona_index',index);
  const cfg=h.context.fillPersonaKeys(seed,7),summary=h.context.pickPersona(seed,'Darwin',7);
  assert.equal(cfg['navigator.platform'],'MacIntel');
  assert.equal(cfg['screen.width'],summary['screen.width']);
  assert.match(previews[index].label,/^macOS/);
 }
 h.prefs.set('cloakfox.container.7.persona_os_mode','legacy');
 const legacyList=h.context.listPersonas('Darwin');
 assert.ok(legacyList.some(p=>p.label.startsWith('Windows')));
});

test('saved 146 OS/hardware filters survive the port and invalid strings keep the legacy path', () => {
  const h = harness('157.0.1');
  h.prefs.set('cloakfox.container.7.persona_os', 'windows');
  h.prefs.set('cloakfox.container.7.persona_hardware', 'intel');
  h.context.fillPersonaKeys(seed, 7);
  assert.deepEqual(h.filters, [{os:'windows', hardware:'intel'}]);
  h.prefs.set('cloakfox.container.7.persona_os', 'invalid');
  h.prefs.set('cloakfox.container.7.persona_hardware', 'invalid');
  h.context.fillPersonaKeys(seed, 7);
  assert.equal(h.filters.length, 1);
});
