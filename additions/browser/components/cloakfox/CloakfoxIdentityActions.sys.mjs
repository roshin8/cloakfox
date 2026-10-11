/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

const active = new Set();
const validId = id => Number.isSafeInteger(id) && id >= 0 && id <= 0xffffffff;
const matches = (tab, id) => Number(tab.userContextId ?? 0) === id;

// SessionStore calls this on its actual records. Closed entries must go through
// removeClosedTabData so late content-process updates cannot resurrect them.
export function pruneContainerRestoreState(root, id, removeClosed = (_win, list, i) => list.splice(i, 1)) {
  if (!validId(id)) throw new Error('Invalid container ID');
  function pruneList(owner, key, selectedKey, keep) {
    const list = owner[key];
    if (!Array.isArray(list)) return;
    const selected = list[Math.max(0, (owner[selectedKey] || 1) - 1)];
    const oldIndex = list.indexOf(selected);
    const keptBefore = list.slice(0, Math.max(0, oldIndex)).filter(keep).length;
    owner[key] = list.filter(keep);
    if (selectedKey in owner && owner[key].length) {
      const index = owner[key].indexOf(selected);
      owner[selectedKey] = (index < 0 ? Math.min(keptBefore, owner[key].length - 1) : index) + 1;
    } else if (selectedKey in owner) owner[selectedKey] = 0;
  }
  function closedList(win, list = []) {
    for (let i = list.length - 1; i >= 0; i--) {
      if (matches(list[i].state || list[i], id)) removeClosed(win, list, i);
    }
  }
  function groups(owner, key) {
    if (!Array.isArray(owner[key])) return;
    for (const group of owner[key]) closedList(owner, group.tabs);
    owner[key] = owner[key].filter(group => group.tabs?.length);
  }
  function windowState(win) {
    pruneList(win, 'tabs', 'selected', tab => !matches(tab, id));
    closedList(win, win._closedTabs);
    groups(win, 'closedGroups');
    // Metadata has no history, but orphan groups/split views must not restore.
    if (win.tabs && win.groups) {
      win.groups = win.groups.filter(group => win.tabs.some(tab => tab.groupId === group.id));
    }
    if (win.tabs && win.splitViews) {
      win.splitViews = win.splitViews.filter(view => win.tabs.filter(tab => tab.splitViewId === view.id).length > 1);
      for (const tab of win.tabs) {
        if (!win.splitViews.some(view => view.id === tab.splitViewId)) delete tab.splitViewId;
      }
    }
    if (win.cookies) win.cookies = win.cookies.filter(cookie => (cookie.originAttributes?.userContextId ?? 0) !== id);
  }
  function state(value) {
    if (!value) return;
    // A single live-window wrapper may contain only closed records.
    windowState(value);
    for (const key of ['windows', '_closedWindows']) {
      if (!Array.isArray(value[key])) continue;
      value[key].forEach(windowState);
      pruneList(value, key, key === 'windows' ? 'selectedWindow' : '', win =>
        win.tabs?.length > 0 || win._closedTabs?.length > 0 || win.closedGroups?.length > 0);
    }
    groups(value, 'savedGroups');
    state(value.lastSessionState);
    state(value.deferredInitialState);
  }
  state(root);
}

