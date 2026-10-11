/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

function dependencies() {
  return { service: Cc['@mozilla.org/toolkit/profile-service;1'].getService(Ci.nsIToolkitProfileService),
    launch: profile => Services.startup.createInstanceWithProfile(profile),
    currentDirectory: Services.dirsvc.get('ProfD', Ci.nsIFile) };
}
function current(profile, deps) {
  return profile === deps.service.currentProfile || profile.rootDir.equals(deps.currentDirectory);
}
function available(profile) {
  try { const lock = profile.lock({}); lock.unlock(); return true; } catch { return false; }
}
function describe(profile, deps) {
  const isCurrent = current(profile, deps);
  return { id: profile.rootDir.path, name: profile.name, current: isCurrent,
    available: !isCurrent && available(profile) };
}
export function listWorkspaces(deps = dependencies()) {
  return Array.from(deps.service.profiles, profile => describe(profile, deps));
}
export function validateWorkspaceName(value) {
  if (typeof value !== 'string' || !value.trim() || value.length > 80 || /[\x00-\x1f\x7f/\\]/.test(value)) {
    throw new Error('Use a workspace name of 1–80 characters without slashes or control characters.');
  }
  return value.trim();
}
let creating = false;
export async function createWorkspace(name, deps = dependencies()) {
  name = validateWorkspaceName(name);
  if (creating) throw new Error('A workspace is already being created.');
  creating = true;
  try {
    if (Array.from(deps.service.profiles).some(p => p.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
      throw new Error('A workspace with this name already exists.');
    }
    // Native service selects a new directory; no caller-supplied path or profile copy.
    const profile = deps.service.createProfile(null, name, 'cloakfox-workspace');
    try { await deps.service.asyncFlush(); }
    catch { throw new Error('The profile was created but its catalog could not be saved. Open about:profiles to recover it before creating another.'); }
    return describe(profile, deps);
  } finally { creating = false; }
}
export function openWorkspace(id, deps = dependencies()) {
  const profile = Array.from(deps.service.profiles).find(p => p.rootDir.path === id);
  if (!profile) throw new Error('This workspace no longer exists. Refresh the list.');
  if (current(profile, deps)) throw new Error('This workspace is already open here.');
  if (!available(profile)) throw new Error('This workspace is already in use or cannot be opened.');
  deps.launch(profile);
}
