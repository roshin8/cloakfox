/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

export const permissionTypes = ['camera', 'microphone', 'geo', 'desktop-notification'];
function dependencies() {
  return { manager: Services.perms, now: () => Date.now(),
    isolation: () => ({ userContext: Services.prefs.getBoolPref('permissions.isolateBy.userContext', false),
      privateBrowsing: Services.prefs.getBoolPref('permissions.isolateBy.privateBrowsing', false) }) };
}
export function permissionIsolation(deps = dependencies()) { return deps.isolation(); }
function snapshot(permission) {
  return { origin: permission.principal.origin, type: permission.type,
    userContextId: permission.principal.originAttributes.userContextId || 0,
    privateBrowsingId: permission.principal.originAttributes.privateBrowsingId || 0,
    browserId: permission.browserId || 0, capability: permission.capability,
    expireType: permission.expireType, expireTime: permission.expireTime,
    modificationTime: permission.modificationTime };
}
function key(record) { return JSON.stringify([record.origin, record.type, record.browserId]); }
export function listPermissionGrants(scope = {}, deps = dependencies()) {
  return deps.manager.getAllByTypes(permissionTypes)
    .filter(p => p.capability === deps.manager.ALLOW_ACTION &&
      (!p.expireTime || p.expireTime > deps.now()))
    .map(snapshot).filter(p => (scope.userContextId === undefined || p.userContextId === scope.userContextId) &&
      (scope.privateBrowsingId === undefined || p.privateBrowsingId === scope.privateBrowsingId))
    .sort((a, b) => key(a).localeCompare(key(b)));
}
function existing(record, deps) {
  const permission = deps.manager.getAllByTypes(permissionTypes).find(p => key(snapshot(p)) === key(record));
  if (!permission || JSON.stringify(snapshot(permission)) !== JSON.stringify(record) ||
      permission.capability !== deps.manager.ALLOW_ACTION ||
      (permission.expireTime && permission.expireTime <= deps.now())) {
    throw new Error('The grant changed or expired. Refresh the dashboard.');
  }
  if (permission.expireType === deps.manager.EXPIRE_POLICY) throw new Error('This grant is controlled by enterprise policy.');
  const isolation = deps.isolation();
  if ((!isolation.userContext && record.userContextId) || (!isolation.privateBrowsing && record.privateBrowsingId)) {
    throw new Error('Permission isolation changed. Restore its original isolation setting before editing this grant.');
  }
  return permission;
}
export function revokePermissionGrant(record, deps = dependencies()) {
  const permission = existing(record, deps);
  if (permission.browserId) deps.manager.removeFromPrincipalForBrowser(permission.principal, permission.type, permission.browserId);
  else deps.manager.removePermission(permission);
}
export function expirePermissionGrant(record, expiry, deps = dependencies()) {
  const permission = existing(record, deps);
  // Tab grants already have a narrower lifetime. Never widen them to profile/session grants.
  if (permission.browserId || permission.expireType === deps.manager.EXPIRE_SESSION_TAB) {
    throw new Error('Tab grants already expire with the tab. Revoke this grant to end it sooner.');
  }
  if (!expiry || !['session', 'time'].includes(expiry.mode)) throw new Error('Choose a session or timed expiry.');
  let expireTime = 0;
  if (expiry.mode === 'time') {
    if (!Number.isSafeInteger(expiry.expiresAt) || expiry.expiresAt <= deps.now() || expiry.expiresAt > deps.now() + 365 * 86400000) {
      throw new Error('Expiry must be within the next year.');
    }
    expireTime = expiry.expiresAt;
  }
  // A shortening control must never extend an existing deadline or session boundary.
  if (permission.expireTime) expireTime = expireTime ? Math.min(expireTime, permission.expireTime) : permission.expireTime;
  const expireType = expiry.mode === 'session' || permission.expireType === deps.manager.EXPIRE_SESSION ||
    permission.principal.originAttributes.privateBrowsingId ? deps.manager.EXPIRE_SESSION : deps.manager.EXPIRE_TIME;
  deps.manager.addFromPrincipal(permission.principal, permission.type, permission.capability, expireType, expireTime);
}
