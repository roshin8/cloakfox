import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../../additions/browser/components/cloakfox/content/ip-warning.js', import.meta.url), 'utf8');

function renderWarning(initial, recheck) {
  const elements = new Map();
  const element = () => ({
    textContent: '', children: [], listeners: {},
    replaceChildren() { this.children = []; },
    append(...children) { this.children.push(...children); },
    addEventListener(type, handler) { this.listeners[type] = handler; },
    setAttribute() {}, removeAttribute() {},
  });
  const get = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const buttons = ['recheck', 'once', 'allow-website', 'container', 'ip'].map(id => Object.assign(get(id), {id}));
  const actions = [];
  let warning = {id: 1, url: 'https://example.com/private', ip: '192.0.2.10', conflicts: [2], ...initial};
  const monitor = {
    getIPWarning: () => warning,
    async resolveIPWarning(token, action) {
      actions.push([token, action]);
      warning = {...warning, ...(recheck?.warning || {ip: '2001:db8::1', conflicts: [2, 3]})};
      if (recheck?.result) return recheck.result;
      return {conflict: true, ip: warning.ip};
    },
  };
  runInNewContext(source, {
    URL, location: {href: 'chrome://browser/content/cloakfox/ip-warning.html?token=test'},
    ChromeUtils: {importESModule: path => path.startsWith('resource:') ? monitor : {
      ContextualIdentityService: {getPublicIdentityFromId: id => ({name: {1: 'Work', 2: 'Personal', 3: 'Shopping'}[id]})},
    }},
    Services: {prefs: {getStringPref: () => 'light'}},
    document: {getElementById: get, querySelectorAll: () => buttons, createElement: element, documentElement: {dataset: {}}},
  });
  get.actions = actions;
  return get;
}

test('website button resolves a hostname exception without overwriting the destination label', async () => {
  const get = renderWarning({}, {result: {continued: true}});
  await get('allow-website').listeners.click();
  assert.deepEqual(get.actions, [['test', 'website']]);
  assert.equal(get('website').textContent, 'example.com');
  assert.equal(get('warning-status').textContent, 'Returning to the website…');
});

function assertLookupExplanation(get, previousContainers) {
  assert.match(get('heading').textContent, /public IP lookups/i);
  const detail = get('warning-detail').textContent;
  assert.match(detail, /public IP lookup for Work/i);
  for (const name of previousContainers) assert.ok(detail.includes(name));
  assert.match(detail, /recorded.*visiting this hostname/i);
  assert.match(detail, /do not confirm the IP seen by this website/i);
  assert.match(detail, /proxy.*IPv4\/IPv6/i);
  assert.doesNotMatch(detail, /uses the same public IP for this hostname/i);
  assert.equal(get('website').textContent, 'example.com');
  assert.equal(get('comparison').hidden, false);
}

test('warning explains lookup evidence without claiming measured website egress', () => {
  const get = renderWarning();
  assertLookupExplanation(get, ['Personal']);
  assert.equal(get('current-ip').textContent, '192.0.2.10');
  assert.match(textOf(get('conflicting-containers')), /IPv4.*192\.0\.2\.10/s);
});

test('recheck keeps the lookup limitation while updating addresses and container names', async () => {
  const get = renderWarning();
  await get('recheck').listeners.click();
  assertLookupExplanation(get, ['Personal', 'Shopping']);
  assert.equal(get('current-ip').textContent, '2001:db8::1');
  assert.match(textOf(get('conflicting-containers')), /Shopping/);
  assert.match(get('warning-status').textContent, /lookups still match.*2001:db8::1/i);
});

function textOf(element) {
  return [element.textContent, ...element.children.map(textOf)].join(' ');
}
const dual = {ipv4: '192.0.2.10', ipv6: '2001:db8::1', errors: {ipv4: null, ipv6: null}, matches: [
  {ip: '192.0.2.10', family: 'ipv4', conflicts: [2]},
  {ip: '2001:db8::1', family: 'ipv6', conflicts: [2]},
]};
test('legacy IPv6 warning shows separate families without fabricating IPv4', () => {
  const get = renderWarning({ip: '2001:db8::1'});
  assert.equal(get('current-ipv6').textContent, '2001:db8::1');
  assert.match(get('current-ipv4').textContent, /Unknown/);
});
test('dual results show both current families and both recorded matches', () => {
  const get = renderWarning(dual);
  assert.equal(get('current-ipv4').textContent, '192.0.2.10');
  assert.equal(get('current-ipv6').textContent, '2001:db8::1');
  const previous = textOf(get('conflicting-containers'));
  assert.match(previous, /IPv4.*192\.0\.2\.10/s);
  assert.match(previous, /IPv6.*2001:db8::1/s);
});
test('other container only displays its recorded matching family', () => {
  const get = renderWarning({...dual, matches: [dual.matches[1]]});
  const previous = textOf(get('conflicting-containers'));
  assert.doesNotMatch(previous, /192\.0\.2\.10/);
  assert.match(previous, /IPv4.*No recorded match/s);
  assert.match(previous, /IPv6.*2001:db8::1/s);
});
for (const [family, other, address] of [['ipv4', 'ipv6', '2001:db8::1'], ['ipv6', 'ipv4', '192.0.2.10']]) {
  test(`${family} unavailable keeps its error separate from the other result`, () => {
    const get = renderWarning({...dual, [family]: '', errors: {[family]: 'route timed out'}});
    assert.match(get('current-'+family).textContent, /Unavailable.*route timed out/);
    assert.equal(get('current-'+other).textContent, address);
  });
}
test('partial recheck error refreshes both families and keeps current matches', async () => {
  const get = renderWarning(dual, {warning: {...dual, ipv4: '', errors: {ipv4: '<route failed>'}, matches: [dual.matches[1]]}, result: {error: 'IPv4 check failed', conflict: true}});
  await get('recheck').listeners.click();
  assert.match(get('current-ipv4').textContent, /Unavailable.*<route failed>/);
  assert.equal(get('current-ipv6').textContent, '2001:db8::1');
  assert.doesNotMatch(textOf(get('conflicting-containers')), /192\.0\.2\.10/);
  assert.match(get('warning-status').textContent, /IPv4 check failed/);
});

for (const [failedFamily, measuredFamily, measuredIP, failure] of [
  ['ipv6', 'ipv4', '192.0.2.99', 'IPv6 timed out'],
  ['ipv4', 'ipv6', '2001:db8::99', 'IPv4 timed out'],
]) {
  test(`incomplete ${failedFamily} recheck does not claim a match when remaining family differs`, async () => {
    const get = renderWarning(dual, {
      warning: {[measuredFamily]: measuredIP, [failedFamily]: null, ip: measuredIP, conflicts: [], matches: [], errors: {[failedFamily]: failure}},
      result: {error: failure, conflict: false},
    });
    await get('recheck').listeners.click();
    assert.match(get('heading').textContent, /IP check incomplete/i);
    assert.match(get('warning-detail').textContent, /previous.*match.*not.*ruled out/i);
    assert.match(get('warning-detail').textContent, /do not confirm the IP seen by this website/i);
    assert.doesNotMatch(get('warning-detail').textContent, /for  when visiting/);
    assert.doesNotMatch(get('comparison-status').textContent, /matching lookup results/i);
    assert.match(get('comparison-status').textContent, /incomplete/i);
    assert.equal(get('current-'+measuredFamily).textContent, measuredIP);
    assert.match(get('current-'+failedFamily).textContent, new RegExp('Unavailable.*'+failure));
  });
}