// Called under SessionWriter's I/O mutex, after a strict current-state save.
// Prune every file that Firefox can load as a restore fallback, preserving
// unrelated containers in each file. Do not create a backup of unsanitized data.
export async function pruneContainerRestoreFiles(id, paths, io = IOUtils) {
  if (!validId(id)) throw new Error('Invalid container ID');
  const candidates = new Set();
  const legacyPath = path => path.replace("jsonlz4", "js").replace("baklz4", "bak");
  for (const key of paths.loadOrder) {
    if (paths[key]) {
      candidates.add(paths[key]);
      candidates.add(legacyPath(paths[key]));
    }
  }
  if (await io.exists(paths.backups)) {
    const oldUpgradePrefix = legacyPath(paths.upgradeBackupPrefix);
    for (const path of await io.getChildren(paths.backups)) {
      if (!path.endsWith('.tmp') &&
          (path.startsWith(paths.upgradeBackupPrefix) || path.startsWith(oldUpgradePrefix))) {
        candidates.add(path);
      }
    }
  }
  for (const path of candidates) {
    if (!(await io.exists(path))) continue;
    const compressed = path.includes('jsonlz4') || path.includes('baklz4');
    const state = await io.readJSON(path, { decompress: compressed });
    if (!state || typeof state !== 'object' || Array.isArray(state)) {
      throw new Error('Invalid session restore state in ' + path);
    }
    pruneContainerRestoreState(state, id);
    await io.writeJSON(path, state, { tmpPath: path + '.tmp', compress: compressed });
  }
}

// Destructive orchestration is separate from UI and native adapters so failures
// can be exercised without touching a real profile. No seeds change on failure.
export async function forgetContainerData(id, { confirmed = false } = {}, dependencies = null) {
  if (!validId(id)) throw new Error('Invalid container ID');
  if (confirmed !== true) throw new Error('Explicit confirmation is required');
  const deps = dependencies || nativeDependencies();
  if (!deps.exists(id)) throw new Error('Container no longer exists');
  if (active.has(id)) throw new Error('Forgetting this container is already in progress');
  deps.preflight(id);
  active.add(id);
  let release;
  let destructive = false;
  let dataCleared = false;
  try {
    release = deps.acquire(id);
    destructive = true;
    await deps.closeTabs(id);
    release?.check?.();
    await deps.pruneRestore(id);
    const failedFlags = await deps.clearData(id);
    if (failedFlags) throw new Error(`Native data clearing failed (flags ${failedFlags})`);
    dataCleared = true;
    deps.clearBounceExceptions?.(id);
    await deps.closeTabs(id);
    release?.check?.();
    await deps.pruneRestore(id);
    deps.rotate(id);
    return { userContextId: id, cleared: true, appearanceChanged: true };
  } catch (error) {
    const detail = dataCleared
      ? 'Site data was cleared, but tab-restore cleanup or appearance reset did not finish. '
      : destructive ? 'Tabs may be closed. Some data may already be removed; appearance was not changed. ' : '';
    throw new Error(detail + error.message, { cause: error });
  } finally {
    try { release?.(); } finally { active.delete(id); }
  }
}

// Native OA bulk cleanup starts unregister jobs without awaiting callbacks.
// Wait explicitly so a failed/pending service worker cannot outlive success.
export async function unregisterContainerWorkers(id, manager, timers) {
  if (!validId(id)) throw new Error('Invalid container ID');
  const registrations = manager.getAllRegistrations();
  const pending = [];
  for (let i = 0; i < registrations.length; i++) {
    const worker = registrations.queryElementAt(i, Ci.nsIServiceWorkerRegistrationInfo);
    if ((worker.principal.originAttributes.userContextId ?? 0) !== id) continue;
    pending.push(new Promise((resolve, reject) => {
      manager.propagateUnregister(worker.principal, {
        unregisterSucceeded: resolve, // false means it was already removed
        unregisterFailed: () => reject(new Error('Service worker unregister failed: ' + worker.scope)),
        QueryInterface: ChromeUtils.generateQI(['nsIServiceWorkerUnregisterCallback']),
      }, worker.scope);
    }));
  }
  if (!pending.length) return;
  let timeout;
  try {
    await Promise.race([Promise.all(pending), new Promise((_, reject) => {
      timeout = timers.setTimeout(() => reject(new Error('Timed out unregistering container service workers')), 15000);
    })]);
  } finally { timers.clearTimeout(timeout); }
}

