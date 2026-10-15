import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function page(actorName, enabled = true) {
  const receivers = new WeakSet(), calls = [];
  class Navigator {}
  const nav = new Navigator(); receivers.add(nav);
  const values = {webdriver: true, pdfViewerEnabled: false, onLine: false, cookieEnabled: false, gpu: {}};
  for (const [name, value] of Object.entries(values)) {
    Object.defineProperty(Navigator.prototype, name, { enumerable: true, configurable: true, get() {
      if (!receivers.has(this)) throw new TypeError('Invalid receiver');
      calls.push(name); return value;
    }});
  }
  Navigator.prototype.javaEnabled = function () {
    if (!receivers.has(this)) throw new TypeError('Invalid receiver');
    calls.push('javaEnabled'); return true;
  };
  const context = vm.createContext({ JSWindowActorChild: class {},
    Services: {prefs: {getBoolPref: () => enabled}},
    Cu: {waiveXrays: x => x, exportFunction: f => f},
  });
  const path = process.env.ACTOR_SOURCE || new URL(`../../additions/browser/components/cloakfox/actors/${actorName}.sys.mjs`, import.meta.url);
  const source = readFileSync(path, 'utf8').replace(`export class ${actorName}`, `class ${actorName}`);
  vm.runInContext(source + `\nglobalThis.Actor = ${actorName};`, context);
  const nativeGetters = Object.fromEntries(Object.keys(values).map(name => [name, Object.getOwnPropertyDescriptor(Navigator.prototype, name).get]));
  const actor = new context.Actor();
  actor.contentWindow = {wrappedJSObject: {Navigator}};
  actor.handleEvent({type: 'DOMDocElementInserted'});
  return {nav, proto: Navigator.prototype, calls, nativeGetters};
}

for (const actorName of ['CloakfoxFeatureDetectChild', 'CloakfoxWebGPUChild']) {
  test(`${actorName} preserves WebIDL receiver checks and native descriptor flags`, () => {
    const h = page(actorName);
    const expected = actorName === 'CloakfoxWebGPUChild' ? {gpu: h.nav.gpu} :
      {pdfViewerEnabled: true, onLine: true, cookieEnabled: true};
    for (const [name, value] of Object.entries(expected)) {
      const d = Object.getOwnPropertyDescriptor(h.proto, name);
      for (const receiver of [{}, null, undefined, Object.create(h.proto)]) {
        assert.throws(() => d.get.call(receiver), {name: 'TypeError'});
      }
      assert.equal(d.get.call(h.nav), value);
      if (actorName === 'CloakfoxWebGPUChild') assert.equal(d.get, h.nativeGetters[name]);
      else assert.equal(d.get.name, `get ${name}`);
      assert.equal(d.get.length, 0);
      assert.equal(d.enumerable, true); assert.equal(d.configurable, true);
      assert.ok(h.calls.includes(name));
    }
    assert.deepEqual(Object.keys(h.nav), []);
    assert.equal(Object.getOwnPropertyDescriptor(h.proto, 'webdriver').get,h.nativeGetters.webdriver,'webdriver remains native');
    if (actorName === 'CloakfoxFeatureDetectChild') {
      assert.throws(() => h.proto.javaEnabled.call({}), {name: 'TypeError'});
      assert.equal(h.nav.javaEnabled(), false);
      assert.ok(h.calls.includes('javaEnabled'));
    }
  });
  test(`${actorName} master switch preserves native values`, () => {
    const h = page(actorName, false);
    assert.equal(h.nav.webdriver, true); assert.equal(h.nav.cookieEnabled, false);
    assert.equal(h.nav.javaEnabled(), true); assert.equal(typeof h.nav.gpu, 'object');
  });
}
