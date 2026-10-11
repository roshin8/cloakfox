import test from 'node:test';
import assert from 'node:assert/strict';
import { listPermissionGrants, revokePermissionGrant, expirePermissionGrant } from '../../additions/browser/components/cloakfox/CloakfoxPermissions.sys.mjs';
import { listWorkspaces, createWorkspace, openWorkspace } from '../../additions/browser/components/cloakfox/CloakfoxWorkspaces.sys.mjs';

function permissions() {
  let entries = [], writes = [], removed = [];
  const manager = { ALLOW_ACTION: 1, EXPIRE_NEVER: 0, EXPIRE_SESSION: 1, EXPIRE_TIME: 2, EXPIRE_POLICY: 3, EXPIRE_SESSION_TAB: 4,
    getAllByTypes: types => entries.filter(p => types.includes(p.type)),
    addFromPrincipal: (...args) => writes.push(args), removePermission: p => removed.push(p),
    removeFromPrincipalForBrowser: (...args) => removed.push(args) };
  function add(id, pb = 0, type = 'camera', properties = {}) {
    const principal = { origin: `https://example.com^userContextId=${id}&privateBrowsingId=${pb}`, originAttributes: { userContextId: id, privateBrowsingId: pb } };
    const p = { principal, type, capability: 1, expireType: 0, expireTime: 0, modificationTime: 10, browserId: 0, ...properties };
    entries.push(p); return p;
  }
  return { manager, now: () => 1000, isolation: () => ({userContext: true, privateBrowsing: true}), add, writes, removed };
}

test('grant inventory distinguishes exact origin attributes, type, expiry and denial', () => {
  const deps = permissions(); deps.add(2); deps.add(3); deps.add(2, 1); deps.add(2, 0, 'cookie');
  deps.add(2, 0, 'geo', {capability: 2}); deps.add(2, 0, 'microphone', {expireTime: 999});
  assert.equal(listPermissionGrants({userContextId: 2, privateBrowsingId: 0}, deps).length, 1);
  assert.equal(listPermissionGrants({}, deps).length, 3);
});
test('expiry uses the original principal and capability, and never extends an existing boundary', () => {
  const deps = permissions(); const p = deps.add(2, 1, 'geo', {expireType: 1, expireTime: 3000});
  const record = listPermissionGrants({}, deps)[0];
  expirePermissionGrant(record, {mode: 'time', expiresAt: 5000}, deps);
  assert.deepEqual(deps.writes[0], [p.principal, 'geo', 1, 1, 3000]);
  expirePermissionGrant(record, {mode: 'session'}, deps);
  assert.deepEqual(deps.writes[1], [p.principal, 'geo', 1, 1, 3000]);
});
test('missing consent, stale grants, policy grants, tab widening and isolation changes fail closed', () => {
  for (const variant of ['stale', 'denied', 'policy', 'tab', 'isolation']) {
    const deps = permissions(); const p = deps.add(2); const record = listPermissionGrants({}, deps)[0];
    if (variant === 'stale') p.modificationTime++;
    if (variant === 'denied') p.capability = 2;
    if (variant === 'policy') { p.expireType = 3; record.expireType = 3; }
    if (variant === 'tab') { p.browserId = 3; record.browserId = 3; }
    if (variant === 'isolation') deps.isolation = () => ({userContext: false, privateBrowsing: true});
    assert.throws(() => expirePermissionGrant(record, {mode: 'time', expiresAt: 5000}, deps));
    assert.equal(deps.writes.length, 0);
  }
});
test('revocation touches only the selected stored principal', () => {
  const deps = permissions(); const p = deps.add(2); deps.add(3); deps.add(2, 1);
  revokePermissionGrant(listPermissionGrants({userContextId: 2, privateBrowsingId: 0}, deps)[0], deps);
  assert.deepEqual(deps.removed, [p]);
});
test('session and timed expiry reject invalid dates without writes', () => {
  const deps = permissions(); deps.add(2); const record = listPermissionGrants({}, deps)[0];
  for (const expiresAt of [0, 1000, Infinity, NaN, 1000 + 366 * 86400000]) {
    assert.throws(() => expirePermissionGrant(record, {mode: 'time', expiresAt}, deps));
  }
  assert.equal(deps.writes.length, 0);
});
function workspaces() {
  const calls = [];
  const file = path => ({path, equals(other) {return path === other.path;}});
  const profile = (name, path, locked = false) => ({name, rootDir: file(path), lock() {if (locked) throw Error('locked'); return {unlock() {}};}});
  const first = profile('Original', '/original');
  const service = {profiles: [first, profile('Other', '/other'), profile('Busy', '/busy', true)], currentProfile: first,
    createProfile(dir, name, source) {calls.push(['create', dir, name, source]); const p = profile(name, '/fresh/' + name); this.profiles.push(p); return p;},
    async asyncFlush() { calls.push(['flush']); } };
  return {service, currentDirectory: file('/original'), calls, launch: p => calls.push(['launch', p.rootDir.path])};
}
test('workspace creation uses native empty profile allocation and saves before success', async () => {
  const deps = workspaces(); const result = await createWorkspace('Research', deps);
  assert.equal(result.name, 'Research'); assert.deepEqual(deps.calls, [['create', null, 'Research', 'cloakfox-workspace'], ['flush']]);
  assert.equal(listWorkspaces(deps).length, 4);
  for (const name of ['original', '../escape', '', 'x\n']) await assert.rejects(createWorkspace(name, deps));
});
test('workspace opening resolves the registered profile and rejects current, busy or arbitrary paths', () => {
  const deps = workspaces();
  for (const id of ['/original', '/busy', '/arbitrary']) assert.throws(() => openWorkspace(id, deps));
  openWorkspace('/other', deps); assert.deepEqual(deps.calls, [['launch', '/other']]);
});
test('profile catalog save failure never launches or deletes profile storage', async () => {
  const deps = workspaces(); deps.service.asyncFlush = async () => {throw Error('conflict');};
  await assert.rejects(createWorkspace('Research', deps), /could not be saved/);
  assert.equal(deps.service.profiles.length, 4); assert.equal(deps.calls.length, 1);
});