// OA0 permissions may have been shared with every container in old profiles,
// and some Firefox permission types always strip OA. Preserve shared choices.
export function containerClearFlags(id, flags) {
  if (!validId(id)) throw new Error('Invalid container ID');
  const shared = flags.CLEAR_SITE_PERMISSIONS | flags.CLEAR_STORAGE_ACCESS |
    flags.CLEAR_STORAGE_PERMISSIONS | flags.CLEAR_SHUTDOWN_EXCEPTIONS;
  return (id === 0 ? flags.CLEAR_ALL & ~shared : flags.CLEAR_ALL) >>> 0;
}

// CookieCleaner historically swallows removal exceptions. Check the observable
// result so those failures cannot silently produce a successful Forget action.
export function assertContainerCookiesCleared(id, cookies) {
  if (!validId(id)) throw new Error('Invalid container ID');
  if (Array.from(cookies).some(cookie => (cookie.originAttributes?.userContextId ?? 0) === id)) {
    throw new Error('Container cookies remain after native data clearing');
  }
}

function nativeDependencies() {
  const { ContextualIdentityService } = ChromeUtils.importESModule(
    'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
  const { SessionStore } = ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
  return {
    exists: id => id === 0 || !!ContextualIdentityService.getPublicIdentityFromId(id),
    preflight: () => SessionStore.assertContainerForgetReady(),
    acquire: id => acquireNavigationGuard(id),
    closeTabs: id => closeTargetTabs(id),
    pruneRestore: id => SessionStore.forgetContainerRestoreData(id),
    clearData: async id => {
      const manager = Cc['@mozilla.org/serviceworkers/manager;1'].getService(Ci.nsIServiceWorkerManager);
      const timers = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
      await unregisterContainerWorkers(id, manager, timers);
      const failedFlags = await new Promise((resolve, reject) => {
        try {
          Services.clearData.deleteDataFromOriginAttributesPatternWithFlags(
            { userContextId: id }, containerClearFlags(id, Ci.nsIClearDataService),
            { onDataDeleted: resolve });
        } catch (error) { reject(error); }
      });
      // A new registration racing native quota cleanup must also finish before
      // appearance rotation. Scoped navigation remains paused throughout.
      await unregisterContainerWorkers(id, manager, timers);
      if (!failedFlags) assertContainerCookiesCleared(id, Services.cookies.cookies);
      return failedFlags;
    },
    clearBounceExceptions: id => ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs').clearBounceExceptions(id),
    rotate: id => rotatePersona(id),
  };
}

function browserWindows() {
  return Array.from(Services.wm.getEnumerator('navigator:browser')).filter(win => !win.closed && win.gBrowser);
}

function isSettings(browser) {
  // Preserve the privileged confirmation/status UI even when clearing UCID 0.
  return browser.currentURI?.spec.split(/[?#]/)[0] === 'about:cloakfox';
}

function targetTabs(id) {
  return browserWindows().flatMap(win => Array.from(win.gBrowser.tabs)
    .filter(tab => Number(tab.getAttribute('usercontextid') || 0) === id && !isSettings(tab.linkedBrowser))
    .map(tab => ({ win, tab })));
}

async function closeTargetTabs(id) {
  const { setTimeout, clearTimeout } = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
  const tabs = targetTabs(id);
  const pending = new Set(tabs.map(({ tab }) => tab.linkedBrowser.frameLoader?.remoteTab?.tabId).filter(Boolean));
  let finish;
  const destroyed = new Promise(resolve => { finish = resolve; });
  const observer = subject => {
    pending.delete(subject.QueryInterface(Ci.nsIRemoteTab).tabId);
    if (!pending.size) finish();
  };
  Services.obs.addObserver(observer, 'ipc:browser-destroyed');
  let timeout;
  try {
    for (const { win, tab } of tabs) {
      // Keep windows alive to avoid racing late closed-window restore snapshots.
      if (win.gBrowser.tabs.length === 1) win.gBrowser.addTrustedTab('about:cloakfox');
      tab.linkedBrowser.browsingContext?.stop(Ci.nsIWebNavigation.STOP_ALL);
      win.gBrowser.removeTab(tab, { animate: false, skipPermitUnload: true, skipSessionStore: true });
    }
    if (!pending.size) finish();
    await Promise.race([destroyed, new Promise((_, reject) => {
      timeout = setTimeout(() => reject(new Error('Timed out closing container tabs; try again')), 15000);
    })]);
  } finally {
    clearTimeout(timeout);
    Services.obs.removeObserver(observer, 'ipc:browser-destroyed');
  }
}

function acquireNavigationGuard(id) {
  // Block fresh requests (including workers), disable newly attached matching
  // contexts, and stop existing target contexts before awaiting tab teardown.
  // Quota/storage worker shutdown is then owned by native ClearDataService.
  const guarded = new Map();
  let guardError;
  const freeze = bc => {
    if (!bc.isContent || (bc.originAttributes?.userContextId ?? 0) !== id) return;
    if (bc.top?.embedderElement && isSettings(bc.top.embedderElement)) return;
    if (!guarded.has(bc)) guarded.set(bc, bc.allowJavascript);
    bc.allowJavascript = false;
    bc.stop(Ci.nsIWebNavigation.STOP_ALL);
  };
  const attached = subject => {
    try { freeze(subject); } catch (error) { guardError = error; }
  };
  const request = subject => {
    try {
      const channel = subject.QueryInterface(Ci.nsIChannel);
      if ((channel.loadInfo.originAttributes.userContextId ?? 0) === id) channel.cancel(Cr.NS_BINDING_ABORTED);
    } catch (error) { guardError = error; }
  };
  Services.obs.addObserver(attached, 'browsing-context-attached');
  Services.obs.addObserver(request, 'http-on-modify-request');
  try {
    for (const { tab } of targetTabs(id)) {
      const bc = tab.linkedBrowser.browsingContext;
      if (bc) for (const child of bc.getAllBrowsingContextsInSubtree()) freeze(child);
    }
  } catch (error) {
    Services.obs.removeObserver(attached, 'browsing-context-attached');
    Services.obs.removeObserver(request, 'http-on-modify-request');
    for (const [bc, previous] of guarded) {
      try { bc.allowJavascript = previous; } catch (_) {}
    }
    throw error;
  }
  const release = () => {
    Services.obs.removeObserver(attached, 'browsing-context-attached');
    Services.obs.removeObserver(request, 'http-on-modify-request');
    for (const [bc, previous] of guarded) {
      try { bc.allowJavascript = previous; } catch (_) { /* destroyed context */ }
    }
  };
  release.check = () => {
    if (guardError) throw new Error('Could not keep container navigation paused: ' + guardError.message);
  };
  return release;
}

function rotatePersona(id) {
  const { fillPersonaKeys, writeHttpProfilePrefs } = ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
  const { applyOverrides } = ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
  const seed = () => {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    return btoa(String.fromCharCode(...bytes));
  };
  const master = seed();
  const bytes = Uint8Array.from(atob(master), c => c.charCodeAt(0));
  const word = i => new DataView(bytes.buffer).getUint32(i * 4);
  const cfg = applyOverrides(id, {
    'fingerprint:secret': master,
    'canvas:seed': word(0), 'audio:seed': word(1), 'font:seed': word(2),
    'fonts:spacing_seed': word(3), 'math:trig_seed': word(4),
    ...fillPersonaKeys(master, id),
  });
  Services.prefs.setStringPref(`cloakfox.container.${id}.math_seed`, master);
  Services.prefs.setStringPref(`cloakfox.container.${id}.keyboard_seed`, seed());
  Services.prefs.setStringPref(`cloakfox.container.${id}.timing_seed`, seed());
  Services.prefs.setStringPref(`cloakfox.s.cloak_cfg_${id}`, JSON.stringify(cfg));
  writeHttpProfilePrefs(id, cfg['navigator.userAgent'] || '');
  Services.prefs.savePrefFile(null);
}
