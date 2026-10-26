import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source = readFileSync(new URL('../../additions/browser/components/cloakfox/content/network-settings.js', import.meta.url), 'utf8');
function renderSettings(rows, history = []) {
  const elements = new Map();
  const element = () => ({textContent: '', children: [], listeners: {}, style: {}, dataset: {}, value: '',
    querySelectorAll(selector) {const matches=[];const walk=node=>{if(node.className?.split(' ').includes(selector.slice(1)))matches.push(node);for(const child of node.children||[])walk(child);};this.children.forEach(walk);return matches;},
    querySelector(selector) {return this.querySelectorAll(selector)[0];},
    append(...children) { this.children.push(...children); },
    replaceChildren() { this.children = []; this.textContent = ''; },
    setAttribute() {}, addEventListener(type, handler) {this.listeners[type] = handler;},
  });
  const get = id => {if (!elements.has(id)) elements.set(id, element()); return elements.get(id);};
  const main = element();
  const monitor = {getIPCheckRoute: () => 'background', setIPCheckRoute() {}, getIPRules: () => ({mode: 'all', include: [], exclude: []}), ipHistory: () => history, ipExceptions: () => [], ipConflictResults: () => rows};
  runInNewContext(source, {
    ChromeUtils: {importESModule: path => path.includes('NetworkPolicy') ? {getContainerNetwork: () => ({mode: 0, proxyURL: '', webrtcMode: 0})} : path.includes('IPConflicts') ? monitor : {ContextualIdentityService: {getPublicIdentities: () => [{userContextId: 1, name: 'Work'}],getUserContextLabel: () => 'Work'}}},
    Services: {prefs: {getBoolPref: () => false, getStringPref: (_key, fallback) => fallback}, obs: {addObserver() {}}},
    document: {getElementById: get, createElement: element, createTextNode: textContent => ({textContent, children: []}), querySelector: () => main, addEventListener() {}},
    window: {addEventListener() {}}, Option: function(textContent, value) {return {textContent, value, children: []};},
  });
  const find = (node, id) => node.id === id ? node : node.children.map(child => find(child, id)).find(Boolean);
  return {panel: find(main, 'cfx-ip-conflict-panel'), results: find(main, 'cfx-ip-results')};
}
const textOf = element => [element.textContent, ...element.children.map(textOf)].join(' ');
test('settings route result identifies both families and their individual errors', () => {
  const {results} = renderSettings([{ucid: 1, ip: '2001:db8::1', ipv4: '', ipv6: '2001:db8::1', errors: {ipv4: 'IPv4 route failed'}, conflicts: [], matches: []}]);
  const text = textOf(results);
  assert.match(text, /IPv4: Unknown.*IPv4 route failed/);
  assert.match(text, /IPv6: 2001:db8::1/);
});
test('settings keeps both measured addresses and displays family for each visit record', () => {
  const history = [
    {ip: '192.0.2.10', ucid: 1, hostname: 'one.example', firstAccessed: 1, lastAccessed: 2, accessCount: 1, urls: ['https://one.example/']},
    {ip: '2001:db8::1', ucid: 1, hostname: 'two.example', firstAccessed: 1, lastAccessed: 2, accessCount: 1, urls: ['https://two.example/']},
  ];
  const {results, panel} = renderSettings([{ucid: 1, ip: '192.0.2.10', ipv4: '192.0.2.10', ipv6: '2001:db8::1', errors: {}, conflicts: [], matches: []}], history);
  assert.match(textOf(results), /IPv4: 192\.0\.2\.10.*IPv6: 2001:db8::1/);
  assert.match(textOf(panel), /IPv4.*192\.0\.2\.10.*one\.example/);
  assert.match(textOf(panel), /IPv6.*2001:db8::1.*two\.example/);
});

test('rich route results never assign aggregate IPv6 conflict to primary IPv4', () => {
  const {results} = renderSettings([
    {ucid: 0, ip: '192.0.2.20', ipv4: '192.0.2.20', ipv6: '2001:db8::1', errors: {}, conflicts: [1]},
    {ucid: 1, ip: '192.0.2.10', ipv4: '192.0.2.10', ipv6: '2001:db8::1', errors: {}, conflicts: [0]},
  ]);
  const work = results.children[1];
  assert.match(work.children[1].textContent, /IPv4: 192\.0\.2\.10.*no match/);
  assert.match(work.children[2].textContent, /IPv6: 2001:db8::1.*same measured address as Default/);
});

test('explicit per-family matches identify IPv6 sharing without implicating IPv4', () => {
  const {results} = renderSettings([
    {ucid: 0, ip: '192.0.2.20', ipv4: '192.0.2.20', ipv6: '2001:db8::1', errors: {}, conflicts: [1], matches: [{family: 'ipv6', ip: '2001:db8::1', conflicts: [1]}]},
    {ucid: 1, ip: '192.0.2.10', ipv4: '192.0.2.10', ipv6: '2001:db8::1', errors: {}, conflicts: [0], matches: [{family: 'ipv6', ip: '2001:db8::1', conflicts: [0]}]},
  ]);
  const work = results.children[1];
  assert.match(work.children[1].textContent, /IPv4: 192\.0\.2\.10.*no match/);
  assert.match(work.children[2].textContent, /IPv6: 2001:db8::1.*same measured address as Default/);
});
