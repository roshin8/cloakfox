import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const servicePath = new URL('../../firefox-src/toolkit/components/cleardata/ClearDataService.sys.mjs', import.meta.url);
const idlPath = new URL('../../firefox-src/toolkit/components/cleardata/nsIClearDataService.idl', import.meta.url);
const available = existsSync(servicePath);
// Evaluate the real native service's JS, including its cleaner dispatch map and
// permission cleaner, against a small storage boundary. No production functions
// are rewritten; only the two Gecko imports are supplied by the test harness.
function fixture() {
  const flags = {};
  for (const [, name, expression] of readFileSync(idlPath, 'utf8').matchAll(/const uint32_t (\w+) = ([\s\S]*?);/g)) {
    flags[name] = vm.runInNewContext(expression, flags) >>> 0;
  }
  const permissions = [0, 2].map(id => ({ id, type: 'camera' }));
  const events = [];
  const context = vm.createContext({
    console: { error: () => {} },
    Ci: new Proxy({ nsIClearDataService: flags }, { get: (object, key) => object[key] || {} }),
    Cr: { NS_OK: 0, NS_ERROR_INVALID_ARG: 1 },
    Components: { ID: value => value },
    ChromeUtils: { defineESModuleGetters() {}, generateQI() { return () => {}; } },
    XPCOMUtils: { defineLazyServiceGetter() {}, defineLazyPreferenceGetter() {} },
    AppConstants: {},
    Services: { qms: {}, obs: { notifyObservers: (_subject, topic) => events.push(topic) },
      cookies: { removeCookiesWithOriginAttributes: pattern => events.push(['cookies', JSON.parse(pattern).userContextId]) },
      perms: { removePermissionsWithAttributes: (pattern, include, exclude) => {
        const id = JSON.parse(pattern).userContextId;
        for (let i = permissions.length - 1; i >= 0; i--) {
          const permission = permissions[i];
          if (permission.id === id && (!include.length || include.includes(permission.type)) && !exclude.includes(permission.type)) permissions.splice(i, 1);
        }
      } },
    },
  });
  let source = readFileSync(servicePath, 'utf8').replace(/^import .*;\n/gm, '').replace('export function ClearDataService', 'function ClearDataService');
  vm.runInContext(source + '\nglobalThis.service = new ClearDataService();', context);
  return { flags, permissions, events, service: context.service };
}
const clear = (service, pattern, flags) => new Promise(resolve => service.deleteDataFromOriginAttributesPatternWithFlags(pattern, flags, { onDataDeleted: resolve }));

test('cookie-only origin clearing leaves shared and scoped permissions and unrelated legacy state alone', { skip: !available }, async () => {
  const f = fixture();
  assert.equal(await clear(f.service, { userContextId: 0 }, f.flags.CLEAR_COOKIES), 0);
  assert.deepEqual(f.permissions.map(p => p.id), [0, 2]);
  assert.deepEqual(f.events, [['cookies', 0]]);
});

test('explicit permission clearing removes only provably scoped nonzero entries', { skip: !available }, async () => {
  const f = fixture();
  await clear(f.service, { userContextId: 2 }, f.flags.CLEAR_SITE_PERMISSIONS);
  assert.deepEqual(f.permissions.map(p => p.id), [0]);
  assert.deepEqual(f.events, []);
});

test('zero flags is a no-op with completion; legacy ALL still delegates with ALL', { skip: !available }, async () => {
  const f = fixture();
  assert.equal(await clear(f.service, { userContextId: 0 }, 0), 0);
  assert.deepEqual(f.events, []);
  let seen;
  // Exercise the real legacy entry point with an instance-level delegate.
  const receiver = { deleteDataFromOriginAttributesPatternWithFlags: (...args) => { seen = args; return 123; } };
  const callback = { onDataDeleted() {} };
  assert.equal(f.service.deleteDataFromOriginAttributesPattern.call(receiver, { userContextId: 2 }, callback), 123);
  assert.equal(seen[1], f.flags.CLEAR_ALL);
  assert.equal(seen[2], callback);
});

test('ALL-minus-permissions keeps the legacy notification and excludes permission cleaners', { skip: !available }, async () => {
  const f = fixture();
  const mask = (f.flags.CLEAR_ALL & ~(f.flags.CLEAR_SITE_PERMISSIONS | f.flags.CLEAR_STORAGE_ACCESS |
    f.flags.CLEAR_STORAGE_PERMISSIONS | f.flags.CLEAR_SHUTDOWN_EXCEPTIONS)) >>> 0;
  let selected;
  const receiver = Object.create(f.service);
  Object.defineProperty(receiver, '_deleteInternal', { value: (flags, callback) => { selected = flags; callback.onDataDeleted(0); return 0; } });
  await clear(receiver, { userContextId: 0 }, mask);
  assert.equal(selected, mask);
  assert.ok(f.events.includes('clear-origin-attributes-data'));
  assert.equal(selected & f.flags.CLEAR_SITE_PERMISSIONS, 0);
});
