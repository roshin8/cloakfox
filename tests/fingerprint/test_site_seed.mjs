import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxSiteSeed.sys.mjs', import.meta.url), 'utf8');
const ctx = vm.createContext({ Uint8Array, TextEncoder, btoa, atob,
  Ci: { nsICryptoHash: { SHA256: 4 } },
  Cc: { '@mozilla.org/security/hash;1': { createInstance() {
    let hash;
    return { init: () => { hash = createHash('sha256'); },
      update: bytes => hash.update(Buffer.from(bytes)), finish: () => hash.digest('latin1') };
  } } },
});
vm.runInContext(source.replace(/^export /gm,''), ctx);
const secret = Buffer.alloc(32, 19).toString('base64');
const derive = (site, base = 42, key = 'canvas:seed', sec = secret) => ctx.deriveSiteSeed(sec, site, key, base);
for (const site of ['(https,example.co.uk)','(http,localhost)','(https,[::1])','12345678-1234-1234-1234-123456789abc.mozilla']) {
  test(`HMAC matches Node crypto for ${site}`, () => {
    const digest = createHmac('sha256', secret).update(`cloakfox-site-v1\ncanvas:seed\n42\n${site}`).digest();
    assert.equal(derive(site), digest.readUInt32BE(0) || 1);
  });
}
test('top-level site stable; foreign ancestor bit removed; scheme/domain/secret/vector change output', () => {
  const a = derive('(https,example.com)');
  assert.equal(a, derive('(https,example.com,f)'));
  assert.equal(a, derive('(https,example.com)'));
  for (const candidate of [derive('(http,example.com)'), derive('(https,other.com)'), derive('(https,example.com)', 43), derive('(https,example.com)',42,'audio:seed'), derive('(https,example.com)',42,'canvas:seed',Buffer.alloc(32,20).toString('base64'))]) assert.notEqual(a,candidate);
});
test('missing/malformed context has no container-wide fallback; explicit zero disables noise', () => {
  for (const key of ['', '(https,)', '(https,example.com,garbage)', '(https,example.com)\nother', 'https://example.com', 'null']) assert.equal(derive(key),0,key);
  assert.equal(derive('(https,example.com)',0),0);
  assert.equal(derive('(https,example.com)',42,'canvas:seed','bad'),0);
});
test('actor reads top-level cookie partition and cfg base seed, not frame origin or legacy seed offset', () => {
  const cfg = { 'fingerprint:secret':secret, 'math:trig_seed':42 };
  const snapshots = { 'cloakfox.s.cloak_cfg_7':JSON.stringify(cfg) };
  const win = { document:{ cookieJarSettings:{ partitionKey:'(https,publisher.co.uk,f)' } }, docShell:{ browsingContext:{ originAttributes:{userContextId:7} } }, location:{ origin:'https://tracker.invalid' } };
  assert.equal(ctx.siteSeedForWindow(win,snapshots,'math:trig_seed'),derive('(https,publisher.co.uk)',42,'math:trig_seed'));
});
test('default container resolves its own secret and explicit zero independently', () => {
  const win={document:{cookieJarSettings:{partitionKey:'(https,one.test)'}},docShell:{browsingContext:{originAttributes:{userContextId:0}}}};
  const snapshot={'cloakfox.s.cloak_cfg_0':JSON.stringify({'fingerprint:secret':secret,'math:trig_seed':42}),
    'cloakfox.s.cloak_cfg_7':JSON.stringify({'fingerprint:secret':Buffer.alloc(32,20).toString('base64'),'math:trig_seed':99})};
  assert.equal(ctx.siteSeedForWindow(win,snapshot,'math:trig_seed'),derive('(https,one.test)',42,'math:trig_seed'));
  snapshot['cloakfox.s.cloak_cfg_0']=JSON.stringify({'fingerprint:secret':secret,'math:trig_seed':0});
  assert.equal(ctx.siteSeedForWindow(win,snapshot,'math:trig_seed'),0);
});
